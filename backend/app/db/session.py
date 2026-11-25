"""Engine, sessions and the per-transaction tenant context used by RLS.

How tenant context reaches PostgreSQL
-------------------------------------
Row-level security policies read two settings: `app.tenant_id` and
`app.user_id`. They are set with `set_config(name, value, is_local => true)`,
which scopes them to the *current transaction*. When the transaction commits
or rolls back, PostgreSQL discards them.

That matters because connections are pooled: a session-level `SET` would stay
on the connection after it returns to the pool and leak into the next
request. Transaction-local settings cannot leak (this also holds behind
PgBouncer in transaction-pooling mode).

The values live in `Session.info`; an `after_begin` listener re-applies them
at the start of every transaction the session opens. If a value is absent,
the setting is never set, the policy compares against NULL, and no rows
match: the system fails closed.
"""

import uuid
from collections.abc import Iterator

from sqlalchemy import create_engine, event, text
from sqlalchemy.engine import Connection, Engine
from sqlalchemy.orm import Session, SessionTransaction, sessionmaker

from app.core.config import get_settings

TENANT_KEY = "tenant_id"
USER_KEY = "user_id"

_SET_CONTEXT = text(
    "SELECT set_config('app.tenant_id', :tenant, true), set_config('app.user_id', :user, true)"
)

_engine: Engine | None = None
_factory: sessionmaker[Session] | None = None


def get_engine() -> Engine:
    global _engine, _factory
    if _engine is None:
        _engine = create_engine(get_settings().database_url, pool_pre_ping=True)
        _factory = sessionmaker(bind=_engine, expire_on_commit=False)
    return _engine


def dispose_engine() -> None:
    """Close all pooled connections and forget the engine (shutdown, tests)."""
    global _engine, _factory
    if _engine is not None:
        _engine.dispose()
    _engine = None
    _factory = None


def session_factory() -> sessionmaker[Session]:
    get_engine()
    assert _factory is not None
    return _factory


def _apply(connection: Connection, info: dict) -> None:
    tenant = info.get(TENANT_KEY)
    user = info.get(USER_KEY)
    connection.execute(_SET_CONTEXT, {"tenant": str(tenant) if tenant else "", "user": str(user) if user else ""})


@event.listens_for(Session, "after_begin")
def _set_context_on_begin(session: Session, transaction: SessionTransaction, connection: Connection) -> None:
    _apply(connection, session.info)


def set_db_context(session: Session, *, tenant_id: uuid.UUID | None = None, user_id: uuid.UUID | None = None) -> None:
    """Bind tenant/user context to this session, effective immediately."""
    session.info[TENANT_KEY] = tenant_id
    session.info[USER_KEY] = user_id
    if session.in_transaction():
        _apply(session.connection(), session.info)


def get_db() -> Iterator[Session]:
    """One session and (normally) one transaction per request."""
    session = session_factory()()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
