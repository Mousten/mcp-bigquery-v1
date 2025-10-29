"""Tests for query result summarizer."""

import pytest
from datetime import datetime, timezone

from mcp_bigquery.agent.summarizer import (
    ResultSummarizer,
    DataSummary,
    ColumnStatistics,
)


@pytest.fixture
def numeric_data():
    """Sample numeric dataset."""
    return [
        {"id": 1, "age": 25, "salary": 50000, "department": "Engineering"},
        {"id": 2, "age": 30, "salary": 60000, "department": "Engineering"},
        {"id": 3, "age": 35, "salary": 70000, "department": "Sales"},
        {"id": 4, "age": 28, "salary": 55000, "department": "Sales"},
        {"id": 5, "age": 42, "salary": 85000, "department": "Marketing"},
        {"id": 6, "age": None, "salary": 52000, "department": "Engineering"},
        {"id": 7, "age": 29, "salary": None, "department": "Marketing"},
    ]


@pytest.fixture
def categorical_data():
    """Sample categorical dataset."""
    return [
        {"country": "USA", "city": "New York", "status": "active"},
        {"country": "USA", "city": "San Francisco", "status": "active"},
        {"country": "UK", "city": "London", "status": "active"},
        {"country": "UK", "city": "Manchester", "status": "inactive"},
        {"country": "USA", "city": "Boston", "status": "active"},
        {"country": "Canada", "city": "Toronto", "status": "active"},
    ]


@pytest.fixture
def mixed_data():
    """Sample mixed dataset with various types."""
    return [
        {
            "timestamp": "2023-01-01T00:00:00Z",
            "value": 100,
            "category": "A",
            "is_valid": True,
        },
        {
            "timestamp": "2023-01-02T00:00:00Z",
            "value": 150,
            "category": "B",
            "is_valid": True,
        },
        {
            "timestamp": "2023-01-03T00:00:00Z",
            "value": 120,
            "category": "A",
            "is_valid": False,
        },
        {
            "timestamp": "2023-01-04T00:00:00Z",
            "value": 180,
            "category": "C",
            "is_valid": True,
        },
    ]


@pytest.fixture
def empty_data():
    """Empty dataset."""
    return []


