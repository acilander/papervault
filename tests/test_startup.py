import asyncio
import os
import shutil
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

import config


@pytest.fixture(autouse=True)
def in_memory_db(monkeypatch, tmp_path):
    """Redirect DB_PATH and SOURCE_DIR to temp paths for each test."""
    test_db = str(tmp_path / "test.db")
    monkeypatch.setattr("db.DB_PATH", test_db)
    import db
    db.DB_PATH = test_db
    db.init_db()

    source_dir = str(tmp_path / "Inbox")
    target_dir = str(tmp_path / "Archive")
    os.makedirs(source_dir, exist_ok=True)
    os.makedirs(target_dir, exist_ok=True)

    monkeypatch.setattr(config, "SOURCE_DIR", source_dir)
    monkeypatch.setattr(config, "TARGET_BASE", target_dir)

    yield tmp_path


def test_api_lifespan_creates_source_dir(in_memory_db):
    """Verify that the API lifespan context manager creates SOURCE_DIR if missing."""
    import api.main as main_module
    import shutil

    if os.path.isdir(config.SOURCE_DIR):
        shutil.rmtree(config.SOURCE_DIR)
    assert not os.path.exists(config.SOURCE_DIR)

    async def run_lifespan():
        async with main_module.lifespan(main_module.app):
            assert os.path.isdir(config.SOURCE_DIR)

    asyncio.run(run_lifespan())
    assert os.path.isdir(config.SOURCE_DIR)
