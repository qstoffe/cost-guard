# Synthetic fixtures

This directory owns deterministic, non-secret test fixtures for Cost Guard development.

Real OpenCode databases, auth files, credentials, personal session exports, runtime caches and other user data MUST NOT be committed here. Later steps may add small synthetic V1 SQLite databases and V2 HTTP/event payload fixtures whose provenance and purpose are documented by their tests.
