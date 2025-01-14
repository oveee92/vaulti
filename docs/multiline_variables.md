# Multiline variables

vaulti will print the decrypted content in one of several ways:

- If the encrypted content does not contain a newline (`\n`), it will print it on the same line, like

```yaml
key: !ENCRYPT value
```

- If the encrypted content contains a newline (`\n`), it will use literal block scalars (`|`) and break it over multiple lines for readability

```yaml
key: !ENCRYPT |
  this is some
  multiline content
  that is encrypted
```

- If the encrypted content *does not* contain a newline at the end, it will additionally add a block chomping indicator (hyphen):

```yaml
key: !ENCRYPT |-
  ------BEGIN CERT------
  abcdefghijklmnopqrstuvqxyz
  nopqrstuvwxyzabcdefghidklm
  abcdefghijklmnopqrstuvqxyz
  ------END CERT------
```

You can also use this while creating or editing secrets, and it will encrypt it correctly for you.
