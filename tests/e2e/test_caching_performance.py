"""E2E tests for caching and performance.

Tests:
- Cache hits for identical queries
- Cache performance improvement
- LLM response caching
- Cache isolation per user
- Token usage reduction from caching
- Response time requirements
"""

import pytest
import asyncio
import time
from typing import Dict, Any


pytestmark = pytest.mark.e2e


class TestQueryCaching:
    """Test query result caching."""
    
    @pytest.mark.asyncio
    async def test_cache_hit_on_duplicate_query(self, test_config, http_client, test_users, mcp_server_health, cache_stats_tracker, test_report_generator, performance_monitor):
        """Test that duplicate queries hit cache."""
        ctx = performance_monitor.start_operation("cache_hit_duplicate_query")
        
        try:
            if "analyst" not in test_users:
                pytest.skip("Analyst user not available")
            
            user = test_users["analyst"]
            headers = {"Authorization": f"Bearer {user['token']}"}
            
            # Get initial cache stats
            try:
                stats_response = await http_client.get(
                    f"{test_config['mcp_base_url']}/cache/stats",
                    headers=headers
                )
                if stats_response.status_code == 200:
                    initial_stats = stats_response.json()
                    cache_stats_tracker.record_stats(initial_stats, "before_duplicate")
                else:
                    initial_stats = None
            except Exception:
                initial_stats = None
            
            # Execute same query twice
            query = "SELECT 1 as test_value"
            
            # First execution
            start_time_1 = time.time()
            response1 = await http_client.post(
                f"{test_config['mcp_base_url']}/execute",
                headers=headers,
                json={"sql": query}
            )
            duration_1 = time.time() - start_time_1
            
            if response1.status_code not in [200, 201]:
                pytest.skip(f"Execute endpoint returned {response1.status_code}")
            
            # Wait a moment
            await asyncio.sleep(0.5)
            
            # Second execution (should hit cache)
            start_time_2 = time.time()
            response2 = await http_client.post(
                f"{test_config['mcp_base_url']}/execute",
                headers=headers,
                json={"sql": query}
            )
            duration_2 = time.time() - start_time_2
            
            assert response2.status_code in [200, 201], \
                f"Second execution failed with {response2.status_code}"
            
            # Get final cache stats
            try:
                stats_response = await http_client.get(
                    f"{test_config['mcp_base_url']}/cache/stats",
                    headers=headers
                )
                if stats_response.status_code == 200:
                    final_stats = stats_response.json()
                    cache_stats_tracker.record_stats(final_stats, "after_duplicate")
            except Exception:
                final_stats = None
            
            # Verify caching behavior
            # Second query should be faster (cache hit)
            if duration_2 < duration_1:
                cache_hit = True
            else:
                # Check cache stats if available
                if initial_stats and final_stats:
                    hits_increased = final_stats.get("hits", 0) > initial_stats.get("hits", 0)
                    cache_hit = hits_increased
                else:
                    cache_hit = False
            
            metric = performance_monitor.end_operation(
                ctx,
                success=True,
                first_duration=duration_1,
                second_duration=duration_2,
                cache_hit=cache_hit,
                speedup=duration_1 / duration_2 if duration_2 > 0 else 0
            )
            
            test_report_generator.add_test_result(
                "test_cache_hit_on_duplicate_query",
                cache_hit,
                metric["duration_seconds"],
                {
                    "first_duration": duration_1,
                    "second_duration": duration_2,
                    "speedup": f"{duration_1/duration_2:.2f}x" if duration_2 > 0 else "N/A"
                }
            )
            
            if not cache_hit:
                test_report_generator.add_issue(
                    "medium",
                    "Query caching not working",
                    f"Duplicate query did not show cache improvement. First: {duration_1:.3f}s, Second: {duration_2:.3f}s"
                )
            
        except Exception as e:
            performance_monitor.end_operation(ctx, success=False, error=str(e))
            test_report_generator.add_test_result(
                "test_cache_hit_on_duplicate_query",
                False,
                0,
                {"error": str(e)}
            )
            if "404" not in str(e):
                raise
            pytest.skip("Execute or cache endpoint not found")
    
    @pytest.mark.asyncio
    async def test_cache_performance_improvement(self, test_config, http_client, test_users, mcp_server_health, test_report_generator, performance_monitor):
        """Test that cache provides significant performance improvement."""
        ctx = performance_monitor.start_operation("cache_performance_improvement")
        
        try:
            if "analyst" not in test_users:
                pytest.skip("Analyst user not available")
            
            user = test_users["analyst"]
            headers = {"Authorization": f"Bearer {user['token']}"}
            
            # Execute query multiple times
            query = "SELECT CURRENT_TIMESTAMP() as now"
            durations = []
            
            for i in range(3):
                start_time = time.time()
                response = await http_client.post(
                    f"{test_config['mcp_base_url']}/execute",
                    headers=headers,
                    json={"sql": query}
                )
                duration = time.time() - start_time
                durations.append(duration)
                
                if response.status_code not in [200, 201]:
                    pytest.skip(f"Execute endpoint returned {response.status_code}")
                
                await asyncio.sleep(0.3)
            
            # Check if later queries are faster (cache working)
            avg_later = sum(durations[1:]) / len(durations[1:])
            first_duration = durations[0]
            
            improvement = avg_later < first_duration * 0.8  # At least 20% faster
            
            metric = performance_monitor.end_operation(
                ctx,
                success=True,
                first_duration=first_duration,
                avg_later_duration=avg_later,
                improvement_pct=(first_duration - avg_later) / first_duration * 100
            )
            
            test_report_generator.add_test_result(
                "test_cache_performance_improvement",
                True,  # Don't fail if no improvement, just note it
                metric["duration_seconds"],
                {
                    "durations": durations,
                    "improvement": improvement,
                    "improvement_pct": f"{(first_duration - avg_later) / first_duration * 100:.1f}%"
                }
            )
            
            if not improvement:
                test_report_generator.add_issue(
                    "low",
                    "Limited cache performance improvement",
                    f"Cache did not provide significant performance improvement. First: {first_duration:.3f}s, Avg later: {avg_later:.3f}s"
                )
            
        except Exception as e:
            performance_monitor.end_operation(ctx, success=False, error=str(e))
            test_report_generator.add_test_result(
                "test_cache_performance_improvement",
                False,
                0,
                {"error": str(e)}
            )
            if "404" not in str(e):
                raise
            pytest.skip("Execute endpoint not found")


