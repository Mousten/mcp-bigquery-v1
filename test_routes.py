#!/usr/bin/env python3
"""Test script to verify FastAPI routes are registered correctly."""
import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from dotenv import load_dotenv
load_dotenv()

from unittest.mock import MagicMock, AsyncMock
from mcp_bigquery.routes.tools import create_tools_router
from mcp_bigquery.api.fastapi_app import create_fastapi_app
from mcp_bigquery.config.settings import ServerConfig

def test_tools_router():
    """Test that tools router has correct routes."""
    print("=" * 60)
    print("Testing tools router creation...")
    print("=" * 60)
    
    # Create mocks
    bigquery_client = MagicMock()
    event_manager = MagicMock()
    event_manager.broadcast = AsyncMock()
    knowledge_base = MagicMock()
    config = MagicMock()
    config.supabase_jwt_secret = "test-secret"
    
    # Create router
    router = create_tools_router(bigquery_client, event_manager, knowledge_base, config)
    
    print(f"\nRouter prefix: {router.prefix}")
    print(f"Number of routes: {len(router.routes)}")
    print("\nRegistered routes:")
    print("-" * 60)
    
    for route in router.routes:
        if hasattr(route, 'path') and hasattr(route, 'methods'):
            for method in route.methods:
                # Note: route.path already includes the router prefix
                print(f"{method:6} {route.path}")
    
    # Check for specific routes we need
    print("\n" + "=" * 60)
    print("Checking for required routes...")
    print("=" * 60)
    
    required_routes = [
        ('GET', '/tools/datasets'),
        ('POST', '/tools/execute_bigquery_sql'),
        ('GET', '/tools/tables'),
        ('POST', '/tools/query'),
    ]
    
    found_routes = set()
    for route in router.routes:
        if hasattr(route, 'path') and hasattr(route, 'methods'):
            for method in route.methods:
                # Note: route.path already includes the router prefix
                found_routes.add((method, route.path))
    
    for method, path in required_routes:
        if (method, path) in found_routes:
            print(f"✓ {method:6} {path}")
        else:
            print(f"✗ {method:6} {path} - NOT FOUND")

def test_fastapi_app():
    """Test that FastAPI app is created correctly."""
    print("\n" + "=" * 60)
    print("Testing FastAPI app creation...")
    print("=" * 60)
    
    # Set dummy environment variables if not set
    if not os.getenv("SUPABASE_URL"):
        os.environ["SUPABASE_URL"] = "https://dummy.supabase.co"
    if not os.getenv("SUPABASE_KEY") and not os.getenv("SUPABASE_ANON_KEY"):
        os.environ["SUPABASE_KEY"] = "dummy-key"
    
    app = create_fastapi_app()
    
    print(f"\nApp title: {app.title}")
    print(f"Number of routes: {len(app.routes)}")
    print("\nRegistered routes on app:")
    print("-" * 60)
    
    for route in app.routes:
        if hasattr(route, 'path') and hasattr(route, 'methods'):
            for method in route.methods:
                print(f"{method:6} {route.path}")

def test_full_app_with_routers():
    """Test full app setup as done in main.py."""
    print("\n" + "=" * 60)
    print("Testing full app setup (simulating main.py)...")
    print("=" * 60)
    
    # Set dummy environment variables if not set
    if not os.getenv("SUPABASE_URL"):
        os.environ["SUPABASE_URL"] = "https://dummy.supabase.co"
    if not os.getenv("SUPABASE_KEY") and not os.getenv("SUPABASE_ANON_KEY"):
        os.environ["SUPABASE_KEY"] = "dummy-key"
    
    # Create app
    app = create_fastapi_app()
    
    # Create mocks
    bigquery_client = MagicMock()
    event_manager = MagicMock()
    event_manager.broadcast = AsyncMock()
    knowledge_base = MagicMock()
    config = MagicMock()
    config.supabase_jwt_secret = "test-secret"
    
    # Create and include tools router (as done in main.py line 141, 157)
    tools_router = create_tools_router(bigquery_client, event_manager, knowledge_base, config)
    app.include_router(tools_router)
    
    print(f"\nApp title: {app.title}")
    print(f"Number of routes: {len(app.routes)}")
    print("\nAll registered routes on full app:")
    print("-" * 60)
    
    for route in app.routes:
        if hasattr(route, 'path') and hasattr(route, 'methods'):
            methods_str = ', '.join(sorted(route.methods))
            print(f"{methods_str:20} {route.path}")
    
    # Check for specific routes we need
    print("\n" + "=" * 60)
    print("Checking for required routes on full app...")
    print("=" * 60)
    
    required_routes = [
        ('GET', '/tools/datasets'),
        ('POST', '/tools/execute_bigquery_sql'),
        ('GET', '/tools/tables'),
        ('POST', '/tools/query'),
    ]
    
    found_routes = set()
    for route in app.routes:
        if hasattr(route, 'path') and hasattr(route, 'methods'):
            for method in route.methods:
                found_routes.add((method, route.path))
    
    all_found = True
    for method, path in required_routes:
        if (method, path) in found_routes:
            print(f"✓ {method:6} {path}")
        else:
            print(f"✗ {method:6} {path} - NOT FOUND")
            all_found = False
    
    if all_found:
        print("\n✅ All required routes are registered correctly!")
    else:
        print("\n❌ Some routes are missing!")

if __name__ == "__main__":
    try:
        test_tools_router()
        test_fastapi_app()
        test_full_app_with_routers()
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
