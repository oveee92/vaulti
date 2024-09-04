#!/usr/bin/env python3

"""
Utility to edit yaml files with inline ansible vault variables

This is a utility to make ansible-vault inline encrypted variables a billion
times easier to work with. Useful if you want to store the variables safely in
AWX, or want to avoid encrypting entire files because you want to be able to
search for all of your variables, but you don't like the way you currently have
to read and write the variables.

It opens an editor based on your EDITOR environment variable, where the
variables have been decrypted. This is indicated by a tag, which is set to
"!ENCRYPTED" by default.

If it cannot decrypt the variable for any reason, it will be indicated with a
"!VAULT_INVALID" tag, which will be translated back to its original value when
you close the editor. It will still try to reencrypt.

From here, you can add or remove the tags from whichever variables you want,
and when you save and quit, it will reencrypt and decrypt things for you as you
specified.

Since ruamel.yaml does a lot of stuff in the background, there are some things
that will be changed automatically:
- Indentation for your multiline strings will always end up with a fixed
  (default 2) spaces relative to the variable it belongs to; i.e. not the 10
  spaces indented or whatever the default is from the `ansible-vault
  encrypt_string` output.
- Header (---) and footer (...) will be added automatically to the variable
  file if it doesn't exist
- Extra whitespaces will be removed (for example `key:  value` -> `key: value`.)
- An extra newline is added below the ansible-vault output, for readability.

This script is developed by someone who just wants it to work, so feel free to
change it if you want to make it work better.

Usage:

./vaulti <file1> <file2> ...
./vaulti <file1> --ask-vault-pass
./vaulti <file1> --vault-id myid1@prompt --vault-id myid2@passwordfile
./vaulti -h


Contributions:

Thanks to Nebucatnetzer for refactoring!

"""

import argparse
import logging
import os
import subprocess
import sys
import tempfile
import re

from argparse import Namespace
from pathlib import Path
from typing import Any
from typing import BinaryIO
from typing import IO
from typing import Iterable
from typing import Union
from typing import List


from ansible import constants as C
from ansible.cli import CLI
from ansible.errors import AnsibleError
from ansible.parsing.dataloader import DataLoader
from ansible.parsing.vault import AnsibleVaultError
from ansible.parsing.vault import (VaultLib, VaultSecret)

from ruamel.yaml import ScalarNode
from ruamel.yaml import YAML
from ruamel.yaml.comments import (
    CommentedMap,
    CommentedSeq,
    TaggedScalar,
)
from ruamel.yaml.compat import StringIO
from ruamel.yaml.constructor import RoundTripConstructor
from ruamel.yaml.tokens import (
    CommentToken,
)  # To be able to insert newlines where needed
from ruamel.yaml.error import StringMark  # To be able to insert newlines where needed
from ruamel.yaml.scanner import ScannerError
from ruamel.yaml.parser import ParserError


DECRYPTED_TAG_NAME = "!ENCRYPT"
INVALID_TAG_NAME = "!COULD_NOT_DECRYPT"
VAULT_ID_TAG_SYMBOL = ":" # The symbol to denote the ansible-vault id
StreamType = Union[BinaryIO, IO[str], StringIO]
VAULT = None


def setup_vault(ask_vault_pass: bool, vault_password_file: str = None,
                vault_ids: list = None) -> VaultLib:
    """Ansible Vault boilerplate"""
    loader = DataLoader()

    # If no custom vauld ids are specified, just go with the default
    if vault_ids is None:
        # This variable might exist, depending on the ansible configuration. Ignore it with pylint
        vault_ids = C.DEFAULT_VAULT_IDENTITY_LIST  # pylint: disable=no-member
    else:
        print(vault_ids)
    # If a vault password file is specified, add it to the default id
    if vault_password_file:
        vault_ids.append(f"@{vault_password_file}")
    # Set up vault
    try:
        vault_secret = CLI.setup_vault_secrets(
            loader=loader,
            vault_ids=vault_ids,
            ask_vault_pass=ask_vault_pass,
        )
    except AnsibleError as err:
        print(f"Could not decrypt. Error is:\n{err}", file=sys.stderr)
        print("Make sure you point to a valid file is you are using the "
              "$ANSIBLE_VAULT_PASSWORD_FILE environment variable", file=sys.stderr)
        sys.exit(1)
    return VaultLib(vault_secret)


