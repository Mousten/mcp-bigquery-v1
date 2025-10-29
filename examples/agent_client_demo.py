"""Demo script showing usage of MCPBigQueryClient and ResultSummarizer.

This example demonstrates:
1. Connecting to the MCP BigQuery server
2. Executing queries
3. Summarizing results for LLM consumption
4. Discovering datasets and tables
"""

import asyncio
from mcp_bigquery.agent import (
    MCPBigQueryClient,
    ResultSummarizer,
)


async def main():
    """Run the demo."""
    
    # Configuration
    base_url = "http://localhost:8000"
    auth_token = "your-supabase-jwt-token"  # Replace with actual token
    
    # Initialize client
    async with MCPBigQueryClient(base_url, auth_token=auth_token) as client:
        
        # 1. Check server health
        print("=" * 60)
        print("1. Checking server health...")
        print("=" * 60)
        health = await client.health_check()
        print(f"Status: {health.status}")
        print()
        
        # 2. Discover available datasets
        print("=" * 60)
        print("2. Discovering datasets...")
        print("=" * 60)
        datasets = await client.get_datasets()
        for dataset in datasets[:3]:  # Show first 3
            print(f"- {dataset.dataset_id}")
            if dataset.description:
                print(f"  Description: {dataset.description}")
        print()
        
        # 3. Discover tables in a dataset
        if datasets:
            dataset_id = datasets[0].dataset_id
            print("=" * 60)
            print(f"3. Discovering tables in {dataset_id}...")
            print("=" * 60)
            tables = await client.get_tables(dataset_id)
            for table in tables[:3]:  # Show first 3
                print(f"- {table.table_id}")
                if table.num_rows:
                    print(f"  Rows: {table.num_rows:,}")
            print()
            
            # 4. Get table schema
            if tables:
                table_id = tables[0].table_id
                print("=" * 60)
                print(f"4. Getting schema for {dataset_id}.{table_id}...")
                print("=" * 60)
                schema = await client.get_table_schema(dataset_id, table_id)
                print(f"Table: {schema.table_id}")
                print(f"Rows: {schema.num_rows:,}" if schema.num_rows else "Rows: Unknown")
                print(f"Fields: {len(schema.schema_fields)}")
                for field in schema.schema_fields[:5]:  # Show first 5 fields
                    print(f"  - {field.get('name')}: {field.get('type')}")
                print()
        
        # 5. Execute a query
        print("=" * 60)
        print("5. Executing a sample query...")
        print("=" * 60)
        sql = """
        SELECT 
            name,
            age,
            salary,
            department
        FROM `project.dataset.employees`
        LIMIT 100
        """
        
        # Note: Replace with actual query for your data
        # For demo purposes, we'll show what the result would look like
        print(f"Query: {sql.strip()}")
        
        # Uncomment to run actual query:
        # result = await client.execute_sql(sql)
        # if result.error:
        #     print(f"Error: {result.error}")
        # else:
        #     print(f"Rows returned: {len(result.rows)}")
        
        # For demo, create sample data
        sample_rows = [
            {"name": "Alice", "age": 30, "salary": 75000, "department": "Engineering"},
            {"name": "Bob", "age": 35, "salary": 85000, "department": "Engineering"},
            {"name": "Charlie", "age": 28, "salary": 65000, "department": "Sales"},
            {"name": "Diana", "age": 42, "salary": 95000, "department": "Management"},
            {"name": "Eve", "age": 26, "salary": 60000, "department": "Marketing"},
        ] * 20  # Simulate 100 rows
        
        print(f"Rows returned: {len(sample_rows)}")
        print()
        
        # 6. Summarize results for LLM
        print("=" * 60)
        print("6. Summarizing results for LLM consumption...")
        print("=" * 60)
        summarizer = ResultSummarizer(max_rows=10, max_categories=5)
        summary = summarizer.summarize(sample_rows)
        
        print(f"Total Rows: {summary.total_rows}")
        print(f"Total Columns: {summary.total_columns}")
        print()
        
        print("Key Insights:")
        for insight in summary.key_insights:
            print(f"- {insight}")
        print()
        
        print("Column Statistics:")
        for col in summary.columns:
            print(f"\n{col.name} ({col.data_type}):")
            print(f"  Non-null: {col.count} ({100 - col.null_percentage:.1f}%)")
            if col.mean is not None:
                print(f"  Mean: {col.mean:.2f}, Median: {col.median:.2f}")
                print(f"  Range: [{col.min:.2f}, {col.max:.2f}]")
            if col.most_common:
                print(f"  Most common:")
                for item in col.most_common[:3]:
                    print(f"    - {item['value']}: {item['count']} times")
        print()
        
        print("Visualization Suggestions:")
        for viz in summary.visualization_suggestions:
            print(f"- {viz['type']}: {viz['description']}")
        print()
        
        # 7. Format summary as text for LLM
        print("=" * 60)
        print("7. Formatted text summary for LLM...")
        print("=" * 60)
        text_summary = summarizer.format_summary_text(summary)
        print(text_summary)
        print()
        
        # 8. Create aggregates for visualization
        print("=" * 60)
        print("8. Creating aggregates for visualization...")
        print("=" * 60)
        agg = summarizer.create_aggregate_summary(
            sample_rows,
            group_by="department",
            numeric_cols=["salary"],
        )
        print(f"Aggregated by department: {len(agg)} groups")
        print()


if __name__ == "__main__":
    print("\n" + "=" * 60)
    print("MCP BigQuery Client & Summarizer Demo")
    print("=" * 60 + "\n")
    
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nDemo interrupted by user")
    except Exception as e:
        print(f"\nError running demo: {e}")
        import traceback
        traceback.print_exc()
