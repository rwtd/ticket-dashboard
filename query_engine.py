#!/usr/bin/env python3
"""
Hybrid Query Engine for Support Analytics
Uses DuckDB + Vanna AI for natural language queries on local CSV data
"""

import os
import duckdb
import pandas as pd
from pathlib import Path
from typing import Dict, List, Optional, Any
import logging

import requests
import json

class SupportQueryEngine:
    """Local-first query engine for support data using DuckDB + Vanna"""
    
    def __init__(self, gemini_api_key: str):
        """Initialize the query engine"""
        self.gemini_api_key = gemini_api_key
        self.db = duckdb.connect(':memory:')  # In-memory database
        self.schema_info = {}
        self.conversation_context = []  # Store conversation history
        self.last_query_info = {}  # Store info about last query
        self.setup_gemini()
        self.discover_data_sources()
        
    def setup_gemini(self):
        """Initialize Gemini API for SQL generation"""
        try:
            if self.gemini_api_key:
                logging.info("Gemini API key provided, ready for SQL generation")
                self.gemini_ready = True
            else:
                logging.warning("No Gemini API key provided, using manual SQL generation")
                self.gemini_ready = False
            
        except Exception as e:
            logging.error(f"Failed to setup Gemini: {e}")
            self.gemini_ready = False
    
    def generate_conversational_response(self, question: str, sql_result: Dict[str, Any]) -> str:
        """Generate a conversational response using Gemini with context"""
        if not self.gemini_ready:
            return self.format_basic_response(sql_result)
        
        # Build conversation context
        context_summary = ""
        if self.conversation_context:
            recent_context = self.conversation_context[-3:]  # Last 3 exchanges
            context_summary = "Recent conversation:\n" + "\n".join([
                f"Q: {ctx['question']}\nA: {ctx['summary']}" for ctx in recent_context
            ])
        
        # Get data summary
        df = sql_result.get('data', pd.DataFrame())
        data_summary = self.generate_data_insights(df, question)
        
        conversational_prompt = f"""You are a helpful data analyst assistant. Provide conversational, insightful responses to questions about support data.

{context_summary}

Current question: "{question}"
Data results: {data_summary}

Provide a conversational response that:
1. Answers the question naturally
2. Provides context and insights
3. Suggests follow-up questions or analysis
4. Acknowledges previous conversation if relevant
5. Is friendly and helpful, not robotic

Keep it concise but insightful (2-4 sentences max)."""

        # Call Gemini for conversational response
        url = "https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent"
        
        headers = {"Content-Type": "application/json"}
        
        data = {
            "contents": [{
                "role": "user", 
                "parts": [{"text": conversational_prompt}]
            }],
            "generationConfig": {
                "temperature": 0.7,
                "maxOutputTokens": 200,
            }
        }
        
        url += f"?key={self.gemini_api_key}"
        
        try:
            response = requests.post(url, headers=headers, json=data, timeout=30)
            if response.status_code == 200:
                result = response.json()
                if 'candidates' in result and len(result['candidates']) > 0:
                    conversational_text = result['candidates'][0]['content']['parts'][0]['text'].strip()
                    return conversational_text
        except Exception as e:
            logging.error(f"Conversational response failed: {e}")
        
        # Fallback to basic formatting
        return self.format_basic_response(sql_result)
    
    def generate_data_insights(self, df: pd.DataFrame, question: str) -> str:
        """Generate key insights from the data"""
        if len(df) == 0:
            return "No data found"
        
        insights = []
        
        # Key findings based on data
        for col in df.columns:
            if 'count' in col.lower():
                total = df[col].sum()
                max_val = df[col].max()
                insights.append(f"Total {col}: {total:,}, highest: {max_val:,}")
            elif df[col].dtype in ['object', 'string']:
                top_value = df[col].iloc[0] if len(df) > 0 else None
                if top_value:
                    insights.append(f"Top {col}: {top_value}")
        
        # Add row count
        insights.append(f"Found {len(df)} result(s)")
        
        return "; ".join(insights[:3])  # Top 3 insights
    
    def format_basic_response(self, sql_result: Dict[str, Any]) -> str:
        """Fallback formatting when conversational AI unavailable"""
        df = sql_result.get('data', pd.DataFrame())
        if len(df) == 0:
            return "I couldn't find any data matching your query. Try rephrasing your question."
        
        # Create a more natural response
        if len(df) == 1 and 'count' in str(df.columns).lower():
            # Single metric response
            col_name = df.columns[0]
            value = df.iloc[0, 0]
            return f"Looking at your data, I found {value:,} for {col_name}. Would you like me to break this down further or look at a specific time period?"
        else:
            return f"I found {len(df)} results. The top result shows: {df.iloc[0].to_dict()}. What aspect would you like me to explore further?"
    
    def generate_sql_with_gemini(self, question: str) -> str:
        """Generate SQL using Gemini API with conversation context"""
        if not self.gemini_ready:
            raise Exception("Gemini API not available")
        
        schema_context = self.get_schema_context()
        
        # Add conversation context
        context_info = ""
        if self.conversation_context:
            context_info = f"\nRecent conversation context: {self.conversation_context[-2:]}"
        
        system_prompt = f"""You are a SQL expert that generates DuckDB-compatible SQL queries. Consider conversation context when generating queries.

AVAILABLE TABLES AND SCHEMA:
{schema_context}

{context_info}

IMPORTANT RULES:
1. Use DuckDB syntax (supports most PostgreSQL features)
2. Table names are: tickets, chats (views that reference CSV files)
3. Use standard SQL functions and window functions
4. For time calculations, use INTERVAL and date functions  
5. Column names are case sensitive and may contain spaces - use double quotes
6. Use proper aggregations and GROUP BY when needed
7. Return ONLY the SQL query, no explanations or markdown

Examples:
- "What are average response times?" → SELECT AVG(CAST(SPLIT_PART("Time to first agent email reply (HH:mm:ss)", ':', 1) AS DECIMAL) + CAST(SPLIT_PART("Time to first agent email reply (HH:mm:ss)", ':', 2) AS DECIMAL)/60) FROM tickets WHERE "Time to first agent email reply (HH:mm:ss)" IS NOT NULL
- "Which agent handles most tickets?" → SELECT "Ticket owner", COUNT(*) FROM tickets WHERE "Ticket owner" IS NOT NULL GROUP BY "Ticket owner" ORDER BY COUNT(*) DESC
- "Show monthly volume" → SELECT DATE_TRUNC('month', CAST("Create date" AS DATE)) as month, COUNT(*) FROM tickets GROUP BY month ORDER BY month"""

        user_prompt = f"Question: {question}\n\nGenerate the SQL query:"
        full_prompt = f"{system_prompt}\n\nUser: {user_prompt}"
        
        # Call Gemini API (same as in Flask app)
        url = "https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent"
        
        headers = {
            "Content-Type": "application/json",
        }
        
        data = {
            "contents": [{
                "role": "user",
                "parts": [{"text": full_prompt}]
            }],
            "generationConfig": {
                "temperature": 0.1,
                "maxOutputTokens": 500,
            }
        }
        
        url += f"?key={self.gemini_api_key}"
        
        response = requests.post(url, headers=headers, json=data, timeout=30)
        
        if response.status_code == 200:
            result = response.json()
            if 'candidates' in result and len(result['candidates']) > 0:
                sql = result['candidates'][0]['content']['parts'][0]['text'].strip()
                
                # Clean up common formatting issues
                if sql.startswith('```sql'):
                    sql = sql.replace('```sql', '').replace('```', '').strip()
                elif sql.startswith('```'):
                    sql = sql.replace('```', '').strip()
                
                return sql
            else:
                raise Exception("No response generated")
        else:
            error_data = response.json() if response.headers.get('content-type', '').startswith('application/json') else {}
            raise Exception(f"API Error: {response.status_code} - {error_data}")
    
    def discover_data_sources(self):
        """Discover and register CSV files as virtual tables"""
        self.schema_info = {}
        
        # Check tickets directory
        tickets_dir = Path("tickets")
        if tickets_dir.exists():
            csv_files = list(tickets_dir.glob("*.csv"))
            if csv_files:
                # Use most recent ticket file
                latest_ticket = max(csv_files, key=lambda x: x.stat().st_mtime)
                self.register_csv_table(latest_ticket, "tickets")
        
        # Check chats directory  
        chats_dir = Path("chats")
        if chats_dir.exists():
            csv_files = list(chats_dir.glob("*.csv"))
            if csv_files:
                # Use most recent chat file
                latest_chat = max(csv_files, key=lambda x: x.stat().st_mtime)
                self.register_csv_table(latest_chat, "chats")
        
        logging.info(f"Discovered {len(self.schema_info)} data sources")
    
    def register_csv_table(self, csv_path: Path, table_name: str):
        """Register a CSV file as a virtual table in DuckDB"""
        try:
            # Get schema information
            sample_df = pd.read_csv(csv_path, nrows=5)
            
            # Create view in DuckDB that references the CSV directly
            self.db.execute(f"""
                CREATE OR REPLACE VIEW {table_name} AS 
                SELECT * FROM read_csv_auto('{csv_path.absolute()}')
            """)
            
            # Store schema info for Vanna
            self.schema_info[table_name] = {
                'path': str(csv_path),
                'columns': list(sample_df.columns),
                'dtypes': {col: str(dtype) for col, dtype in sample_df.dtypes.items()},
                'sample_values': sample_df.head(2).to_dict('records')
            }
            
            logging.info(f"Registered {table_name} with {len(sample_df.columns)} columns")
            
        except Exception as e:
            logging.error(f"Failed to register {csv_path}: {e}")
    
    def get_schema_context(self) -> str:
        """Generate schema context for Vanna/LLM"""
        context_parts = []
        
        for table_name, info in self.schema_info.items():
            context_parts.append(f"""
TABLE: {table_name}
COLUMNS: {', '.join(info['columns'][:20])}{'...' if len(info['columns']) > 20 else ''}
SAMPLE DATA: {info['sample_values'][:2]}
""")
        
        return '\n'.join(context_parts)
    
    def query(self, question: str) -> Dict[str, Any]:
        """Execute a natural language query and return conversational results"""
        try:
            # Generate SQL
            if self.gemini_ready:
                sql = self.generate_sql_with_gemini(question)
            else:
                sql = self.manual_sql_generation(question)
            
            # Clean up the SQL
            sql = sql.strip().rstrip(';')
            
            logging.info(f"Generated SQL: {sql}")
            
            # Execute query
            result_df = self.db.execute(sql).fetchdf()
            
            # Prepare result dictionary
            result = {
                'success': True,
                'sql': sql,
                'data': result_df,
                'summary': self.generate_summary(result_df, question),
                'row_count': len(result_df)
            }
            
            # Generate conversational response
            conversational_response = self.generate_conversational_response(question, result)
            result['conversational_response'] = conversational_response
            
            # Store in conversation context
            self.conversation_context.append({
                'question': question,
                'summary': self.generate_data_insights(result_df, question),
                'sql': sql
            })
            
            # Keep only last 5 exchanges
            if len(self.conversation_context) > 5:
                self.conversation_context = self.conversation_context[-5:]
            
            # Store last query info for follow-ups
            self.last_query_info = {
                'question': question,
                'result_df': result_df,
                'sql': sql
            }
            
            return result
            
        except Exception as e:
            logging.error(f"Query failed: {e}")
            return {
                'success': False,
                'error': str(e),
                'sql': sql if 'sql' in locals() else None,
                'suggestion': self.suggest_alternative(question),
                'conversational_response': f"I had trouble with that query. {self.suggest_alternative(question)}"
            }
    
    def manual_sql_generation(self, question: str) -> str:
        """Fallback SQL generation for common queries"""
        question_lower = question.lower()
        
        if 'response time' in question_lower or ('average' in question_lower and 'time' in question_lower):
            return """
            SELECT 
                'Time to first agent email reply (HH:mm:ss)' as metric,
                COUNT(*) as ticket_count,
                AVG(CASE 
                    WHEN "Time to first agent email reply (HH:mm:ss)" LIKE '%:%' 
                    THEN CAST(SPLIT_PART("Time to first agent email reply (HH:mm:ss)", ':', 1) AS DECIMAL) + 
                         CAST(SPLIT_PART("Time to first agent email reply (HH:mm:ss)", ':', 2) AS DECIMAL)/60
                    ELSE NULL 
                END) as avg_hours
            FROM tickets 
            WHERE "Time to first agent email reply (HH:mm:ss)" IS NOT NULL 
                AND "Time to first agent email reply (HH:mm:ss)" != ''
            """
            
        elif 'agent' in question_lower and ('most' in question_lower or 'handles' in question_lower):
            return """
            SELECT 
                "Ticket owner",
                COUNT(*) as ticket_count,
                COUNT(*) * 100.0 / SUM(COUNT(*)) OVER() as percentage
            FROM tickets 
            WHERE "Ticket owner" IS NOT NULL 
                AND "Ticket owner" != ''
            GROUP BY "Ticket owner"
            ORDER BY ticket_count DESC
            LIMIT 10
            """
            
        elif 'volume' in question_lower or ('ticket' in question_lower and 'count' in question_lower):
            return """
            SELECT 
                DATE_TRUNC('month', CAST("Create date" AS DATE)) as month,
                COUNT(*) as ticket_count
            FROM tickets 
            WHERE "Create date" IS NOT NULL
            GROUP BY DATE_TRUNC('month', CAST("Create date" AS DATE))
            ORDER BY month DESC
            LIMIT 12
            """
            
        else:
            # Default: show available data
            return "SELECT COUNT(*) as total_tickets FROM tickets"
    
    def generate_summary(self, result_df: pd.DataFrame, question: str) -> str:
        """Generate a human-readable summary of query results"""
        if len(result_df) == 0:
            return "No results found for your query."
        
        summary = []
        summary.append(f"Found {len(result_df)} result(s) for: '{question}'")
        
        # Show key insights based on data
        for col in result_df.columns:
            if 'count' in col.lower():
                total = result_df[col].sum()
                summary.append(f"Total {col}: {total:,}")
            elif 'average' in col.lower() or 'avg' in col.lower():
                avg_val = result_df[col].mean()
                summary.append(f"Average {col}: {avg_val:.2f}")
        
        return '\n'.join(summary)
    
    def suggest_alternative(self, question: str) -> str:
        """Suggest alternative queries when one fails"""
        suggestions = [
            "What are the average response times?",
            "Which agent handles the most tickets?",
            "Show me ticket volume by month",
            "How many tickets were created this year?",
            "What are the top 5 ticket categories?"
        ]
        
        return f"Try asking: {', '.join(suggestions[:3])}"
    
    def get_available_tables(self) -> Dict[str, Any]:
        """Get information about available tables"""
        return self.schema_info
    
    def test_connection(self) -> Dict[str, Any]:
        """Test the query engine setup"""
        try:
            # Test DuckDB
            test_result = self.db.execute("SELECT 'DuckDB is working!' as status").fetchone()
            
            # Test data access
            available_tables = list(self.schema_info.keys())
            
            return {
                'success': True,
                'duckdb_status': test_result[0] if test_result else 'OK',
                'available_tables': available_tables,
                'total_tables': len(available_tables),
                'gemini_ready': getattr(self, 'gemini_ready', False)
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }

