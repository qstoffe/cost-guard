# Executable validation policies

`file-budgets.json` is consumed by the source-local package validator and tests.
Its limits were moved unchanged from the former governance directory.

Do not silently raise limits, rebaseline exceptions or weaken validation to make
a change pass. Refactor the responsible code or obtain an explicit scoped decision.
Documentary architecture/policies and historical results live in the private
development repository; source tests and builds must not depend on that access.
