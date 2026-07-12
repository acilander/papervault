import sys
import os
import pytest
from unittest.mock import MagicMock, patch
from PIL import Image

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))


@pytest.fixture(autouse=True)
def reset_vision_service():
    """Reset cached vision service between tests."""
    import vision
    vision._service = None
    yield
    vision._service = None


def make_test_image(tmp_path, color=(255, 255, 255)) -> str:
    """Create a minimal test PNG image."""
    img_path = str(tmp_path / "test_header.png")
    Image.new("RGB", (200, 80), color=color).save(img_path)
    return img_path


class TestAnalyzeLogo:
    def test_returns_string_for_valid_image(self, tmp_path):
        """analyze_logo returns a non-empty string for a valid image."""
        img_path = make_test_image(tmp_path)
        mock_model = MagicMock()
        mock_model.query.return_value = {"answer": "Sparkasse"}

        import vision
        service = vision.VisionService()
        service._model = mock_model
        vision._service = service
        result = vision.analyze_logo(img_path)

        assert isinstance(result, str)
        assert result == "Sparkasse"

    def test_strips_whitespace_from_answer(self, tmp_path):
        """analyze_logo strips leading/trailing whitespace from model answer."""
        img_path = make_test_image(tmp_path)
        mock_model = MagicMock()
        mock_model.query.return_value = {"answer": "  Deutsche Bank  "}

        import vision
        service = vision.VisionService()
        service._model = mock_model
        vision._service = service
        result = vision.analyze_logo(img_path)

        assert result == "Deutsche Bank"

    def test_returns_empty_string_when_model_returns_empty(self, tmp_path):
        """analyze_logo returns empty string when model finds nothing."""
        img_path = make_test_image(tmp_path)
        mock_model = MagicMock()
        mock_model.query.return_value = {"answer": "  "}

        import vision
        service = vision.VisionService()
        service._model = mock_model
        vision._service = service
        result = vision.analyze_logo(img_path)

        assert result == ""

    def test_load_skipped_when_already_cached(self):
        """VisionService._load does nothing if _model is already set (caching guard)."""
        import vision
        service = vision.VisionService()
        sentinel = MagicMock()
        service._model = sentinel

        with patch("torch.cuda.is_available", return_value=True), \
             patch("transformers.AutoModelForCausalLM.from_pretrained") as mock_from_pretrained, \
             patch("transformers.AutoTokenizer.from_pretrained") as mock_tokenizer:
            service._load()

        mock_from_pretrained.assert_not_called()
        mock_tokenizer.assert_not_called()
        assert service._model is sentinel

    def test_transformers_not_imported_at_module_level(self):
        """transformers must only be imported lazily inside VisionService._load, not at module top-level."""
        import vision
        import inspect
        source = inspect.getsource(vision)
        lines = source.splitlines()
        # Find module-level lines (before any class/def)
        top_level = []
        for line in lines:
            if line.startswith("def ") or line.startswith("class "):
                break
            top_level.append(line)
        top_level_src = "\n".join(top_level)
        assert "from transformers" not in top_level_src
        assert "import transformers" not in top_level_src

    def test_analyze_logo_raises_on_missing_file(self, tmp_path):
        """analyze_logo raises FileNotFoundError for non-existent image."""
        import vision
        mock_model = MagicMock()
        mock_model.query.return_value = {"answer": "test"}
        service = vision.VisionService()
        service._model = mock_model
        vision._service = service

        with pytest.raises(Exception):
            vision.analyze_logo(str(tmp_path / "nonexistent.png"))
