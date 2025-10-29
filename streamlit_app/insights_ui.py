"""Insights rendering UI for tabular results and visualizations."""
import streamlit as st
import pandas as pd
from typing import Dict, Any, List, Optional
import plotly.express as px
import plotly.graph_objects as go
from .utils import (
    convert_bigquery_results_to_dataframe,
    extract_numeric_columns,
    extract_categorical_columns,
    extract_datetime_columns,
    calculate_summary_stats,
    get_chart_type_icon,
    create_download_link
)


def render_query_results(results: Dict[str, Any]) -> None:
    """Render query results with tables and statistics.
    
    Args:
        results: BigQuery results dictionary
    """
    if not results or "rows" not in results:
        st.info("No results to display")
        return
    
    # Convert to DataFrame
    df = convert_bigquery_results_to_dataframe(results)
    
    if df.empty:
        st.info("Query returned no rows")
        return
    
    # Show summary stats
    stats = calculate_summary_stats(df)
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("Total Rows", f"{stats['total_rows']:,}")
    with col2:
        st.metric("Columns", stats['total_columns'])
    with col3:
        st.metric("Numeric Cols", stats['numeric_columns'])
    with col4:
        st.metric("Size", f"{stats['memory_usage_mb']:.2f} MB")
    
    # Show dataframe
    st.subheader("📋 Results Table")
    st.dataframe(df, use_container_width=True, height=400)
    
    # Download button
    csv = create_download_link(df)
    st.download_button(
        label="⬇️ Download CSV",
        data=csv,
        file_name="query_results.csv",
        mime="text/csv",
        use_container_width=True
    )


def render_chart_suggestions(
    suggestions: List[Dict[str, Any]],
    results: Dict[str, Any]
) -> None:
    """Render chart suggestions and allow users to visualize data.
    
    Args:
        suggestions: List of chart suggestions
        results: BigQuery results for plotting
    """
    if not suggestions:
        return
    
    st.subheader("📊 Suggested Visualizations")
    
    # Convert results to DataFrame
    df = convert_bigquery_results_to_dataframe(results)
    
    if df.empty:
        st.info("No data available for visualization")
        return
    
    # Create tabs for each suggestion
    if len(suggestions) == 1:
        # Single suggestion - no tabs
        suggestion = suggestions[0]
        render_single_chart(suggestion, df)
    else:
        # Multiple suggestions - use tabs
        tabs = st.tabs([
            f"{get_chart_type_icon(s['chart_type'])} {s['title']}"
            for s in suggestions
        ])
        
        for tab, suggestion in zip(tabs, suggestions):
            with tab:
                render_single_chart(suggestion, df)


def render_single_chart(suggestion: Dict[str, Any], df: pd.DataFrame) -> None:
    """Render a single chart based on suggestion.
    
    Args:
        suggestion: Chart suggestion
        df: DataFrame with data
    """
    chart_type = suggestion.get("chart_type", "").lower()
    title = suggestion.get("title", "Chart")
    description = suggestion.get("description", "")
    x_column = suggestion.get("x_column")
    y_columns = suggestion.get("y_columns", [])
    config = suggestion.get("config", {})
    
    # Show description
    if description:
        st.markdown(f"*{description}*")
    
    try:
        if chart_type == "bar":
            render_bar_chart(df, x_column, y_columns, title, config)
        elif chart_type == "line":
            render_line_chart(df, x_column, y_columns, title, config)
        elif chart_type == "pie":
            render_pie_chart(df, x_column, y_columns[0] if y_columns else None, title, config)
        elif chart_type == "scatter":
            render_scatter_chart(df, x_column, y_columns, title, config)
        elif chart_type == "area":
            render_area_chart(df, x_column, y_columns, title, config)
        elif chart_type == "metric":
            render_metric(df, y_columns, config)
        elif chart_type == "table":
            render_table(df, config)
        else:
            st.warning(f"Chart type '{chart_type}' not yet supported")
    except Exception as e:
        st.error(f"Failed to render chart: {str(e)}")


def render_bar_chart(
    df: pd.DataFrame,
    x_column: Optional[str],
    y_columns: List[str],
    title: str,
    config: Dict[str, Any]
) -> None:
    """Render a bar chart."""
    if not x_column or not y_columns:
        st.warning("Missing column specifications for bar chart")
        return
    
    # Ensure columns exist
    if x_column not in df.columns:
        st.warning(f"Column '{x_column}' not found in results")
        return
    
    # Use first y_column that exists
    y_column = next((col for col in y_columns if col in df.columns), None)
    if not y_column:
        st.warning(f"No valid y-columns found in results")
        return
    
    fig = px.bar(
        df,
        x=x_column,
        y=y_column,
        title=title,
        **config
    )
    st.plotly_chart(fig, use_container_width=True)


