"""Neo4j driver lifecycle and read-only query execution."""

from contextlib import contextmanager
from typing import Any, Iterator

from neo4j import Driver, GraphDatabase, READ_ACCESS

from .config import get_settings


_driver: Driver | None = None


def get_driver() -> Driver:
    global _driver
    if _driver is None:
        s = get_settings()
        if not s.neo4j_password:
            raise RuntimeError("NEO4J_PASSWORD is not set")
        _driver = GraphDatabase.driver(
            s.neo4j_uri,
            auth=(s.neo4j_user, s.neo4j_password),
        )
    return _driver


def close_driver() -> None:
    global _driver
    if _driver is not None:
        _driver.close()
        _driver = None


@contextmanager
def read_session() -> Iterator[Any]:
    drv = get_driver()
    db = get_settings().neo4j_database
    with drv.session(
        database=db,
        default_access_mode=READ_ACCESS,
    ) as session:
        yield session


def run_read_query(cypher: str, params: dict[str, Any] | None = None) -> list[Any]:
    params = params or {}
    with read_session() as session:
        result = session.run(cypher, params)
        # Use raw field values, not record.data(): .data() JSON-serializes graph types
        # (nodes → property dicts, rels → (start, type, end) tuples), which breaks serializers.
        return [dict(record.items()) for record in result]
