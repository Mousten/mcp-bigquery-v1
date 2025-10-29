"""Query result summarization utilities for LLM consumption.

This module provides utilities to summarize large BigQuery result sets
into compact representations suitable for LLM processing, including
descriptive statistics, aggregations, and text summaries.
"""

import logging
from typing import Any, Dict, List, Optional, Set, Union
from collections import Counter

import pandas as pd
from pydantic import BaseModel, Field


logger = logging.getLogger(__name__)


class ColumnStatistics(BaseModel):
    """Statistics for a single column."""
    name: str
    data_type: str
    count: int
    null_count: int
    null_percentage: float
    unique_count: Optional[int] = None
    
    # Numeric statistics
    min: Optional[float] = None
    max: Optional[float] = None
    mean: Optional[float] = None
    median: Optional[float] = None
    std: Optional[float] = None
    percentile_25: Optional[float] = None
    percentile_75: Optional[float] = None
    
    # Categorical statistics
    most_common: List[Dict[str, Any]] = Field(default_factory=list)
    sample_values: List[Any] = Field(default_factory=list)


class DataSummary(BaseModel):
    """Summary of query results."""
    total_rows: int
    total_columns: int
    sampled_rows: int
    columns: List[ColumnStatistics] = Field(default_factory=list)
    key_insights: List[str] = Field(default_factory=list)
    visualization_suggestions: List[Dict[str, Any]] = Field(default_factory=list)
    
    
