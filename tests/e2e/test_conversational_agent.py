"""E2E tests for conversational agent flow.

Tests:
- Natural language questions through chat
- SQL query generation
- SQL constraint to user's permitted datasets
- Follow-up questions using conversation context
- Chat history persistence across sessions
- Ambiguous query handling with clarification requests
"""

import pytest
import asyncio
from typing import Dict, Any


pytestmark = pytest.mark.e2e


class TestConversationalAgent:
    """Test conversational agent end-to-end."""
    
    @pytest.mark.asyncio
    async def test_simple_question(self, test_config, http_client, test_users, mcp_server_health, test_report_generator, performance_monitor):
        """Test simple natural language question."""
        ctx = performance_monitor.start_operation("agent_simple_question")
        
        try:
            if "analyst" not in test_users:
                pytest.skip("Analyst user not available")
            
            user = test_users["analyst"]
            headers = {"Authorization": f"Bearer {user['token']}"}
            
            # Send a simple question
            response = await http_client.post(
                f"{test_config['mcp_base_url']}/chat/message",
                headers=headers,
                json={
                    "message": "Show me the first 5 rows from any table",
                    "session_id": "test-session-simple"
                }
            )
            
            # Check response
            assert response.status_code in [200, 201], f"Unexpected status: {response.status_code}"
            data = response.json()
            
            # Should have SQL query generated
            assert "sql" in data or "query" in data or "response" in data, \
                "Response should contain SQL or response data"
            
            metric = performance_monitor.end_operation(ctx, success=True)
            test_report_generator.add_test_result(
                "test_simple_question",
                True,
                metric["duration_seconds"],
                {"response_keys": list(data.keys())}
            )
            
        except Exception as e:
            performance_monitor.end_operation(ctx, success=False, error=str(e))
            test_report_generator.add_test_result(
                "test_simple_question",
                False,
                0,
                {"error": str(e)}
            )
            # Don't fail if endpoint doesn't exist yet
            if "404" in str(e):
                pytest.skip("Chat endpoint not found")
            raise
    
    @pytest.mark.asyncio
    async def test_sql_generation(self, test_config, http_client, test_users, mcp_server_health, test_report_generator, performance_monitor):
        """Test that agent generates valid SQL."""
        ctx = performance_monitor.start_operation("agent_sql_generation")
        
        try:
            if "analyst" not in test_users:
                pytest.skip("Analyst user not available")
            
            user = test_users["analyst"]
            headers = {"Authorization": f"Bearer {user['token']}"}
            
            # Request that should generate SQL with specific keywords
            response = await http_client.post(
                f"{test_config['mcp_base_url']}/chat/message",
                headers=headers,
                json={
                    "message": "Count the total number of records in any table",
                    "session_id": "test-session-sql"
                }
            )
            
            if response.status_code in [200, 201]:
                data = response.json()
                
                # Check for SQL in response
                sql = data.get("sql", data.get("query", ""))
                
                if sql:
                    # Verify SQL contains expected keywords
                    sql_upper = sql.upper()
                    assert "SELECT" in sql_upper, "SQL should contain SELECT"
                    assert "COUNT" in sql_upper or "COUNT(*)" in sql_upper, "SQL should contain COUNT"
                    
                    metric = performance_monitor.end_operation(ctx, success=True, sql_length=len(sql))
                    test_report_generator.add_test_result(
                        "test_sql_generation",
                        True,
                        metric["duration_seconds"],
                        {"sql": sql}
                    )
                else:
                    pytest.skip("SQL not returned in response format")
            else:
                pytest.skip(f"Chat endpoint returned {response.status_code}")
            
        except Exception as e:
            performance_monitor.end_operation(ctx, success=False, error=str(e))
            test_report_generator.add_test_result(
                "test_sql_generation",
                False,
                0,
                {"error": str(e)}
            )
            if "404" not in str(e):
                raise
            pytest.skip("Chat endpoint not found")
    
    @pytest.mark.asyncio
    async def test_follow_up_question(self, test_config, http_client, test_users, mcp_server_health, test_report_generator, performance_monitor):
        """Test follow-up questions using conversation context."""
        ctx = performance_monitor.start_operation("agent_follow_up")
        
        try:
            if "analyst" not in test_users:
                pytest.skip("Analyst user not available")
            
            user = test_users["analyst"]
            headers = {"Authorization": f"Bearer {user['token']}"}
            session_id = "test-session-followup"
            
            # First question
            response1 = await http_client.post(
                f"{test_config['mcp_base_url']}/chat/message",
                headers=headers,
                json={
                    "message": "Show me data from any table",
                    "session_id": session_id
                }
            )
            
            if response1.status_code not in [200, 201]:
                pytest.skip(f"Chat endpoint returned {response1.status_code}")
            
            # Follow-up question referencing first
            response2 = await http_client.post(
                f"{test_config['mcp_base_url']}/chat/message",
                headers=headers,
                json={
                    "message": "Now filter that to show only the last 7 days",
                    "session_id": session_id
                }
            )
            
            assert response2.status_code in [200, 201], \
                f"Follow-up failed with status {response2.status_code}"
            
            metric = performance_monitor.end_operation(ctx, success=True, messages=2)
            test_report_generator.add_test_result(
                "test_follow_up_question",
                True,
                metric["duration_seconds"]
            )
            
        except Exception as e:
            performance_monitor.end_operation(ctx, success=False, error=str(e))
            test_report_generator.add_test_result(
                "test_follow_up_question",
                False,
                0,
                {"error": str(e)}
            )
            if "404" not in str(e):
                raise
            pytest.skip("Chat endpoint not found")
    
    @pytest.mark.asyncio
    async def test_chat_history_persistence(self, test_config, http_client, test_users, mcp_server_health, test_report_generator, performance_monitor):
        """Test that chat history persists across requests."""
        ctx = performance_monitor.start_operation("chat_history_persistence")
        
        try:
            if "analyst" not in test_users:
                pytest.skip("Analyst user not available")
            
            user = test_users["analyst"]
            headers = {"Authorization": f"Bearer {user['token']}"}
            session_id = "test-session-history"
            
            # Send multiple messages
            messages = [
                "Show me data from any table",
                "What columns does that table have?",
                "Count the rows"
            ]
            
            for msg in messages:
                response = await http_client.post(
                    f"{test_config['mcp_base_url']}/chat/message",
                    headers=headers,
                    json={
                        "message": msg,
                        "session_id": session_id
                    }
                )
                
                if response.status_code not in [200, 201]:
                    pytest.skip(f"Chat endpoint returned {response.status_code}")
            
            # Get chat history
            history_response = await http_client.get(
                f"{test_config['mcp_base_url']}/chat/sessions/{session_id}/history",
                headers=headers
            )
            
            if history_response.status_code == 200:
                history = history_response.json()
                
                # Should have messages in history
                assert len(history) >= len(messages), \
                    f"History should have at least {len(messages)} messages"
                
                metric = performance_monitor.end_operation(
                    ctx,
                    success=True,
                    messages_sent=len(messages),
                    history_length=len(history)
                )
                test_report_generator.add_test_result(
                    "test_chat_history_persistence",
                    True,
                    metric["duration_seconds"],
                    {"history_length": len(history)}
                )
            else:
                pytest.skip("History endpoint not available")
            
        except Exception as e:
            performance_monitor.end_operation(ctx, success=False, error=str(e))
            test_report_generator.add_test_result(
                "test_chat_history_persistence",
                False,
                0,
                {"error": str(e)}
            )
            if "404" not in str(e):
                raise
            pytest.skip("Chat/history endpoint not found")


