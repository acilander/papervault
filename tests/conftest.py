import importlib
import os
import tempfile

# Force safe test directories in the environment before ANY modules are imported!
# This guarantees 100% isolation, even if other modules import 'SOURCE_DIR' directly at load-time.
_TEST_TEMP_DIR = tempfile.mkdtemp(prefix="papervault_test_")
_test_target = os.path.join(_TEST_TEMP_DIR, "test_archive")
_test_source = os.path.join(_TEST_TEMP_DIR, "test_inbox")
os.makedirs(_test_target, exist_ok=True)
os.makedirs(_test_source, exist_ok=True)

os.environ["SOURCE_DIR"] = _test_source
os.environ["TARGET_BASE"] = _test_target
os.environ["DB_PATH"] = os.path.join(_test_target, "archive.db")

import pytest
import config

@pytest.fixture(autouse=True)
def isolate_filesystem_during_tests(tmp_path, monkeypatch):
    """Globally redirects all config path variables to a safe temporary test directory.
    This guarantees that unit tests never write to or pollute the production directories.
    """
    # Monkeypatch central config paths to match the test env
    monkeypatch.setattr(config, "TARGET_BASE", _test_target)
    monkeypatch.setattr(config, "SOURCE_DIR", _test_source)
    monkeypatch.setattr(config, "DUPLICATES_DIR", os.path.join(_test_target, "duplicates"))
    monkeypatch.setattr(config, "FAILED_DIR", os.path.join(_test_target, "failed"))
    monkeypatch.setattr(config, "ENCRYPTED_DIR", os.path.join(_test_target, "encrypted"))
    monkeypatch.setattr(config, "REVIEW_DIR", os.path.join(_test_target, "review"))
    monkeypatch.setattr(config, "IGNORED_DIR", os.path.join(_test_target, "ignored"))
    monkeypatch.setattr(config, "LOG_FILE", os.path.join(_test_target, "processing_log.jsonl"))
    monkeypatch.setattr(config, "DB_PATH", os.path.join(_test_target, "archive.db"))

    # Also update pipeline module if it imported them directly on module loading
    try:
        import pipeline.core as pipeline_core
        monkeypatch.setattr(pipeline_core, "FAILED_DIR", os.path.join(_test_target, "failed"))
        monkeypatch.setattr(pipeline_core, "REVIEW_DIR", os.path.join(_test_target, "review"))
    except Exception:
        pass

    module_paths = {
        "storage": {"LOG_FILE": os.path.join(_test_target, "processing_log.jsonl")},
        "pipeline.steps": {
            "DUPLICATES_DIR": os.path.join(_test_target, "duplicates"),
            "IGNORED_DIR": os.path.join(_test_target, "ignored"),
        },
        "services.import_service": {"SOURCE_DIR": _test_source},
        "pdf_utils": {"TARGET_BASE": _test_target},
        "pdf_thumbnails": {
            "TARGET_BASE": _test_target,
            "THUMBNAILS_DIR": os.path.join(_test_target, "thumbnails"),
        },
        "api.routes.documents": {
            "SOURCE_DIR": _test_source,
            "TARGET_BASE": _test_target,
        },
        "api.routes.senders": {
            "SOURCE_DIR": _test_source,
            "TARGET_BASE": _test_target,
        },
        "api.routes.monitor": {
            "SOURCE_DIR": _test_source,
            "TARGET_BASE": _test_target,
            "LOG_FILE": os.path.join(_test_target, "processing_log.jsonl"),
        },
    }
    for module_name, values in module_paths.items():
        try:
            module = importlib.import_module(module_name)
            for attribute, value in values.items():
                monkeypatch.setattr(module, attribute, value)
        except Exception:
            pass

    yield
