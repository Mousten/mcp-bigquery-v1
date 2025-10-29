"""Tests for prompt builder."""

import pytest
from mcp_bigquery.agent.prompts import PromptBuilder


class TestPromptBuilder:
    """Tests for PromptBuilder."""
    
    def test_build_system_prompt_with_specific_datasets(self):
        """Test building system prompt with specific datasets."""
        allowed_datasets = {"sales", "marketing"}
        allowed_tables = {
            "sales": {"orders", "customers"},
            "marketing": {"campaigns"}
        }
        project_id = "my-project"
        
        prompt = PromptBuilder.build_system_prompt(
            allowed_datasets=allowed_datasets,
            allowed_tables=allowed_tables,
            project_id=project_id
        )
        
        assert "my-project.sales.orders" in prompt
        assert "my-project.sales.customers" in prompt
        assert "my-project.marketing.campaigns" in prompt
        assert "BigQuery" in prompt
    
    def test_build_system_prompt_with_wildcard(self):
        """Test building system prompt with wildcard datasets."""
        allowed_datasets = {"*"}
        allowed_tables = {}
        project_id = "my-project"
        
        prompt = PromptBuilder.build_system_prompt(
            allowed_datasets=allowed_datasets,
            allowed_tables=allowed_tables,
            project_id=project_id
        )
        
        assert "All datasets" in prompt
        assert "my-project" in prompt
    
    def test_build_system_prompt_empty_datasets(self):
        """Test building system prompt with no datasets."""
        prompt = PromptBuilder.build_system_prompt(
            allowed_datasets=set(),
            allowed_tables={},
            project_id="my-project"
        )
        
        assert "No datasets currently accessible" in prompt
        assert "administrator" in prompt
    
    def test_build_sql_generation_prompt(self):
        """Test building SQL generation prompt."""
        prompt = PromptBuilder.build_sql_generation_prompt(
            question="What are the top 5 products?",
            schema_info="Table: products\nColumns: id, name, price",
            conversation_history="[user]: Hello\n[assistant]: Hi there!"
        )
        
        assert "What are the top 5 products?" in prompt
        assert "Table: products" in prompt
        assert "[user]: Hello" in prompt
        assert "JSON object" in prompt
    
    def test_build_summary_prompt(self):
        """Test building summary prompt."""
        prompt = PromptBuilder.build_summary_prompt(
            question="Show me sales",
            sql_query="SELECT * FROM sales",
            results_preview="id=1, amount=100\nid=2, amount=200",
            row_count=50,
            columns=["id", "amount"]
        )
        
        assert "Show me sales" in prompt
        assert "SELECT * FROM sales" in prompt
        assert "Total rows: 50" in prompt
        assert "id, amount" in prompt
    
    def test_build_chart_suggestion_prompt(self):
        """Test building chart suggestion prompt."""
        prompt = PromptBuilder.build_chart_suggestion_prompt(
            result_schema='[{"name": "region", "type": "STRING"}]',
            sample_data='[{"region": "West", "sales": 1000}]',
            row_count=10,
            numeric_columns=["sales"],
            categorical_columns=["region"],
            datetime_columns=[]
        )
        
        assert "region" in prompt
        assert "sales" in prompt
        assert "Row count: 10" in prompt
        assert "chart_type" in prompt
    
    def test_build_clarification_prompt(self):
        """Test building clarification prompt."""
        prompt = PromptBuilder.build_clarification_prompt(
            question="Show me data",
            issue="Need to specify which table",
            datasets=["sales", "marketing"]
        )
        
        assert "Show me data" in prompt
        assert "Need to specify which table" in prompt
        assert "sales" in prompt
        assert "marketing" in prompt
    
    def test_format_conversation_history_empty(self):
        """Test formatting empty conversation history."""
        formatted = PromptBuilder.format_conversation_history([])
        
        assert "No previous conversation" in formatted
    
    def test_format_conversation_history_with_messages(self):
        """Test formatting conversation history with messages."""
        messages = [
            {"role": "user", "content": "Hello", "created_at": "2024-01-01"},
            {"role": "assistant", "content": "Hi there", "created_at": "2024-01-01"},
            {"role": "user", "content": "Show me data"},
        ]
        
        formatted = PromptBuilder.format_conversation_history(messages)
        
        assert "[user" in formatted
        assert "[assistant" in formatted
        assert "Hello" in formatted
        assert "Hi there" in formatted
        assert "Show me data" in formatted
    
    def test_format_conversation_history_limit(self):
        """Test that conversation history respects limit."""
        messages = [
            {"role": "user", "content": f"Message {i}"}
            for i in range(10)
        ]
        
        formatted = PromptBuilder.format_conversation_history(messages, limit=3)
        
        # Should only include last 3 messages
        assert "Message 7" in formatted
        assert "Message 8" in formatted
        assert "Message 9" in formatted
        assert "Message 0" not in formatted
    
    def test_format_schema_info_empty(self):
        """Test formatting empty schema info."""
        formatted = PromptBuilder.format_schema_info([])
        
        assert "No schema information available" in formatted
    
    def test_format_schema_info_with_tables(self):
        """Test formatting schema info with tables."""
        schemas = [
            {
                "table_name": "my-project.sales.orders",
                "fields": [
                    {
                        "name": "order_id",
                        "type": "INTEGER",
                        "mode": "REQUIRED",
                        "description": "Unique order ID"
                    },
                    {
                        "name": "amount",
                        "type": "FLOAT",
                        "mode": "NULLABLE"
                    }
                ]
            }
        ]
        
        formatted = PromptBuilder.format_schema_info(schemas)
        
        assert "my-project.sales.orders" in formatted
        assert "order_id" in formatted
        assert "INTEGER" in formatted
        assert "REQUIRED" in formatted
        assert "Unique order ID" in formatted
        assert "amount" in formatted
        assert "FLOAT" in formatted
    
    def test_format_schema_info_multiple_tables(self):
        """Test formatting schema info with multiple tables."""
        schemas = [
            {
                "table_name": "table1",
                "fields": [{"name": "col1", "type": "STRING", "mode": "NULLABLE"}]
            },
            {
                "table_name": "table2",
                "fields": [{"name": "col2", "type": "INTEGER", "mode": "NULLABLE"}]
            }
        ]
        
        formatted = PromptBuilder.format_schema_info(schemas)
        
        assert "table1" in formatted
        assert "table2" in formatted
        assert "col1" in formatted
        assert "col2" in formatted
