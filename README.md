# Vaulti

Utility to edit, create, encrypt and decrypt ansible-vault in-line encrypted variables in yaml files.

## Usage

```shell
./vaulti file1 # If you want it to use standard ansible environment vars for the vault password
./vaulti file1 file2 # Define multiple files if you wish
./vaulti file1 --ask-vault-pass # If you want to specify the password on the CLI
./vaulti file1 -r # Prints the output, doesn't let you edit. Useful for setting up custom git diff, etc.
```

You can add or remove the `!ENCRYPTED` tags as you wish, and it will encrypt or decrypt for you.

If it finds vaulted variables it cannot decrypt, it shows you with a tag like `!VAULT_INVALID`. It returns unchanged to `!vault` when you exit the editor.

## Example

```shell
# You can test this by cloning the repo, cd into it and running
git clone https://github.com/oveee92/vaulti.git && cd vaulti
export ANSIBLE_VAULT_PASSWORD_FILE=.example_vault_pass.txt
./vaulti example_encrypted_data.yaml
# Make some changes to existing variables, create some new ones or remove some tags
# Save and quit, then open it regularly to see what changed, or just run git diff to see what happened
git diff example_encrypted_data.yaml
```

The partial vault-encrypted file looks like this:

```yaml
enc_variable: !vault |
  $ANSIBLE_VAULT;1.1;AES256
  66373364636166306131353930333262303162396534373632346137316437636338333431616...

plain_variable: gonna

list_variable: # Encrypted variables as list items might not be valid for ansible though
  - !vault |
    $ANSIBLE_VAULT;1.1;AES256
    66323661363266353635316639333063333134633831613763333031646566323531393238353...


list_of_dicts:
  - plaintext: you
    encrypted: !vault |
      $ANSIBLE_VAULT;1.1;AES256
      39323233613537376363333139616137653065663334366538643631353333653833666163663...

# (...)
```

Running `./vaulti myfile.yml` opens your editor like this

```yaml
enc_variable: !ENCRYPTED Never

plain_variable: gonna

list_variable: # Encrypted variables as list items might not be valid for ansible though
  - !ENCRYPTED give

list_of_dicts:
  - plaintext: you
    encrypted: !ENCRYPTED up

# (...)
```

Now you can remove the `!ENCRYPTED` tag to decrypt and add new `!ENCRYPT` tags to encrypt, before saving and quitting!
You can also add new variables, both with and without the tag, and comment whereever the yaml spec lets you.
Block scalars also work, if you need to include newlines (`|`, `>`, `|-`, etc.)

## Why this exists

Ansible-vault works fine for encrypting/decrypting/editing whole files, but there are times you don't want to encrypt entire files:

If you use AWX/AAP, having vault-encrypted files is difficult; you either have to
- include the vault password in whichever container/EE you are running the playbooks (therefore requiring a custom image), or
- decrypt the file when syncing the inventory (making all your secrets plaintext for those with high enough access in AWX)

If your control repo is getting large, with lots of hostvars and groupvars, and you want to find out where certain variables are defined,
you won't be able to search vault-encrypted files, since their key is also encrypted.

So you try inline encryption, but using it with `ansible-vault edit <file>` is no longer possible, you have to do something like this:

```shell
## To encrypt
ansible-vault encrypt_string # <enter>
SomePasswordOrSomething # <Ctrl-D>, NOT <enter> unless you need the newline encrypted too
# Then copy the output into your yaml file, making sure the indentation is still ok

## To edit
# Just encrypt a new string and replace it

## To decrypt
ansible -i the/relevant/inventory the-relevant-host -m debug -a "var=TheAnsibleVaultedVariable"
```

Yikes...

If you wish you had `ansible-vault edit` for partially encrypted files, that is what this utility is trying to do.

## Why you should NOT use this

This is created by a sysadmin, not a professional programmer. It is possible that an unhandled exception thrown or edge-case
schenario will overwrite the partially encrypted yaml file with junk or empty data. It isn't likely, and I've used it without
issue for some time, but if you don't have your files in a git repo with the ability to revert files easily,
please dont use this just yet :)

Also, if you try to change the yaml tags between `!VAULT_INVALID`, `!vault` and `!ENCRYPTED` when editing, you'll probably end up with unencrypted
or broken variables. Stick to adding or removing the `!ENCRYPTED` tags only.

## Caveats

Since it uses the fantastic (yet sparsely documented) `ruamel.yaml`, and the yaml spec is pretty extensive, this utility does
make some "non-negotiable" changes to your files that you should be aware of:

- Indentation for your multiline strings will always end up with a fixed (default 2) spaces relative to the variable it belongs to;
  i.e. not the 10 spaces indented or whatever the default is from the `ansible-vault encrypt_string` output. This is good for consistency, but it means the indentation
  of the inline-encrypted variables will probably change the first time you use this. If you don't change the decrypted value it should remain the same though, except for the indent change.
- Extra whitespaces will be removed whereever it is found (for example `key:  value` -> `key: value`)

Also, there are a few "opinionated" things I've hardcoded, which are relatively easy to comment out or change if you wish it.

- Header (`---`) and footer (`...`) will be added automatically to the variable file if it doesn't exist.
- An extra newline is added below the ansible-vault output, for readability.
- No automatic line breaks for long values.

I have not yet implemented anything with different vault IDs, because I've never used it...

I have not tested all possible ways of defining ansible-vault credentials, just the environment variable `ANSIBLE_VAULT_PASSWORD_FILE` and `--ask-vault-pass`

## Dependencies

ruamel.yaml 