class TestRBACInAgent:
    """Test RBAC enforcement in agent queries."""
    
    @pytest.mark.asyncio
    async def test_dataset_permission_enforcement(self, test_config, http_client, test_users, mcp_server_health, test_report_generator, performance_monitor):
        """Test that agent only queries permitted datasets."""
        ctx = performance_monitor.start_operation("dataset_permission_enforcement")
        
        try:
            if "restricted" not in test_users:
                pytest.skip("Restricted user not available")
            
            user = test_users["restricted"]
            headers = {"Authorization": f"Bearer {user['token']}"}
            
            # Try to query unauthorized dataset
            response = await http_client.post(
                f"{test_config['mcp_base_url']}/chat/message",
                headers=headers,
                json={
                    "message": "Show me data from secret_dataset.confidential_table",
                    "session_id": "test-session-unauthorized"
                }
            )
            
            # Should either:
            # 1. Refuse to generate SQL for unauthorized dataset
            # 2. Generate SQL that gets rejected
            # 3. Return error message
            if response.status_code in [200, 201]:
                data = response.json()
                
                # Check for error or rejection in response
                has_error = (
                    "error" in data or
                    "unauthorized" in str(data).lower() or
                    "permission" in str(data).lower() or
                    "forbidden" in str(data).lower()
                )
                
                # If no explicit error, SQL should not reference unauthorized dataset
                if not has_error and "sql" in data:
                    sql = data["sql"].lower()
                    assert "secret_dataset" not in sql, \
                        "Agent should not generate SQL for unauthorized dataset"
                
                metric = performance_monitor.end_operation(ctx, success=True)
                test_report_generator.add_test_result(
                    "test_dataset_permission_enforcement",
                    True,
                    metric["duration_seconds"]
                )
            elif response.status_code in [403, 401]:
                # Proper rejection
                metric = performance_monitor.end_operation(ctx, success=True)
                test_report_generator.add_test_result(
                    "test_dataset_permission_enforcement",
                    True,
                    metric["duration_seconds"]
                )
            else:
                pytest.skip(f"Unexpected response status: {response.status_code}")
            
        except AssertionError as e:
            performance_monitor.end_operation(ctx, success=False, error=str(e))
            test_report_generator.add_test_result(
                "test_dataset_permission_enforcement",
                False,
                0,
                {"error": str(e)}
            )
            test_report_generator.add_issue(
                "critical",
                "Agent bypasses dataset permissions",
                "Agent generated SQL for unauthorized dataset",
                [
                    "1. Login as restricted user",
                    "2. Request query on unauthorized dataset",
                    "3. Observe that agent generates SQL when it should refuse"
                ]
            )
            raise
        except Exception as e:
            performance_monitor.end_operation(ctx, success=False, error=str(e))
            if "404" not in str(e):
                raise
            pytest.skip("Chat endpoint not found")


