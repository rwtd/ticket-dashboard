#!/usr/bin/env python3
"""
Enhanced Query Engine with Google Sheets Integration
Provides AI access to all historical data and dashboard logic awareness
"""

import os
import duckdb
import pandas as pd
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime, timedelta, date
import logging
import re

import requests
import json

# Import Google Sheets functionality
try:
    from googleapiclient.discovery import build
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from google.oauth2.service_account import Credentials as ServiceAccountCredentials
    from googleapiclient.errors import HttpError
    GOOGLE_SHEETS_AVAILABLE = True
except ImportError:
    GOOGLE_SHEETS_AVAILABLE = False

class EnhancedSupportQueryEngine:
    """Enhanced query engine with Google Sheets integration and dashboard logic awareness"""
    
    def __init__(self, gemini_api_key: str, sheets_credentials_path: str = None):
        """Initialize the enhanced query engine"""
        self.gemini_api_key = gemini_api_key
        self.sheets_credentials_path = sheets_credentials_path
        self.db = duckdb.connect(':memory:')
        self.schema_info = {}
        self.conversation_context = []
        self.sheets_service = None
        self.dashboard_logic = self._load_dashboard_logic()
        
        # Initialize components
        self.setup_gemini()
        self.setup_sheets_connection()
        self.discover_data_sources()
        self.load_sheets_data()
        
    def _load_dashboard_logic(self) -> Dict[str, str]:
        """Load dashboard calculation logic for AI awareness"""
        return {
            'response_time_calculation': """
Response times are calculated by converting 'Time to first agent email reply (HH:mm:ss)' 
from HH:mm:ss format to decimal hours. Formula: hours + (minutes/60) + (seconds/3600).
Weekend responses are flagged separately using schedule.yaml configuration.
""",
            'agent_mapping': """
Agent names are standardized across all data:
- 'Gillie'/'Gillie E'/'Girly E' → 'Girly' 
- 'Shan'/'Shan D' → 'Bhushan'
- 'Chris'/'Chris S' → 'Francis'
- 'Nora'/'Nora N' → 'Nova'
This ensures consistent reporting across tickets and chats.
""",
            'weekend_detection': """
Weekends are defined as Friday 7PM through Monday 6AM based on config/schedule.yaml.
This accounts for reduced staffing and different performance expectations.
Weekend analysis excludes these periods from standard metrics unless specifically requested.
""",
            'timezone_conversion': """
All timestamps are converted to ADT (Atlantic Daylight Time):
- Tickets: CDT → ADT (+1 hour) 
- Chats: UTC → ADT (-3 hours in summer, -4 hours in winter)
This provides consistent local business time for all analytics.
""",
            'bot_detection': """
Chat bots are identified as:
- 'Wynn AI' (sales bot)
- 'Agent Scrape' (support bot, formerly Traject Data Customer Support)
Bot performance is tracked separately with satisfaction ratings and transfer rates.
""",
            'satisfaction_analysis': """
Chat satisfaction uses LiveChat's rating system:
- "rated good" = 5 (positive)
- "rated bad" = 1 (negative)  
- "not rated" = excluded from satisfaction calculations
Bot vs human satisfaction is compared to identify performance gaps.
""",
            'pipeline_filtering': """
Ticket analysis automatically excludes 'SPAM Tickets' pipeline data.
Valid pipelines include main support channels and specialized workflows.
""",
            'volume_trends': """
Volume analysis uses:
- Daily: Individual date breakdown with trend detection
- Weekly: Monday-Sunday periods with 12-week rolling display
- Monthly: Calendar month aggregation with seasonal pattern recognition
""",
            'performance_benchmarks': """
Standard performance targets:
- Response time: <2 hours average (tickets)
- Bot satisfaction: >80% positive rating
- Transfer rate: <30% bot-to-human escalation
- Weekend impact: Expected 1.5x slower response times
"""
        }
    
    def setup_sheets_connection(self):
        """Initialize Google Sheets API connection"""
        if not GOOGLE_SHEETS_AVAILABLE:
            logging.warning("Google Sheets integration unavailable - install google-api-python-client")
            return
            
        if not self.sheets_credentials_path or not Path(self.sheets_credentials_path).exists():
            logging.warning("Google Sheets credentials not found - using local data only")
            return
            
        try:
            if self.sheets_credentials_path.endswith('service_account_credentials.json'):
                # Service account credentials
                credentials = ServiceAccountCredentials.from_service_account_file(
                    self.sheets_credentials_path,
                    scopes=['https://www.googleapis.com/auth/spreadsheets.readonly']
                )
            else:
                # OAuth credentials
                credentials = Credentials.from_authorized_user_file(
                    self.sheets_credentials_path,
                    scopes=['https://www.googleapis.com/auth/spreadsheets.readonly']
                )
                
            self.sheets_service = build('sheets', 'v4', credentials=credentials)
            logging.info("✅ Google Sheets connection established")
            
        except Exception as e:
            logging.error(f"Failed to connect to Google Sheets: {e}")
    
    def load_sheets_data(self):
        """Load data from Google Sheets if available"""
        if not self.sheets_service:
            return
            
        # This would load from your actual sheets
        # For now, we'll use the discover_data_sources method
        logging.info("📊 Loading data from Google Sheets...")
        
        # TODO: Add specific sheet IDs and ranges based on your setup
        # self.load_sheet_data('SHEET_ID', 'Tickets!A:Z', 'tickets_archive')
        # self.load_sheet_data('SHEET_ID', 'Chats!A:Z', 'chats_archive')
    
    def load_sheet_data(self, sheet_id: str, range_name: str, table_name: str):
        """Load specific sheet data into DuckDB"""
        if not self.sheets_service:
            return
            
        try:
            result = self.sheets_service.spreadsheets().values().get(
                spreadsheetId=sheet_id,
                range=range_name
            ).execute()
            
            values = result.get('values', [])
            if not values:
                logging.warning(f"No data found in {range_name}")
                return
                
            # Convert to DataFrame
            df = pd.DataFrame(values[1:], columns=values[0])  # First row as headers
            
            # Register in DuckDB
            self.db.register(table_name, df)
            
            # Store schema info
            self.schema_info[table_name] = {
                'source': 'google_sheets',
                'sheet_id': sheet_id,
                'range': range_name,
                'columns': list(df.columns),
                'dtypes': {col: str(dtype) for col, dtype in df.dtypes.items()},
                'sample_values': df.head(2).to_dict('records'),
                'row_count': len(df)
            }
            
            logging.info(f"✅ Loaded {len(df)} rows from {range_name} into {table_name}")
            
        except Exception as e:
            logging.error(f"Failed to load sheet data: {e}")
    
    def setup_gemini(self):
        """Initialize Gemini API"""
        self.gemini_ready = bool(self.gemini_api_key)
        if self.gemini_ready:
            logging.info("✅ Gemini API ready for enhanced queries")
        else:
            logging.warning("⚠️ No Gemini API key - using fallback responses")
    
    def discover_data_sources(self):
        """Discover and register all available data sources"""
        # Load local CSV files (fallback)
        self._load_local_csv_files()
        
        # If sheets not available, ensure we have local data
        if not self.sheets_service and not self.schema_info:
            logging.warning("No data sources available - check Google Sheets credentials or local CSV files")
    
    def _load_local_csv_files(self):
        """Load local CSV files as fallback"""
        # Check tickets directory
        tickets_dir = Path("tickets")
        if tickets_dir.exists():
            csv_files = list(tickets_dir.glob("*.csv"))
            if csv_files:
                latest_ticket = max(csv_files, key=lambda x: x.stat().st_mtime)
                self.register_csv_table(latest_ticket, "tickets")
        
        # Check chats directory  
        chats_dir = Path("chats")
        if chats_dir.exists():
            csv_files = list(chats_dir.glob("*.csv"))
            if csv_files:
                latest_chat = max(csv_files, key=lambda x: x.stat().st_mtime)
                self.register_csv_table(latest_chat, "chats")
    
    def register_csv_table(self, csv_path: Path, table_name: str):
        """Register a CSV file as a virtual table in DuckDB"""
        try:
            sample_df = pd.read_csv(csv_path, nrows=5)
            
            # Create view in DuckDB
            self.db.execute(f"""
                CREATE OR REPLACE VIEW {table_name} AS 
                SELECT * FROM read_csv_auto('{csv_path.absolute()}')
            """)
            
            # Store schema info
            self.schema_info[table_name] = {
                'source': 'local_csv',
                'path': str(csv_path),
                'columns': list(sample_df.columns),
                'dtypes': {col: str(dtype) for col, dtype in sample_df.dtypes.items()},
                'sample_values': sample_df.head(2).to_dict('records')
            }
            
            logging.info(f"✅ Registered {table_name} from {csv_path}")
            
        except Exception as e:
            logging.error(f"Failed to register {csv_path}: {e}")
    
    def parse_time_range(self, query: str) -> Tuple[Optional[str], Optional[str]]:
        """Parse natural language time ranges from queries"""
        query_lower = query.lower()
        today = date.today()
        
        # Common patterns
        if 'last 35 days' in query_lower or 'past 35 days' in query_lower:
            start_date = today - timedelta(days=35)
            return start_date.isoformat(), today.isoformat()
            
        if 'last 30 days' in query_lower or 'past 30 days' in query_lower:
            start_date = today - timedelta(days=30)
            return start_date.isoformat(), today.isoformat()
            
        if 'this month' in query_lower:
            start_date = today.replace(day=1)
            return start_date.isoformat(), today.isoformat()
            
        if 'last month' in query_lower:
            first_this_month = today.replace(day=1)
            last_month_end = first_this_month - timedelta(days=1)
            last_month_start = last_month_end.replace(day=1)
            return last_month_start.isoformat(), last_month_end.isoformat()
            
        if 'this quarter' in query_lower:
            quarter = (today.month - 1) // 3 + 1
            quarter_start = date(today.year, (quarter - 1) * 3 + 1, 1)
            return quarter_start.isoformat(), today.isoformat()
            
        if 'this year' in query_lower:
            year_start = date(today.year, 1, 1)
            return year_start.isoformat(), today.isoformat()
            
        # Try to extract specific numbers like "last 90 days"
        days_match = re.search(r'(?:last|past)\s+(\d+)\s+days?', query_lower)
        if days_match:
            days = int(days_match.group(1))
            start_date = today - timedelta(days=days)
            return start_date.isoformat(), today.isoformat()
            
        return None, None
    
    def generate_enhanced_sql(self, question: str) -> str:
        """Generate SQL with time range awareness and dashboard logic"""
        if not self.gemini_ready:
            return self.manual_sql_generation(question)
        
        # Parse time range from question
        start_date, end_date = self.parse_time_range(question)
        
        # Get schema context
        schema_context = self.get_enhanced_schema_context()
        
        # Add dashboard logic context
        dashboard_context = self.get_dashboard_logic_context()
        
        # Add time range context
        time_context = ""
        if start_date and end_date:
            time_context = f"""
TIME RANGE DETECTED: {start_date} to {end_date}
- For tickets: Use CREATE DATE column with date filtering
- For chats: Use appropriate date column for the specified range
- Apply timezone conversion as per dashboard logic
"""
        
        system_prompt = f"""You are an expert SQL analyst for a support ticket dashboard with deep knowledge of our business logic.

AVAILABLE DATA SOURCES:
{schema_context}

DASHBOARD CALCULATION LOGIC:
{dashboard_context}

{time_context}

IMPORTANT SQL RULES:
1. Use DuckDB syntax with PostgreSQL compatibility
2. Apply proper timezone conversions (CDT→ADT for tickets, UTC→ADT for chats)  
3. Use standardized agent names (Girly, Bhushan, Francis, Nova)
4. Exclude SPAM pipeline tickets automatically
5. Handle time ranges naturally - if user asks for "last 35 days", filter appropriately
6. Column names may contain spaces - use double quotes
7. For response time calculations, convert HH:mm:ss to decimal hours
8. Apply weekend detection logic when relevant

RESPONSE FORMAT: Return ONLY the SQL query, no explanations or markdown.

Examples:
- "last 35 days average response time" → Filter CREATE_DATE >= CURRENT_DATE - INTERVAL '35 days'
- "which agent handles most tickets this month" → Filter to current month, group by agent
- "bot satisfaction last quarter" → Filter chats to last quarter, analyze bot ratings"""

        user_prompt = f"Generate SQL for: {question}"
        full_prompt = f"{system_prompt}\n\nUser Question: {user_prompt}"
        
        return self.call_gemini_for_sql(full_prompt)
    
    def get_enhanced_schema_context(self) -> str:
        """Generate enhanced schema context with business logic"""
        context_parts = []
        
        for table_name, info in self.schema_info.items():
            source_type = info.get('source', 'unknown')
            row_count = info.get('row_count', 'unknown')
            
            context_parts.append(f"""
TABLE: {table_name} (Source: {source_type}, Rows: {row_count})
COLUMNS: {', '.join(info['columns'][:15])}{'...' if len(info['columns']) > 15 else ''}
SAMPLE DATA: {info['sample_values'][:1]}
BUSINESS CONTEXT: {'Tickets with response times and agent assignments' if 'ticket' in table_name.lower() else 'Chat data with bot interactions and satisfaction ratings' if 'chat' in table_name.lower() else 'Support data'}
""")
        
        return '\n'.join(context_parts)
    
    def get_dashboard_logic_context(self) -> str:
        """Get dashboard calculation logic for AI awareness"""
        return '\n'.join([f"{key.upper()}: {value.strip()}" 
                         for key, value in self.dashboard_logic.items()])
    
    def call_gemini_for_sql(self, prompt: str) -> str:
        """Call Gemini API for SQL generation"""
        url = "https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent"
        
        headers = {"Content-Type": "application/json"}
        
        data = {
            "contents": [{
                "role": "user",
                "parts": [{"text": prompt}]
            }],
            "generationConfig": {
                "temperature": 0.1,
                "maxOutputTokens": 800,
            }
        }
        
        url += f"?key={self.gemini_api_key}"
        
        try:
            response = requests.post(url, headers=headers, json=data, timeout=30)
            
            if response.status_code == 200:
                result = response.json()
                if 'candidates' in result and len(result['candidates']) > 0:
                    sql = result['candidates'][0]['content']['parts'][0]['text'].strip()
                    
                    # Clean up formatting
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
                
        except Exception as e:
            logging.error(f"Gemini SQL generation failed: {e}")
            return self.manual_sql_generation(prompt)
    
    def generate_conversational_response(self, question: str, sql_result: Dict[str, Any]) -> str:
        """Generate conversational response with dashboard logic awareness"""
        if not self.gemini_ready:
            return self.format_basic_response(sql_result)
        
        # Build enhanced context
        context_summary = ""
        if self.conversation_context:
            recent_context = self.conversation_context[-3:]
            context_summary = "Recent conversation:\n" + "\n".join([
                f"Q: {ctx['question']}\nA: {ctx['summary']}" for ctx in recent_context
            ])
        
        # Get data insights with dashboard logic
        df = sql_result.get('data', pd.DataFrame())
        data_summary = self.generate_enhanced_insights(df, question)
        
        # Add dashboard logic explanation if relevant
        logic_explanation = self.get_relevant_dashboard_logic(question)
        
        conversational_prompt = f"""You are an expert support analytics assistant with deep knowledge of our dashboard calculations.

{context_summary}

Current question: "{question}"
Data results: {data_summary}
Dashboard logic context: {logic_explanation}

Provide a conversational response that:
1. Answers the question naturally with specific numbers
2. Explains the calculation methodology when relevant  
3. Provides business context and insights
4. Suggests follow-up questions or deeper analysis
5. References dashboard logic when explaining results
6. Is friendly and insightful, not robotic

Keep it concise but informative (3-5 sentences max)."""

        return self.call_gemini_for_conversation(conversational_prompt)
    
    def get_relevant_dashboard_logic(self, question: str) -> str:
        """Get relevant dashboard logic based on the question"""
        question_lower = question.lower()
        relevant_logic = []
        
        if any(term in question_lower for term in ['response time', 'reply time', 'response']):
            relevant_logic.append(self.dashboard_logic['response_time_calculation'])
            
        if any(term in question_lower for term in ['weekend', 'saturday', 'sunday']):
            relevant_logic.append(self.dashboard_logic['weekend_detection'])
            
        if any(term in question_lower for term in ['agent', 'staff', 'team member']):
            relevant_logic.append(self.dashboard_logic['agent_mapping'])
            
        if any(term in question_lower for term in ['bot', 'ai', 'wynn', 'scrape']):
            relevant_logic.append(self.dashboard_logic['bot_detection'])
            
        if any(term in question_lower for term in ['satisfaction', 'rating', 'good', 'bad']):
            relevant_logic.append(self.dashboard_logic['satisfaction_analysis'])
            
        return '\n'.join(relevant_logic) if relevant_logic else "Standard dashboard calculations apply."
    
    def generate_enhanced_insights(self, df: pd.DataFrame, question: str) -> str:
        """Generate enhanced insights with business context"""
        if len(df) == 0:
            return "No data found for the specified criteria"
        
        insights = []
        
        # Enhanced insights based on data patterns
        for col in df.columns:
            if 'response' in col.lower() and 'time' in col.lower():
                if pd.api.types.is_numeric_dtype(df[col]):
                    avg_time = df[col].mean()
                    insights.append(f"Average response time: {avg_time:.1f} hours")
                    
            elif 'count' in col.lower() or col.lower().endswith('_count'):
                total = df[col].sum()
                max_val = df[col].max()
                insights.append(f"Total {col}: {total:,} (highest single: {max_val:,})")
                
            elif 'agent' in col.lower() or 'owner' in col.lower():
                if len(df) <= 10:  # Show top agents for small result sets
                    top_agents = df[col].value_counts().head(3)
                    agent_summary = ', '.join([f"{agent}: {count}" for agent, count in top_agents.items()])
                    insights.append(f"Top agents: {agent_summary}")
        
        # Add time range context if detected
        start_date, end_date = self.parse_time_range(question)
        if start_date and end_date:
            insights.append(f"Analysis period: {start_date} to {end_date}")
        
        insights.append(f"Dataset: {len(df)} records analyzed")
        
        return '; '.join(insights[:4])  # Top 4 insights
    
    def call_gemini_for_conversation(self, prompt: str) -> str:
        """Call Gemini for conversational response"""
        url = "https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent"
        
        headers = {"Content-Type": "application/json"}
        
        data = {
            "contents": [{
                "role": "user", 
                "parts": [{"text": prompt}]
            }],
            "generationConfig": {
                "temperature": 0.7,
                "maxOutputTokens": 300,
            }
        }
        
        url += f"?key={self.gemini_api_key}"
        
        try:
            response = requests.post(url, headers=headers, json=data, timeout=30)
            if response.status_code == 200:
                result = response.json()
                if 'candidates' in result and len(result['candidates']) > 0:
                    return result['candidates'][0]['content']['parts'][0]['text'].strip()
        except Exception as e:
            logging.error(f"Conversational response failed: {e}")
        
        return self.format_basic_response({'data': pd.DataFrame()})
    
    def query(self, question: str) -> Dict[str, Any]:
        """Execute enhanced query with Google Sheets integration"""
        try:
            # Generate enhanced SQL with time awareness
            sql = self.generate_enhanced_sql(question)
            logging.info(f"Generated enhanced SQL: {sql}")
            
            # Execute query
            result_df = self.db.execute(sql).fetchdf()
            
            # Prepare enhanced result
            result = {
                'success': True,
                'sql': sql,
                'data': result_df,
                'summary': self.generate_enhanced_insights(result_df, question),
                'row_count': len(result_df),
                'data_sources': list(self.schema_info.keys()),
                'time_range': self.parse_time_range(question)
            }
            
            # Generate enhanced conversational response
            conversational_response = self.generate_conversational_response(question, result)
            result['conversational_response'] = conversational_response
            
            # Store in conversation context
            self.conversation_context.append({
                'question': question,
                'summary': self.generate_enhanced_insights(result_df, question),
                'sql': sql,
                'timestamp': datetime.now().isoformat()
            })
            
            # Keep only last 5 exchanges
            if len(self.conversation_context) > 5:
                self.conversation_context = self.conversation_context[-5:]
            
            return result
            
        except Exception as e:
            logging.error(f"Enhanced query failed: {e}")
            return {
                'success': False,
                'error': str(e),
                'sql': sql if 'sql' in locals() else None,
                'suggestion': self.suggest_alternative(question),
                'conversational_response': f"I had trouble with that query. {self.suggest_alternative(question)}"
            }
    
    def manual_sql_generation(self, question: str) -> str:
        """Enhanced fallback SQL generation"""
        question_lower = question.lower()
        
        # Parse time range for manual generation
        start_date, end_date = self.parse_time_range(question)
        date_filter = ""
        if start_date and end_date:
            date_filter = f"WHERE \"Create date\" >= '{start_date}' AND \"Create date\" <= '{end_date}'"
        
        if 'response time' in question_lower:
            return f"""
            SELECT 
                AVG(CASE 
                    WHEN "Time to first agent email reply (HH:mm:ss)" LIKE '%:%' 
                    THEN CAST(SPLIT_PART("Time to first agent email reply (HH:mm:ss)", ':', 1) AS DECIMAL) + 
                         CAST(SPLIT_PART("Time to first agent email reply (HH:mm:ss)", ':', 2) AS DECIMAL)/60
                    ELSE NULL 
                END) as avg_response_hours
            FROM tickets 
            WHERE "Time to first agent email reply (HH:mm:ss)" IS NOT NULL 
                AND "Time to first agent email reply (HH:mm:ss)" != ''
                {date_filter.replace('WHERE', 'AND') if date_filter else ''}
            """
            
        elif 'agent' in question_lower and 'most' in question_lower:
            return f"""
            SELECT 
                "Ticket owner",
                COUNT(*) as ticket_count
            FROM tickets 
            WHERE "Ticket owner" IS NOT NULL 
                AND "Ticket owner" != ''
                {date_filter.replace('WHERE', 'AND') if date_filter else ''}
            GROUP BY "Ticket owner"
            ORDER BY ticket_count DESC
            LIMIT 10
            """
            
        else:
            return f"SELECT COUNT(*) as total_records FROM tickets {date_filter}"
    
    def suggest_alternative(self, question: str) -> str:
        """Enhanced alternative suggestions"""
        suggestions = [
            "For the last 35 days, what was the average response time?",
            "Which agent handled the most tickets this month?", 
            "Show me bot satisfaction rates for the past quarter",
            "What's the trend in weekend vs weekday performance?",
            "How many tickets did we process this year?"
        ]
        
        return f"Try asking: {', '.join(suggestions[:3])}"
    
    def format_basic_response(self, sql_result: Dict[str, Any]) -> str:
        """Enhanced fallback formatting"""
        df = sql_result.get('data', pd.DataFrame())
        if len(df) == 0:
            return "I couldn't find data matching your query. Try specifying a different time range or criteria."
        
        return f"I found {len(df)} results. The analysis shows interesting patterns - would you like me to break this down by time period or specific agents?"

# Factory function for enhanced engine
def create_enhanced_query_engine(gemini_api_key: str, sheets_credentials_path: str = None) -> EnhancedSupportQueryEngine:
    """Create an enhanced query engine with Google Sheets integration"""
    return EnhancedSupportQueryEngine(gemini_api_key, sheets_credentials_path)