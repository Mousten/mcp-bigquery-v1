#!/usr/bin/env python3
"""
E2E Test Runner with comprehensive reporting.

This script runs all E2E integration tests and generates a detailed report.

Usage:
    python tests/e2e/run_e2e_tests.py
    
    Or with pytest directly:
    RUN_E2E_TESTS=true pytest tests/e2e/ -v -m e2e --tb=short

Requirements:
    - MCP server running (default: http://localhost:8000)
    - Supabase project configured
    - Test users created with appropriate roles
    - BigQuery test datasets accessible
    - LLM provider API keys configured

Environment Variables:
    RUN_E2E_TESTS=true              # Enable E2E tests
    MCP_BASE_URL=http://localhost:8000
    SUPABASE_URL=https://...
    SUPABASE_KEY=...
    SUPABASE_SERVICE_KEY=...
    SUPABASE_JWT_SECRET=...
    PROJECT_ID=your-gcp-project
    OPENAI_API_KEY=sk-...           # Optional, for OpenAI tests
    ANTHROPIC_API_KEY=sk-ant-...    # Optional, for Anthropic tests
"""

import os
import sys
import subprocess
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, List


def check_prerequisites() -> Dict[str, Any]:
    """Check if prerequisites are met for E2E tests."""
    print("🔍 Checking prerequisites...")
    
    checks = {
        "environment": {},
        "services": {},
        "ready": True
    }
    
    # Check environment variables
    required_env = [
        "SUPABASE_URL",
        "SUPABASE_KEY",
        "SUPABASE_JWT_SECRET",
        "PROJECT_ID"
    ]
    
    for var in required_env:
        value = os.getenv(var)
        checks["environment"][var] = "✅ Set" if value else "❌ Missing"
        if not value:
            checks["ready"] = False
    
    # Check optional LLM provider keys
    llm_keys = {
        "OPENAI_API_KEY": os.getenv("OPENAI_API_KEY"),
        "ANTHROPIC_API_KEY": os.getenv("ANTHROPIC_API_KEY"),
        "GOOGLE_API_KEY": os.getenv("GOOGLE_API_KEY")
    }
    
    has_llm_key = any(llm_keys.values())
    checks["environment"]["LLM_PROVIDER_KEY"] = "✅ At least one set" if has_llm_key else "⚠️  None set"
    
    # Check MCP server
    mcp_url = os.getenv("MCP_BASE_URL", "http://localhost:8000")
    checks["services"]["MCP_SERVER"] = mcp_url
    
    try:
        import httpx
        import asyncio
        
        async def check_server():
            async with httpx.AsyncClient(timeout=5.0) as client:
                try:
                    response = await client.get(f"{mcp_url}/health")
                    return response.status_code == 200
                except Exception:
                    return False
        
        server_up = asyncio.run(check_server())
        checks["services"]["MCP_SERVER_STATUS"] = "✅ Running" if server_up else "❌ Not accessible"
        if not server_up:
            checks["ready"] = False
    except Exception as e:
        checks["services"]["MCP_SERVER_STATUS"] = f"❌ Error: {str(e)}"
        checks["ready"] = False
    
    return checks


def print_prerequisites_report(checks: Dict[str, Any]):
    """Print prerequisites check report."""
    print("\n" + "="*60)
    print("PREREQUISITES CHECK")
    print("="*60)
    
    print("\n📋 Environment Variables:")
    for var, status in checks["environment"].items():
        print(f"  {var}: {status}")
    
    print("\n🌐 Services:")
    for service, status in checks["services"].items():
        print(f"  {service}: {status}")
    
    print("\n" + "="*60)
    if checks["ready"]:
        print("✅ All prerequisites met - ready to run tests")
    else:
        print("❌ Some prerequisites missing - tests may fail")
    print("="*60 + "\n")


def run_tests() -> Dict[str, Any]:
    """Run E2E tests using pytest."""
    print("🧪 Running E2E tests...\n")
    
    # Set environment variable to enable E2E tests
    env = os.environ.copy()
    env["RUN_E2E_TESTS"] = "true"
    
    # Run pytest with JSON report
    cmd = [
        "pytest",
        "tests/e2e/",
        "-v",
        "-m", "e2e",
        "--tb=short",
        "--json-report",
        "--json-report-file=test_results/e2e_report.json",
        "--json-report-indent=2"
    ]
    
    try:
        result = subprocess.run(
            cmd,
            env=env,
            capture_output=True,
            text=True
        )
        
        return {
            "exit_code": result.returncode,
            "stdout": result.stdout,
            "stderr": result.stderr,
            "success": result.returncode == 0
        }
    except Exception as e:
        return {
            "exit_code": -1,
            "stdout": "",
            "stderr": str(e),
            "success": False,
            "error": str(e)
        }


