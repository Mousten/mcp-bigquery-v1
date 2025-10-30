#!/bin/bash
# E2E Test Environment Setup Script
#
# This script helps set up the environment for running E2E tests.
# It checks prerequisites and guides you through configuration.

set -e

echo "=================================================="
echo "E2E Test Environment Setup"
echo "=================================================="
echo ""

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check if .env file exists
if [ ! -f .env ]; then
    echo -e "${YELLOW}⚠️  No .env file found${NC}"
    echo "Creating .env from .env.example..."
    
    if [ -f .env.example ]; then
        cp .env.example .env
        echo -e "${GREEN}✅ Created .env file${NC}"
        echo "Please edit .env and fill in your credentials."
    else
        echo -e "${RED}❌ .env.example not found${NC}"
        exit 1
    fi
else
    echo -e "${GREEN}✅ .env file exists${NC}"
fi

echo ""
echo "Checking required environment variables..."
echo ""

# Function to check env var
check_env_var() {
    local var_name=$1
    local var_value=$(grep "^${var_name}=" .env 2>/dev/null | cut -d '=' -f 2-)
    
    if [ -z "$var_value" ] || [ "$var_value" = "your-value-here" ] || [ "$var_value" = "TODO" ]; then
        echo -e "  ${RED}❌ ${var_name}${NC} - Not set or placeholder"
        return 1
    else
        echo -e "  ${GREEN}✅ ${var_name}${NC} - Set"
        return 0
    fi
}

# Check required variables
required_vars=(
    "PROJECT_ID"
    "SUPABASE_URL"
    "SUPABASE_KEY"
    "SUPABASE_JWT_SECRET"
)

all_required_set=true
for var in "${required_vars[@]}"; do
    if ! check_env_var "$var"; then
        all_required_set=false
    fi
done

echo ""
echo "Checking optional LLM provider keys..."
echo ""

# Check LLM provider keys
llm_keys=(
    "OPENAI_API_KEY"
    "ANTHROPIC_API_KEY"
    "GOOGLE_API_KEY"
)

has_llm_key=false
for var in "${llm_keys[@]}"; do
    if check_env_var "$var"; then
        has_llm_key=true
    fi
done

if [ "$has_llm_key" = false ]; then
    echo -e "${YELLOW}⚠️  No LLM provider keys set. Some tests will be skipped.${NC}"
fi

echo ""
echo "=================================================="
echo ""

if [ "$all_required_set" = false ]; then
    echo -e "${RED}❌ Required environment variables missing${NC}"
    echo "Please edit .env and set all required variables."
    echo ""
    echo "Required variables:"
    for var in "${required_vars[@]}"; do
        echo "  - $var"
    done
    echo ""
    exit 1
fi

echo -e "${GREEN}✅ All required environment variables are set${NC}"
echo ""

# Check if MCP server is running
echo "Checking MCP server..."
MCP_URL=$(grep "^MCP_BASE_URL=" .env 2>/dev/null | cut -d '=' -f 2- | tr -d ' ' || echo "http://localhost:8000")

if curl -s -f -o /dev/null "${MCP_URL}/health" 2>/dev/null; then
    echo -e "${GREEN}✅ MCP server is running at ${MCP_URL}${NC}"
else
    echo -e "${YELLOW}⚠️  MCP server not accessible at ${MCP_URL}${NC}"
    echo ""
    echo "To start the MCP server, run:"
    echo "  uvicorn mcp_bigquery.main:app --reload"
    echo "  OR"
    echo "  python -m mcp_bigquery.main http"
    echo ""
fi

echo ""
echo "=================================================="
echo ""

# Check Python dependencies
echo "Checking Python dependencies..."
if command -v uv &> /dev/null; then
    echo -e "${GREEN}✅ uv package manager found${NC}"
    echo "Installing dependencies..."
    uv sync --dev
    echo -e "${GREEN}✅ Dependencies installed${NC}"
elif command -v pip &> /dev/null; then
    echo -e "${YELLOW}⚠️  uv not found, using pip${NC}"
    echo "Installing dependencies..."
    pip install -e ".[dev]"
    echo -e "${GREEN}✅ Dependencies installed${NC}"
else
    echo -e "${RED}❌ No Python package manager found${NC}"
    echo "Please install uv or pip"
    exit 1
fi

echo ""
echo "=================================================="
echo ""

# Check test users
echo "Test User Setup"
echo "---------------"
echo ""
echo "E2E tests require test users in Supabase with different roles:"
echo ""
echo "  1. test-admin@example.com (Admin role)"
echo "  2. test-analyst@example.com (Analyst role)"
echo "  3. test-viewer@example.com (Viewer role)"
echo "  4. test-restricted@example.com (Restricted role)"
echo ""
echo "Password for all: TestPassword123!"
echo ""
echo "Please create these users in your Supabase project:"
echo "  1. Go to Supabase Dashboard > Authentication > Users"
echo "  2. Add each user with the specified email and password"
echo "  3. Assign appropriate roles in your RBAC tables"
echo ""

read -p "Have you created the test users? (y/N): " -n 1 -r
echo ""

if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo -e "${YELLOW}⚠️  Test users not created. Some tests will be skipped.${NC}"
else
    echo -e "${GREEN}✅ Test users ready${NC}"
fi

echo ""
echo "=================================================="
echo ""

# Check BigQuery setup
echo "BigQuery Setup"
echo "--------------"
echo ""
echo "Ensure your BigQuery project has:"
echo "  - Test datasets accessible"
echo "  - Service account with BigQuery Data Viewer role"
echo "  - KEY_FILE path is correct in .env"
echo ""

KEY_FILE=$(grep "^KEY_FILE=" .env 2>/dev/null | cut -d '=' -f 2-)
if [ -n "$KEY_FILE" ] && [ -f "$KEY_FILE" ]; then
    echo -e "${GREEN}✅ Service account key file found at: ${KEY_FILE}${NC}"
else
    echo -e "${YELLOW}⚠️  Service account key file not found or not set${NC}"
fi

echo ""
echo "=================================================="
echo ""

# Summary
echo "Environment Setup Complete!"
echo ""
echo "Next steps:"
echo "  1. Ensure MCP server is running"
echo "  2. Create test users in Supabase"
echo "  3. Verify BigQuery access"
echo "  4. Run tests with:"
echo ""
echo "     export RUN_E2E_TESTS=true"
echo "     python tests/e2e/run_e2e_tests.py"
echo ""
echo "     OR"
echo ""
echo "     RUN_E2E_TESTS=true pytest tests/e2e/ -v -m e2e"
echo ""
echo "=================================================="
