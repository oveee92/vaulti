import sys
import os
import nox
import shutil
import filecmp
from ruamel.yaml import YAML
from ruamel.yaml.comments import TaggedScalar
from ansible.parsing.vault import (VaultLib, VaultSecret)


@nox.session
def test_replace_keyname(session):
    """ This tests for whether keys can be updated, and whether the vaulted value
    remains the same when not being changed """

    vault_pass = "default"
    yaml_content_initial = """---
Never: gonna
give: you
up: !vault |
  $ANSIBLE_VAULT;1.1;AES256
  64646434633864633465393633663064653139346166393436653938363931663435366435343665
  3362313635653035343865363033323762383535613130300a326563633934316561656362633665
  35396630316530353764616338353436323832616365383731303165626535306132353663336465
  6564373632303764370a643631303336653433623531643565306139383335366262303064623263
  3664
...
"""
    yaml_content_expected = """---
Neverever: gonna
give: you
up: !vault |
  $ANSIBLE_VAULT;1.1;AES256
  64646434633864633465393633663064653139346166393436653938363931663435366435343665
  3362313635653035343865363033323762383535613130300a326563633934316561656362633665
  35396630316530353764616338353436323832616365383731303165626535306132353663336465
  6564373632303764370a643631303336653433623531643565306139383335366262303064623263
  3664

...
"""

    with open("test1_password.txt", "w", encoding="utf-8") as f:
        f.write(vault_pass)
    with open("test1_initial.yaml", "w", encoding="utf-8") as f:
        f.write(yaml_content_initial)
    with open("test1_expect.yaml", "w", encoding="utf-8") as f:
        f.write(yaml_content_expected)

    # Run vaulti, editing with sed
    session.env["VISUAL"] = "sed -i s/Never/Neverever/"
    session.env["ANSIBLE_VAULT_PASSWORD_FILE"] = "test1_password.txt"
    session.run("bash", "-c", f"vaulti test1_initial.yaml", external=True)

    # Diff them and fail if they are not the same
    if filecmp.cmp("test1_initial.yaml", "test1_expect.yaml"):
        os.remove("test1_initial.yaml")        
        os.remove("test1_expect.yaml")        
        os.remove("test1_password.txt")        
    else:
        raise AssertionError("File did not get changed as expected")


