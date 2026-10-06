# Persisted V2 cancellation error

## Summary

Read-only inspection of the reported second prompt confirmed the current V2
assistant error shape above: `type: aborted`, no `name`, `finish: error`, a
completed timestamp, and no tokens on the terminal assistant message. The old
normalizer returned `dict`, losing the cancellation discriminator. The message
is deliberately redacted; recognition must depend on the explicit type, not its
text. Session identities, prompts and assistant content are not retained.
