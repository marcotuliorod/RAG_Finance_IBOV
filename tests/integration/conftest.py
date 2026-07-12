import os

import psycopg
import pytest

TEST_DATABASE_URL = os.environ.get(
    "TEST_DATABASE_URL", "postgresql://postgres:localdev@localhost:5433/postgres"
)


@pytest.fixture
def conn():
    connection = psycopg.connect(TEST_DATABASE_URL)
    try:
        yield connection
    finally:
        connection.rollback()
        connection.close()