def extract_vault_label(vaulttext: str) -> str:
    """Extracts the label from the Vault ID line in the encrypted data.
    Returns an empty string if default"""
    first_line = vaulttext.splitlines()[0]
    parts = first_line.split(";")
    if len(parts) >= 4:
        return parts[3]  # This is the label
    return ""  # Return "" if no label is present

def constructor_tmp_decrypt(_: RoundTripConstructor, node: ScalarNode) -> TaggedScalar:
    """Constructor to translate between encrypted and unencrypted tags when
    loading yaml

    Gets passed self as an argument from YAML.
    """
    try:
        # pylint: disable=possibly-used-before-assignment
        decrypted_value = VAULT.decrypt(vaulttext=node.value).decode("utf-8")
    except (AnsibleError, AnsibleVaultError):
        # If the value cannot be decrypted for some reason, just use the
        # original value and add an invalid tag
        return TaggedScalar(value=node.value, style="|", tag=INVALID_TAG_NAME)

    label = extract_vault_label(node.value)
    if label != "":
        decrypted_tag_with_label = f"{DECRYPTED_TAG_NAME}{VAULT_ID_TAG_SYMBOL}{label}"
    else:
        decrypted_tag_with_label = DECRYPTED_TAG_NAME

    # Make it easier to read decrypted variables with newlines in it
    if "\n" in decrypted_value:
        return TaggedScalar(value=decrypted_value, style="|", tag=decrypted_tag_with_label)
    return TaggedScalar(value=decrypted_value, style="", tag=decrypted_tag_with_label)


def constructor_tmp_encrypt(
        _: RoundTripConstructor, node: ScalarNode, tag_suffix: str = None
    ) -> TaggedScalar:
    """Constructor to encrypt YAML.

    Gets passed self as an argument from YAML.
    """

    #print(f"Encrypting {node.tag} {node.value} with vault id {tag_suffix}")

    if tag_suffix is None:
        secret = get_secret_for_vault_id(VAULT, "default")
        vault_id = "default"
    else:
        secret = get_secret_for_vault_id(VAULT, tag_suffix)
        vault_id = tag_suffix

    # Seems to need explicit values for secret and vault_id even when you just want the default,
    # It seems to just select the first VaultSecret object otherwise, which is rarely default.
    encrypted_value = VAULT.encrypt(
        plaintext=node.value, secret=secret, vault_id=vault_id
    ).decode("utf-8")

    return TaggedScalar(value=encrypted_value, style="|", tag="!vault")


def constructor_tmp_invalid(_: RoundTripConstructor, node: ScalarNode) -> TaggedScalar:
    """ The invalid tag should just be translated directly back to the original tag and value """
    return TaggedScalar(value=node.value, style="|", tag="!vault")


def is_commented_map(data: Any) -> bool:
    """Helper function for readability"""
    return isinstance(data, CommentedMap)


def is_commented_seq(data: Any) -> bool:
    """Helper function for readability"""
    return isinstance(data, CommentedSeq)


def is_tagged_scalar(data: Any) -> bool:
    """Helper function for readability"""
    return isinstance(data, TaggedScalar)


def _process_commented_map(
    original_data: CommentedMap, reencrypted_data: CommentedMap
) -> tuple[CommentedMap, CommentedMap]:
    """Helper function for compare_and_update. Loops over keys in a dict"""
    for key in reencrypted_data:
        if (
            is_tagged_scalar(reencrypted_data[key])
            and reencrypted_data[key].tag.value == "!vault"
        ):
            ensure_newline(reencrypted_data, key)
        if key in original_data:
            # If ansible vault fails, use the new data instead of crashing
            try:
                reencrypted_data[key] = compare_and_update(
                    original_data=original_data[key],
                    reencrypted_data=reencrypted_data[key],
                )
            except (AnsibleError, AnsibleVaultError):
                reencrypted_data[key] = reencrypted_data[key]
    return original_data, reencrypted_data


def _process_commented_seq(
    original_data: CommentedSeq, reencrypted_data: CommentedSeq
) -> tuple[CommentedSeq, CommentedSeq]:
    """Helper function for compare_and_update. Loops over items in a list"""
    for i in range(len(reencrypted_data)):  # pylint: disable=consider-using-enumerate
        if (
            is_tagged_scalar(reencrypted_data[i])
            and reencrypted_data[i].tag.value == "!vault"
        ):
            ensure_newline(reencrypted_data, str(i))
        # If ansible vault fails, use the new data instead of crashing
        try:
            if i < len(original_data):
                reencrypted_data[i] = compare_and_update(
                    original_data=original_data[i],
                    reencrypted_data=reencrypted_data[i],
                )
            else:
                reencrypted_data[i] = reencrypted_data[i]
        except (AnsibleError, AnsibleVaultError):
            reencrypted_data[i] = reencrypted_data[i]

    return original_data, reencrypted_data


