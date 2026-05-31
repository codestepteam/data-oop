"""Pluggable execution layer for external data sources.

A connector only stores *which* source to talk to (``kind`` + an env-var reference);
the actual driver and query execution live here, behind a small registry so new
backends (e.g. BigQuery, Snowflake) plug in without touching the repository or sync code.

Credentials are NEVER stored in the graph. ``ConnectorDef.dsn_ref`` is the NAME of an
environment variable holding the real DSN (with password); BigQuery reads its project
and a credentials env-var reference from ``ConnectorDef.metadata``.
"""

from __future__ import annotations

import os
from typing import Any, Callable
from urllib.parse import urlparse

from .exceptions import TBoxError
from .models import ConnectorDef

# An executor takes a connector + a SQL string and returns rows as dicts (column -> value).
Executor = Callable[[ConnectorDef, str], list[dict[str, Any]]]

_EXECUTORS: dict[str, Executor] = {}


def register_executor(kind: str, executor: Executor) -> None:
    """Register (or override) the executor used for a connector ``kind``."""
    _EXECUTORS[kind] = executor


def get_executor(kind: str) -> Executor:
    executor = _EXECUTORS.get(kind)
    if executor is None:
        raise TBoxError(
            f"No executor registered for connector kind {kind!r}. "
            f"Available: {sorted(_EXECUTORS)}"
        )
    return executor


def fetch_rows(connector: ConnectorDef, sql: str) -> list[dict[str, Any]]:
    """Run ``sql`` against ``connector`` and return result rows as dicts."""
    return get_executor(connector.kind)(connector, sql)


def _require_dsn(connector: ConnectorDef) -> str:
    """Read the real DSN from the env var named by ``connector.dsn_ref``."""
    if not connector.dsn_ref:
        raise TBoxError(f"Connector {connector.name!r} has no dsn_ref set")
    dsn = os.environ.get(connector.dsn_ref)
    if not dsn:
        raise TBoxError(
            f"Environment variable {connector.dsn_ref!r} is not set "
            f"(required by connector {connector.name!r})"
        )
    return dsn


def _postgres_executor(connector: ConnectorDef, sql: str) -> list[dict[str, Any]]:
    try:
        import psycopg
    except ImportError as exc:  # pragma: no cover - exercised only without the extra
        raise TBoxError(
            "psycopg is required for postgres connectors. Install with: pip install 'data-oop[postgres]'"
        ) from exc

    dsn = _require_dsn(connector)
    with psycopg.connect(dsn) as conn, conn.cursor() as cur:
        cur.execute(sql)
        columns = [desc[0] for desc in cur.description]
        return [dict(zip(columns, row)) for row in cur.fetchall()]


def _mysql_executor(connector: ConnectorDef, sql: str) -> list[dict[str, Any]]:
    try:
        import pymysql
    except ImportError as exc:  # pragma: no cover - exercised only without the extra
        raise TBoxError(
            "PyMySQL is required for mysql connectors. Install with: pip install 'data-oop[mysql]'"
        ) from exc

    # PyMySQL has no DSN-string constructor; parse the URL form mysql://user:pass@host:port/db.
    url = urlparse(_require_dsn(connector))
    conn = pymysql.connect(
        host=url.hostname,
        port=url.port or 3306,
        user=url.username,
        password=url.password or "",
        database=(url.path or "").lstrip("/") or None,
        cursorclass=pymysql.cursors.DictCursor,
    )
    try:
        with conn.cursor() as cur:
            cur.execute(sql)
            return [dict(row) for row in cur.fetchall()]
    finally:
        conn.close()


def _bigquery_executor(connector: ConnectorDef, sql: str) -> list[dict[str, Any]]:
    try:
        from google.cloud import bigquery
    except ImportError as exc:  # pragma: no cover - exercised only without the extra
        raise TBoxError(
            "google-cloud-bigquery is required for bigquery connectors. "
            "Install with: pip install 'data-oop[bigquery]'"
        ) from exc

    # BigQuery doesn't fit the DSN model: read project + an optional credentials env-var
    # reference from metadata. With no credentials_ref, fall back to Application Default
    # Credentials (ADC).
    project = connector.metadata.get("project")
    credentials_ref = connector.metadata.get("credentials_ref")
    if credentials_ref:
        credentials_path = os.environ.get(credentials_ref)
        if not credentials_path:
            raise TBoxError(
                f"Environment variable {credentials_ref!r} is not set "
                f"(credentials_ref for connector {connector.name!r})"
            )
        client = bigquery.Client.from_service_account_json(credentials_path, project=project)
    else:
        client = bigquery.Client(project=project)
    return [dict(row.items()) for row in client.query(sql).result()]


register_executor("postgres", _postgres_executor)
register_executor("mysql", _mysql_executor)
register_executor("bigquery", _bigquery_executor)