def generate_markdown_report(test_results: Dict[str, Any], checks: Dict[str, Any]) -> str:
    """Generate comprehensive markdown report."""
    
    timestamp = datetime.now(timezone.utc).isoformat()
    
    report = f"""# E2E Integration Test Report

**Generated:** {timestamp}

## Executive Summary

"""
    
    # Prerequisites summary
    report += "### Prerequisites Status\n\n"
    all_prereqs_met = checks["ready"]
    report += f"- **Status:** {'✅ All prerequisites met' if all_prereqs_met else '❌ Some prerequisites missing'}\n"
    report += f"- **MCP Server:** {checks['services'].get('MCP_SERVER_STATUS', 'Unknown')}\n"
    report += f"- **Environment:** {sum(1 for v in checks['environment'].values() if '✅' in v)}/{len(checks['environment'])} variables set\n\n"
    
    # Test execution summary
    report += "### Test Execution\n\n"
    
    if test_results.get("success"):
        report += "- **Overall Status:** ✅ PASSED\n"
    elif test_results.get("exit_code") == -1:
        report += "- **Overall Status:** ❌ ERROR\n"
    else:
        report += "- **Overall Status:** ❌ FAILED\n"
    
    report += f"- **Exit Code:** {test_results.get('exit_code', 'N/A')}\n\n"
    
    # Test output
    if test_results.get("stdout"):
        report += "## Test Output\n\n```\n"
        report += test_results["stdout"][:5000]  # Limit output length
        if len(test_results["stdout"]) > 5000:
            report += "\n... (output truncated)"
        report += "\n```\n\n"
    
    if test_results.get("stderr"):
        report += "## Errors\n\n```\n"
        report += test_results["stderr"][:2000]
        if len(test_results["stderr"]) > 2000:
            report += "\n... (output truncated)"
        report += "\n```\n\n"
    
    # Production readiness assessment
    report += "## Production Readiness Assessment\n\n"
    
    production_ready = all_prereqs_met and test_results.get("success", False)
    
    if production_ready:
        report += "### ✅ SYSTEM IS PRODUCTION READY\n\n"
        report += "All E2E tests passed successfully. The system is ready for production deployment.\n\n"
    else:
        report += "### ❌ SYSTEM NOT PRODUCTION READY\n\n"
        report += "**Blockers:**\n\n"
        
        if not all_prereqs_met:
            report += "- Prerequisites not met (see above)\n"
        
        if not test_results.get("success"):
            report += "- E2E tests failed\n"
        
        report += "\n**Recommended Actions:**\n\n"
        report += "1. Review test failures and error messages\n"
        report += "2. Ensure all prerequisites are configured correctly\n"
        report += "3. Fix identified issues\n"
        report += "4. Re-run E2E tests\n\n"
    
    # Next steps
    report += "## Next Steps\n\n"
    
    if production_ready:
        report += "1. Review performance metrics\n"
        report += "2. Conduct user acceptance testing (UAT)\n"
        report += "3. Prepare production deployment\n"
        report += "4. Set up monitoring and alerting\n"
        report += "5. Create runbook for operations team\n"
    else:
        report += "1. Review and address all failing tests\n"
        report += "2. Verify all configuration is correct\n"
        report += "3. Check that all services are running\n"
        report += "4. Re-run tests after fixes\n"
    
    return report


def save_report(report: str, filename: str = "E2E_TEST_REPORT.md"):
    """Save report to file."""
    report_dir = Path("test_results")
    report_dir.mkdir(exist_ok=True)
    
    report_path = report_dir / filename
    report_path.write_text(report)
    
    return report_path


def main():
    """Main entry point."""
    print("="*60)
    print("E2E INTEGRATION TEST SUITE")
    print("="*60)
    print()
    
    # Check prerequisites
    checks = check_prerequisites()
    print_prerequisites_report(checks)
    
    if not checks["ready"]:
        print("⚠️  WARNING: Not all prerequisites are met.")
        print("Tests may fail or be skipped.\n")
        
        response = input("Continue anyway? (y/N): ")
        if response.lower() != 'y':
            print("Aborting.")
            return 1
    
    # Run tests
    test_results = run_tests()
    
    # Generate report
    print("\n" + "="*60)
    print("GENERATING REPORT")
    print("="*60 + "\n")
    
    report = generate_markdown_report(test_results, checks)
    report_path = save_report(report)
    
    print(f"📄 Report saved to: {report_path}")
    print()
    
    # Print summary
    print("="*60)
    print("SUMMARY")
    print("="*60)
    
    if test_results.get("success"):
        print("✅ All E2E tests PASSED")
        exit_code = 0
    elif test_results.get("exit_code") == -1:
        print("❌ Test execution ERROR")
        exit_code = 2
    else:
        print("❌ Some E2E tests FAILED")
        exit_code = 1
    
    print(f"📊 Full report: {report_path}")
    print("="*60)
    
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
