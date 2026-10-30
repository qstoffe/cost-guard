# Synthetic OpenAI TLS regression chain

These are disposable localhost test certificates and a **synthetic server key**,
not credentials or certificates from a workstation/provider. Generated offline
with .NET `CertificateRequest`; no machine certificate store was changed.

- `root.pem`: synthetic server-authentication trust root, valid 2020–2045.
- `unrelated-root.pem`: an independent synthetic root for untrusted-chain rejection.
- `server.pem`: localhost leaf and current intermediate, valid 2020–2045.
- `expired-intermediate.pem`: the same intermediate subject/key, expired in 2021.
- `expired-server.pem`: expired localhost leaf and the current intermediate.
- `synthetic-server-key.pem`: only the disposable localhost leaf's private key.

The server supplies its current chain. Loading the expired intermediate beside
the root reproduces OpenSSL's trusted-first expiry failure. The Windows ROOT-only
context must succeed without admitting expired leaves, untrusted chains or a
hostname mismatch. Everything stays on loopback; no package or external tool is
needed to execute the tests.
