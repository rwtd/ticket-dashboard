#!/usr/bin/env python3
"""
Support Analytics MCP Server
Provides AI tools for analyzing ticket and chat data using Model Context Protocol
"""

import asyncio
import json
import pandas as pd
import numpy as np
from pathlib import Path
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
import logging

try:
    from mcp.server.fastmcp import FastMCP
    from mcp.types import Tool, TextContent
except ImportError:
    print("MCP SDK not found. Install with: uv add 'mcp[cli]'")
    exit(1)

# Initialize FastMCP server
mcp = FastMCP("support-analytics")

# Global data storage
ticket_data = {}
chat_data = {}

class DataAnalyzer:
    """Analytics engine for support data"""
    
    def __init__(self):
        self.ticket_df = None
        self.chat_df = None
    
    def load_data(self):
        """Load available ticket and chat data"""
        try:
            # Load ticket data
            ticket_dir = Path("tickets")
            if ticket_dir.exists():
                ticket_files = list(ticket_dir.glob("*.csv"))
                if ticket_files:
                    # Load most recent ticket file
                    latest_ticket = max(ticket_files, key=lambda x: x.stat().st_mtime)
                    self.ticket_df = pd.read_csv(latest_ticket)
                    logging.info(f"Loaded {len(self.ticket_df)} tickets from {latest_ticket.name}")
            
            # Load chat data
            chat_dir = Path("chats") 
            if chat_dir.exists():
                chat_files = list(chat_dir.glob("*.csv"))
                if chat_files:
                    # Load most recent chat file
                    latest_chat = max(chat_files, key=lambda x: x.stat().st_mtime)
                    self.chat_df = pd.read_csv(latest_chat)
                    logging.info(f"Loaded {len(self.chat_df)} chats from {latest_chat.name}")
                    
        except Exception as e:
            logging.error(f"Error loading data: {e}")

# Initialize analyzer
analyzer = DataAnalyzer()
analyzer.load_data()

@mcp.tool()
async def get_dataset_info() -> str:
    """Get information about available datasets"""
    info = []
    
    if analyzer.ticket_df is not None:
        ticket_info = f"""
TICKET DATASET:
- Records: {len(analyzer.ticket_df):,}
- Columns: {', '.join(analyzer.ticket_df.columns.tolist())}
- Date range: {analyzer.ticket_df['Date Created'].min() if 'Date Created' in analyzer.ticket_df.columns else 'Unknown'} to {analyzer.ticket_df['Date Created'].max() if 'Date Created' in analyzer.ticket_df.columns else 'Unknown'}
"""
        info.append(ticket_info)
    
    if analyzer.chat_df is not None:
        chat_info = f"""
CHAT DATASET:
- Records: {len(analyzer.chat_df):,}
- Columns: {', '.join(analyzer.chat_df.columns.tolist())}
- Date range: {analyzer.chat_df['Date'].min() if 'Date' in analyzer.chat_df.columns else 'Unknown'} to {analyzer.chat_df['Date'].max() if 'Date' in analyzer.chat_df.columns else 'Unknown'}
"""
        info.append(chat_info)
    
    return '\n'.join(info) if info else "No datasets currently loaded"

