# Installation and basic usage

## Installation

The dists have been published to PyPi, you can easily install it with `pip install vaulti-ansible`.

Alternatively, you can clone this repo and use another installation method:

```shell
# You can test this by cloning the repo, cd into it
git clone https://github.com/oveee92/vaulti.git && cd vaulti

# then EITHER install it with pip to get it installed into your PATH and as a python module
pip install .
vaulti example/example_data.yml
# OR put it somewhere in the PATH yourself
cp .src/vaulti_ansible/vaulti.py ~/.local/bin/vaulti
vaulti example/example_data.yml
# OR just use it directly without "installing" it
./src/vaulti_ansible/vaulti.py example/example_data.yml

```

## Simple example

Now you can set up and use it. Example here works in the git directory if you used `git clone` above,
but you can very easily just create your own files to test with.

```shell
# If you want to use a password file, you can set it as a variable
export ANSIBLE_VAULT_PASSWORD_FILE=example/.default_vault_pass.txt
# OR specify it on the command line
vaulti example/example_data.yml --vault-password-file example/.default_vault_pass.txt
```

Make some changes to existing variables, create some new ones or remove some tags.

Save and quit, then open it regularly to see what changed, or just run git diff to see what happened.

```shell
git diff example_encrypted_data.yaml
```

## General usage

You can use the standard ansible methods of defining a vault password or vault password file, like `--ask-vault-pass` parameter,
`ANSIBLE_VAULT_PASSWORD_FILE` environment variable and `--vault-id`.

There are some quality of life features built in, such as:

- if you edit the file to some invalid yaml, you'll get the chance to re-open the file and try again
- ditto if you try to encrypt with a vault id that you didn't load when starting
- if you comment out a line while it is decrypted, it will not be reencrypted, but it will produce a warning.

Variable files that could not be decrypted for whatever reason, get a tag indicating the problem, but is left untouched after exiting.

## Available tags

The list of tags, both for success and failure, are currently:

### Success

- `!ENCRYPT` : Variables that have been decrypted, and will be reencrypted when you close the editor
- `!ENCRYPT:[label]`, for example `!ENCRYPT:foo`: Indicates that this value was decrypted with a specific vault-id label.

### Failure

**Warning**: Do not change these during the editing process. Changing the value of encrypted strings will almost certainly corrupt them,
and changing the tag value to something else might subject them to further processing (for example encrypting the encrypted content).

- `!VAULT_FORMAT_ERROR` : Variables that could not be parsed due to ansible-vault rejecting the format. Ensure it was copypasted correctly, with no trailing whitespace characters. It will revert to the original `!vault` tag/value untouched after you close the editor.
- `!UNKNOWN_VAULT_ID_LABEL` : Variables that could not be decrypted, most likely because you did not load/specify the relevant vault id. It will revert to the original `!vault` tag/value untouched after you close the editor.
- `!COULD_NOT_DECRYPT` : Variables that could not be decrypted for any other reason, but most probably because you specified the wrong password. It will revert to the original `!vault` tag/value untouched after you close the editor.
- `![any tag]:[label]`, for example `!UNKNOWN_VAULT_ID_LABEL:foo`: The label just indicates the vault-id fetched from the payload string. If nothing is specified, it uses the default vault id.
