# Migrations

Alembic is included in `requirements.txt`, but the MVP currently creates tables on app startup for fast local iteration.

When the schema stabilizes, initialize Alembic here and switch production deployments to migration-driven schema changes.
