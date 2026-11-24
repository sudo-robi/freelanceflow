import importlib.util
from pathlib import Path

import pytest
import sqlalchemy

DATABASE_PATH = Path(__file__).resolve().parents[1] / "app" / "database.py"


def load_database(monkeypatch, url=None, env_present=True):
    """Load a fresh copy of database.py so import-time configuration can be tested."""
    original_create_engine = sqlalchemy.create_engine
    captured = {}

    def fake_create_engine(dsn, **kwargs):
        captured["dsn"] = dsn
        captured["kwargs"] = kwargs
        return original_create_engine("sqlite://")

    monkeypatch.setattr(sqlalchemy, "create_engine", fake_create_engine)
    if env_present:
        monkeypatch.setenv("DATABASE_URL", url)
    else:
        monkeypatch.delenv("DATABASE_URL", raising=False)

    spec = importlib.util.spec_from_file_location("freelanceflow_database_under_test", DATABASE_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module, captured


def test_defaults_to_local_sqlite(monkeypatch):
    module, captured = load_database(monkeypatch, env_present=False)

    assert module.DATABASE_URL == "sqlite:///./freelanceflow.db"
    assert captured["dsn"] == "sqlite:///./freelanceflow.db"
    assert captured["kwargs"] == {"connect_args": {"check_same_thread": False}}
    assert module.SessionLocal.kw["bind"] is not None


def test_postgres_scheme_is_normalized_to_psycopg(monkeypatch):
    module, captured = load_database(monkeypatch, "postgres://user:pass@host:5432/freelanceflow")

    assert module.DATABASE_URL == "postgresql+psycopg://user:pass@host:5432/freelanceflow"
    assert captured["dsn"] == module.DATABASE_URL
    assert captured["kwargs"] == {"connect_args": {}}


def test_postgresql_scheme_is_normalized_to_psycopg(monkeypatch):
    module, captured = load_database(monkeypatch, "postgresql://user:pass@host:5432/freelanceflow")

    assert module.DATABASE_URL == "postgresql+psycopg://user:pass@host:5432/freelanceflow"
    assert captured["dsn"] == module.DATABASE_URL
    assert captured["kwargs"] == {"connect_args": {}}


def test_other_database_urls_are_left_unchanged(monkeypatch):
    module, captured = load_database(monkeypatch, "sqlite+pysqlite:////tmp/other.db")

    assert captured["dsn"] == "sqlite+pysqlite:////tmp/other.db"
    assert captured["kwargs"] == {"connect_args": {"check_same_thread": False}}
    assert module.Base.metadata is not None


def test_non_sqlite_non_postgres_urls_have_no_connect_args(monkeypatch):
    _, captured = load_database(monkeypatch, "mysql+pymysql://user:pass@host/db")

    assert captured["dsn"] == "mysql+pymysql://user:pass@host/db"
    assert captured["kwargs"] == {"connect_args": {}}


class FakeSession:
    def __init__(self):
        self.closed = False

    def close(self):
        self.closed = True


def test_get_db_yields_then_closes_the_session(monkeypatch):
    module, _ = load_database(monkeypatch, env_present=False)
    session = FakeSession()
    monkeypatch.setattr(module, "SessionLocal", lambda: session)

    generator = module.get_db()
    assert next(generator) is session
    with pytest.raises(StopIteration):
        next(generator)

    assert session.closed is True


def test_get_db_closes_the_session_on_error(monkeypatch):
    module, _ = load_database(monkeypatch, env_present=False)
    session = FakeSession()
    monkeypatch.setattr(module, "SessionLocal", lambda: session)

    generator = module.get_db()
    next(generator)
    with pytest.raises(RuntimeError, match="boom"):
        generator.throw(RuntimeError("boom"))

    assert session.closed is True
