"""Shared test fixtures for AgentTracer backend tests.

Inspired by old/backend/tests/conftest.py but adapted for the single-file
SQLite implementation.
"""

from pathlib import Path

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from agent_tracer.main import app

# Use a test database to avoid interfering with development data
TEST_DB_DIR = Path(__file__).parent.parent / "data" / "test"


@pytest_asyncio.fixture(scope="function")
async def client() -> AsyncClient:
    """Create test HTTP client with the FastAPI app.

    Each test gets a fresh client. The app uses in-memory SQLite
    so data doesn't persist between tests.
    """
    # Override the DB path to use test directory
    import agent_tracer.main as main_module

    # Store original DB_PATH and set test path
    original_db_path = main_module.DB_PATH
    TEST_DB_DIR.mkdir(parents=True, exist_ok=True)
    main_module.DB_PATH = TEST_DB_DIR / "test_agent_tracer.db"

    # Re-initialize DB for each test
    main_module.init_db()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

    # Restore original DB path
    main_module.DB_PATH = original_db_path

    # Cleanup test database
    if TEST_DB_DIR.exists():
        for f in TEST_DB_DIR.glob("test_*.db*"):
            try:
                f.unlink()
            except Exception:
                pass


@pytest.fixture
def anyio_backend():
    """Configure anyio to use asyncio for async tests."""
    return "asyncio"
