# OpenCode V1 fixture contract

`schema.sql` is a deliberately minimal synthetic legacy projection schema for the
V1 adapter. Tests create temporary SQLite databases at runtime and insert small
JSON message/part payloads matching the semantics consumed by Cost Guard.

No real user OpenCode database is copied into the repository. The fixture keeps
adapter tests deterministic and proves that production reads are independent of
an installed `opencode` executable.
