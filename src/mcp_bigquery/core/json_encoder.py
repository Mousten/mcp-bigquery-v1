"""Custom JSON encoder to handle datetime objects and other non-serializable types."""
import json
import datetime
from unittest.mock import Mock


class CustomJSONEncoder(json.JSONEncoder):
    """Custom JSON encoder to handle datetime objects and other non-serializable types."""

    def default(self, o):
        # Handle Mock objects (for testing) - convert to None
        if isinstance(o, Mock):
            return None
        
        if isinstance(o, (datetime.datetime, datetime.date, datetime.time)):
            return o.isoformat()
        elif isinstance(o, datetime.timedelta):
            return str(o)
        elif hasattr(o, "to_dict") and callable(getattr(o, "to_dict", None)):
            try:
                result = o.to_dict()
                # Ensure to_dict() returns a dict and not the same object
                if isinstance(result, dict) and result is not o:
                    return result
            except (TypeError, AttributeError, RecursionError):
                pass
        return super(CustomJSONEncoder, self).default(o)