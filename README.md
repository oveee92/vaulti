# Vaulti

Like `ansible-vault edit`, but for files with inline encrypted variables!

Edit, create, encrypt and decrypt ansible-vault in-line encrypted variables in yaml files.


## Usage example

https://github.com/user-attachments/assets/74480694-3333-4405-8f68-248af21c9999


## Quick start

```shell
# Install it
pip install vaulti-ansible

# Open a file for editing
vaulti file.yml

# See more options
vaulti -h
```

## Features

- Encrypt or decrypt files by adding or removing custom tags
- Change encrypted values directly
- Works for simple variables, lists, dicts, multiline variables (literals) and anchors
- Works with multiple / non-default vault-ids
- Print decrypted files to stdout
- Some Quality of Life features to let you reopen the file if simple mistakes are made

See [examples folder](examples/) for more examples and user guides


## Why this exists

The standard `ansible-vault` works fine for encrypting/decrypting/editing whole files, but there are times you don't want to encrypt entire files; for example:

If you use AWX/AAP, having vault-encrypted files is a bit difficult; you either have to:

- include the vault password in whichever container/Execution environment you are running the playbooks (therefore requiring a custom container image), or
- decrypt the file when syncing the inventory (making all your secrets plaintext for those with high enough access in AWX)

Additionally, if your control repo is getting large, with lots of `host_vars` variables, `group_vars` variables, complex playbooks and roles, and you want
to find out where certain variables are defined, you won't be able to search full vault-encrypted files easily, since all the keys are also encrypted.

So then you try inline encryption, which solves pretty much all of these problems, but using it with `ansible-vault edit <file>` is no longer possible...
you now have to do something like this instead:

```shell
## To encrypt:
ansible-vault encrypt_string # <enter>
SomePasswordOrSomething # <Ctrl-D>, NOT <enter> unless you need the newline encrypted too
# Then copy the output into your yaml file, making sure the indentation is still ok

## To edit:
# Not possible, just encrypt a new string and replace it.

## To view:
ansible -i the/relevant/inventory the-relevant-host -m debug -a "var=TheRelevantVariable"

## To decrypt:
# Not possible, just view it and copy-paste the content where needed

```

Not really easy to remember the encrypt and view steps, pretty error-prone and requires you to actually run something with ansible, putting the variable
somewhere where it will actually be read (hostvars or groupvars). It is *much* easier to just open the decrypted content and edit it directly.


## Why you should NOT use this

I am a sysadmin by trade, not really a professional programmer, and the quality of the code might reflect that. It is getting better over time, but
there may still be edge cases where strange things could happen to the file you are editing. Yaml is a pretty complex specification after all. It
isn't likely to break, and I've used it without issue for some time, but if you don't have your files in a git repo with the ability to revert files
easily, please at least initialize a git repo first and do an initial commit! If you need this utility, it's probably time for version control anyway)

## Caveats

Since it uses the fantastic (yet sparsely documented) `ruamel.yaml`, and the yaml spec is pretty extensive, this utility does
make some "non-negotiable" changes to your files that you should be aware of, that happens when we load and parse the yaml data:

- Indentation for your multiline strings will always end up with a fixed (default two) spaces relative to the variable it belongs to;
  i.e. not the 10 spaces indented or whatever the default is from the `ansible-vault encrypt_string` output. This is good for consistency, but it does mean that the indentation
  of your inline-encrypted variables will probably change the first time you use this, if you've previously used `ansible-vault encrypt_string` to generate the encrypted strings.
  If you don't change the decrypted value, it should remain the same though, except for the indent change.
- Extra whitespaces will be removed whereever it is found (for example `key:  value` -> `key: value`)

Also, there are a few "opinionated" things I've hardcoded, which are relatively easy to comment out or change in `setup_yaml()` if you wish it.

- Header (`---`) and footer (`...`) will be added automatically to the variable file if it doesn't exist.
- An indent equals two spaces
- The hyphen starting each list items is indented, not inline with the parent key
- An extra newline is added below the ansible-vault output, for readability.
- No automatic line breaks for long values.

Finally, a word on diffs. The utility revolves around decrypting and reencrypting the variables, which means that every time you open a file with it, the
encrypted string actually changes (different salt for each reencrypt). Part of the utility is therefore dedicated to looping through the re-encrypted file, comparing it with
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
