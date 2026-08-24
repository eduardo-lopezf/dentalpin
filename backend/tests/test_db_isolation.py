"""The suite must never be able to reach the application database.

Every test calls ``Base.metadata.drop_all``. Before this guard existed the
suite inherited ``DATABASE_URL`` verbatim, so a local run wiped the dev
database — schema, demo clinic, user accounts and all. These tests pin the
invariant so it cannot regress silently.
"""

from sqlalchemy.engine import make_url

from app import database as app_database
from app.config import settings

from .conftest import TEST_DATABASE_URL


def test_test_database_is_suffixed() -> None:
    """The database under test is always a dedicated ``*_test`` one."""
    assert make_url(TEST_DATABASE_URL).database.endswith("_test")


def test_test_database_is_not_the_app_database() -> None:
    """A dev DATABASE_URL is redirected, never used as-is."""
    app_db_name = make_url(settings.DATABASE_URL).database

    if app_db_name and app_db_name.endswith("_test"):
        # CI already points DATABASE_URL at a dedicated test database.
        return

    assert make_url(TEST_DATABASE_URL).database != app_db_name


def test_global_engine_points_at_test_database() -> None:
    """Sessions opened outside a request also land on the test database.

    Event handlers and background tasks use ``async_session_maker`` directly,
    bypassing the ``get_db`` override. If this regresses, those writes go to
    the real ``DATABASE_URL`` while assertions read the test database — which
    is how 14 patient_timeline tests started failing once the two databases
    stopped being the same one.
    """
    expected = make_url(TEST_DATABASE_URL).database

    assert app_database.engine.url.database == expected
    assert app_database.async_session_maker().bind.url.database == expected