def render_line_chart(
    df: pd.DataFrame,
    x_column: Optional[str],
    y_columns: List[str],
    title: str,
    config: Dict[str, Any]
) -> None:
    """Render a line chart."""
    if not x_column or not y_columns:
        st.warning("Missing column specifications for line chart")
        return
    
    if x_column not in df.columns:
        st.warning(f"Column '{x_column}' not found in results")
        return
    
    # Filter y_columns that exist
    valid_y_columns = [col for col in y_columns if col in df.columns]
    if not valid_y_columns:
        st.warning(f"No valid y-columns found in results")
        return
    
    fig = go.Figure()
    
    for y_col in valid_y_columns:
        fig.add_trace(go.Scatter(
            x=df[x_column],
            y=df[y_col],
            mode='lines+markers',
            name=y_col
        ))
    
    fig.update_layout(title=title, **config)
    st.plotly_chart(fig, use_container_width=True)


def render_pie_chart(
    df: pd.DataFrame,
    x_column: Optional[str],
    y_column: Optional[str],
    title: str,
    config: Dict[str, Any]
) -> None:
    """Render a pie chart."""
    if not x_column or not y_column:
        st.warning("Missing column specifications for pie chart")
        return
    
    if x_column not in df.columns or y_column not in df.columns:
        st.warning(f"Columns '{x_column}' or '{y_column}' not found in results")
        return
    
    fig = px.pie(
        df,
        names=x_column,
        values=y_column,
        title=title,
        **config
    )
    st.plotly_chart(fig, use_container_width=True)


def render_scatter_chart(
    df: pd.DataFrame,
    x_column: Optional[str],
    y_columns: List[str],
    title: str,
    config: Dict[str, Any]
) -> None:
    """Render a scatter chart."""
    if not x_column or not y_columns:
        st.warning("Missing column specifications for scatter chart")
        return
    
    if x_column not in df.columns:
        st.warning(f"Column '{x_column}' not found in results")
        return
    
    y_column = next((col for col in y_columns if col in df.columns), None)
    if not y_column:
        st.warning(f"No valid y-columns found in results")
        return
    
    fig = px.scatter(
        df,
        x=x_column,
        y=y_column,
        title=title,
        **config
    )
    st.plotly_chart(fig, use_container_width=True)


def render_area_chart(
    df: pd.DataFrame,
    x_column: Optional[str],
    y_columns: List[str],
    title: str,
    config: Dict[str, Any]
) -> None:
    """Render an area chart."""
    if not x_column or not y_columns:
        st.warning("Missing column specifications for area chart")
        return
    
    if x_column not in df.columns:
        st.warning(f"Column '{x_column}' not found in results")
        return
    
    valid_y_columns = [col for col in y_columns if col in df.columns]
    if not valid_y_columns:
        st.warning(f"No valid y-columns found in results")
        return
    
    fig = go.Figure()
    
    for y_col in valid_y_columns:
        fig.add_trace(go.Scatter(
            x=df[x_column],
            y=df[y_col],
            mode='lines',
            fill='tonexty',
            name=y_col
        ))
    
    fig.update_layout(title=title, **config)
    st.plotly_chart(fig, use_container_width=True)


def render_metric(
    df: pd.DataFrame,
    columns: List[str],
    config: Dict[str, Any]
) -> None:
    """Render key metrics."""
    if not columns:
        st.warning("No columns specified for metrics")
        return
    
    valid_columns = [col for col in columns if col in df.columns]
    if not valid_columns:
        st.warning("No valid columns found for metrics")
        return
    
    cols = st.columns(len(valid_columns))
    
    for col_widget, col_name in zip(cols, valid_columns):
        with col_widget:
            # Calculate metric (sum for numeric, count for others)
            if pd.api.types.is_numeric_dtype(df[col_name]):
                value = df[col_name].sum()
                st.metric(col_name, f"{value:,.2f}")
            else:
                value = df[col_name].nunique()
                st.metric(col_name, value)


def render_table(
    df: pd.DataFrame,
    config: Dict[str, Any]
) -> None:
    """Render a styled table."""
    st.dataframe(df, use_container_width=True, height=400)
