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


def test_provider_and_engine_literals_tolerate_hyphens_and_case():
    # "azure-openai" is an easy env-var typo for "azure_openai" — should
    # normalize instead of raising a pydantic ValidationError at startup.
    settings = Settings(
        embedding_provider="azure-openai",
        chat_provider="AZURE-OpenAI",
        source_db_engine="PostgreSQL",
    )

    assert settings.embedding_provider == "azure_openai"
    assert settings.chat_provider == "azure_openai"
    assert settings.source_db_engine == "postgresql"


def test_database_settings_engine_tolerates_hyphens_and_case():
    db = DatabaseSettings(engine="MySQL")
    assert db.engine == "mysql"


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
