# Vaulti

Utility to edit, create, encrypt and decrypt ansible-vault in-line encrypted variables in yaml files.

If you wish you had `ansible-vault edit` for partially encrypted files, that is what this utility is trying to do.

## Usage

https://github.com/user-attachments/assets/74480694-3333-4405-8f68-248af21c9999

```shell
./vaulti file1 # If you want it to use standard ansible environment vars for the vault password
./vaulti file1 [file2] [file3] [...] # Define multiple files if you wish
./vaulti file1 --ask-vault-pass # If you want to specify the password on the CLI
./vaulti file1 --ask-vault-pass --vault-id mylabel@prompt # You can also specify vault ids
./vaulti file1 -r # Prints the output, doesn't let you edit. Useful for setting up custom git textconv, etc.
```

See `./vaulti -h` for more usage details

## About

### General

This utility opens an editor where the encrypted variables have been decrypted!

The "secret" variables are indicated with a special tag, `!ENCRYPT`.

You can use the standard ansible methods of defining a vault password or vault password file, like `--ask-vault-pass` parameter,
`ANSIBLE_VAULT_PASSWORD_FILE` environment variable and `--vault-id`.

You can:

- Add or remove the `!ENCRYPT` tags as you wish, and it will encrypt or decrypt for you.
- Read, edit and encrypt block scalars if you need to include newlines (`|`, `>`, `|-`, etc.), which can be useful when you want to encrypt private keys or other multi-line things.
- Read and edit different vault ids in the same file
- Swap to a different vault-id

There are some quality of life features built in, such as:

- if you edit the file to some invalid yaml, you'll get the chance to re-open the file and try again
- ditto if you try to encrypt with a vault id that you didn't load when starting
- if you comment out a line while it is decrypted, it will not be reencrypted, but it will produce a warning.

Variable files that could not be decrypted for whatever reason, get a tag indicating the problem, but is left untouched after exiting. Those tags are currently:

- `!ENCRYPT` : Variables that have been decrypted, and will be reencrypted when you close the editor
- `!VAULT_FORMAT_ERROR` : Variables that could not be parsed due to ansible-vault rejecting the format. It will revert to the original `!vault` tag/value untouched after you close the editor.
- `!UNKNOWN_VAULT_ID_LABEL` : Variables that could not be decrypted, most likely because you did not load/specify the relevant vault id. It will revert to the original `!vault` tag/value untouched after you close the editor.
- `!COULD_NOT_DECRYPT` : Variables that could not be decrypted, probably because you specified the wrong password. It will revert to the original `!vault` tag/value untouched after you close the editor.
- `![any tag]:[label]`, for example `!ENCRYPT:foo`: Indicates that this value was decrypted with a specific vault-id label.



### Vault ids

Secrets decrypted with the non-default ID will be shown in the tag as `!ENCRYPT:mylabel`. You can also set these labels yourself, as long as 
you actually loaded the relevant vault-id when starting the utility.

**WARNING**: The labels are there to help *you* when prompted, but ansible-vault will try all of the keys when decrypting no matter what.
So if you have two vault-ids, but you swap the passwords on the prompt, it will still decrypt just fine. However, when you save and quit,
now you'll encrypt the variables with the swapped passwords instead, which might lead to confusion.

If it finds vaulted variables it cannot decrypt for any reason, it leaves them unencrypted, but changes the tag to `!COULD_NOT_DECRYPT`.
The tag returns to `!vault` when you exit the editor.


## Example

```shell
# You can test this by cloning the repo, cd into it
git clone https://github.com/oveee92/vaulti.git && cd vaulti

# then EITHER install it with pip to get it installed into your PATH
pip install .
vaulti example/example_data.yml
# OR just use it directly
./src/vaulti_ansible/vaulti.py example/example_data.yml

# If you want to use a password file, you can set it as a variable
export ANSIBLE_VAULT_PASSWORD_FILE=example/.default_vault_pass.txt
# OR specify it on the command line
vaulti example/example_data.yml --vault-password-file example/.default_vault_pass.txt

# To see the variables encrypted with the foo vault ID, load it too
vaulti example/example_data.yml --vault-id foo@prompt
vaulti example/example_data.yml --vault-password-file example/.default_vault_pass.txt --vault-id foo@example/.foo_vault_pass.txt

# Make some changes to existing variables, create some new ones or remove some tags
# Save and quit, then open it regularly to see what changed, or just run git diff to see what happened
git diff example_encrypted_data.yaml
```

## Why this exists

