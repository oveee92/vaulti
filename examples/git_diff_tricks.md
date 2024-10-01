# Git diff tricks

You can set up a script that decrypts the contents of your files so that your git diff is actually useful for ansible-vault,
not just a random encrypted-armored vault string.

Using a custom conversion of the data is called `textconv` in git.

It has several parts, and is set up so that it only works for you, and doesn't mess up the config of your team.

## Custom wrapper script

The script basically tries to verify whether it is a yaml file and contains the string `!vault`. If it does, it
passes it to vaulti with the `--view|-r` option, and if not, it just cats it out as it is.

Content of `~/.local/bin/vaulti_wrapper.sh`:

```shell
#!/bin/bash

# Check if the file ends with .yml or .yaml
if [[ "$1" == *.yml || "$1" == *.yaml ]]; then
    # If the file contains the magic string "!vault", run the custom command
    if grep -q "!vault" "$1"; then
        vaulti -r "$1"
    else
        # If not, just cat the file
        cat "$1"
    fi
else
    # If the file is not a .yml or .yaml file, output it unchanged
    cat "$1"
fi
```

## Global gitconfig

Then you have to specify a custom textconv on the "vaulti" diff, in your home directory.

Content of ~/.gitconfig
```ini
[diff "vaulti]
textconv = ~/.local/bin/vaulti_wrapper.sh
```

## Git attributes

You have to specify which files should use the custom textconv. I just select all files.
Put it in `.git/info/attributes` so that your change stays local and won't affect your team.

Content of `<repo>/.git/info/attributes`

```ini
* diff=vaulti
```

## General

Now when you use `git diff`, it will (of course) be a little slower than normal, but will now
show you the diff of the decrypted content, which might be very useful.

If you want to see the actual content again, just remove the content of `<repo>/.git/info/attributes`.

If you want to see the actual content again temporarily, just use `git diff --no-textconv`

## Future

This is not a very "stable" configuration, and might have a lot of caveats. It might break the git diff functionality if you
haven't set up the `ANSIBLE_VAULT_PASSWORD_FILE` variable, it might not work for vault-encrypted (whole) files,
but is very useful in cases where you are changing lots of encrypted variables and want sanity checks every now and then.

Use it if you find it helpful!
