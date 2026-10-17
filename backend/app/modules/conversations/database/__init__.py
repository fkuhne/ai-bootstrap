"""The database: the connection to PostgreSQL, where the conversations are kept.

The module reads and writes through it, and the `migrate-db` job creates its tables from
`migrations/`.
"""
