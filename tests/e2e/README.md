# End-to-End Integration Test Suite

Comprehensive E2E integration tests for the complete AI agent system, verifying all components work together correctly in real-world scenarios.

## Overview

This test suite validates the entire system stack:

- **Authentication & Authorization** - JWT tokens, RBAC, session management
- **LLM Provider Integration** - OpenAI, Anthropic, provider switching
- **Conversational Agent** - Natural language to SQL, context handling
- **MCP + BigQuery** - Dataset discovery, query execution, results
- **Caching & Performance** - Query caching, LLM caching, response times
- **Multi-User Scenarios** - Concurrent sessions, data isolation
- **Error Handling** - Graceful failures, user-friendly messages

## Quick Start

### Prerequisites

1. **Running MCP Server**
   ```bash
   # Start the MCP server
   uvicorn mcp_bigquery.main:app --reload
   # Or
   python -m mcp_bigquery.main http
   ```

2. **Supabase Project**
   - Project created and configured
   - Authentication enabled
   - RBAC tables set up (see `docs/supabase_setup.sql`)
   - Test users created

3. **BigQuery Setup**
   - Test datasets accessible
   - Service account with read permissions
   - Test data available

4. **Environment Variables**
   ```bash
   # Copy .env.example and configure
   cp .env.example .env
   
   # Required variables
   export RUN_E2E_TESTS=true
   export MCP_BASE_URL=http://localhost:8000
   export SUPABASE_URL=https://your-project.supabase.co
   export SUPABASE_KEY=your-anon-key
   export SUPABASE_SERVICE_KEY=your-service-key
   export SUPABASE_JWT_SECRET=your-jwt-secret
   export PROJECT_ID=your-gcp-project-id
   
   # At least one LLM provider
   export OPENAI_API_KEY=sk-...
   export ANTHROPIC_API_KEY=sk-ant-...
   ```

5. **Test Users**
   
   Create test users in Supabase with different roles:
   - `test-admin@example.com` - Admin role (full access)
   - `test-analyst@example.com` - Analyst role (standard access)
   - `test-viewer@example.com` - Viewer role (read-only)
   - `test-restricted@example.com` - Restricted role (limited datasets)
   
   Password for all: `TestPassword123!`

### Running Tests

**Option 1: Using the test runner (recommended)**
```bash
# Run all E2E tests with comprehensive reporting
python tests/e2e/run_e2e_tests.py
```

**Option 2: Using pytest directly**
```bash
# Run all E2E tests
RUN_E2E_TESTS=true pytest tests/e2e/ -v -m e2e

# Run specific test file
RUN_E2E_TESTS=true pytest tests/e2e/test_auth_flow.py -v

# Run with coverage
RUN_E2E_TESTS=true pytest tests/e2e/ -v -m e2e --cov=src/mcp_bigquery

# Run with detailed output
RUN_E2E_TESTS=true pytest tests/e2e/ -v -m e2e --tb=short -s
```

**Option 3: Skip E2E tests (default)**
```bash
# Run all tests except E2E
pytest -m "not e2e"
```

## Test Organization

### Test Files

- **`conftest.py`** - Shared fixtures, configuration, and utilities
  - Test user management
  - Performance monitoring
  - Cache statistics tracking
  - Report generation

- **`test_auth_flow.py`** - Authentication & Authorization
  - Login with password
  - Magic link authentication
  - Token validation
  - Session persistence
  - RBAC enforcement
  - Unauthorized access blocking

- **`test_llm_integration.py`** - LLM Provider Integration
  - OpenAI provider creation and queries
  - Anthropic provider creation and queries
  - Token counting accuracy
  - Provider error handling
  - Invalid API key handling

- **`test_conversational_agent.py`** - Conversational Agent Flow
  - Natural language question processing
  - SQL query generation
  - Follow-up questions with context
  - Chat history persistence
  - RBAC enforcement in agent
  - Ambiguous query handling
  - Invalid SQL prevention

- **`test_caching_performance.py`** - Caching & Performance
  - Query result caching
  - Cache hit verification
  - Performance improvement from cache
  - LLM response caching
  - Cache isolation between users
  - Response time requirements (<10s)
  - Token usage tracking

- **`run_e2e_tests.py`** - Test runner and report generator

## Test Scenarios

### 1. Authentication & Authorization Flow

**Scenario**: User signup/login through Streamlit UI
- ✅ Email/password authentication
- ✅ Magic link (passwordless) authentication
- ✅ JWT token issuance and validation
- ✅ Session persistence across requests
- ✅ Unauthorized access blocked (401)
- ✅ Invalid token rejected (401)
- ✅ Role-based access control

