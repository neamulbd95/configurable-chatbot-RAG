import pytest

from ragchatbot.config.settings import DatabaseSettings
from ragchatbot.db.source_adapter import SourceDBError, build_engine, reflect_table


def test_reflect_table_wraps_connection_failure_with_identifying_prefix():
    # Unreachable port + short timeout: any failure here proves the wrapping
    # works, without needing a live database.
    db_settings = DatabaseSettings(
        engine="postgresql", host="localhost", port=58347, user="u", password="p", database="d"
    )
    engine = build_engine(db_settings, connect_timeout_seconds=1)

    with pytest.raises(SourceDBError, match="Source DB table lookup failed for 'products'"):
        reflect_table(engine, "products")


def test_reflect_table_error_message_includes_schema_when_set():
    db_settings = DatabaseSettings(
        engine="postgresql", host="localhost", port=58347, user="u", password="p", database="d"
    )
    engine = build_engine(db_settings, connect_timeout_seconds=1)

    with pytest.raises(SourceDBError, match="Source DB table lookup failed for 'esg.asset'"):
        reflect_table(engine, "asset", schema="esg")