def compare_and_update(
    original_data: Union[CommentedMap | CommentedSeq | TaggedScalar],
    reencrypted_data: Union[CommentedMap | CommentedSeq | TaggedScalar],
) -> Union[CommentedMap | CommentedSeq | TaggedScalar]:
    """Take the new and original data, find each !vault entry, and if it exists
    in the original data, decrypt both and compare them. If they are the same,
    prefer the original data, to prevent useless diffs. Will also ensure that there
    is a newline after a vaulted variable (for readability)"""

    # Loop recursively through everything
    if is_commented_map(original_data) and is_commented_map(reencrypted_data):
        original_data, reencrypted_data = _process_commented_map(
            original_data, reencrypted_data  # type: ignore[arg-type]
        )
    elif is_commented_seq(original_data) and is_commented_seq(reencrypted_data):
        original_data, reencrypted_data = _process_commented_seq(
            original_data, reencrypted_data  # type: ignore[arg-type]
        )

    elif (
        is_tagged_scalar(original_data)
        and original_data.tag.value == "!vault"
        and is_tagged_scalar(reencrypted_data)
        and reencrypted_data.tag.value == "!vault"
    ):
        if (
            VAULT.decrypt(original_data.value) == VAULT.decrypt(reencrypted_data.value) and
            extract_vault_label(original_data.value) == extract_vault_label(reencrypted_data.value)
        ):
            return original_data

    return reencrypted_data


def ensure_newline(data: Union[CommentedMap, CommentedSeq], key: "str") -> None:
    """Utility script, to avoid having to write it twice in the recursive stuff above"""
    comment_nextline = data.ca.items.get(key)
    # Ensure that there is at least one newline after the vaulted value, for readability
    if comment_nextline is None:
        data.ca.items[key] = [None, None, None, None]
        # All this just to make a newline... not 100% sure how this StringMark
        # stuff works
        newline_token = CommentToken(
            "\n",
            start_mark=StringMark(
                buffer=data, pointer=0, name=None, index=0, line=0, column=0
            ),
            end_mark=StringMark(
                buffer=data, pointer=1, name=None, index=1, line=0, column=1
            ),
        )
        data.ca.items[key][2] = newline_token


def setup_yaml() -> YAML:
    """Set up the neccesary yaml loader stuff"""
    yaml = YAML()
    # Don't strip out unneccesary quotes around scalar variables
    yaml.preserve_quotes = True
    # Prevent the yaml dumper from line-breaking the longer variables
    yaml.width = 2147483647
    yaml.explicit_start = True  # Add --- at the start of the file
    yaml.explicit_end = True  # Add ... at the end of the file
    # Ensure list items are indented, not inline with the parent variable
    yaml.indent(mapping=2, sequence=4, offset=2)
    # Register the constructor to let the yaml loader do the decrypting for you
    return yaml


def read_encrypted_yaml_file(file: Path) -> Any:
    """Add a custom constructor to decrypt vault, and load the content"""
    yaml = setup_yaml()
    yaml.constructor.add_constructor("!vault", constructor_tmp_decrypt)
    with open(file, "r", encoding="utf-8") as file_to_decrypt:
        return yaml.load(file_to_decrypt)


def read_yaml_file(file: Path) -> Any:
    """Load the yaml file"""
    yaml = setup_yaml()
    try:
        with open(file, "r", encoding="utf-8") as file_to_read:
            return yaml.load(file_to_read)
    except IsADirectoryError as err:
        print(f"Specified file is a directory. Error is:\n{err}", file=sys.stderr)
        sys.exit(1)


def display_yaml_data_and_exit(yaml_data: Union[Path, StreamType]) -> None:
    """Dumps the unencrypted content without opening an editor"""
    yaml = setup_yaml()
    yaml.dump(data=yaml_data, stream=sys.stdout)
    sys.exit(0)


def _get_default_editor() -> List[str]:
    """Get the default editor and open the provided file

    Ignores additional parameters provided to the editor.
    """
    editor = os.environ.get("VISUAL", "").split()
    if not editor:
        editor = os.environ.get("EDITOR", "nano").split()

    if not editor:
        print("No editor configured in neither VISUAL nor EDITOR variable. Exiting.")
        sys.exit(1)
    return editor