Ansible-vault works fine for encrypting/decrypting/editing whole files, but there are times you don't want to encrypt entire files; for example:

If you use AWX/AAP, having vault-encrypted files is a bit difficult; you either have to
- include the vault password in whichever container/EE you are running the playbooks (therefore requiring a custom image), or
- decrypt the file when syncing the inventory (making all your secrets plaintext for those with high enough access in AWX)

If your control repo is getting large, with lots of host vars and group vars, and you want to find out where certain variables are defined,
you won't be able to search full vault-encrypted files easily, since their key is also encrypted.

So you try inline encryption, which solves these problems, but using it with `ansible-vault edit <file>` is no longer possible...
you have to do something like this:

```shell
## To encrypt
ansible-vault encrypt_string # <enter>
SomePasswordOrSomething # <Ctrl-D>, NOT <enter> unless you need the newline encrypted too
# Then copy the output into your yaml file, making sure the indentation is still ok

## To edit
# Encrypt a new string and replace it

## To decrypt
ansible -i the/relevant/inventory the-relevant-host -m debug -a "var=TheAnsibleVaultedVariable"
```

Not really easy to remember, pretty error-prone and requires you to actually run something with ansible, putting the variable
somewhere where it will actually be read (hostvars or groupvars). Much easier to just open the decrypted content and edit it directly.


## Why you should NOT use this

This is created by a sysadmin, not a professional programmer. It is getting better over time, but there may still be edge cases where
strange things could happen to the file you are editing. It isn't likely, and I've used it without issue for some time, but if you don't
have your files in a git repo with the ability to revert files easily, please dont use this just yet (or just initialize a git repo first!)

Also, if you try to change the yaml tags between `!COULD_NOT_DECRYPT`, `!vault` and `!ENCRYPT` when editing, you'll probably end up with unencrypted
or broken variables. Stick to adding or removing the `!ENCRYPT` tags and their labels only, for a good time.


## Caveats

Since it uses the fantastic (yet sparsely documented) `ruamel.yaml`, and the yaml spec is pretty extensive, this utility does
make some "non-negotiable" changes to your files that you should be aware of, that happens when we load and parse the yaml data:

- Indentation for your multiline strings will always end up with a fixed (default 2) spaces relative to the variable it belongs to;
  i.e. not the 10 spaces indented or whatever the default is from the `ansible-vault encrypt_string` output. This is good for consistency, but it does mean that the indentation
  of your inline-encrypted variables will probably change the first time you use this if you've previously used `ansible-vault encrypt_string` to generate the encrypted strings.
  If you don't change the decrypted value it should remain the same though, except for the indent change.
- Extra whitespaces will be removed whereever it is found (for example `key:  value` -> `key: value`)

Also, there are a few "opinionated" things I've hardcoded, which are relatively easy to comment out or change if you wish it.

- Header (`---`) and footer (`...`) will be added automatically to the variable file if it doesn't exist.
- A tab/indent equals two spaces
- The hyphen starting each list items is indented, not inline with the parent key
- An extra newline is added below the ansible-vault output, for readability.
- No automatic line breaks for long values.


Finally, a word on diffs. The script revolves around decrypting and reencrypting the variables, which means that every time you open a file with it, the
encrypted string actually changes (different salt for each reencrypt). Part of the script is therefore dedicated to looping through the re-encrypted file, comparing it with
the original decrypted data, and preferring the old encrypted string if the actual decrypted value hasn't changed. That means that any git diff produced by these changes will
usually only involve the relevant changed variables, but it is a "best effort" process. If you change the number encrypted variables in a list, the items
whose list index was changed will be re-encrypted with a new salt, since the original value cannot be found. Same goes for any variables where you change
the key name. Create the key/entry with a regular editor first if this is important to you.

## Dependencies

Won't put the dependencies in the `pyproject.toml` file for now, since with Ansible, sometimes you
want ansible-core on a specific version to keep a consistent execution environment. Any mention of
the required libraries will make pip upgrade `ansible` and `ansible-core` packages even if the
requirements don't make it necessary.

Having to use `--no-deps` for installing this tool is just asking for trouble.

Dependencies are:

```
# We're using typing classes from Python3.9, and __future__ annotations is not not available before python 3.7.
# Since ansible seems to skip 3.7, let's just say 3.8. Might work with 3.7, if you are using that for some reason.
python>=3.8 

ruamel.yaml>=0.16.6 # Won't work before this version due to TaggedScalar changes
ansible>=2.4.0.0 # Won't work for older versions due to pycrypto
```
