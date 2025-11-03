#!/usr/bin/env python3
"""Diagnostic script to check MCP server endpoint availability."""
import sys
import httpx
import json
import asyncio

def print_header(text):
    """Print a formatted header."""
    print("\n" + "=" * 70)
    print(f"  {text}")
    print("=" * 70)

def print_result(success, message):
    """Print a test result."""
    icon = "✅" if success else "❌"
    print(f"{icon} {message}")

async def test_endpoint(client, method, url, json_data=None, description=None):
    """Test a single endpoint."""
    desc = description or f"{method} {url}"
    try:
        if method.upper() == "GET":
            response = await client.get(url)
        elif method.upper() == "POST":
            response = await client.post(url, json=json_data)
        else:
            print_result(False, f"{desc}: Unsupported method")
            return False
        
        if response.status_code == 200:
            print_result(True, f"{desc}: {response.status_code} OK")
            return True
        elif response.status_code == 401:
            print_result(False, f"{desc}: {response.status_code} Unauthorized (route exists, auth needed)")
            return True  # Route exists, just needs auth
        elif response.status_code == 404:
            print_result(False, f"{desc}: {response.status_code} Not Found")
            return False
        else:
            print_result(False, f"{desc}: {response.status_code}")
            return False
    except httpx.ConnectError:
        print_result(False, f"{desc}: Connection failed (server not running?)")
        return False
    except Exception as e:
        print_result(False, f"{desc}: {type(e).__name__}: {str(e)}")
        return False

async def diagnose_server(base_url="http://localhost:8000", token=None):
    """Run comprehensive server diagnostics."""
    print_header("MCP BigQuery Server Diagnostics")
    print(f"Base URL: {base_url}")
    print(f"Auth Token: {'Provided' if token else 'Not provided'}")
    
    headers = {}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    
    async with httpx.AsyncClient(headers=headers, timeout=10.0) as client:
        # Test basic connectivity
        print_header("1. Basic Connectivity")
        root_ok = await test_endpoint(client, "GET", base_url, description="GET /")
        docs_ok = await test_endpoint(client, "GET", f"{base_url}/docs", description="GET /docs (OpenAPI docs)")
        health_ok = await test_endpoint(client, "GET", f"{base_url}/health", description="GET /health")
        
        # Test HTTP mode endpoints
        print_header("2. HTTP Mode Endpoints (routes at /tools/*)")
        http_datasets = await test_endpoint(
            client, "GET", f"{base_url}/tools/datasets", 
            description="GET /tools/datasets"
        )
        http_execute = await test_endpoint(
            client, "POST", f"{base_url}/tools/execute_bigquery_sql",
            json_data={"sql": "SELECT 1 as num", "use_cache": True},
            description="POST /tools/execute_bigquery_sql"
        )
        http_tables = await test_endpoint(
            client, "GET", f"{base_url}/tools/tables?dataset_id=test",
            description="GET /tools/tables"
        )
        
        # Test HTTP-Stream mode endpoints
        print_header("3. HTTP-Stream Mode Endpoints (routes at /stream/tools/*)")
        stream_datasets = await test_endpoint(
            client, "GET", f"{base_url}/stream/tools/datasets",
            description="GET /stream/tools/datasets"
        )
        stream_execute = await test_endpoint(
            client, "POST", f"{base_url}/stream/tools/execute_bigquery_sql",
            json_data={"sql": "SELECT 1 as num", "use_cache": True},
            description="POST /stream/tools/execute_bigquery_sql"
        )
        stream_tables = await test_endpoint(
            client, "GET", f"{base_url}/stream/tools/tables?dataset_id=test",
            description="GET /stream/tools/tables"
        )
        
        # Test preferences endpoint (should exist in both modes)
        print_header("4. Other Endpoints")
        prefs_get = await test_endpoint(
            client, "POST", f"{base_url}/preferences/get",
            json_data={"key": "test"},
            description="POST /preferences/get"
        )
        
        # Summary
        print_header("Diagnosis Summary")
        
        if http_datasets or http_execute:
            print("🎯 Server is running in HTTP MODE")
            print("   Routes available at: /tools/datasets, /tools/execute_bigquery_sql, etc.")
            print("   Client should use: base_url='http://localhost:8000'")
            print("   ✅ This is the CORRECT configuration for the current client")
        elif stream_datasets or stream_execute:
            print("🎯 Server is running in HTTP-STREAM MODE")
            print("   Routes available at: /stream/tools/datasets, /stream/tools/execute_bigquery_sql, etc.")
            print("   ❌ Client is configured for HTTP mode (routes at /tools/*)")
            print("   🔧 FIX: Either:")
            print("      1. Restart server in HTTP mode: uv run mcp-bigquery --transport http --port 8000")
            print("      2. Update client base_url to include /stream prefix")
        elif root_ok or docs_ok:
            print("⚠️  Server is running but BigQuery tool endpoints are NOT registered")
            print("   Possible issues:")
            print("   - Router not included in FastAPI app")
            print("   - Server started in different mode (SSE, stdio)")
            print("   - Initialization error prevented router registration")
        else:
            print("❌ Server is NOT running or not accessible")
            print("   🔧 FIX:")
            print("      1. Start the server: uv run mcp-bigquery --transport http --port 8000")
            print("      2. Check firewall/network settings")
            print("      3. Verify server logs for startup errors")
        
        if not token:
            print("\n⚠️  Note: No auth token provided - some endpoints may show 401 instead of 200")
            print("   To test with auth, run: python diagnose_server.py --token YOUR_JWT_TOKEN")

def main():
    """Main entry point."""
    import argparse
    parser = argparse.ArgumentParser(description="Diagnose MCP BigQuery server endpoints")
    parser.add_argument("--url", default="http://localhost:8000", help="Server base URL")
    parser.add_argument("--token", help="JWT auth token (optional)")
    args = parser.parse_args()
    
    try:
        asyncio.run(diagnose_server(args.url, args.token))
    except KeyboardInterrupt:
        print("\n\nDiagnostics interrupted")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n❌ Error running diagnostics: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()
