"""Example usage of the InsightsAgent for conversational BigQuery analytics."""

import asyncio
import os
from mcp_bigquery.agent import InsightsAgent, AgentRequest
from mcp_bigquery.llm.factory import create_provider_from_env
from mcp_bigquery.client import MCPClient, ClientConfig
from mcp_bigquery.core.supabase_client import SupabaseKnowledgeBase


async def main():
    """Run example agent interactions."""
    
    # Initialize components
    print("Initializing agent components...")
    
    # 1. LLM Provider (OpenAI or Anthropic based on env)
    llm_provider = create_provider_from_env()
    print(f"✓ LLM Provider: {llm_provider.provider_name}")
    
    # 2. MCP Client
    client_config = ClientConfig(
        base_url=os.getenv("MCP_BASE_URL", "http://localhost:8000"),
        auth_token=os.getenv("AUTH_TOKEN")
    )
    mcp_client = MCPClient(client_config)
    print("✓ MCP Client initialized")
    
    # 3. Knowledge Base (Supabase)
    kb = SupabaseKnowledgeBase()
    await kb.verify_connection()
    print("✓ Knowledge Base connected")
    
    # 4. Create Agent
    agent = InsightsAgent(
        llm_provider=llm_provider,
        mcp_client=mcp_client,
        kb=kb,
        project_id=os.getenv("PROJECT_ID", "my-project"),
        enable_caching=True
    )
    print("✓ InsightsAgent created\n")
    
    # Example 1: Simple query
    print("=" * 60)
    print("Example 1: Simple Query")
    print("=" * 60)
    
    request1 = AgentRequest(
        question="What are the top 5 products by revenue?",
        session_id="demo-session-1",
        user_id="demo-user",
        allowed_datasets={"sales"},
        allowed_tables={"sales": {"orders", "products"}},
        context_turns=0  # No previous context
    )
    
    print(f"Question: {request1.question}")
    response1 = await agent.process_question(request1)
    
    if response1.success:
        print(f"\n✓ Success!")
        print(f"\nSQL Query:\n{response1.sql_query}")
        print(f"\nExplanation: {response1.sql_explanation}")
        print(f"\nAnswer:\n{response1.answer}")
        print(f"\nChart Suggestions:")
        for i, chart in enumerate(response1.chart_suggestions, 1):
            print(f"  {i}. {chart.chart_type}: {chart.title}")
            print(f"     {chart.description}")
    else:
        print(f"\n✗ Error: {response1.error}")
    
    # Example 2: Follow-up question using context
    print("\n" + "=" * 60)
    print("Example 2: Follow-up Question with Context")
    print("=" * 60)
    
    request2 = AgentRequest(
        question="What about last quarter?",
        session_id="demo-session-1",  # Same session
        user_id="demo-user",
        allowed_datasets={"sales"},
        allowed_tables={"sales": {"orders", "products"}},
        context_turns=2  # Include previous exchange
    )
    
    print(f"Question: {request2.question}")
    response2 = await agent.process_question(request2)
    
    if response2.success:
        print(f"\n✓ Success!")
        print(f"\nSQL Query:\n{response2.sql_query}")
        print(f"\nAnswer:\n{response2.answer}")
    else:
        print(f"\n✗ Error: {response2.error}")
    
    # Example 3: Permission-restricted query
    print("\n" + "=" * 60)
    print("Example 3: Permission-Restricted Query")
    print("=" * 60)
    
    request3 = AgentRequest(
        question="Show me data from the hr_employees table",
        session_id="demo-session-2",
        user_id="demo-user",
        allowed_datasets={"sales"},  # User only has sales access
        allowed_tables={"sales": {"orders", "products"}},
    )
    
    print(f"Question: {request3.question}")
    response3 = await agent.process_question(request3)
    
    if response3.success:
        print(f"\n✓ Success!")
        print(f"\nAnswer:\n{response3.answer}")
    else:
        print(f"\n✗ Expected error (permission denied):")
        print(f"   Error type: {response3.error_type}")
        print(f"   Message: {response3.error}")
    
    # Example 4: Complex analytical question
    print("\n" + "=" * 60)
    print("Example 4: Complex Analytical Question")
    print("=" * 60)
    
    request4 = AgentRequest(
        question="Compare average order value across regions for the last 6 months",
        session_id="demo-session-3",
        user_id="demo-user",
        allowed_datasets={"sales"},
        allowed_tables={"sales": {"orders", "regions"}},
    )
    
    print(f"Question: {request4.question}")
    response4 = await agent.process_question(request4)
    
    if response4.success:
        print(f"\n✓ Success!")
        print(f"\nSQL Query:\n{response4.sql_query}")
        print(f"\nAnswer:\n{response4.answer}")
        
        if response4.results:
            rows = response4.results.get("rows", [])
            print(f"\nRows returned: {len(rows)}")
            if rows:
                print(f"First row: {rows[0]}")
        
        print(f"\nChart Suggestions:")
        for i, chart in enumerate(response4.chart_suggestions, 1):
            print(f"  {i}. {chart.chart_type}: {chart.title}")
    else:
        print(f"\n✗ Error: {response4.error}")
    
    # Cleanup
    await mcp_client.close()
    print("\n" + "=" * 60)
    print("Demo completed!")
    print("=" * 60)