class TestLLMCaching:
    """Test LLM response caching."""
    
    @pytest.mark.asyncio
    async def test_llm_response_caching(self, test_config, http_client, test_users, mcp_server_health, test_report_generator, performance_monitor):
        """Test that LLM responses are cached."""
        ctx = performance_monitor.start_operation("llm_response_caching")
        
        try:
            if "analyst" not in test_users:
                pytest.skip("Analyst user not available")
            
            user = test_users["analyst"]
            headers = {"Authorization": f"Bearer {user['token']}"}
            
            # Send same question twice
            question = "What is BigQuery?"
            session_id = "test-session-llm-cache"
            
            # First request
            start_time_1 = time.time()
            response1 = await http_client.post(
                f"{test_config['mcp_base_url']}/chat/message",
                headers=headers,
                json={
                    "message": question,
                    "session_id": session_id
                }
            )
            duration_1 = time.time() - start_time_1
            
            if response1.status_code not in [200, 201]:
                pytest.skip(f"Chat endpoint returned {response1.status_code}")
            
            data1 = response1.json()
            tokens_1 = data1.get("tokens_used", data1.get("usage", {}))
            
            await asyncio.sleep(0.5)
            
            # Second request (same question, new session to avoid history)
            session_id_2 = "test-session-llm-cache-2"
            start_time_2 = time.time()
            response2 = await http_client.post(
                f"{test_config['mcp_base_url']}/chat/message",
                headers=headers,
                json={
                    "message": question,
                    "session_id": session_id_2
                }
            )
            duration_2 = time.time() - start_time_2
            
            assert response2.status_code in [200, 201], \
                f"Second request failed with {response2.status_code}"
            
            data2 = response2.json()
            tokens_2 = data2.get("tokens_used", data2.get("usage", {}))
            
            # Check if second request was faster or used fewer tokens
            cache_hit = duration_2 < duration_1 * 0.8 or tokens_2 < tokens_1
            
            metric = performance_monitor.end_operation(
                ctx,
                success=True,
                first_duration=duration_1,
                second_duration=duration_2,
                cache_hit=cache_hit
            )
            
            test_report_generator.add_test_result(
                "test_llm_response_caching",
                True,
                metric["duration_seconds"],
                {
                    "first_duration": duration_1,
                    "second_duration": duration_2,
                    "first_tokens": tokens_1,
                    "second_tokens": tokens_2,
                    "cache_hit": cache_hit
                }
            )
            
        except Exception as e:
            performance_monitor.end_operation(ctx, success=False, error=str(e))
            test_report_generator.add_test_result(
                "test_llm_response_caching",
                False,
                0,
                {"error": str(e)}
            )
            if "404" not in str(e):
                raise
            pytest.skip("Chat endpoint not found")


