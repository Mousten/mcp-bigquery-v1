"""BigQuery client initialization and management."""
import sys
from google.cloud import bigquery
from google.oauth2 import service_account
from ..config.settings import ServerConfig


def init_bigquery_client(config: ServerConfig) -> bigquery.Client:
    """Initialize BigQuery client with the provided configuration.
    
    Args:
        config: Server configuration containing project_id and optional key_file
        
    Returns:
        Initialized BigQuery client
        
    Raises:
        SystemExit: If client initialization fails
    """
    try:
        if config.key_file:
            credentials = service_account.Credentials.from_service_account_file(
                config.key_file
            )
            return bigquery.Client(project=config.project_id, credentials=credentials)
        else:
            return bigquery.Client(project=config.project_id)
    except Exception as e:
        print(f"Failed to initialize BigQuery client: {e}")
        sys.exit(1)