@mcp.tool()
async def analyze_ticket_volume(time_period: str = "monthly") -> str:
    """Analyze ticket volume by time period (daily, weekly, monthly)"""
    if analyzer.ticket_df is None:
        return "No ticket data available"
    
    try:
        df = analyzer.ticket_df.copy()
        
        # Convert date column
        date_col = None
        for col in ['Date Created', 'Created', 'date_created', 'timestamp']:
            if col in df.columns:
                date_col = col
                break
        
        if not date_col:
            return "No date column found in ticket data"
        
        df[date_col] = pd.to_datetime(df[date_col])
        
        # Group by time period
        if time_period == "daily":
            grouped = df.groupby(df[date_col].dt.date).size()
        elif time_period == "weekly":
            grouped = df.groupby(df[date_col].dt.to_period('W')).size()
        elif time_period == "monthly":
            grouped = df.groupby(df[date_col].dt.to_period('M')).size()
        else:
            return "Invalid time period. Use: daily, weekly, or monthly"
        
        # Format results
        results = []
        results.append(f"TICKET VOLUME ANALYSIS ({time_period.upper()})")
        results.append("=" * 50)
        
        for period, count in grouped.tail(10).items():
            results.append(f"{period}: {count:,} tickets")
        
        # Add statistics
        results.append(f"\nSTATISTICS:")
        results.append(f"Average: {grouped.mean():.1f} tickets per {time_period[:-2] if time_period.endswith('ly') else time_period}")
        results.append(f"Peak: {grouped.max():,} tickets")
        results.append(f"Total: {grouped.sum():,} tickets")
        
        return '\n'.join(results)
        
    except Exception as e:
        return f"Error analyzing ticket volume: {str(e)}"

@mcp.tool()
async def analyze_agent_performance() -> str:
    """Analyze performance metrics for each support agent"""
    if analyzer.ticket_df is None:
        return "No ticket data available"
    
    try:
        df = analyzer.ticket_df.copy()
        
        # Find agent column
        agent_col = None
        for col in ['Ticket owner', 'Agent', 'Assignee', 'Owner', 'agent', 'assignee']:
            if col in df.columns:
                agent_col = col
                break
        
        if not agent_col:
            return "No agent column found in ticket data"
        
        # Group by agent
        agent_stats = []
        
        for agent in df[agent_col].value_counts().head(10).index:
            agent_tickets = df[df[agent_col] == agent]
            
            stats = {
                'agent': agent,
                'total_tickets': len(agent_tickets),
                'percentage': (len(agent_tickets) / len(df)) * 100
            }
            
            # Calculate response time if available
            for time_col in ['Response Time', 'response_time', 'first_response_time']:
                if time_col in df.columns:
                    try:
                        response_times = pd.to_numeric(agent_tickets[time_col], errors='coerce')
                        stats['avg_response_time'] = response_times.mean()
                        break
                    except:
                        pass
            
            agent_stats.append(stats)
        
        # Format results
        results = []
        results.append("AGENT PERFORMANCE ANALYSIS")
        results.append("=" * 50)
        
        for stats in agent_stats:
            results.append(f"\n{stats['agent']}:")
            results.append(f"  Tickets: {stats['total_tickets']:,} ({stats['percentage']:.1f}%)")
            if 'avg_response_time' in stats:
                results.append(f"  Avg Response Time: {stats['avg_response_time']:.1f} hours")
        
        return '\n'.join(results)
        
    except Exception as e:
        return f"Error analyzing agent performance: {str(e)}"

@mcp.tool()
async def analyze_chat_metrics() -> str:
    """Analyze chat metrics including bot vs human performance"""
    if analyzer.chat_df is None:
        return "No chat data available"
    
    try:
        df = analyzer.chat_df.copy()
        
        results = []
        results.append("CHAT ANALYTICS")
        results.append("=" * 50)
        
        # Total chats
        results.append(f"Total Chats: {len(df):,}")
        
        # Bot vs Human analysis
        bot_keywords = ['bot', 'ai', 'wynn', 'scrape', 'automated']
        human_agents = []
        bots = []
        
        if 'Agent' in df.columns:
            for agent in df['Agent'].value_counts().index:
                if any(keyword.lower() in str(agent).lower() for keyword in bot_keywords):
                    bots.append(agent)
                else:
                    human_agents.append(agent)
        
        if bots:
            bot_chats = df[df['Agent'].isin(bots)]
            results.append(f"\nBot Chats: {len(bot_chats):,} ({len(bot_chats)/len(df)*100:.1f}%)")
            
            # Bot satisfaction if available
            for rating_col in ['Rating', 'Satisfaction', 'rating', 'satisfaction']:
                if rating_col in df.columns:
                    try:
                        good_ratings = bot_chats[df[rating_col] == 'rated good']
                        bad_ratings = bot_chats[df[rating_col] == 'rated bad']
                        total_rated = len(good_ratings) + len(bad_ratings)
                        if total_rated > 0:
                            satisfaction = (len(good_ratings) / total_rated) * 100
                            results.append(f"Bot Satisfaction: {satisfaction:.1f}% ({len(good_ratings)}/{total_rated})")
                        break
                    except:
                        pass
        
        if human_agents:
            human_chats = df[df['Agent'].isin(human_agents)]
            results.append(f"\nHuman Agent Chats: {len(human_chats):,} ({len(human_chats)/len(df)*100:.1f}%)")
            
            # Top human agents
            results.append("\nTop Human Agents:")
            for agent in df[df['Agent'].isin(human_agents)]['Agent'].value_counts().head(5).items():
                results.append(f"  {agent[0]}: {agent[1]:,} chats")
        
        return '\n'.join(results)
        
    except Exception as e:
        return f"Error analyzing chat metrics: {str(e)}"