def open_file_in_default_editor(file_name: Path) -> None:
    """Opens a file in the default editor"""
    logger = logging.getLogger("Vaulti")
    editor = _get_default_editor()
    logger.info("Opening editor with params: %s", str(editor))
    subprocess.run(editor + [file_name], check=True)


def write_data_to_temporary_file(data_to_write: Union[Path, StreamType]) -> Path:
    """Write the yaml contents to a temporary file, for editing"""
    yaml = setup_yaml()
    # Create a temporary file
    with tempfile.NamedTemporaryFile(
        mode="w", delete=False, prefix="vaultedit_", suffix=".yaml"
    ) as temp_file:
        yaml.dump(data_to_write, temp_file)
        return Path(temp_file.name)

# Define a router function for the multi-constructor, since it takes 3 arguments
def vault_tag_router(loader, _tag_suffix: str, node: ScalarNode) -> TaggedScalar:
    """Router function to handle vault-related tags."""
    return constructor_tmp_encrypt(loader, node, tag_suffix=_tag_suffix)

def encrypt_and_write_tmp_file(
    tmp_file: Path, final_file: Path, original_data: CommentedMap
) -> None:
    """Reencrypts yaml data and writes it to a file"""
    yaml = setup_yaml()
    # Register the constructor to let the yaml loader do the
    # reencrypting for you Adding it this late to avoid encryption step
    # before the editor opens
    yaml.constructor.add_multi_constructor(
        f"{DECRYPTED_TAG_NAME}{VAULT_ID_TAG_SYMBOL}",
        vault_tag_router
    )
    yaml.constructor.add_constructor(DECRYPTED_TAG_NAME, constructor_tmp_encrypt)
    yaml.constructor.add_constructor(INVALID_TAG_NAME, constructor_tmp_invalid)

    def prompt_user_action() -> str:
        while True:
            try:
                user_input = input("Keep editing file (e), Discard changes (d) ? ").strip().lower()
                if user_input in ['e', 'd']:
                    return user_input
                print("Invalid input. What would you like to do?")
            except KeyboardInterrupt:
                sys.exit(0)

    # After the editor is closed, reload the yaml from the tmp-file
    # Give the user a chance to re-open the file if the yaml could not be parsed
    is_file_parsed = False
    while not is_file_parsed:
        with open(tmp_file, "r", encoding="utf-8") as file:
            try:
                edited_data = yaml.load(file)
                is_file_parsed = True
            except (ScannerError, ParserError, ValueError) as err:
                if err is ValueError:
                    print(f"Encountered Vault ID which has not been loaded. Error is:\n{err}")
                else:
                    print(f"The edited file is no longer valid YAML. Error is:\n{err}")
                print("What would you like to do?")
                user_retry = prompt_user_action()

                if user_retry == 'e':
                    open_file_in_default_editor(tmp_file.absolute())
                elif user_retry == 'd':
                    print("Changes discarded. Exiting")
                    sys.exit(0)
            except AnsibleError as err:
                print(f"AnsibleError. Error is:\n{err}", file=sys.stderr)
                sys.exit(1)

    # Loop through all the values of the new data, making sure that
    # any encrypted data unchanged from the original still uses the
    # original vault encrypted data. This makes your git diffs much
    # cleaner.
    final_data = compare_and_update(original_data, edited_data)
    # Then write the final data back to the original file
    with open(final_file, "w", encoding="utf-8") as file:
        yaml.dump(final_data, file)

    # A common mistake is to comment out a decrypted secret line,
    # making it plaintext. Ensure the user is notified of this.
    with open(final_file, "r", encoding="utf-8") as file:
        content = file.read()
    if re.search(r".*#.*" + re.escape(DECRYPTED_TAG_NAME) + r".*", content):
        print(
            (f"WARNING! The final file '{final_file}' seems to have secrets that were not "
              "reencrypted due to being commented out in the editor! Search the file for "
             f"instances of '{DECRYPTED_TAG_NAME}' that are commented out."),
            file=sys.stderr
        )