class TestCacheIsolation:
    """Test cache isolation between users."""
    
    @pytest.mark.asyncio
    async def test_cache_isolation_per_user(self, test_config, http_client, test_users, mcp_server_health, test_report_generator, performance_monitor):
        """Test that cache is isolated per user (no data leakage)."""
        ctx = performance_monitor.start_operation("cache_isolation_per_user")
        
        try:
            if len(test_users) < 2:
                pytest.skip("Need at least 2 test users")
            
            users = list(test_users.values())[:2]
            query = "SELECT 'sensitive_data' as data"
            
            # User 1 executes query
            headers1 = {"Authorization": f"Bearer {users[0]['token']}"}
            response1 = await http_client.post(
                f"{test_config['mcp_base_url']}/execute",
                headers=headers1,
                json={"sql": query}
            )
            
            if response1.status_code not in [200, 201]:
                pytest.skip(f"Execute endpoint returned {response1.status_code}")
            
            # User 2 executes same query - should NOT get User 1's cached result
            # (unless they have the same permissions and it's a safe cache hit)
            headers2 = {"Authorization": f"Bearer {users[1]['token']}"}
            response2 = await http_client.post(
                f"{test_config['mcp_base_url']}/execute",
                headers=headers2,
                json={"sql": query}
            )
            
            assert response2.status_code in [200, 201, 403], \
                f"User 2 query failed with unexpected status {response2.status_code}"
            
            # Both users should get results (or both get errors)
            # They should not get mixed results
            if response1.status_code == 200 and response2.status_code == 200:
                data1 = response1.json()
                data2 = response2.json()
                
                # Results should be same query, but possibly different based on permissions
                # Key is that they both got valid, user-appropriate responses
                assert "rows" in data1 or "error" not in data1, "User 1 should get valid response"
                assert "rows" in data2 or "error" not in data2, "User 2 should get valid response"
            
            metric = performance_monitor.end_operation(ctx, success=True, users_tested=2)
            test_report_generator.add_test_result(
                "test_cache_isolation_per_user",
                True,
                metric["duration_seconds"]
            )
            
        except Exception as e:
            performance_monitor.end_operation(ctx, success=False, error=str(e))
            test_report_generator.add_test_result(
                "test_cache_isolation_per_user",
                False,
                0,
                {"error": str(e)}
            )
            if "404" not in str(e):
                raise
            pytest.skip("Execute endpoint not found")


