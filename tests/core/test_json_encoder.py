"""Tests for CustomJSONEncoder."""
import json
from datetime import datetime, date, time, timedelta, timezone
from unittest.mock import MagicMock

import pytest

from mcp_bigquery.core.json_encoder import CustomJSONEncoder


class TestCustomJSONEncoder:
    """Tests for CustomJSONEncoder."""

    def test_encode_datetime(self):
        """Test encoding datetime objects."""
        dt = datetime(2025, 1, 15, 10, 30, 45, tzinfo=timezone.utc)
        result = json.dumps({"timestamp": dt}, cls=CustomJSONEncoder)
        assert "2025-01-15T10:30:45+00:00" in result

    def test_encode_date(self):
        """Test encoding date objects."""
        d = date(2025, 1, 15)
        result = json.dumps({"date": d}, cls=CustomJSONEncoder)
        assert "2025-01-15" in result

    def test_encode_time(self):
        """Test encoding time objects."""
        t = time(10, 30, 45)
        result = json.dumps({"time": t}, cls=CustomJSONEncoder)
        assert "10:30:45" in result

    def test_encode_timedelta(self):
        """Test encoding timedelta objects."""
        td = timedelta(days=1, hours=2, minutes=3)
        result = json.dumps({"duration": td}, cls=CustomJSONEncoder)
        assert "1 day, 2:03:00" in result

    def test_encode_mock_object(self):
        """Test encoding Mock objects returns None."""
        mock = MagicMock()
        result = json.dumps({"mock": mock}, cls=CustomJSONEncoder)
        assert result == '{"mock": null}'

    def test_encode_mock_in_nested_structure(self):
        """Test encoding Mock objects in nested structures."""
        data = {
            "query_id": "test-123",
            "statistics": {
                "totalBytesProcessed": 1000,
                "totalRows": MagicMock(),  # This would happen with getattr(mock, "attr", None)
                "duration_ms": 42.5
            }
        }
        result = json.dumps(data, cls=CustomJSONEncoder)
        parsed = json.loads(result)
        assert parsed["statistics"]["totalRows"] is None
        assert parsed["statistics"]["totalBytesProcessed"] == 1000

    def test_encode_object_with_to_dict(self):
        """Test encoding objects with to_dict method."""
        class CustomObject:
            def to_dict(self):
                return {"id": 123, "name": "test"}

        obj = CustomObject()
        result = json.dumps({"obj": obj}, cls=CustomJSONEncoder)
        parsed = json.loads(result)
        assert parsed["obj"]["id"] == 123
        assert parsed["obj"]["name"] == "test"

    def test_encode_object_with_invalid_to_dict(self):
        """Test encoding objects with to_dict that doesn't return dict."""
        class InvalidObject:
            def to_dict(self):
                return "not a dict"

        obj = InvalidObject()
        with pytest.raises(TypeError):
            json.dumps({"obj": obj}, cls=CustomJSONEncoder)

    def test_encode_object_with_recursive_to_dict(self):
        """Test encoding objects with recursive to_dict doesn't cause infinite loop."""
        class RecursiveObject:
            def to_dict(self):
                return self  # Returns itself - would cause recursion

        obj = RecursiveObject()
        with pytest.raises(TypeError):
            json.dumps({"obj": obj}, cls=CustomJSONEncoder)

    def test_encode_mixed_types(self):
        """Test encoding a complex structure with multiple types."""
        data = {
            "timestamp": datetime(2025, 1, 15, 10, 30, 45, tzinfo=timezone.utc),
            "date": date(2025, 1, 15),
            "duration": timedelta(hours=2),
            "mock_value": MagicMock(),
            "normal_value": "test",
            "number": 42
        }
        result = json.dumps(data, cls=CustomJSONEncoder)
        parsed = json.loads(result)
        
        assert "2025-01-15T10:30:45+00:00" in parsed["timestamp"]
        assert parsed["date"] == "2025-01-15"
        assert "2:00:00" in parsed["duration"]
        assert parsed["mock_value"] is None
        assert parsed["normal_value"] == "test"
        assert parsed["number"] == 42

    def test_encode_list_with_mocks(self):
        """Test encoding lists containing Mock objects."""
        data = [1, 2, MagicMock(), 4, MagicMock()]
        result = json.dumps(data, cls=CustomJSONEncoder)
        parsed = json.loads(result)
        assert parsed == [1, 2, None, 4, None]

    def test_bigquery_result_structure(self):
        """Test encoding structure similar to BigQuery results."""
        mock_job = MagicMock()
        mock_job.job_id = "test-job-id"
        mock_job.total_bytes_processed = 1000
        mock_job.started = datetime(2025, 1, 15, 10, 0, 0, tzinfo=timezone.utc)
        mock_job.ended = datetime(2025, 1, 15, 10, 0, 5, tzinfo=timezone.utc)
        
        # This simulates what happens in the handler
        statistics = {
            "totalBytesProcessed": mock_job.total_bytes_processed,
            "totalRows": getattr(mock_job, "total_rows", None),  # Returns MagicMock
            "duration_ms": (
                (mock_job.ended - mock_job.started).total_seconds() * 1000
            ),
            "started": mock_job.started.isoformat(),
            "ended": mock_job.ended.isoformat(),
        }
        
        result = json.dumps(statistics, cls=CustomJSONEncoder)
        parsed = json.loads(result)
        
        assert parsed["totalBytesProcessed"] == 1000
        assert parsed["totalRows"] is None  # Mock converted to None
        assert parsed["duration_ms"] == 5000.0
        assert "2025-01-15T10:00:00+00:00" in parsed["started"]
        assert "2025-01-15T10:00:05+00:00" in parsed["ended"]