def parse_arguments() -> Namespace:
    """Parse the arguments from the command line"""
    parser = argparse.ArgumentParser(
        prog="vaulti", description="Helps you with inline encrypted variables"
    )

    parser.add_argument(
        "-r",
        "--view",
        action="store_true",
        help="Just print the decrypted output, don't open an editor. " +
            "NOTE: This will print your secrets in plaintext",
    )
    parser.add_argument(
        "-f",
        "--force",
        "--force-create",
        action="store_true",
        help="If the file you specified does not already exist, create it",
    )

    parser.add_argument(
        "-v",
        "--verbose",
        action="store_const",
        dest="loglevel",
        const=logging.INFO,
        help="Print more details, for debugging. " +
            "NOTE: This will print your secrets in plaintext",
    )
    parser.add_argument(
        "files", nargs="+", help="Specify one or more files that the script should open"
    )
    parser.add_argument(
        '--vault-id', action='append',
        help='Specify Vault ID(s) on the format label@sourcefile or label@prompt. ' +
             "One vault id per '--vault-id' parameter", default=[]
    )
    parser.add_argument(
        "-J", "--ask-vault-pass", "--ask-vault-password", action="store_true",
        help="Get prompted for the default vault-id " +
              "(basically the same as '--vault-id @prompt'). " +
              "Only use this if everything in the file is encrypted with a single password",
    )
    parser.add_argument(
        "--vault-password-file",
        help="Specify the password file for the default vault-id " +
              "(basically the same as '--vault-id @somefile.txt'). " +
              "Only use this if everything in the file is encrypted with a single password",
    )

    return parser.parse_args()


def main_loop(filenames: Iterable[Path], view_only: bool, force_create: bool) -> None:
    """Loop through each file specified as params"""
    for filename in filenames:

        # Has the file been created by this script?
        file_force_created = False

        # Read the original file without custom constructors (for comparing
        # later) (Deepcopy doesn't seem to work, so just load it before
        # defining custom constructors
        try:
            original_data = read_yaml_file(filename)
        except ScannerError as err:
            print(f"'{filename}' is not a valid YAML file. Error is\n{err}", file=sys.stderr)
            sys.exit(1)
        except FileNotFoundError:
            if force_create:
                #original_data = open(filename, "x", encoding="utf-8")
                with open(filename, "x", encoding="utf-8") as empty_file:
                    original_data = empty_file
                file_force_created = True
            else:
                print(
                    f"File '{filename}' doesn't exist. Create non-existant files with -f.",
                    file=sys.stderr
                )
                sys.exit(1)

        # Load the yaml file into memory (will now auto-decrypt vault because
        # of the constructors)
        decrypted_data = read_encrypted_yaml_file(filename)

        if view_only:
            display_yaml_data_and_exit(decrypted_data)
        # Run the rest inside a try-finally block to make sure the decrypted
        # tmp-file is deleted afterwards
        try:
            temp_filename = write_data_to_temporary_file(decrypted_data)
            created_time = os.stat(temp_filename).st_ctime
            open_file_in_default_editor(temp_filename.absolute())
            # Don't do anything if the file hasn't been changed since its creation
            changed_time = os.stat(temp_filename).st_ctime
            if created_time != changed_time:
                encrypt_and_write_tmp_file(
                    tmp_file=temp_filename,
                    final_file=filename,
                    original_data=original_data,
                )
            else:
                # If the file was created but never changed, delete it
                if file_force_created:
                    os.unlink(filename)
        finally:
            os.unlink(temp_filename)

def get_secret_for_vault_id(vault_lib: VaultLib, vault_id: str) -> VaultSecret:
    """
    Retrieves the VaultSecret associated with a specific vault-id from a VaultLib object.

    :param vault_lib: The VaultLib object containing vault secrets.
    :param vault_id: The vault-id label whose secret you want to retrieve.
    :return: The VaultSecret associated with the specified vault-id.
    """
    # Access the _secrets attribute to get the dictionary of vault secrets
    vault_secrets = vault_lib.secrets  # This is a list of tuples (vault_id, VaultSecret)

    for id_label, secret in vault_secrets:
        if id_label == vault_id:
            return secret

    raise ValueError(f"Vault secret with vault-id '{vault_id}' not found.")

def main() -> None:
    """Parse arguments and set up logging before moving on to the main loop"""
    args = parse_arguments()
    # Need to use the VAULT variable in the custom constructors, and I couldn't figure
    # out how to pass it as an extra parameter to the add_constructor function
    # pylint: disable=global-statement
    global VAULT

    try:
        VAULT = setup_vault(
                    ask_vault_pass=args.ask_vault_pass,
                    vault_password_file=args.vault_password_file,
                    vault_ids=args.vault_id
        )
    except KeyboardInterrupt:
        sys.exit(0)
    logging.basicConfig(level=args.loglevel, format="%(levelname)s: %(message)s")
    main_loop(args.files, view_only=args.view, force_create=args.force)


if __name__ == "__main__":
    main()