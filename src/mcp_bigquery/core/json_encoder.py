"""Custom JSON encoder to handle datetime objects and other non-serializable types."""
import json
import datetime


class CustomJSONEncoder(json.JSONEncoder):
    """Custom JSON encoder to handle datetime objects and other non-serializable types."""

    def default(self, o):
        if isinstance(o, (datetime.datetime, datetime.date, datetime.time)):
            return o.isoformat()
        elif isinstance(o, datetime.timedelta):
            return str(o)
        elif hasattr(o, "to_dict"):
            return o.to_dict()
        return super(CustomJSONEncoder, self).default(o)