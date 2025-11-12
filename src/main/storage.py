from sqlalchemy import create_engine, text
from .config import PG_DSN


engine = create_engine(PG_DSN, pool_pre_ping=True)


SCHEMA_SQL = """
create table if not exists trades (
ts timestamptz primary key,
price double precision not null,
size double precision not null
);
"""


def ensure_schema():
    with engine.begin() as conn:
        conn.execute(text(SCHEMA_SQL))