@mcp.tool()
async def search_tickets(query: str, limit: int = 10) -> str:
    """Search tickets by content, subject, or other fields"""
    if analyzer.ticket_df is None:
        return "No ticket data available"
    
    try:
        df = analyzer.ticket_df.copy()
        
        # Search in text fields
        text_columns = []
        for col in df.columns:
            if df[col].dtype == 'object':  # String columns
                text_columns.append(col)
        
        # Perform search
        mask = pd.Series([False] * len(df))
        query_lower = query.lower()
        
        for col in text_columns:
            try:
                mask |= df[col].astype(str).str.lower().str.contains(query_lower, na=False)
            except:
                pass
        
        results_df = df[mask].head(limit)
        
        if len(results_df) == 0:
            return f"No tickets found matching '{query}'"
        
        # Format results
        results = []
        results.append(f"SEARCH RESULTS FOR '{query}'")
        results.append("=" * 50)
        results.append(f"Found {len(results_df)} tickets (showing first {min(limit, len(results_df))})")
        
        for idx, row in results_df.iterrows():
            results.append(f"\nTicket {idx}:")
            # Show key fields
            for col in ['Subject', 'Status', 'Ticket owner', 'Date Created'][:3]:
                if col in row:
                    results.append(f"  {col}: {row[col]}")
        
        return '\n'.join(results)
        
    except Exception as e:
        return f"Error searching tickets: {str(e)}"