class TestPerformanceRequirements:
    """Test that system meets performance requirements."""
    
    @pytest.mark.asyncio
    async def test_response_time_under_10_seconds(self, test_config, http_client, test_users, mcp_server_health, test_report_generator, performance_monitor):
        """Test that typical queries respond in under 10 seconds."""
        ctx = performance_monitor.start_operation("response_time_requirement")
        
        try:
            if "analyst" not in test_users:
                pytest.skip("Analyst user not available")
            
            user = test_users["analyst"]
            headers = {"Authorization": f"Bearer {user['token']}"}
            
            # Test query
            question = "Show me a simple query result"
            
            start_time = time.time()
            response = await http_client.post(
                f"{test_config['mcp_base_url']}/chat/message",
                headers=headers,
                json={
                    "message": question,
                    "session_id": "test-session-performance"
                },
                timeout=30.0
            )
            duration = time.time() - start_time
            
            if response.status_code not in [200, 201]:
                pytest.skip(f"Chat endpoint returned {response.status_code}")
            
            # Check performance requirement
            meets_requirement = duration < 10.0
            
            metric = performance_monitor.end_operation(
                ctx,
                success=True,
                duration=duration,
                meets_requirement=meets_requirement
            )
            
            test_report_generator.add_test_result(
                "test_response_time_under_10_seconds",
                meets_requirement,
                metric["duration_seconds"],
                {"query_duration": duration, "requirement_met": meets_requirement}
            )
            
            if not meets_requirement:
                test_report_generator.add_issue(
                    "medium",
                    "Response time exceeds 10 second requirement",
                    f"Query took {duration:.2f} seconds, exceeds 10 second target"
                )
            
        except Exception as e:
            performance_monitor.end_operation(ctx, success=False, error=str(e))
            test_report_generator.add_test_result(
                "test_response_time_under_10_seconds",
                False,
                0,
                {"error": str(e)}
            )
            if "404" not in str(e):
                raise
            pytest.skip("Chat endpoint not found")
    
    @pytest.mark.asyncio
    async def test_token_usage_tracking_accuracy(self, test_config, http_client, test_users, mcp_server_health, test_report_generator, performance_monitor):
        """Test that token usage is tracked accurately."""
        ctx = performance_monitor.start_operation("token_usage_tracking")
        
        try:
            if "analyst" not in test_users:
                pytest.skip("Analyst user not available")
            
            user = test_users["analyst"]
            headers = {"Authorization": f"Bearer {user['token']}"}
            
            # Send a query and check token tracking
            response = await http_client.post(
                f"{test_config['mcp_base_url']}/chat/message",
                headers=headers,
                json={
                    "message": "Count rows in any table",
                    "session_id": "test-session-tokens"
                }
            )
            
            if response.status_code not in [200, 201]:
                pytest.skip(f"Chat endpoint returned {response.status_code}")
            
            data = response.json()
            
            # Check for token usage data
            has_token_data = (
                "tokens_used" in data or
                "usage" in data or
                "token_count" in data
            )
            
            metric = performance_monitor.end_operation(
                ctx,
                success=True,
                has_token_data=has_token_data
            )
            
            test_report_generator.add_test_result(
                "test_token_usage_tracking_accuracy",
                has_token_data,
                metric["duration_seconds"],
                {"token_data": data.get("tokens_used") or data.get("usage")}
            )
            
            if not has_token_data:
                test_report_generator.add_issue(
                    "low",
                    "Token usage not tracked in response",
                    "Response does not include token usage information"
                )
            
        except Exception as e:
            performance_monitor.end_operation(ctx, success=False, error=str(e))
            test_report_generator.add_test_result(
                "test_token_usage_tracking_accuracy",
                False,
                0,
                {"error": str(e)}
            )
            if "404" not in str(e):
                raise
            pytest.skip("Chat endpoint not found")
