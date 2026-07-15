import pytest
import os
import config

@pytest.fixture(autouse=True)
def isolate_filesystem_during_tests(tmp_path, monkeypatch):
    """Globally redirects all config path variables to a safe temporary test directory.
    This guarantees that unit tests never write to or pollute the production directories.
    """
    test_target = os.path.join(tmp_path, "test_archive")
    test_source = os.path.join(tmp_path, "test_inbox")
    os.makedirs(test_target, exist_ok=True)
    os.makedirs(test_source, exist_ok=True)

    # Monkeypatch central config paths
    monkeypatch.setattr(config, "TARGET_BASE", test_target)
    monkeypatch.setattr(config, "SOURCE_DIR", test_source)
    monkeypatch.setattr(config, "DUPLICATES_DIR", os.path.join(test_target, "duplicates"))
    monkeypatch.setattr(config, "FAILED_DIR", os.path.join(test_target, "failed"))
    monkeypatch.setattr(config, "ENCRYPTED_DIR", os.path.join(test_target, "encrypted"))
    monkeypatch.setattr(config, "REVIEW_DIR", os.path.join(test_target, "review"))
    monkeypatch.setattr(config, "IGNORED_DIR", os.path.join(test_target, "ignored"))
    monkeypatch.setattr(config, "LOG_FILE", os.path.join(test_target, "processing_log.jsonl"))
    monkeypatch.setattr(config, "DB_PATH", os.path.join(test_target, "archive.db"))

    # Also update pipeline module if it imported them directly on module loading
    try:
        import pipeline.core as pipeline_core
        monkeypatch.setattr(pipeline_core, "FAILED_DIR", os.path.join(test_target, "failed"))
        monkeypatch.setattr(pipeline_core, "REVIEW_DIR", os.path.join(test_target, "review"))
    except Exception:
        pass

    yield