@mcp.tool()
async def analyze_response_times() -> str:
    """Analyze average response times across all tickets and agents"""
    if analyzer.ticket_df is None:
        return "No ticket data available"
    
    try:
        df = analyzer.ticket_df.copy()
        
        # Find response time columns
        response_time_cols = []
        for col in df.columns:
            if 'response' in col.lower() and 'time' in col.lower():
                response_time_cols.append(col)
        
        if not response_time_cols:
            return "No response time columns found in ticket data"
        
        results = []
        results.append("RESPONSE TIME ANALYSIS")
        results.append("=" * 50)
        
        # Analyze each response time column
        for col in response_time_cols[:3]:  # Top 3 most relevant columns
            try:
                # Try to convert time format (HH:mm:ss) to hours
                time_data = df[col].dropna()
                if len(time_data) == 0:
                    continue
                
                # Convert time strings to hours
                hours_list = []
                for time_str in time_data:
                    if pd.isna(time_str) or time_str == '':
                        continue
                    try:
                        # Handle HH:mm:ss format
                        if ':' in str(time_str):
                            parts = str(time_str).split(':')
                            if len(parts) >= 2:
                                hours = float(parts[0]) + float(parts[1])/60
                                if len(parts) == 3:
                                    hours += float(parts[2])/3600
                                hours_list.append(hours)
                        else:
                            # Try direct numeric conversion
                            hours_list.append(float(time_str))
                    except:
                        continue
                
                if hours_list:
                    avg_hours = sum(hours_list) / len(hours_list)
                    median_hours = sorted(hours_list)[len(hours_list)//2]
                    
                    results.append(f"\n{col}:")
                    results.append(f"  Average: {avg_hours:.1f} hours")
                    results.append(f"  Median: {median_hours:.1f} hours")
                    results.append(f"  Tickets with data: {len(hours_list):,}")
                    
                    # Quick stats
                    if avg_hours < 1:
                        results.append(f"  ⚡ Excellent - Under 1 hour average")
                    elif avg_hours < 4:
                        results.append(f"  ✅ Good - Under 4 hour average") 
                    elif avg_hours < 24:
                        results.append(f"  ⚠️  Moderate - Same day response")
                    else:
                        results.append(f"  🔴 Slow - Over 24 hour average")
                        
            except Exception as e:
                results.append(f"\nError analyzing {col}: {str(e)}")
        
        # Agent-specific response times
        agent_col = None
        for col in ['Ticket owner', 'Agent', 'Assignee', 'Owner']:
            if col in df.columns:
                agent_col = col
                break
        
        if agent_col and response_time_cols:
            results.append(f"\nTOP AGENT RESPONSE TIMES:")
            results.append("-" * 30)
            
            main_response_col = response_time_cols[0]  # Use first/main response time column
            
            for agent in df[agent_col].value_counts().head(5).index:
                agent_data = df[df[agent_col] == agent][main_response_col].dropna()
                if len(agent_data) > 0:
                    agent_hours = []
                    for time_str in agent_data:
                        try:
                            if ':' in str(time_str):
                                parts = str(time_str).split(':')
                                if len(parts) >= 2:
                                    hours = float(parts[0]) + float(parts[1])/60
                                    if len(parts) == 3:
                                        hours += float(parts[2])/3600
                                    agent_hours.append(hours)
                        except:
                            continue
                    
                    if agent_hours:
                        avg_agent_hours = sum(agent_hours) / len(agent_hours)
                        results.append(f"{agent}: {avg_agent_hours:.1f} hours avg ({len(agent_hours)} tickets)")
        
        return '\n'.join(results) if results else "No response time data found"
        
    except Exception as e:
        return f"Error analyzing response times: {str(e)}"

@mcp.tool()
async def get_time_period_analysis(start_date: str, end_date: str) -> str:
    """Analyze metrics for a specific time period (YYYY-MM-DD format)"""
    if analyzer.ticket_df is None:
        return "No ticket data available"
    
    try:
        df = analyzer.ticket_df.copy()
        
        # Find date column
        date_col = None
        for col in ['Date Created', 'Created', 'date_created', 'timestamp']:
            if col in df.columns:
                date_col = col
                break
        
        if not date_col:
            return "No date column found"
        
        # Filter by date range
        df[date_col] = pd.to_datetime(df[date_col])
        start_dt = pd.to_datetime(start_date)
        end_dt = pd.to_datetime(end_date)
        
        filtered_df = df[(df[date_col] >= start_dt) & (df[date_col] <= end_dt)]
        
        if len(filtered_df) == 0:
            return f"No tickets found in date range {start_date} to {end_date}"
        
        # Generate analysis
        results = []
        results.append(f"ANALYSIS FOR {start_date} TO {end_date}")
        results.append("=" * 50)
        results.append(f"Total Tickets: {len(filtered_df):,}")
        results.append(f"Daily Average: {len(filtered_df) / (end_dt - start_dt).days:.1f}")
        
        # Agent breakdown
        if 'Ticket owner' in filtered_df.columns:
            results.append("\nTop Agents in Period:")
            for agent, count in filtered_df['Ticket owner'].value_counts().head(5).items():
                results.append(f"  {agent}: {count:,} tickets")
        
        return '\n'.join(results)
        
    except Exception as e:
        return f"Error analyzing time period: {str(e)}"

def run_server():
    """Run the MCP server"""
    logging.basicConfig(level=logging.INFO)
    # Load data on startup
    analyzer.load_data()
    # Run the MCP server with proper transport
    mcp.run(transport="stdio")

if __name__ == "__main__":
    run_server()