**Acceptance Criteria**:
- Valid credentials create authenticated session
- Invalid credentials are rejected
- Sessions persist across page reloads
- Unauthorized requests return 401/403
- Different roles have different permissions

### 2. LLM Provider Integration

**Scenario**: Test OpenAI and Anthropic providers
- ✅ OpenAI provider selection and query execution
- ✅ Anthropic provider selection and query execution
- ✅ Token counting accuracy
- ✅ Error handling for invalid API keys
- ✅ Error handling for missing API keys

**Acceptance Criteria**:
- Both providers can be initialized and used
- Queries return valid responses
- Token counting is consistent
- Invalid API keys raise authentication errors
- Missing API keys are rejected at initialization

### 3. Conversational Agent Flow

**Scenario**: Natural language questions through chat
- ✅ Simple question processing
- ✅ SQL query generation from natural language
- ✅ Follow-up questions using conversation context
- ✅ Chat history persistence
- ✅ RBAC enforcement (only permitted datasets)
- ✅ Ambiguous query handling
- ✅ Invalid SQL prevention (e.g., DELETE operations)

**Acceptance Criteria**:
- Natural language converts to valid SQL
- Generated SQL respects user permissions
- Follow-up questions reference conversation context
- Chat history persists and loads correctly
- System refuses destructive operations
- Ambiguous queries get clarification or reasonable assumptions

### 4. MCP Client & BigQuery Integration

**Scenario**: Agent queries BigQuery through MCP server
- ✅ Dataset discovery
- ✅ Table listing
- ✅ Schema introspection
- ✅ Query execution
- ✅ Result formatting
- ✅ Error handling for invalid SQL
- ✅ Permission denials

**Acceptance Criteria**:
- Can discover and list datasets/tables
- Can retrieve table schemas
- Can execute SQL queries
- Results are formatted correctly
- Invalid SQL returns clear error
- Unauthorized access returns 403

### 5. Caching & Performance

**Scenario**: Submit identical queries and verify caching
- ✅ Cache hits for duplicate queries
- ✅ Performance improvement from cache
- ✅ LLM response caching
- ✅ Cache isolation per user
- ✅ Token usage reduction
- ✅ Response times < 10 seconds

**Acceptance Criteria**:
- Duplicate queries hit cache
- Cached responses are faster
- Cache doesn't leak between users
- Token usage reduced for cached LLM responses
- Typical queries respond in < 10 seconds

### 6. Multi-User Scenarios

**Scenario**: Concurrent users with different roles
- ✅ Session isolation between users
- ✅ Chat history separation
- ✅ Cache isolation
- ✅ Permission enforcement per user

**Acceptance Criteria**:
- Users can work concurrently
- Sessions don't mix between users
- Chat histories are separate
- Cache respects user permissions

## Test Results and Reporting

### Report Generation

After running tests, a comprehensive markdown report is generated:

```
test_results/
├── E2E_TEST_REPORT.md       # Main report
└── e2e_report.json          # JSON test results
```

### Report Contents

- **Executive Summary** - Overall pass/fail status
- **Prerequisites Check** - Environment and service status
- **Test Results** - Detailed results for each test
- **Issues Found** - Bugs with severity and reproduction steps
- **Performance Metrics** - Response times, cache hit rates, token usage
- **Production Readiness** - Assessment and blockers
- **Recommendations** - Next steps and improvements

### Report Example

```markdown
# E2E Integration Test Report

## Summary
- Total Tests: 45
- Passed: 42 ✅
- Failed: 3 ❌
- Pass Rate: 93.3%
- Production Ready: ❌ NO (3 critical issues)

## Critical Issues
1. **Agent bypasses dataset permissions**
   - Severity: CRITICAL
   - Agent generated SQL for unauthorized dataset
   - Reproduction: Login as restricted user, request unauthorized data

## Performance Metrics
- Average Response Time: 2.3s ✅
- Cache Hit Rate: 78% ✅
- Token Usage Reduction: 65% ✅
```

## Performance Monitoring

The test suite includes performance monitoring:

```python
@pytest.fixture
def performance_monitor():
    """Monitor performance metrics during tests."""
    # Tracks:
    # - Operation durations
    # - Response times
    # - Cache performance
    # - Token usage
```

**Metrics Tracked**:
- Operation durations
- Response times (first vs cached)
- Cache hit/miss rates
- Token usage per operation
- Request throughput

