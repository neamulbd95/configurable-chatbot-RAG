from ragchatbot.config.settings import DatabaseSettings, Settings


def test_sqlalchemy_url_postgresql():
    db = DatabaseSettings(engine="postgresql", host="h", port=5432, user="u", password="p", database="d")
    assert db.sqlalchemy_url() == "postgresql+psycopg://u:p@h:5432/d"


def test_sqlalchemy_url_mysql():
    db = DatabaseSettings(engine="mysql", host="h", port=3306, user="u", password="p", database="d")
    assert db.sqlalchemy_url() == "mysql+pymysql://u:p@h:3306/d"


def test_sqlalchemy_url_driver_override():
    db = DatabaseSettings(
        engine="postgresql",
        host="h",
        port=5432,
        user="u",
        password="p",
        database="d",
        driver_override="postgresql+asyncpg",
    )
    assert db.sqlalchemy_url() == "postgresql+asyncpg://u:p@h:5432/d"


def test_settings_source_db_and_vector_db_are_independent():
    settings = Settings(
        source_db_engine="mysql",
        source_db_host="source-host",
        vector_db_host="vector-host",
    )

    source = settings.source_db()
    vector = settings.vector_db()

    assert source.engine == "mysql"
    assert source.host == "source-host"
    # Vector store is always postgresql regardless of the source engine.
    assert vector.engine == "postgresql"
    assert vector.host == "vector-host"
