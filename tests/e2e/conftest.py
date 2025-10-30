"""Shared fixtures and configuration for E2E integration tests.

These tests require:
- Running MCP server (http://localhost:8000)
- Supabase project with proper setup
- Valid test users with different roles
- BigQuery test datasets
- LLM provider API keys

Run with: pytest tests/e2e/ -v -m e2e
Skip with: pytest -m "not e2e"
"""

import os
import asyncio
import time
from typing import Dict, Any, Optional, List
from datetime import datetime, timezone
import pytest
import httpx
from supabase import create_client, Client

# Test configuration
TEST_CONFIG = {
    "mcp_base_url": os.getenv("MCP_BASE_URL", "http://localhost:8000"),
    "supabase_url": os.getenv("SUPABASE_URL"),
    "supabase_key": os.getenv("SUPABASE_KEY"),
    "supabase_service_key": os.getenv("SUPABASE_SERVICE_KEY"),
    "supabase_jwt_secret": os.getenv("SUPABASE_JWT_SECRET"),
    "project_id": os.getenv("PROJECT_ID"),
    "openai_api_key": os.getenv("OPENAI_API_KEY"),
    "anthropic_api_key": os.getenv("ANTHROPIC_API_KEY"),
    "run_e2e_tests": os.getenv("RUN_E2E_TESTS", "").lower() in ("true", "1", "yes"),
}

# Mark all tests in e2e as e2e tests
pytestmark = pytest.mark.e2e


def pytest_configure(config):
    """Register custom markers."""
    config.addinivalue_line(
        "markers", "e2e: marks tests as end-to-end integration tests"
    )


def should_run_e2e_tests():
    """Check if E2E tests should run."""
    return TEST_CONFIG["run_e2e_tests"]


def skip_if_e2e_disabled():
    """Skip test if E2E tests are disabled."""
    if not should_run_e2e_tests():
        pytest.skip("E2E tests disabled (set RUN_E2E_TESTS=true to enable)")


def check_required_config(keys: List[str]):
    """Check if required config keys are present."""
    missing = [k for k in keys if not TEST_CONFIG.get(k)]
    if missing:
        pytest.skip(f"Missing required config: {', '.join(missing)}")