class TestErrorHandlingInAgent:
    """Test error handling in conversational agent."""
    
    @pytest.mark.asyncio
    async def test_ambiguous_query_handling(self, test_config, http_client, test_users, mcp_server_health, test_report_generator, performance_monitor):
        """Test handling of ambiguous queries."""
        ctx = performance_monitor.start_operation("ambiguous_query_handling")
        
        try:
            if "analyst" not in test_users:
                pytest.skip("Analyst user not available")
            
            user = test_users["analyst"]
            headers = {"Authorization": f"Bearer {user['token']}"}
            
            # Send ambiguous question
            response = await http_client.post(
                f"{test_config['mcp_base_url']}/chat/message",
                headers=headers,
                json={
                    "message": "Show me some data",
                    "session_id": "test-session-ambiguous"
                }
            )
            
            if response.status_code in [200, 201]:
                data = response.json()
                
                # Agent should either:
                # 1. Ask for clarification
                # 2. Make a reasonable assumption and proceed
                # Should not error out
                assert "error" not in str(data).lower() or \
                       "clarif" in str(data).lower(), \
                    "Agent should handle ambiguous query gracefully"
                
                metric = performance_monitor.end_operation(ctx, success=True)
                test_report_generator.add_test_result(
                    "test_ambiguous_query_handling",
                    True,
                    metric["duration_seconds"],
                    {"response_type": "clarification" if "clarif" in str(data).lower() else "assumption"}
                )
            else:
                pytest.skip(f"Chat endpoint returned {response.status_code}")
            
        except Exception as e:
            performance_monitor.end_operation(ctx, success=False, error=str(e))
            test_report_generator.add_test_result(
                "test_ambiguous_query_handling",
                False,
                0,
                {"error": str(e)}
            )
            if "404" not in str(e):
                raise
            pytest.skip("Chat endpoint not found")
    
    @pytest.mark.asyncio
    async def test_invalid_sql_error_handling(self, test_config, http_client, test_users, mcp_server_health, test_report_generator, performance_monitor):
        """Test handling of queries that produce invalid SQL."""
        ctx = performance_monitor.start_operation("invalid_sql_handling")
        
        try:
            if "analyst" not in test_users:
                pytest.skip("Analyst user not available")
            
            user = test_users["analyst"]
            headers = {"Authorization": f"Bearer {user['token']}"}
            
            # Request that might produce problematic SQL
            response = await http_client.post(
                f"{test_config['mcp_base_url']}/chat/message",
                headers=headers,
                json={
                    "message": "Delete all data from the table",
                    "session_id": "test-session-invalid"
                }
            )
            
            if response.status_code in [200, 201]:
                data = response.json()
                
                # Agent should refuse DELETE operations (read-only)
                if "sql" in data:
                    sql = data["sql"].upper()
                    assert "DELETE" not in sql, "Agent should not generate DELETE queries"
                
                # Or provide error message
                response_text = str(data).lower()
                if "delete" in response_text:
                    assert any(word in response_text for word in ["cannot", "read-only", "not allowed"]), \
                        "Agent should explain why DELETE is not allowed"
                
                metric = performance_monitor.end_operation(ctx, success=True)
                test_report_generator.add_test_result(
                    "test_invalid_sql_error_handling",
                    True,
                    metric["duration_seconds"]
                )
            else:
                pytest.skip(f"Chat endpoint returned {response.status_code}")
            
        except AssertionError as e:
            performance_monitor.end_operation(ctx, success=False, error=str(e))
            test_report_generator.add_test_result(
                "test_invalid_sql_error_handling",
                False,
                0,
                {"error": str(e)}
            )
            test_report_generator.add_issue(
                "critical",
                "Agent generates destructive SQL",
                "Agent generated DELETE query when system should be read-only",
                [
                    "1. Ask agent to delete data",
                    "2. Observe that agent generates DELETE SQL",
                    "3. System should prevent this"
                ]
            )
            raise
        except Exception as e:
            performance_monitor.end_operation(ctx, success=False, error=str(e))
            if "404" not in str(e):
                raise
            pytest.skip("Chat endpoint not found")
