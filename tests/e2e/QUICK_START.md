# E2E Tests Quick Start Guide

## TL;DR

```bash
# 1. Setup environment
./tests/e2e/setup_test_environment.sh

# 2. Start MCP server (in another terminal)
uvicorn mcp_bigquery.main:app --reload

# 3. Run tests
export RUN_E2E_TESTS=true
python tests/e2e/run_e2e_tests.py
```

## What Gets Tested?

✅ **Authentication** - Login, tokens, sessions, RBAC  
✅ **LLM Providers** - OpenAI & Anthropic integration  
✅ **Conversational Agent** - Natural language → SQL → Results  
✅ **Caching** - Query & LLM response caching  
✅ **Performance** - Response times, token usage  
✅ **Security** - RBAC enforcement, data isolation  

## Prerequisites

1. **Environment Variables** (copy from `.env.example`)
   ```bash
   PROJECT_ID=your-gcp-project
   SUPABASE_URL=https://xxx.supabase.co
   SUPABASE_KEY=xxx
   SUPABASE_SERVICE_KEY=xxx
   SUPABASE_JWT_SECRET=xxx
   OPENAI_API_KEY=sk-...        # Optional
   ANTHROPIC_API_KEY=sk-ant-... # Optional
   ```

2. **Test Users in Supabase**
   - `test-admin@example.com` (password: `TestPassword123!`)
   - `test-analyst@example.com` (password: `TestPassword123!`)
   - `test-viewer@example.com` (password: `TestPassword123!`)
   - `test-restricted@example.com` (password: `TestPassword123!`)

3. **Running MCP Server**
   ```bash
   uvicorn mcp_bigquery.main:app --reload
   # Should be accessible at http://localhost:8000
   ```

## Running Tests

### Option 1: Full Test Suite with Report (Recommended)
```bash
export RUN_E2E_TESTS=true
python tests/e2e/run_e2e_tests.py
```
- Checks prerequisites
- Runs all tests
- Generates comprehensive report
- Report saved to `test_results/E2E_TEST_REPORT.md`

### Option 2: Using pytest
```bash
RUN_E2E_TESTS=true pytest tests/e2e/ -v -m e2e
```

### Option 3: Run Specific Tests
```bash
# Authentication tests only
RUN_E2E_TESTS=true pytest tests/e2e/test_auth_flow.py -v

# LLM integration tests only
RUN_E2E_TESTS=true pytest tests/e2e/test_llm_integration.py -v

# Caching tests only
RUN_E2E_TESTS=true pytest tests/e2e/test_caching_performance.py -v
```

## Test Results

After running, check:
- **Terminal Output** - Pass/fail summary
- **test_results/E2E_TEST_REPORT.md** - Detailed report
- **test_results/e2e_report.json** - Machine-readable results

## Common Issues

### "MCP server not accessible"
```bash
# Start the server
uvicorn mcp_bigquery.main:app --reload
```

### "Test users not found"
Create users in Supabase Dashboard → Authentication → Users

### "Tests are skipped"
```bash
# Make sure to enable E2E tests
export RUN_E2E_TESTS=true
```

### "OpenAI/Anthropic tests skipped"
Provider tests require valid API keys. Set:
```bash
export OPENAI_API_KEY=sk-...
export ANTHROPIC_API_KEY=sk-ant-...
```

## What's Tested

| Test Area | Tests | Coverage |
|-----------|-------|----------|
| **Authentication** | 8 tests | Login, tokens, RBAC, session persistence |
| **LLM Integration** | 7 tests | OpenAI, Anthropic, token counting, errors |
| **Conversational Agent** | 8 tests | NL→SQL, follow-ups, history, RBAC |
| **Caching & Performance** | 8 tests | Cache hits, performance, isolation |
| **Total** | **31 tests** | **Complete system integration** |

## Expected Results

✅ **Production Ready** if:
- All tests pass
- No critical issues
- Response times < 10s
- Cache hit rate > 50%

❌ **Not Production Ready** if:
- Critical issues found
- Authentication failures
- Data leakage detected
- Performance requirements not met

## Need Help?

- Full documentation: `tests/e2e/README.md`
- Implementation details: `E2E_INTEGRATION_TESTING_IMPLEMENTATION.md`
- Setup script: `tests/e2e/setup_test_environment.sh`