@pytest.fixture(scope="session")
def event_loop():
    """Create event loop for async tests."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="session")
def test_config():
    """Get test configuration."""
    skip_if_e2e_disabled()
    check_required_config(["supabase_url", "supabase_key", "project_id"])
    return TEST_CONFIG


@pytest.fixture(scope="session")
def supabase_client(test_config):
    """Create Supabase client for test setup."""
    return create_client(
        test_config["supabase_url"],
        test_config["supabase_service_key"] or test_config["supabase_key"]
    )


@pytest.fixture
async def http_client():
    """Create HTTP client for API calls."""
    async with httpx.AsyncClient(timeout=30.0) as client:
        yield client


@pytest.fixture
async def test_users(supabase_client, test_config):
    """Create or get test users with different roles.
    
    Returns:
        dict: Test users with credentials and tokens
            {
                "admin": {"email": "...", "password": "...", "token": "...", "user_id": "..."},
                "analyst": {"email": "...", "password": "...", "token": "...", "user_id": "..."},
                "viewer": {"email": "...", "password": "...", "token": "...", "user_id": "..."},
                "restricted": {"email": "...", "password": "...", "token": "...", "user_id": "..."},
            }
    """
    skip_if_e2e_disabled()
    
    users = {
        "admin": {
            "email": "test-admin@example.com",
            "password": "TestPassword123!",
            "role": "admin"
        },
        "analyst": {
            "email": "test-analyst@example.com",
            "password": "TestPassword123!",
            "role": "analyst"
        },
        "viewer": {
            "email": "test-viewer@example.com",
            "password": "TestPassword123!",
            "role": "viewer"
        },
        "restricted": {
            "email": "test-restricted@example.com",
            "password": "TestPassword123!",
            "role": "restricted"
        }
    }
    
    # Try to authenticate existing users or create them
    for role, user_data in users.items():
        try:
            # Try to sign in
            response = supabase_client.auth.sign_in_with_password({
                "email": user_data["email"],
                "password": user_data["password"]
            })
            user_data["token"] = response.session.access_token
            user_data["user_id"] = response.user.id
        except Exception as e:
            # User doesn't exist, skip for now
            # In real setup, would create users via Supabase admin API
            pytest.skip(f"Test user {role} not found. Please create test users first.")
    
    return users


@pytest.fixture
def performance_monitor():
    """Monitor performance metrics during tests."""
    
    class PerformanceMonitor:
        def __init__(self):
            self.metrics = []
        
        def start_operation(self, operation: str) -> Dict[str, Any]:
            """Start timing an operation."""
            return {
                "operation": operation,
                "start_time": time.time(),
                "start_timestamp": datetime.now(timezone.utc).isoformat()
            }
        
        def end_operation(self, context: Dict[str, Any], **kwargs) -> Dict[str, Any]:
            """End timing an operation and record metrics."""
            end_time = time.time()
            duration = end_time - context["start_time"]
            
            metric = {
                **context,
                "end_time": end_time,
                "end_timestamp": datetime.now(timezone.utc).isoformat(),
                "duration_seconds": duration,
                **kwargs
            }
            
            self.metrics.append(metric)
            return metric
        
        def get_metrics(self) -> List[Dict[str, Any]]:
            """Get all recorded metrics."""
            return self.metrics
        
        def get_summary(self) -> Dict[str, Any]:
            """Get summary statistics."""
            if not self.metrics:
                return {}
            
            durations = [m["duration_seconds"] for m in self.metrics]
            operations = {}
            
            for metric in self.metrics:
                op = metric["operation"]
                if op not in operations:
                    operations[op] = []
                operations[op].append(metric["duration_seconds"])
            
            return {
                "total_operations": len(self.metrics),
                "total_duration": sum(durations),
                "avg_duration": sum(durations) / len(durations),
                "min_duration": min(durations),
                "max_duration": max(durations),
                "operations": {
                    op: {
                        "count": len(times),
                        "avg": sum(times) / len(times),
                        "min": min(times),
                        "max": max(times)
                    }
                    for op, times in operations.items()
                }
            }
    
    return PerformanceMonitor()


@pytest.fixture
def test_queries():
    """Get test queries for different scenarios."""
    return {
        "simple": {
            "question": "Show me the top 5 rows from any table",
            "expected_keywords": ["SELECT", "LIMIT", "5"]
        },
        "aggregation": {
            "question": "Count the total number of records",
            "expected_keywords": ["COUNT", "SELECT"]
        },
        "filtering": {
            "question": "Show me records from the last 30 days",
            "expected_keywords": ["WHERE", "DATE"]
        },
        "join": {
            "question": "Join two tables and show the results",
            "expected_keywords": ["JOIN", "SELECT"]
        },
        "invalid": {
            "question": "Show me data from unauthorized_dataset.secret_table",
            "expect_error": True
        },
        "ambiguous": {
            "question": "Show me some data",
            "expect_clarification": True
        }
    }


@pytest.fixture
async def mcp_server_health(http_client, test_config):
    """Check if MCP server is running and healthy."""
    skip_if_e2e_disabled()
    
    try:
        response = await http_client.get(f"{test_config['mcp_base_url']}/health")
        if response.status_code != 200:
            pytest.skip(f"MCP server not healthy: {response.status_code}")
    except Exception as e:
        pytest.skip(f"MCP server not accessible: {e}")
    
    return True


@pytest.fixture
def cache_stats_tracker():
    """Track cache statistics during tests."""
    
    class CacheStatsTracker:
        def __init__(self):
            self.stats = []
        
        def record_stats(self, stats: Dict[str, Any], label: str = ""):
            """Record cache stats snapshot."""
            self.stats.append({
                "label": label,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "stats": stats
            })
        
        def get_cache_hit_rate(self) -> Optional[float]:
            """Calculate cache hit rate from recorded stats."""
            if len(self.stats) < 2:
                return None
            
            first = self.stats[0]["stats"]
            last = self.stats[-1]["stats"]
            
            hits_delta = last.get("hits", 0) - first.get("hits", 0)
            total_delta = (
                last.get("hits", 0) + last.get("misses", 0) - 
                first.get("hits", 0) - first.get("misses", 0)
            )
            
            if total_delta == 0:
                return None
            
            return hits_delta / total_delta
        
        def get_stats_delta(self) -> Optional[Dict[str, Any]]:
            """Get delta between first and last stats."""
            if len(self.stats) < 2:
                return None
            
            first = self.stats[0]["stats"]
            last = self.stats[-1]["stats"]
            
            return {
                key: last.get(key, 0) - first.get(key, 0)
                for key in set(list(first.keys()) + list(last.keys()))
            }
    
    return CacheStatsTracker()


@pytest.fixture
def test_report_generator():
    """Generate test reports and documentation."""
    
    class TestReportGenerator:
        def __init__(self):
            self.results = []
            self.issues = []
            self.metrics = {}
        
        def add_test_result(self, test_name: str, passed: bool, duration: float, 
                          details: Optional[Dict[str, Any]] = None):
            """Add a test result."""
            self.results.append({
                "test_name": test_name,
                "passed": passed,
                "duration": duration,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "details": details or {}
            })
        
        def add_issue(self, severity: str, title: str, description: str,
                     reproduction_steps: Optional[List[str]] = None):
            """Add a bug or issue."""
            self.issues.append({
                "severity": severity,
                "title": title,
                "description": description,
                "reproduction_steps": reproduction_steps or [],
                "timestamp": datetime.now(timezone.utc).isoformat()
            })
        
        def add_metric(self, name: str, value: Any):
            """Add a performance metric."""
            self.metrics[name] = value
        
        def generate_summary(self) -> Dict[str, Any]:
            """Generate test summary."""
            passed = sum(1 for r in self.results if r["passed"])
            failed = len(self.results) - passed
            
            return {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "total_tests": len(self.results),
                "passed": passed,
                "failed": failed,
                "pass_rate": passed / len(self.results) if self.results else 0,
                "total_duration": sum(r["duration"] for r in self.results),
                "issues_found": len(self.issues),
                "critical_issues": sum(1 for i in self.issues if i["severity"] == "critical"),
                "metrics": self.metrics,
                "production_ready": failed == 0 and len([i for i in self.issues if i["severity"] == "critical"]) == 0
            }
        
        def generate_markdown_report(self) -> str:
            """Generate markdown report."""
            summary = self.generate_summary()
            
            report = f"""# E2E Integration Test Report

