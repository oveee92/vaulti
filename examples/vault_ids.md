# Vault ids

## Usage

```shell
# To see the variables encrypted with the foo vault ID, load it too, either being prompted for the password, or referring to a file
vaulti example/example_data.yml --vault-id foo@prompt
vaulti example/example_data.yml --vault-id foo@example/.foo_vault_pass.txt
```

## Explanations

Secrets decrypted with the non-default ID will be shown in the tag as `!ENCRYPT:mylabel`. You can also set these labels yourself in the edit
mode, as long as you actually loaded the relevant vault-id when starting the utility.

**WARNING**: The labels are there to help *you* when prompted, but ansible-vault will try all of the keys when decrypting no matter what.
So if you have two vault-ids, but you swap the passwords on the prompt, it will still decrypt just fine. However, when you save and quit,
now you'll encrypt the variables with the swapped passwords instead, which will definitely lead to confusion.
