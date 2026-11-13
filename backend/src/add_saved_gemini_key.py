"""Idempotent additive migration; never rewrites existing accounts or secrets."""
from pathlib import Path
import sys

from sqlalchemy import inspect, text

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def migrate(engine):
    with engine.begin() as connection:
        columns = {column['name'] for column in inspect(connection).get_columns('users')}
        if 'gemini_api_key_encrypted' in columns:
            return False
        connection.execute(text('ALTER TABLE users ADD COLUMN gemini_api_key_encrypted VARCHAR(1024) NULL'))
    return True


if __name__ == '__main__':
    from app.db.database import engine
    changed = migrate(engine)
    print('Saved Gemini key column added.' if changed else 'Saved Gemini key column already exists.')