class ResultSummarizer:
    """Utility class for summarizing BigQuery query results.
    
    This class provides methods to:
    - Limit result rows for token budget management
    - Compute descriptive statistics for numeric and categorical columns
    - Generate high-level text summaries
    - Produce visualization-ready aggregates
    
    Args:
        max_rows: Maximum number of rows to include in summary (default: 100)
        max_categories: Maximum number of categories to show for categorical columns (default: 10)
        include_samples: Whether to include sample values (default: True)
        
    Example:
        >>> summarizer = ResultSummarizer(max_rows=50)
        >>> summary = summarizer.summarize(query_results)
        >>> print(summary.key_insights)
    """
    
    def __init__(
        self,
        max_rows: int = 100,
        max_categories: int = 10,
        include_samples: bool = True,
    ):
        self.max_rows = max_rows
        self.max_categories = max_categories
        self.include_samples = include_samples
        
    def summarize(self, rows: List[Dict[str, Any]]) -> DataSummary:
        """Generate a comprehensive summary of query results.
        
        Args:
            rows: List of result rows as dictionaries
            
        Returns:
            DataSummary with statistics and insights
        """
        if not rows:
            return DataSummary(
                total_rows=0,
                total_columns=0,
                sampled_rows=0,
                key_insights=["No data returned"],
            )
            
        # Convert to DataFrame for easier analysis
        df = pd.DataFrame(rows)
        total_rows = len(df)
        
        # Sample if needed
        sampled_df = df if total_rows <= self.max_rows else df.sample(n=self.max_rows, random_state=42)
        
        # Compute column statistics
        columns = []
        for col in df.columns:
            col_stats = self._compute_column_statistics(df, col, sampled_df)
            columns.append(col_stats)
            
        # Generate insights
        insights = self._generate_insights(df, columns)
        
        # Generate visualization suggestions
        viz_suggestions = self._generate_visualization_suggestions(df, columns)
        
        return DataSummary(
            total_rows=total_rows,
            total_columns=len(df.columns),
            sampled_rows=len(sampled_df),
            columns=columns,
            key_insights=insights,
            visualization_suggestions=viz_suggestions,
        )
        
    def limit_rows(self, rows: List[Dict[str, Any]], max_rows: Optional[int] = None) -> List[Dict[str, Any]]:
        """Limit the number of rows to a maximum.
        
        Args:
            rows: List of result rows
            max_rows: Maximum number of rows (uses instance default if not provided)
            
        Returns:
            Limited list of rows
        """
        limit = max_rows if max_rows is not None else self.max_rows
        return rows[:limit]
        
    def create_aggregate_summary(
        self,
        rows: List[Dict[str, Any]],
        group_by: Optional[str] = None,
        numeric_cols: Optional[List[str]] = None,
    ) -> List[Dict[str, Any]]:
        """Create an aggregate summary for visualization.
        
        Args:
            rows: List of result rows
            group_by: Optional column to group by
            numeric_cols: Optional list of numeric columns to aggregate
            
        Returns:
            List of aggregated rows suitable for visualization
        """
        if not rows:
            return []
            
        df = pd.DataFrame(rows)
        
        if group_by and group_by in df.columns:
            # Group and aggregate
            if numeric_cols:
                agg_cols = [col for col in numeric_cols if col in df.columns]
            else:
                agg_cols = df.select_dtypes(include=['number']).columns.tolist()
                
            if agg_cols:
                grouped = df.groupby(group_by)[agg_cols].agg(['sum', 'mean', 'count'])
                result = grouped.reset_index().to_dict(orient='records')
                return result[:self.max_categories]
            else:
                # Just count by group
                counts = df[group_by].value_counts().head(self.max_categories)
                return [{"category": k, "count": v} for k, v in counts.items()]
        else:
            # Return limited rows
            return self.limit_rows(rows)
            
    def format_summary_text(self, summary: DataSummary) -> str:
        """Format a DataSummary as human-readable text.
        
        Args:
            summary: DataSummary to format
            
        Returns:
            Formatted text summary
        """
        lines = []
        lines.append(f"# Query Result Summary")
        lines.append(f"")
        lines.append(f"**Total Rows:** {summary.total_rows:,}")
        lines.append(f"**Total Columns:** {summary.total_columns}")
        if summary.sampled_rows < summary.total_rows:
            lines.append(f"**Sampled Rows:** {summary.sampled_rows:,} (for analysis)")
        lines.append(f"")
        
        # Key insights
        if summary.key_insights:
            lines.append("## Key Insights")
            for insight in summary.key_insights:
                lines.append(f"- {insight}")
            lines.append("")
            
        # Column summaries
        lines.append("## Column Statistics")
        for col in summary.columns:
            lines.append(f"")
            lines.append(f"### {col.name} ({col.data_type})")
            lines.append(f"- **Non-null values:** {col.count:,} ({100 - col.null_percentage:.1f}%)")
            
            if col.unique_count:
                lines.append(f"- **Unique values:** {col.unique_count:,}")
                
            if col.mean is not None:
                lines.append(f"- **Mean:** {col.mean:.2f}")
                lines.append(f"- **Median:** {col.median:.2f}")
                lines.append(f"- **Std Dev:** {col.std:.2f}")
                lines.append(f"- **Range:** [{col.min:.2f}, {col.max:.2f}]")
                
            if col.most_common:
                lines.append(f"- **Most common values:**")
                for item in col.most_common[:5]:
                    lines.append(f"  - {item['value']}: {item['count']} occurrences")
                    
        # Visualization suggestions
        if summary.visualization_suggestions:
            lines.append("")
            lines.append("## Visualization Suggestions")
            for i, viz in enumerate(summary.visualization_suggestions, 1):
                lines.append(f"{i}. **{viz['type']}**: {viz['description']}")
                
        return "\n".join(lines)
        
    def _compute_column_statistics(
        self,
        df: pd.DataFrame,
        col: str,
        sampled_df: pd.DataFrame,
    ) -> ColumnStatistics:
        """Compute statistics for a single column.
        
        Args:
            df: Full DataFrame
            col: Column name
            sampled_df: Sampled DataFrame for expensive operations
            
        Returns:
            ColumnStatistics for the column
        """
        series = df[col]
        count = series.count()
        null_count = series.isna().sum()
        null_percentage = (null_count / len(series)) * 100 if len(series) > 0 else 0
        
        # Infer data type
        dtype = str(series.dtype)
        if pd.api.types.is_numeric_dtype(series):
            data_type = "numeric"
        elif pd.api.types.is_datetime64_any_dtype(series):
            data_type = "datetime"
        elif pd.api.types.is_bool_dtype(series):
            data_type = "boolean"
        else:
            data_type = "categorical"
            
        stats = ColumnStatistics(
            name=col,
            data_type=data_type,
            count=int(count),
            null_count=int(null_count),
            null_percentage=float(null_percentage),
        )
        
        # Unique count (use sampled for large datasets)
        try:
            stats.unique_count = int(sampled_df[col].nunique())
        except Exception:
            pass
            
        # Numeric statistics
        if data_type == "numeric":
            try:
                stats.min = float(series.min()) if not pd.isna(series.min()) else None
                stats.max = float(series.max()) if not pd.isna(series.max()) else None
                stats.mean = float(series.mean()) if not pd.isna(series.mean()) else None
                stats.median = float(series.median()) if not pd.isna(series.median()) else None
                stats.std = float(series.std()) if not pd.isna(series.std()) else None
                stats.percentile_25 = float(series.quantile(0.25)) if not pd.isna(series.quantile(0.25)) else None
                stats.percentile_75 = float(series.quantile(0.75)) if not pd.isna(series.quantile(0.75)) else None
            except Exception as e:
                logger.warning(f"Failed to compute numeric stats for {col}: {e}")
                
        # Categorical statistics
        if data_type in ("categorical", "boolean"):
            try:
                value_counts = sampled_df[col].value_counts()
                stats.most_common = [
                    {"value": str(val), "count": int(cnt)}
                    for val, cnt in value_counts.head(self.max_categories).items()
                ]
            except Exception as e:
                logger.warning(f"Failed to compute categorical stats for {col}: {e}")
                
        # Sample values
        if self.include_samples and data_type != "numeric":
            try:
                samples = sampled_df[col].dropna().head(5).tolist()
                stats.sample_values = [str(val) for val in samples]
            except Exception:
                pass
                
        return stats
        
    def _generate_insights(
        self,
        df: pd.DataFrame,
        columns: List[ColumnStatistics],
    ) -> List[str]:
        """Generate key insights from the data.
        
        Args:
            df: DataFrame with results
            columns: Column statistics
            
        Returns:
            List of insight strings
        """
        insights = []
        
        # Dataset size insight
        if len(df) > 10000:
            insights.append(f"Large dataset with {len(df):,} rows")
        elif len(df) == 0:
            insights.append("No data returned")
        else:
            insights.append(f"Dataset contains {len(df):,} rows")
            
        # Column count
        insights.append(f"Query returns {len(columns)} columns")
        
        # Null value insights
        high_null_cols = [col for col in columns if col.null_percentage > 50]
        if high_null_cols:
            insights.append(
                f"{len(high_null_cols)} column(s) with >50% null values: "
                f"{', '.join(c.name for c in high_null_cols[:3])}"
            )
            
        # Data type distribution
        type_counts = Counter(col.data_type for col in columns)
        type_summary = ", ".join(f"{count} {dtype}" for dtype, count in type_counts.most_common())
        insights.append(f"Column types: {type_summary}")
        
        # High cardinality insights
        high_cardinality = [col for col in columns if col.unique_count and col.unique_count > len(df) * 0.9]
        if high_cardinality:
            insights.append(
                f"{len(high_cardinality)} high-cardinality column(s): "
                f"{', '.join(c.name for c in high_cardinality[:3])}"
            )
            
        # Numeric range insights
        numeric_cols = [col for col in columns if col.data_type == "numeric" and col.min is not None]
        for col in numeric_cols[:3]:
            if col.std and col.mean and col.std / col.mean > 1.0:
                insights.append(f"{col.name} shows high variability (σ/μ > 1)")
                
        return insights
        
    def _generate_visualization_suggestions(
        self,
        df: pd.DataFrame,
        columns: List[ColumnStatistics],
    ) -> List[Dict[str, Any]]:
        """Generate visualization suggestions based on data characteristics.
        
        Args:
            df: DataFrame with results
            columns: Column statistics
            
        Returns:
            List of visualization suggestion dicts
        """
        suggestions = []
        
        numeric_cols = [col for col in columns if col.data_type == "numeric"]
        categorical_cols = [col for col in columns if col.data_type == "categorical" and col.unique_count and col.unique_count < 20]
        datetime_cols = [col for col in columns if col.data_type == "datetime"]
        
        # Time series
        if datetime_cols and numeric_cols:
            suggestions.append({
                "type": "line",
                "description": f"Time series of {numeric_cols[0].name} over {datetime_cols[0].name}",
                "x": datetime_cols[0].name,
                "y": numeric_cols[0].name,
            })
            
        # Bar chart for categorical + numeric
        if categorical_cols and numeric_cols:
            suggestions.append({
                "type": "bar",
                "description": f"Bar chart of {numeric_cols[0].name} by {categorical_cols[0].name}",
                "x": categorical_cols[0].name,
                "y": numeric_cols[0].name,
            })
            
        # Scatter for numeric pairs
        if len(numeric_cols) >= 2:
            suggestions.append({
                "type": "scatter",
                "description": f"Scatter plot of {numeric_cols[0].name} vs {numeric_cols[1].name}",
                "x": numeric_cols[0].name,
                "y": numeric_cols[1].name,
            })
            
        # Distribution for single numeric
        if len(numeric_cols) >= 1:
            suggestions.append({
                "type": "histogram",
                "description": f"Distribution of {numeric_cols[0].name}",
                "x": numeric_cols[0].name,
            })
            
        # Pie chart for categorical
        if categorical_cols:
            suggestions.append({
                "type": "pie",
                "description": f"Distribution of {categorical_cols[0].name}",
                "values": categorical_cols[0].name,
            })
            
        return suggestions[:3]