# Utility functions for Flask integration
def create_query_engine(gemini_api_key: str) -> SupportQueryEngine:
    """Factory function to create a query engine instance"""
    return SupportQueryEngine(gemini_api_key)

def format_query_response(result: Dict[str, Any]) -> str:
    """Format query response for display in chat interface"""
    if not result['success']:
        return result.get('conversational_response', f"❌ Query failed: {result['error']}")
    
    # Use conversational response if available
    if 'conversational_response' in result:
        response = result['conversational_response']
        
        # Optionally add SQL query for transparency (smaller/less prominent)
        if result.get('sql'):
            response += f"\n\n<details><summary>📊 View SQL Query</summary>\n\n```sql\n{result['sql']}\n```\n</details>"
        
        return response
    
    # Fallback to old format if no conversational response
    df = result['data']
    summary = result['summary']
    
    response_parts = []
    response_parts.append(summary)
    response_parts.append("")
    
    # Show key data points conversationally
    if len(df) == 1:
        # Single result - make it conversational
        row = df.iloc[0]
        key_findings = []
        for col, val in row.items():
            if pd.notna(val):
                if isinstance(val, (int, float)):
                    key_findings.append(f"{col}: {val:,}")
                else:
                    key_findings.append(f"{col}: {val}")
        
        response_parts.append("Here's what I found: " + ", ".join(key_findings))
    else:
        # Multiple results - show top few
        response_parts.append(f"I found {len(df)} results. Here are the top ones:")
        for idx, row in df.head(5).iterrows():
            row_summary = []
            for col, val in row.items():
                if pd.notna(val) and len(row_summary) < 3:  # Show top 3 columns
                    if isinstance(val, (int, float)):
                        row_summary.append(f"{col}: {val:,}")
                    else:
                        row_summary.append(f"{col}: {val}")
            response_parts.append(f"• {', '.join(row_summary)}")
    
    return '\n'.join(response_parts)