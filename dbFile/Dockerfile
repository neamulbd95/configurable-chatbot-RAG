# Source RDBMS for local development/testing: a plain PostgreSQL image
# pre-seeded with a sample products/orders schema (init.sql) matching
# config/tables.example.yaml, so ingestion has real data to pull from
# immediately — no manual data entry needed to try the pipeline end to end.
#
# This is a *source data fixture*, not the app's vector store — the vector
# store is a separate, independently-configured database per FR-1.7 (see
# the `vector-store` service in the root docker-compose.yml). In a real
# deployment this container is replaced by your actual production RDBMS;
# nothing about the app assumes this image.

FROM postgres:16

ENV POSTGRES_USER=postgres
ENV POSTGRES_PASSWORD=postgres
ENV POSTGRES_DB=app

COPY init.sql /docker-entrypoint-initdb.d/init.sql