class TestResultSummarizer:
    """Tests for ResultSummarizer class."""
    
    def test_initialization(self):
        """Test summarizer initialization."""
        summarizer = ResultSummarizer(max_rows=50, max_categories=5)
        assert summarizer.max_rows == 50
        assert summarizer.max_categories == 5
        assert summarizer.include_samples is True
        
    def test_summarize_numeric_data(self, numeric_data):
        """Test summarization of numeric data."""
        summarizer = ResultSummarizer()
        summary = summarizer.summarize(numeric_data)
        
        assert isinstance(summary, DataSummary)
        assert summary.total_rows == 7
        assert summary.total_columns == 4
        assert summary.sampled_rows == 7
        assert len(summary.columns) == 4
        
        # Check numeric columns
        age_col = next(c for c in summary.columns if c.name == "age")
        assert age_col.data_type == "numeric"
        assert age_col.count == 6  # One null value
        assert age_col.null_count == 1
        assert age_col.mean is not None
        assert age_col.median is not None
        assert age_col.std is not None
        assert age_col.min is not None
        assert age_col.max is not None
        
        salary_col = next(c for c in summary.columns if c.name == "salary")
        assert salary_col.data_type == "numeric"
        assert salary_col.count == 6  # One null value
        
    def test_summarize_categorical_data(self, categorical_data):
        """Test summarization of categorical data."""
        summarizer = ResultSummarizer()
        summary = summarizer.summarize(categorical_data)
        
        assert summary.total_rows == 6
        assert summary.total_columns == 3
        
        # Check categorical columns
        country_col = next(c for c in summary.columns if c.name == "country")
        assert country_col.data_type == "categorical"
        assert country_col.unique_count is not None
        assert len(country_col.most_common) > 0
        assert country_col.most_common[0]["value"] == "USA"
        assert country_col.most_common[0]["count"] == 3
        
        status_col = next(c for c in summary.columns if c.name == "status")
        assert status_col.data_type == "categorical"
        
    def test_summarize_mixed_data(self, mixed_data):
        """Test summarization of mixed data types."""
        summarizer = ResultSummarizer()
        summary = summarizer.summarize(mixed_data)
        
        assert summary.total_rows == 4
        assert summary.total_columns == 4
        
        # Check different data types
        value_col = next(c for c in summary.columns if c.name == "value")
        assert value_col.data_type == "numeric"
        
        category_col = next(c for c in summary.columns if c.name == "category")
        assert category_col.data_type == "categorical"
        
        is_valid_col = next(c for c in summary.columns if c.name == "is_valid")
        # Boolean columns may be detected as boolean or numeric depending on pandas version
        assert is_valid_col.data_type in ("boolean", "numeric")
        
    def test_summarize_empty_data(self, empty_data):
        """Test summarization of empty dataset."""
        summarizer = ResultSummarizer()
        summary = summarizer.summarize(empty_data)
        
        assert summary.total_rows == 0
        assert summary.total_columns == 0
        assert summary.sampled_rows == 0
        assert len(summary.columns) == 0
        assert "No data returned" in summary.key_insights
        
    def test_limit_rows(self, numeric_data):
        """Test limiting number of rows."""
        summarizer = ResultSummarizer(max_rows=3)
        limited = summarizer.limit_rows(numeric_data)
        
        assert len(limited) == 3
        assert limited == numeric_data[:3]
        
    def test_limit_rows_custom_max(self, numeric_data):
        """Test limiting rows with custom maximum."""
        summarizer = ResultSummarizer(max_rows=10)
        limited = summarizer.limit_rows(numeric_data, max_rows=2)
        
        assert len(limited) == 2
        
    def test_limit_rows_no_limit_needed(self, numeric_data):
        """Test limiting when dataset is smaller than limit."""
        summarizer = ResultSummarizer(max_rows=100)
        limited = summarizer.limit_rows(numeric_data)
        
        assert len(limited) == len(numeric_data)
        
    def test_sampling_large_dataset(self):
        """Test that large datasets are sampled."""
        # Create a large dataset
        large_data = [{"id": i, "value": i * 10} for i in range(200)]
        
        summarizer = ResultSummarizer(max_rows=50)
        summary = summarizer.summarize(large_data)
        
        assert summary.total_rows == 200
        assert summary.sampled_rows == 50
        
    def test_create_aggregate_summary_with_groupby(self, numeric_data):
        """Test creating aggregate summary with groupby."""
        summarizer = ResultSummarizer()
        agg = summarizer.create_aggregate_summary(
            numeric_data,
            group_by="department",
            numeric_cols=["salary"],
        )
        
        assert len(agg) <= summarizer.max_categories
        assert isinstance(agg, list)
        
    def test_create_aggregate_summary_without_groupby(self, numeric_data):
        """Test creating aggregate summary without groupby."""
        summarizer = ResultSummarizer(max_rows=3)
        agg = summarizer.create_aggregate_summary(numeric_data)
        
        assert len(agg) == 3
        assert agg == numeric_data[:3]
        
    def test_create_aggregate_summary_empty(self, empty_data):
        """Test aggregate summary with empty data."""
        summarizer = ResultSummarizer()
        agg = summarizer.create_aggregate_summary(empty_data)
        
        assert len(agg) == 0
        
    def test_format_summary_text(self, numeric_data):
        """Test formatting summary as text."""
        summarizer = ResultSummarizer()
        summary = summarizer.summarize(numeric_data)
        text = summarizer.format_summary_text(summary)
        
        assert "Query Result Summary" in text
        assert "Total Rows:" in text
        assert "Total Columns:" in text
        assert "Key Insights" in text
        assert "Column Statistics" in text
        
    def test_format_summary_text_with_sampling(self):
        """Test format with sampling indication."""
        large_data = [{"id": i, "value": i * 10} for i in range(200)]
        summarizer = ResultSummarizer(max_rows=50)
        summary = summarizer.summarize(large_data)
        text = summarizer.format_summary_text(summary)
        
        assert "Sampled Rows:" in text
        
    def test_key_insights_generation(self, numeric_data):
        """Test that key insights are generated."""
        summarizer = ResultSummarizer()
        summary = summarizer.summarize(numeric_data)
        
        assert len(summary.key_insights) > 0
        assert any("rows" in insight.lower() for insight in summary.key_insights)
        assert any("column" in insight.lower() for insight in summary.key_insights)
        
    def test_key_insights_null_values(self, numeric_data):
        """Test insights about null values."""
        # Create data with high null percentage
        data_with_nulls = [
            {"id": 1, "value": 100, "optional": None},
            {"id": 2, "value": 200, "optional": None},
            {"id": 3, "value": 300, "optional": "data"},
        ]
        
        summarizer = ResultSummarizer()
        summary = summarizer.summarize(data_with_nulls)
        
        # Should mention high null values
        null_insights = [i for i in summary.key_insights if "null" in i.lower()]
        assert len(null_insights) > 0
        
    def test_visualization_suggestions_numeric(self, numeric_data):
        """Test visualization suggestions for numeric data."""
        summarizer = ResultSummarizer()
        summary = summarizer.summarize(numeric_data)
        
        assert len(summary.visualization_suggestions) > 0
        
        # Should suggest appropriate charts for numeric data
        chart_types = [viz["type"] for viz in summary.visualization_suggestions]
        assert any(t in ["bar", "scatter", "histogram"] for t in chart_types)
        
    def test_visualization_suggestions_categorical(self, categorical_data):
        """Test visualization suggestions for categorical data."""
        summarizer = ResultSummarizer()
        summary = summarizer.summarize(categorical_data)
        
        assert len(summary.visualization_suggestions) > 0
        
    def test_visualization_suggestions_mixed(self, mixed_data):
        """Test visualization suggestions for mixed data."""
        summarizer = ResultSummarizer()
        summary = summarizer.summarize(mixed_data)
        
        assert len(summary.visualization_suggestions) > 0
        
    def test_column_statistics_null_percentage(self):
        """Test null percentage calculation."""
        data = [
            {"value": 1},
            {"value": None},
            {"value": 3},
            {"value": None},
        ]
        
        summarizer = ResultSummarizer()
        summary = summarizer.summarize(data)
        
        value_col = summary.columns[0]
        assert value_col.null_percentage == 50.0
        assert value_col.null_count == 2
        assert value_col.count == 2
        
    def test_column_statistics_unique_count(self, categorical_data):
        """Test unique count calculation."""
        summarizer = ResultSummarizer()
        summary = summarizer.summarize(categorical_data)
        
        country_col = next(c for c in summary.columns if c.name == "country")
        assert country_col.unique_count == 3  # USA, UK, Canada
        
        city_col = next(c for c in summary.columns if c.name == "city")
        assert city_col.unique_count == 6  # New York, San Francisco, London, Manchester, Boston, Toronto
        
    def test_column_statistics_percentiles(self, numeric_data):
        """Test percentile calculation for numeric columns."""
        summarizer = ResultSummarizer()
        summary = summarizer.summarize(numeric_data)
        
        age_col = next(c for c in summary.columns if c.name == "age")
        assert age_col.percentile_25 is not None
        assert age_col.percentile_75 is not None
        assert age_col.percentile_25 < age_col.percentile_75
        
    def test_column_statistics_most_common(self, categorical_data):
        """Test most common values for categorical columns."""
        summarizer = ResultSummarizer(max_categories=2)
        summary = summarizer.summarize(categorical_data)
        
        country_col = next(c for c in summary.columns if c.name == "country")
        assert len(country_col.most_common) <= 2
        assert country_col.most_common[0]["value"] == "USA"
        assert country_col.most_common[0]["count"] == 3
        
    def test_column_statistics_sample_values(self, categorical_data):
        """Test sample values for categorical columns."""
        summarizer = ResultSummarizer(include_samples=True)
        summary = summarizer.summarize(categorical_data)
        
        city_col = next(c for c in summary.columns if c.name == "city")
        assert len(city_col.sample_values) > 0
        assert all(isinstance(v, str) for v in city_col.sample_values)
        
    def test_column_statistics_no_samples(self, categorical_data):
        """Test that samples are excluded when disabled."""
        summarizer = ResultSummarizer(include_samples=False)
        summary = summarizer.summarize(categorical_data)
        
        city_col = next(c for c in summary.columns if c.name == "city")
        assert len(city_col.sample_values) == 0
        
    def test_high_cardinality_insight(self):
        """Test insight for high cardinality columns."""
        # Create data with high cardinality
        data = [{"id": i, "name": f"name_{i}"} for i in range(100)]
        
        summarizer = ResultSummarizer()
        summary = summarizer.summarize(data)
        
        # Should detect high cardinality
        high_card_insights = [i for i in summary.key_insights if "high-cardinality" in i.lower()]
        assert len(high_card_insights) > 0
        
    def test_data_type_distribution_insight(self, numeric_data):
        """Test insight about data type distribution."""
        summarizer = ResultSummarizer()
        summary = summarizer.summarize(numeric_data)
        
        # Should mention column types
        type_insights = [i for i in summary.key_insights if "Column types:" in i]
        assert len(type_insights) > 0
        
    def test_numeric_variability_insight(self):
        """Test insight about high variability in numeric columns."""
        # Create data with high variability
        data = [
            {"value": 1},
            {"value": 100},
            {"value": 5},
            {"value": 200},
            {"value": 10},
        ]
        
        summarizer = ResultSummarizer()
        summary = summarizer.summarize(data)
        
        # Should detect high variability
        var_insights = [i for i in summary.key_insights if "variability" in i.lower()]
        assert len(var_insights) > 0
        
    def test_aggregate_by_categorical_only(self, categorical_data):
        """Test aggregation when no numeric columns present."""
        summarizer = ResultSummarizer()
        agg = summarizer.create_aggregate_summary(
            categorical_data,
            group_by="country",
        )
        
        assert len(agg) > 0
        # Should return counts by category
        assert all("category" in item or "count" in item for item in agg)
