"""Example usage of the MCP BigQuery client.

This script demonstrates how to use the MCP BigQuery client to interact
with the server, including authentication, query execution, and streaming.
"""

import asyncio
import os
from mcp_bigquery.client import MCPClient, ClientConfig


async def main():
    """Main example function demonstrating client usage."""
    
    # Option 1: Create config from environment
    # Set MCP_BASE_URL and MCP_AUTH_TOKEN environment variables
    config = ClientConfig.from_env()
    
    # Option 2: Create config explicitly
    # config = ClientConfig(
    #     base_url="http://localhost:8000",
    #     auth_token="your-jwt-token",
    #     timeout=60.0,
    #     max_retries=3
    # )
    
    # Use client as async context manager
    async with MCPClient(config) as client:
        try:
            print("=" * 60)
            print("MCP BigQuery Client Example")
            print("=" * 60)
            
            # 1. List datasets
            print("\n1. Listing datasets...")
            datasets_result = await client.list_datasets()
            print(f"Found {len(datasets_result.get('datasets', []))} datasets")
            
            # 2. List tables in first dataset
            if datasets_result.get('datasets'):
                dataset_id = datasets_result['datasets'][0]
                print(f"\n2. Listing tables in dataset '{dataset_id}'...")
                tables_result = await client.list_tables(dataset_id)
                print(f"Found {len(tables_result.get('tables', []))} tables")
                
                # 3. Get schema for first table
                if tables_result.get('tables'):
                    table_id = tables_result['tables'][0]
                    print(f"\n3. Getting schema for table '{table_id}'...")
                    schema_result = await client.get_table_schema(
                        dataset_id=dataset_id,
                        table_id=table_id
                    )
                    print(f"Table has {len(schema_result.get('schema', []))} columns")
            
            # 4. Execute a simple query
            print("\n4. Executing a simple query...")
            query_result = await client.execute_sql(
                sql="SELECT 1 as test_column",
                maximum_bytes_billed=100000000,
                use_cache=True
            )
            print(f"Query returned {query_result.get('total_rows', 0)} rows")
            if query_result.get('rows'):
                print(f"First row: {query_result['rows'][0]}")
            
            # 5. Get query suggestions
            print("\n5. Getting query suggestions...")
            suggestions_result = await client.get_query_suggestions(
                query_context="Show me recent records",
                limit=3
            )
            print(f"Received {len(suggestions_result.get('suggestions', []))} suggestions")
            
            # 6. Cache management
            print("\n6. Getting cache statistics...")
            cache_stats = await client.manage_cache(action="get_stats")
            print(f"Cache stats: {cache_stats}")
            
            print("\n" + "=" * 60)
            print("Example completed successfully!")
            print("=" * 60)
            
        except Exception as e:
            print(f"\nError: {type(e).__name__}: {e}")
            import traceback
            traceback.print_exc()


async def streaming_example():
    """Example of streaming events from the server."""
    
    config = ClientConfig.from_env()
    
    async with MCPClient(config) as client:
        print("=" * 60)
        print("Streaming Events Example")
        print("=" * 60)
        print("\nListening for events (press Ctrl+C to stop)...\n")
        
        try:
            async for event in client.stream_events(channel="system"):
                event_type = event.get("type", "unknown")
                print(f"Received event: {event_type}")
                
                if event_type == "query_started":
                    print(f"  Query ID: {event.get('query_id')}")
                elif event_type == "query_completed":
                    print(f"  Query ID: {event.get('query_id')}")
                    print(f"  Duration: {event.get('duration_ms')}ms")
                
        except KeyboardInterrupt:
            print("\nStreaming stopped by user")


if __name__ == "__main__":
    # Check if required environment variables are set
    if not os.getenv("MCP_AUTH_TOKEN"):
        print("WARNING: MCP_AUTH_TOKEN environment variable not set")
        print("Please set your JWT token:")
        print("  export MCP_AUTH_TOKEN='your-jwt-token'")
        print()
    
    if not os.getenv("MCP_BASE_URL"):
        print("INFO: Using default MCP_BASE_URL=http://localhost:8000")
        print()
    
    # Run the main example
    print("Running main example...")
    asyncio.run(main())
    
    # Uncomment to run streaming example
    # print("\n\nRunning streaming example...")
    # asyncio.run(streaming_example())
