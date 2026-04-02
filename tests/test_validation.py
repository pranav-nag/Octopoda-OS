"""
Tests for API input validation — the production safety net.
Proves: empty keys rejected, oversized values rejected, field limits enforced.
"""

import pytest
from pydantic import ValidationError


class TestRememberValidation:
    """RememberRequest model validation."""

    def test_valid_request(self):
        from synrix_runtime.api.cloud_models import RememberRequest
        req = RememberRequest(key="test_key", value={"data": 42})
        assert req.key == "test_key"

    def test_empty_key_rejected(self):
        from synrix_runtime.api.cloud_models import RememberRequest
        with pytest.raises(ValidationError):
            RememberRequest(key="", value="test")

    def test_blank_key_rejected(self):
        from synrix_runtime.api.cloud_models import RememberRequest
        with pytest.raises(ValidationError):
            RememberRequest(key="   ", value="test")

    def test_oversized_key_rejected(self):
        from synrix_runtime.api.cloud_models import RememberRequest
        with pytest.raises(ValidationError):
            RememberRequest(key="x" * 600, value="test")

    def test_oversized_value_rejected(self):
        from synrix_runtime.api.cloud_models import RememberRequest
        huge_value = "x" * (2 * 1024 * 1024)  # 2MB string
        with pytest.raises(ValidationError):
            RememberRequest(key="test", value=huge_value)

    def test_normal_value_accepted(self):
        from synrix_runtime.api.cloud_models import RememberRequest
        req = RememberRequest(key="k", value={"nested": {"data": [1, 2, 3]}})
        assert req.value["nested"]["data"] == [1, 2, 3]


class TestBatchValidation:
    """BatchRememberRequest validation."""

    def test_valid_batch(self):
        from synrix_runtime.api.cloud_models import BatchRememberRequest, RememberRequest
        items = [RememberRequest(key=f"k{i}", value=i) for i in range(10)]
        req = BatchRememberRequest(items=items)
        assert len(req.items) == 10

    def test_empty_batch_rejected(self):
        from synrix_runtime.api.cloud_models import BatchRememberRequest
        with pytest.raises(ValidationError):
            BatchRememberRequest(items=[])


class TestRawWriteValidation:
    """RawWriteRequest validation."""

    def test_empty_key_rejected(self):
        from synrix_runtime.api.cloud_models import RawWriteRequest
        with pytest.raises(ValidationError):
            RawWriteRequest(key="", value="test")

    def test_oversized_value_rejected(self):
        from synrix_runtime.api.cloud_models import RawWriteRequest
        with pytest.raises(ValidationError):
            RawWriteRequest(key="k", value="x" * (2 * 1024 * 1024))