async def interactive_mode():
    """Interactive REPL mode for the agent."""
    
    print("\n" + "=" * 60)
    print("Interactive Agent Mode")
    print("=" * 60)
    print("Type 'exit' or 'quit' to stop\n")
    
    # Initialize components
    llm_provider = create_provider_from_env()
    client_config = ClientConfig.from_env()
    mcp_client = MCPClient(client_config)
    kb = SupabaseKnowledgeBase()
    
    agent = InsightsAgent(
        llm_provider=llm_provider,
        mcp_client=mcp_client,
        kb=kb,
        project_id=os.getenv("PROJECT_ID", "my-project"),
        enable_caching=True
    )
    
    session_id = "interactive-session"
    user_id = os.getenv("USER_ID", "interactive-user")
    
    # Get user permissions (example)
    allowed_datasets = {"sales", "marketing"}
    allowed_tables = {
        "sales": {"orders", "products", "customers"},
        "marketing": {"campaigns", "leads"}
    }
    
    print(f"Session ID: {session_id}")
    print(f"User ID: {user_id}")
    print(f"Allowed datasets: {', '.join(allowed_datasets)}\n")
    
    while True:
        try:
            question = input("You: ").strip()
            
            if question.lower() in ("exit", "quit"):
                print("Goodbye!")
                break
            
            if not question:
                continue
            
            # Create request
            request = AgentRequest(
                question=question,
                session_id=session_id,
                user_id=user_id,
                allowed_datasets=allowed_datasets,
                allowed_tables=allowed_tables,
                context_turns=5
            )
            
            # Process with agent
            response = await agent.process_question(request)
            
            if response.success:
                print(f"\nAgent: {response.answer}\n")
                
                if response.sql_query:
                    print(f"SQL: {response.sql_query}\n")
                
                if response.chart_suggestions:
                    print("Suggested visualizations:")
                    for chart in response.chart_suggestions[:3]:
                        print(f"  - {chart.chart_type}: {chart.title}")
                    print()
            else:
                print(f"\nError: {response.error}\n")
        
        except KeyboardInterrupt:
            print("\nGoodbye!")
            break
        except Exception as e:
            print(f"\nError: {e}\n")
    
    await mcp_client.close()


if __name__ == "__main__":
    # Run examples
    print("\n" + "=" * 60)
    print("InsightsAgent Examples")
    print("=" * 60)
    
    # Check if required environment variables are set
    required_vars = ["PROJECT_ID", "OPENAI_API_KEY", "SUPABASE_URL", "SUPABASE_KEY"]
    missing_vars = [var for var in required_vars if not os.getenv(var)]
    
    if missing_vars:
        print(f"\n⚠ Warning: Missing environment variables: {', '.join(missing_vars)}")
        print("Some examples may not work correctly.\n")
    
    # Choose mode
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "interactive":
        asyncio.run(interactive_mode())
    else:
        asyncio.run(main())
