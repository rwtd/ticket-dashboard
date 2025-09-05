#!/usr/bin/env python3
"""
Agent Performance Analyzer
Generates comprehensive agent performance comparison dashboards
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import json

class AgentPerformanceAnalyzer:
    """Analyzes agent performance metrics and generates comparison dashboards"""
    
    def __init__(self):
        self.df = None
        self.processed_files = []
        
    def load_data(self, ticket_files: List[Path]) -> pd.DataFrame:
        """Load and validate ticket CSV files"""
        if not ticket_files:
            raise FileNotFoundError("No ticket CSV files found")

        all_data = []
        for file_path in ticket_files:
            try:
                df = pd.read_csv(file_path, low_memory=False, dtype=str, na_values=['', 'NULL', 'null', 'None'])
                all_data.append(df)
                self.processed_files.append(file_path)
                print(f"Loaded {len(df):,} records from {file_path.name}")
            except Exception as e:
                print(f"⚠️  Could not load {file_path.name}: {e}")

        if not all_data:
            raise ValueError("No valid ticket data could be loaded.")

        self.df = pd.concat(all_data, ignore_index=True)
        print(f"✅ Total ticket records loaded: {len(self.df):,}")
        return self.df
    
    def process_data(self) -> pd.DataFrame:
        """Apply all necessary data transformations"""
        if self.df is None:
            raise ValueError("No data loaded. Call load_data() first.")
            
        self.df = self._convert_timezone(self.df)
        self.df = self._map_staff_names(self.df)
        self.df = self._add_weekend_flag(self.df)
        self.df = self._calc_first_response(self.df)
        self.df = self._remove_spam(self.df)
        
        return self.df
    
    def _convert_timezone(self, df: pd.DataFrame) -> pd.DataFrame:
        """Convert CDT timestamps to EDT"""
        import pytz
        
        central = pytz.timezone("US/Central")
        eastern = pytz.timezone("US/Eastern")
        
        date_cols = [
            "Create date", "Close date", "First agent email response date",
            "Last activity date", "Last Closed Date", "Last contacted date",
            "Last customer reply date", "Owner assigned date",
            "Last message received date", "Last response date"
        ]
        
        for col in date_cols:
            if col in df.columns:
                df[col] = (
                    pd.to_datetime(df[col], errors="coerce")
                    .dt.tz_localize(central, ambiguous=False, nonexistent="shift_forward")
                    .dt.tz_convert(eastern)
                )
        
        return df
    
    def _map_staff_names(self, df: pd.DataFrame) -> pd.DataFrame:
        """Standardize staff names"""
        mapping = {
            "Girly E": "Girly",
            "Gillie E": "Girly",
            "Gillie": "Girly",
            "Nora N": "Nova", 
            "Nora": "Nova",
            "Chris S": "Francis",
            "Chris": "Francis",
            "Shan D": "Bhushan", 
            "Shan": "Bhushan",
        }
        df["Case Owner"] = df["Ticket owner"].map(mapping).fillna(df["Ticket owner"])
        return df
    
    def _add_weekend_flag(self, df: pd.DataFrame) -> pd.DataFrame:
        """Flag weekend tickets - simplified version"""
        df["Weekend_Ticket"] = df["Create date"].dt.dayofweek >= 5  # Saturday=5, Sunday=6
        return df
    
    def _calc_first_response(self, df: pd.DataFrame) -> pd.DataFrame:
        """Calculate first response times"""
        def _delta(row):
            if row["Pipeline"] == "Live Chat ":
                return pd.Timedelta(seconds=30)
            if pd.isna(row["First agent email response date"]) or pd.isna(row["Create date"]):
                return pd.NaT
            
            # Calculate response time
            response_time = row["First agent email response date"] - row["Create date"]
            
            # Validate that response time is positive
            if response_time.total_seconds() <= 0:
                return pd.NaT
                
            return response_time
        
        df["First Response Time"] = df.apply(_delta, axis=1)
        df["First Response Time (Hours)"] = df["First Response Time"].dt.total_seconds() / 3600
        
        # Log validation results
        total_records = len(df)
        valid_count = df["First Response Time (Hours)"].notna().sum()
        print(f"✅ Calculated first-response times for {valid_count:,} of {total_records:,} tickets")
        
        return df
    
    def _remove_spam(self, df: pd.DataFrame) -> pd.DataFrame:
        """Remove SPAM tickets"""
        pre_count = len(df)
        df = df[df["Pipeline"] != "SPAM Tickets"].copy()
        removed_count = pre_count - len(df)
        print(f"Removed {removed_count:,} SPAM tickets.")
        return df
    
    def analyze_performance(self, period: str = 'all') -> Dict:
        """Generate agent performance analysis for specified period"""
        if self.df is None:
            raise ValueError("No data loaded. Call load_data() and process_data() first.")
        
        # Filter by time period
        filtered_df = self._filter_by_period(self.df, period)
        
        if len(filtered_df) == 0:
            return {"error": f"No data available for period: {period}"}
        
        # Filter out LiveChat and weekday tickets only
        weekday_df = filtered_df[filtered_df['Weekend_Ticket'] == False].copy()
        non_livechat_df = weekday_df[weekday_df['Pipeline'] != 'Live Chat '].copy()
        
        if len(non_livechat_df) == 0:
            return {"error": "No non-LiveChat weekday data available"}
        
        # Calculate agent metrics
        agent_stats = []
        agents = ['Nova', 'Girly', 'Francis', 'Bhushan']
        
        for agent in agents:
            agent_data = non_livechat_df[non_livechat_df['Case Owner'] == agent]
            all_agent_data = weekday_df[weekday_df['Case Owner'] == agent]
            
            if len(agent_data) > 0:
                response_times = agent_data['First Response Time (Hours)'].dropna()
                if len(response_times) > 0:
                    stats = {
                        'Agent': agent,
                        'Total_Tickets': len(all_agent_data),
                        'Non_LiveChat_Tickets': len(agent_data),
                        'Avg_Response_Hours': response_times.mean(),
                        'Median_Response_Hours': response_times.median(),
                        'Std_Response_Hours': response_times.std(),
                        'Min_Response_Hours': response_times.min(),
                        'Max_Response_Hours': response_times.max(),
                        'Q25_Response_Hours': response_times.quantile(0.25),
                        'Q75_Response_Hours': response_times.quantile(0.75),
                        'Pipeline_Breakdown': all_agent_data['Pipeline'].value_counts().to_dict()
                    }
                    agent_stats.append(stats)
        
        if not agent_stats:
            return {"error": "No agent data available"}
        
        # Convert to DataFrame and calculate percentages
        stats_df = pd.DataFrame(agent_stats)
        total_tickets = stats_df['Total_Tickets'].sum()
        if total_tickets > 0:
            stats_df['Percentage'] = (stats_df['Total_Tickets'] / total_tickets * 100).round(1)
        
        # Calculate date range info
        date_info = {
            'start_date': filtered_df['Create date'].min().strftime('%Y-%m-%d'),
            'end_date': filtered_df['Create date'].max().strftime('%Y-%m-%d'),
            'total_records': len(filtered_df),
            'weekday_records': len(weekday_df),
            'non_livechat_records': len(non_livechat_df)
        }
        
        return {
            'period': period,
            'date_info': date_info,
            'agent_stats': stats_df.to_dict('records'),
            'summary': self._generate_insights(stats_df, period)
        }
    
    def _filter_by_period(self, df: pd.DataFrame, period: str) -> pd.DataFrame:
        """Filter dataframe by time period"""
        if period == 'all':
            return df
        
        latest_date = df['Create date'].max()
        
        if period == '12_weeks':
            cutoff_date = latest_date - timedelta(weeks=12)
        elif period == '4_weeks':
            cutoff_date = latest_date - timedelta(weeks=4)
        elif period == '8_weeks':
            cutoff_date = latest_date - timedelta(weeks=8)
        else:
            return df
        
        return df[df['Create date'] >= cutoff_date].copy()
    
    def _generate_insights(self, stats_df: pd.DataFrame, period: str) -> Dict:
        """Generate insights based on the performance data"""
        if len(stats_df) == 0:
            return {}
        
        # Find best performers in different categories
        volume_leader = stats_df.loc[stats_df['Total_Tickets'].idxmax()]
        speed_leader = stats_df.loc[stats_df['Median_Response_Hours'].idxmin()]
        consistency_leader = stats_df.loc[stats_df['Std_Response_Hours'].idxmin()]
        
        return {
            'volume_leader': {
                'agent': volume_leader['Agent'],
                'tickets': int(volume_leader['Total_Tickets']),
                'percentage': volume_leader['Percentage']
            },
            'speed_leader': {
                'agent': speed_leader['Agent'],
                'median_hours': speed_leader['Median_Response_Hours'],
                'median_minutes': speed_leader['Median_Response_Hours'] * 60
            },
            'consistency_leader': {
                'agent': consistency_leader['Agent'],
                'std_hours': consistency_leader['Std_Response_Hours']
            },
            'period_description': self._get_period_description(period)
        }
    
    def _get_period_description(self, period: str) -> str:
        """Get human-readable period description"""
        descriptions = {
            'all': 'All Available Data',
            '12_weeks': 'Last 12 Weeks',
            '4_weeks': 'Last 4 Weeks',
            '8_weeks': 'Last 8 Weeks'
        }
        return descriptions.get(period, period)
    
    def generate_dashboard_html(self, analysis: Dict) -> str:
        """Generate HTML dashboard from analysis results"""
        if 'error' in analysis:
            return f"<html><body><h1>Error</h1><p>{analysis['error']}</p></body></html>"
        
        period = analysis['period']
        date_info = analysis['date_info']
        agent_stats = analysis['agent_stats']
        insights = analysis['summary']
        
        # Generate the dashboard HTML using the same template as our standalone dashboards
        template = self._get_dashboard_template()
        
        # Prepare data for the template
        dashboard_data = {
            'period_title': self._get_period_description(period),
            'date_range': f"{date_info['start_date']} to {date_info['end_date']}",
            'agent_cards': self._generate_agent_cards(agent_stats),
            'chart_data': self._generate_chart_data(agent_stats),
            'insights': self._generate_insights_html(insights, agent_stats)
        }
        
        return template.format(**dashboard_data)
    
    def _get_dashboard_template(self) -> str:
        """Get the HTML template for the dashboard"""
        # Read the template from our existing dashboard files and adapt it
        # For now, return a simplified version
        return """
        <!DOCTYPE html>
        <html lang="en">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>Agent Performance Comparison - {period_title}</title>
            <script src="https://cdn.plot.ly/plotly-latest.min.js"></script>
            <style>
                body {{ font-family: 'Segoe UI', sans-serif; background: linear-gradient(135deg, #1e1e2e 0%, #2a2d47 100%); color: #e0e0e0; margin: 0; padding: 20px; }}
                .container {{ max-width: 1400px; margin: 0 auto; }}
                .header {{ text-align: center; background: rgba(23, 23, 35, 0.8); padding: 30px; border-radius: 15px; margin-bottom: 30px; }}
                .header h1 {{ font-size: 2.5em; margin-bottom: 10px; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); -webkit-background-clip: text; -webkit-text-fill-color: transparent; }}
                .metrics-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: 20px; margin-bottom: 30px; }}
                .metric-card {{ background: rgba(23, 23, 35, 0.8); border-radius: 15px; padding: 25px; text-align: center; }}
                .chart-container {{ background: rgba(23, 23, 35, 0.8); border-radius: 15px; padding: 20px; margin-bottom: 20px; }}
                .insights {{ background: rgba(23, 23, 35, 0.8); border-radius: 15px; padding: 30px; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>🎯 Agent Performance Comparison</h1>
                    <div style="font-size: 1.2em; color: #a0a0a0;">{period_title}</div>
                    <div style="color: #00d4aa; font-weight: bold;">📅 {date_range}</div>
                </div>
                
                <div class="metrics-grid">
                    {agent_cards}
                </div>
                
                <div class="chart-container">
                    <div id="comparisonChart"></div>
                </div>
                
                <div class="insights">
                    {insights}
                </div>
            </div>
            
            <script>
                {chart_data}
            </script>
        </body>
        </html>
        """
    
    def _generate_agent_cards(self, agent_stats: List[Dict]) -> str:
        """Generate HTML for agent metric cards"""
        cards = []
        colors = ['#4ecdc4', '#ff6b6b', '#feca57', '#a29bfe']
        
        for i, stats in enumerate(agent_stats):
            agent = stats['Agent']
            color = colors[i % len(colors)]
            
            card = f"""
            <div class="metric-card" style="border-left: 4px solid {color};">
                <h3 style="color: #00d4aa;">{agent}</h3>
                <div style="font-size: 2.2em; font-weight: bold; color: {color}; margin: 10px 0;">
                    {stats['Total_Tickets']}
                </div>
                <div style="color: #a0a0a0; margin-bottom: 15px;">
                    Total Tickets ({stats['Percentage']:.1f}%)
                </div>
                <div style="font-size: 0.8em; color: #c0c0c0; line-height: 1.4;">
                    <strong>Median:</strong> {stats['Median_Response_Hours']:.2f}h ({stats['Median_Response_Hours']*60:.0f} min)<br>
                    <strong>Average:</strong> {stats['Avg_Response_Hours']:.2f}h<br>
                    <strong>Range:</strong> {stats['Min_Response_Hours']:.3f}h - {stats['Max_Response_Hours']:.2f}h
                </div>
            </div>
            """
            cards.append(card)
        
        return ''.join(cards)
    
    def _generate_chart_data(self, agent_stats: List[Dict]) -> str:
        """Generate JavaScript for chart data"""
        agents = [s['Agent'] for s in agent_stats]
        tickets = [s['Total_Tickets'] for s in agent_stats]
        medians = [s['Median_Response_Hours'] * 60 for s in agent_stats]  # Convert to minutes
        
        return f"""
        const agents = {agents};
        const tickets = {tickets};
        const medianMinutes = {medians};
        const colors = ['#4ecdc4', '#ff6b6b', '#feca57', '#a29bfe'];
        
        Plotly.newPlot('comparisonChart', [
            {{
                x: agents,
                y: medianMinutes,
                name: 'Median Response (min)',
                type: 'bar',
                marker: {{ color: colors, opacity: 0.8 }},
                yaxis: 'y'
            }},
            {{
                x: agents,
                y: tickets,
                name: 'Total Tickets',
                type: 'scatter',
                mode: 'lines+markers',
                marker: {{ color: '#00d4aa', size: 10 }},
                line: {{ color: '#00d4aa', width: 3 }},
                yaxis: 'y2'
            }}
        ], {{
            title: {{ text: '🎯 Performance vs Volume Comparison', font: {{ size: 18, color: '#e0e0e0' }} }},
            plot_bgcolor: 'rgba(30, 30, 46, 0.8)',
            paper_bgcolor: 'rgba(23, 23, 35, 0.9)',
            font: {{ color: '#e0e0e0' }},
            showlegend: true,
            legend: {{ bgcolor: 'rgba(23, 23, 35, 0.8)' }},
            yaxis: {{ title: 'Median Response Time (minutes)', side: 'left' }},
            yaxis2: {{ title: 'Total Tickets', side: 'right', overlaying: 'y' }},
            height: 500
        }});
        """
    
    def _generate_insights_html(self, insights: Dict, agent_stats: List[Dict]) -> str:
        """Generate HTML for insights section"""
        if not insights:
            return "<p>No insights available.</p>"
        
        return f"""
        <h2 style="color: #00d4aa; margin-bottom: 20px;">🔍 Performance Insights</h2>
        <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap: 20px;">
            <div style="background: rgba(102, 126, 234, 0.1); padding: 20px; border-radius: 10px; border-left: 4px solid #667eea;">
                <h4 style="color: #667eea; margin-bottom: 10px;">🏆 Volume Leader</h4>
                <p><strong>{insights['volume_leader']['agent']}</strong> handled {insights['volume_leader']['tickets']} tickets ({insights['volume_leader']['percentage']:.1f}% of total volume)</p>
            </div>
            <div style="background: rgba(102, 126, 234, 0.1); padding: 20px; border-radius: 10px; border-left: 4px solid #667eea;">
                <h4 style="color: #667eea; margin-bottom: 10px;">⚡ Speed Champion</h4>
                <p><strong>{insights['speed_leader']['agent']}</strong> achieved fastest median response time: {insights['speed_leader']['median_minutes']:.0f} minutes</p>
            </div>
            <div style="background: rgba(102, 126, 234, 0.1); padding: 20px; border-radius: 10px; border-left: 4px solid #667eea;">
                <h4 style="color: #667eea; margin-bottom: 10px;">📊 Most Consistent</h4>
                <p><strong>{insights['consistency_leader']['agent']}</strong> showed most consistent performance with {insights['consistency_leader']['std_hours']:.2f}h standard deviation</p>
            </div>
        </div>
        """