**Performance Targets**:
- Response time: < 10 seconds
- Cache hit rate: > 50%
- Token reduction: > 40%

## Troubleshooting

### Tests are skipped

**Cause**: `RUN_E2E_TESTS` not set or prerequisites missing

**Solution**:
```bash
export RUN_E2E_TESTS=true
# Ensure all required environment variables are set
```

### MCP server not accessible

**Cause**: Server not running or wrong URL

**Solution**:
```bash
# Start server
uvicorn mcp_bigquery.main:app --reload

# Or check URL
export MCP_BASE_URL=http://localhost:8000
```

### Authentication failures

**Cause**: Test users not created or invalid credentials

**Solution**:
1. Create test users in Supabase
2. Ensure passwords match `TestPassword123!`
3. Verify JWT secret is correct

### BigQuery permission errors

**Cause**: Service account lacks permissions or datasets not accessible

**Solution**:
1. Grant BigQuery Data Viewer role to service account
2. Verify `PROJECT_ID` is correct
3. Check test datasets exist and are accessible

### LLM provider errors

**Cause**: Invalid or missing API keys

**Solution**:
```bash
# Set valid API keys
export OPENAI_API_KEY=sk-...
export ANTHROPIC_API_KEY=sk-ant-...
```

### Tests timeout

**Cause**: Queries taking too long or server overloaded

**Solution**:
1. Increase timeout in test configuration
2. Use smaller test datasets
3. Enable caching to improve performance

## Continuous Integration

### GitHub Actions Example

```yaml
name: E2E Tests

on: [push, pull_request]

jobs:
  e2e:
    runs-on: ubuntu-latest
    
    services:
      mcp-server:
        # Start MCP server as service
        
    steps:
      - uses: actions/checkout@v2
      
      - name: Set up Python
        uses: actions/setup-python@v2
        with:
          python-version: '3.10'
      
      - name: Install dependencies
        run: |
          pip install uv
          uv sync --dev
      
      - name: Run E2E tests
        env:
          RUN_E2E_TESTS: true
          MCP_BASE_URL: http://localhost:8000
          SUPABASE_URL: ${{ secrets.SUPABASE_URL }}
          SUPABASE_KEY: ${{ secrets.SUPABASE_KEY }}
          SUPABASE_JWT_SECRET: ${{ secrets.SUPABASE_JWT_SECRET }}
          PROJECT_ID: ${{ secrets.PROJECT_ID }}
          OPENAI_API_KEY: ${{ secrets.OPENAI_API_KEY }}
        run: |
          python tests/e2e/run_e2e_tests.py
      
      - name: Upload test report
        uses: actions/upload-artifact@v2
        with:
          name: e2e-test-report
          path: test_results/
```

## Contributing

### Adding New E2E Tests

1. **Create test file** in `tests/e2e/`
2. **Import fixtures** from `conftest.py`
3. **Mark tests** with `@pytest.mark.e2e`
4. **Use performance monitoring**:
   ```python
   ctx = performance_monitor.start_operation("operation_name")
   # ... test code ...
   performance_monitor.end_operation(ctx, success=True)
   ```
5. **Report results**:
   ```python
   test_report_generator.add_test_result(
       "test_name", passed, duration, details
   )
   ```
6. **Document issues**:
   ```python
   test_report_generator.add_issue(
       "severity", "title", "description", reproduction_steps
   )
   ```

### Test Conventions

- Use descriptive test names
- Include docstrings explaining what's tested
- Use appropriate assertions with clear messages
- Handle expected errors with `pytest.raises()`
- Skip tests gracefully when prerequisites missing
- Track performance for all operations
- Generate detailed reports

## FAQ

**Q: How long do E2E tests take?**
A: Typically 2-5 minutes depending on LLM response times and caching.

**Q: Can I run tests against production?**
A: No, E2E tests should only run against test environments with test data.

**Q: Do tests make real API calls?**
A: Yes, tests make real calls to MCP server, Supabase, BigQuery, and LLM providers.

**Q: How do I test specific scenarios only?**
A: Use pytest markers or run specific test files:
```bash
pytest tests/e2e/test_auth_flow.py -v
```

**Q: Are tests safe to run repeatedly?**
A: Yes, tests use separate sessions and should be idempotent.

**Q: What if I don't have all LLM providers?**
A: Tests will skip provider-specific tests if API keys aren't set.

## Support

For issues or questions:
1. Check this README
2. Review test output and reports
3. Check MCP server logs
4. Verify all prerequisites
5. Create issue with test report attached
