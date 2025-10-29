"""Utility functions for the Streamlit app."""
import json
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone
import pandas as pd

logger = logging.getLogger(__name__)


def format_timestamp(timestamp_str: str) -> str:
    """Format timestamp for display.
    
    Args:
        timestamp_str: ISO format timestamp string
        
    Returns:
        Formatted timestamp string
    """
    try:
        dt = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
        return dt.strftime("%b %d, %Y %I:%M %p")
    except Exception:
        return timestamp_str


def format_token_count(count: int) -> str:
    """Format token count for display.
    
    Args:
        count: Token count
        
    Returns:
        Formatted token count string
    """
    if count >= 1_000_000:
        return f"{count / 1_000_000:.1f}M"
    elif count >= 1_000:
        return f"{count / 1_000:.1f}K"
    else:
        return str(count)


def convert_bigquery_results_to_dataframe(results: Dict[str, Any]) -> pd.DataFrame:
    """Convert BigQuery results to pandas DataFrame.
    
    Args:
        results: BigQuery results dictionary
        
    Returns:
        pandas DataFrame
    """
    if not results or "rows" not in results:
        return pd.DataFrame()
    
    rows = results["rows"]
    if not rows:
        return pd.DataFrame()
    
    # Convert to DataFrame
    df = pd.DataFrame(rows)
    
    # Try to infer types from schema if available
    if "schema" in results:
        schema = results["schema"]
        for field in schema:
            col_name = field.get("name")
            col_type = field.get("type", "").upper()
            
            if col_name in df.columns:
                try:
                    if col_type in ["INTEGER", "INT64"]:
                        df[col_name] = pd.to_numeric(df[col_name], errors='coerce').astype('Int64')
                    elif col_type in ["FLOAT", "FLOAT64", "NUMERIC", "BIGNUMERIC"]:
                        df[col_name] = pd.to_numeric(df[col_name], errors='coerce')
                    elif col_type in ["BOOL", "BOOLEAN"]:
                        df[col_name] = df[col_name].astype(bool)
                    elif col_type in ["DATE", "DATETIME", "TIMESTAMP"]:
                        df[col_name] = pd.to_datetime(df[col_name], errors='coerce')
                except Exception as e:
                    logger.warning(f"Failed to convert column {col_name} to {col_type}: {e}")
    
    return df


def extract_numeric_columns(df: pd.DataFrame) -> List[str]:
    """Extract numeric column names from DataFrame.
    
    Args:
        df: pandas DataFrame
        
    Returns:
        List of numeric column names
    """
    return df.select_dtypes(include=['number']).columns.tolist()


def extract_categorical_columns(df: pd.DataFrame) -> List[str]:
    """Extract categorical column names from DataFrame.
    
    Args:
        df: pandas DataFrame
        
    Returns:
        List of categorical column names
    """
    return df.select_dtypes(include=['object', 'category', 'string']).columns.tolist()


def extract_datetime_columns(df: pd.DataFrame) -> List[str]:
    """Extract datetime column names from DataFrame.
    
    Args:
        df: pandas DataFrame
        
    Returns:
        List of datetime column names
    """
    return df.select_dtypes(include=['datetime', 'datetime64']).columns.tolist()


def truncate_text(text: str, max_length: int = 100) -> str:
    """Truncate text to maximum length.
    
    Args:
        text: Text to truncate
        max_length: Maximum length
        
    Returns:
        Truncated text
    """
    if len(text) <= max_length:
        return text
    return text[:max_length] + "..."


def format_sql_query(sql: str) -> str:
    """Format SQL query for display.
    
    Args:
        sql: SQL query string
        
    Returns:
        Formatted SQL query
    """
    # Basic formatting - could be enhanced with sqlparse
    keywords = [
        'SELECT', 'FROM', 'WHERE', 'GROUP BY', 'ORDER BY', 'HAVING',
        'JOIN', 'LEFT JOIN', 'RIGHT JOIN', 'INNER JOIN', 'OUTER JOIN',
        'LIMIT', 'OFFSET', 'AS', 'ON', 'AND', 'OR', 'NOT', 'IN',
        'DISTINCT', 'COUNT', 'SUM', 'AVG', 'MIN', 'MAX'
    ]
    
    formatted = sql
    for keyword in keywords:
        formatted = formatted.replace(f' {keyword} ', f'\n{keyword} ')
        formatted = formatted.replace(f' {keyword.lower()} ', f'\n{keyword} ')
    
    return formatted.strip()


def safe_json_loads(json_str: str, default: Any = None) -> Any:
    """Safely parse JSON string.
    
    Args:
        json_str: JSON string
        default: Default value if parsing fails
        
    Returns:
        Parsed JSON or default value
    """
    try:
        return json.loads(json_str)
    except Exception:
        return default


def get_chart_type_icon(chart_type: str) -> str:
    """Get icon for chart type.
    
    Args:
        chart_type: Chart type
        
    Returns:
        Emoji icon
    """
    icons = {
        "bar": "📊",
        "line": "📈",
        "pie": "🥧",
        "scatter": "🔵",
        "area": "📉",
        "table": "📋",
        "metric": "🔢",
        "map": "🗺️",
        "heatmap": "🌡️",
        "histogram": "📊"
    }
    return icons.get(chart_type.lower(), "📊")


def calculate_summary_stats(df: pd.DataFrame) -> Dict[str, Any]:
    """Calculate summary statistics for DataFrame.
    
    Args:
        df: pandas DataFrame
        
    Returns:
        Dictionary of summary statistics
    """
    stats = {
        "total_rows": len(df),
        "total_columns": len(df.columns),
        "numeric_columns": len(extract_numeric_columns(df)),
        "categorical_columns": len(extract_categorical_columns(df)),
        "datetime_columns": len(extract_datetime_columns(df)),
        "memory_usage_mb": df.memory_usage(deep=True).sum() / 1024 / 1024
    }
    
    # Add basic stats for numeric columns
    numeric_cols = extract_numeric_columns(df)
    if numeric_cols:
        stats["numeric_summary"] = df[numeric_cols].describe().to_dict()
    
    return stats


def format_error_message(error: str, error_type: Optional[str] = None) -> str:
    """Format error message for display.
    
    Args:
        error: Error message
        error_type: Error type
        
    Returns:
        Formatted error message
    """
    error_icons = {
        "authentication": "🔒",
        "authorization": "⛔",
        "validation": "❌",
        "execution": "💥",
        "llm": "🤖",
        "network": "🌐",
        "rate_limit": "⏱️",
        "unknown": "❓"
    }
    
    icon = error_icons.get(error_type or "unknown", "❌")
    return f"{icon} {error}"


def create_download_link(df: pd.DataFrame, filename: str = "data.csv") -> str:
    """Create a download link for DataFrame.
    
    Args:
        df: pandas DataFrame
        filename: Filename for download
        
    Returns:
        CSV string
    """
    return df.to_csv(index=False)