Generated: {summary['timestamp']}

## Summary

- **Total Tests**: {summary['total_tests']}
- **Passed**: {summary['passed']} ✅
- **Failed**: {summary['failed']} ❌
- **Pass Rate**: {summary['pass_rate']:.1%}
- **Total Duration**: {summary['total_duration']:.2f}s
- **Issues Found**: {summary['issues_found']}
- **Critical Issues**: {summary['critical_issues']}
- **Production Ready**: {'✅ YES' if summary['production_ready'] else '❌ NO'}

## Test Results

"""
            for result in self.results:
                status = "✅ PASS" if result["passed"] else "❌ FAIL"
                report += f"- {status} `{result['test_name']}` ({result['duration']:.2f}s)\n"
            
            if self.issues:
                report += "\n## Issues Found\n\n"
                for issue in self.issues:
                    report += f"### {issue['severity'].upper()}: {issue['title']}\n\n"
                    report += f"{issue['description']}\n\n"
                    if issue['reproduction_steps']:
                        report += "**Reproduction Steps:**\n"
                        for i, step in enumerate(issue['reproduction_steps'], 1):
                            report += f"{i}. {step}\n"
                        report += "\n"
            
            if self.metrics:
                report += "\n## Performance Metrics\n\n"
                for name, value in self.metrics.items():
                    report += f"- **{name}**: {value}\n"
            
            return report
    
    return TestReportGenerator()
