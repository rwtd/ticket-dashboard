from pathlib import Path
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from ticket_processor import TicketDataProcessor

class IndividualAgentAnalyzer:
    """Analyzer for comparing individual agent performance against team averages."""
    
    def __init__(self):
        self.ticket_processor = TicketDataProcessor()
        self.data = None
        self.processed_data = None
        
    def load_data(self, file_paths: List[Path]) -> None:
        """Load ticket data from CSV files."""
        self.data = self.ticket_processor.load_data(file_paths)
        print(f"✅ Loaded {len(self.data)} ticket records for individual analysis")
        
    def process_data(self) -> None:
        """Process the loaded data."""
        if self.data is None:
            raise ValueError("No data loaded. Call load_data() first.")
        
        self.processed_data = self.ticket_processor.process_data()
        print(f"✅ Processed {len(self.processed_data)} ticket records")
        
    def _filter_by_period(self, period: str) -> pd.DataFrame:
        """Filter data by the specified time period."""
        if self.processed_data is None:
            raise ValueError("Data not processed. Call process_data() first.")
            
        data = self.processed_data.copy()
        
        if period == 'all':
            return data
            
        # Calculate cutoff date
        import pytz
        eastern = pytz.timezone("US/Eastern")
        now = datetime.now(tz=eastern)
        
        if period == '4_weeks':
            cutoff = now - timedelta(weeks=4)
        elif period == '8_weeks':
            cutoff = now - timedelta(weeks=8)  
        elif period == '12_weeks':
            cutoff = now - timedelta(weeks=12)
        else:
            return data
            
        # Filter by date (data already has timezone-aware timestamps)
        return data[data['Create date'] >= cutoff]
        
    def analyze_individual_vs_team(self, selected_agent: str, period: str = 'all') -> Dict[str, Any]:
        """Compare individual agent performance against team averages."""
        try:
            # Filter data by period
            filtered_data = self._filter_by_period(period)
            
            # Remove SPAM tickets and LiveChat for response time calculations
            clean_data = filtered_data[
                (filtered_data['Pipeline'] != 'SPAM Tickets') & 
                (filtered_data['Weekend_Ticket'] == False)
            ].copy()
            
            # Calculate response time stats (excluding LiveChat)
            response_data = clean_data[clean_data['Pipeline'] != 'Live Chat '].copy()
            
            if response_data.empty:
                return {'error': 'No valid ticket data found for the selected period'}
                
            # Individual agent stats
            agent_data = response_data[response_data['Case Owner'] == selected_agent].copy()
            
            if agent_data.empty:
                return {'error': f'No tickets found for agent {selected_agent} in the selected period'}
                
            # Team stats (all agents)
            team_stats = self._calculate_team_stats(response_data)
            individual_stats = self._calculate_individual_stats(agent_data)
            
            # Volume comparison (including all tickets, not just response time eligible)
            volume_data = clean_data.copy()
            total_team_volume = len(volume_data)
            individual_volume = len(volume_data[volume_data['Case Owner'] == selected_agent])
            
            # Calculate percentages
            volume_percentage = (individual_volume / total_team_volume * 100) if total_team_volume > 0 else 0
            
            # Get date range
            date_range = self._get_date_range(filtered_data, period)
            
            return {
                'agent_name': selected_agent,
                'period': period,
                'date_range': date_range,
                'individual_stats': {
                    **individual_stats,
                    'volume': individual_volume,
                    'volume_percentage': volume_percentage
                },
                'team_stats': {
                    **team_stats,
                    'total_volume': total_team_volume
                },
                'comparison': self._create_comparison(individual_stats, team_stats, volume_percentage),
                'summary': self._generate_insights(selected_agent, individual_stats, team_stats, volume_percentage)
            }
            
        except Exception as e:
            return {'error': f'Analysis failed: {str(e)}'}
            
    def _calculate_individual_stats(self, agent_data: pd.DataFrame) -> Dict[str, float]:
        """Calculate performance stats for individual agent."""
        if len(agent_data) == 0:
            return {'tickets': 0, 'avg_response_hours': 0, 'median_response_hours': 0}
            
        response_times = agent_data['First Response Time (Hours)'].dropna()
        
        return {
            'tickets': len(agent_data),
            'avg_response_hours': response_times.mean() if len(response_times) > 0 else 0,
            'median_response_hours': response_times.median() if len(response_times) > 0 else 0
        }
        
    def _calculate_team_stats(self, team_data: pd.DataFrame) -> Dict[str, Any]:
        """Calculate team-wide performance averages."""
        response_times = team_data['First Response Time (Hours)'].dropna()
        
        # Calculate per-agent stats first
        agent_stats = team_data.groupby('Case Owner').agg({
            'First Response Time (Hours)': ['count', 'mean', 'median', 'std']
        }).round(3)
        
        # Flatten column names
        agent_stats.columns = ['Tickets', 'Avg_Response_Hours', 'Median_Response_Hours', 'Std_Response_Hours']
        agent_stats = agent_stats.fillna(0)
        
        # Overall team averages
        team_avg_response = response_times.mean() if len(response_times) > 0 else 0
        team_median_response = response_times.median() if len(response_times) > 0 else 0
        
        return {
            'total_tickets': len(team_data),
            'avg_response_hours': team_avg_response,
            'median_response_hours': team_median_response,
            'agent_breakdown': agent_stats.to_dict('index')
        }
        
    def _create_comparison(self, individual: Dict, team: Dict, volume_percentage: float) -> Dict[str, str]:
        """Create performance comparison indicators."""
        comparison = {}
        
        # Response speed comparison
        if individual['avg_response_hours'] < team['avg_response_hours']:
            speed_diff = team['avg_response_hours'] - individual['avg_response_hours']
            comparison['speed'] = f"✅ {speed_diff:.2f}h faster than team average"
        else:
            speed_diff = individual['avg_response_hours'] - team['avg_response_hours']
            comparison['speed'] = f"⚠️ {speed_diff:.2f}h slower than team average"
            
        # Median response comparison
        if individual['median_response_hours'] < team['median_response_hours']:
            median_diff = team['median_response_hours'] - individual['median_response_hours']
            comparison['median'] = f"✅ Median response {median_diff:.2f}h faster than team median"
        else:
            median_diff = individual['median_response_hours'] - team['median_response_hours']
            comparison['median'] = f"⚠️ Median response {median_diff:.2f}h slower than team median"
            
        # Volume percentage
        comparison['volume'] = f"📊 Handled {volume_percentage:.1f}% of total team tickets during this period"
            
        return comparison
        
    def _generate_insights(self, agent_name: str, individual: Dict, team: Dict, volume_pct: float) -> List[str]:
        """Generate performance insights."""
        insights = [
            f"📊 {agent_name} handled {individual['tickets']} tickets ({volume_pct:.1f}% of team volume)",
            f"⚡ Average response time: {individual['avg_response_hours']:.2f}h (team: {team['avg_response_hours']:.2f}h)",
            f"🎯 Median response time: {individual['median_response_hours']:.2f}h (team: {team['median_response_hours']:.2f}h)"
        ]
        
        # Add performance insights
        if individual['avg_response_hours'] < team['avg_response_hours']:
            insights.append("🏆 Responding faster than team average")
        
        if individual['median_response_hours'] < team['median_response_hours']:
            insights.append("🎯 Median performance better than team")
            
        return insights
        
    def _get_date_range(self, data: pd.DataFrame, period: str) -> str:
        """Get human-readable date range."""
        if data.empty:
            return "No data"
            
        data['Create date'] = pd.to_datetime(data['Create date'])
        start_date = data['Create date'].min().strftime('%Y-%m-%d')
        end_date = data['Create date'].max().strftime('%Y-%m-%d') 
        
        return f"{start_date} to {end_date}"
        
    def _get_period_description(self, period: str) -> str:
        """Get human-readable period description."""
        period_map = {
            'all': 'All Time',
            '4_weeks': 'Last 4 Weeks', 
            '8_weeks': 'Last 8 Weeks',
            '12_weeks': 'Last 12 Weeks'
        }
        return period_map.get(period, period)
        
    def generate_dashboard_html(self, analysis: Dict[str, Any]) -> str:
        """Generate HTML dashboard for individual vs team comparison."""
        if 'error' in analysis:
            return f"<html><body><h1>Error</h1><p>{analysis['error']}</p></body></html>"
            
        agent_name = analysis['agent_name']
        period_title = self._get_period_description(analysis['period'])
        date_range = analysis['date_range']
        individual = analysis['individual_stats']
        team = analysis['team_stats']
        comparison = analysis['comparison']
        insights = analysis['summary']
        
        # Create chart data for individual vs team comparison
        chart_data = self._create_chart_data(individual, team, agent_name)
        
        html = f"""
        <!DOCTYPE html>
        <html lang="en">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>{agent_name} vs Team Performance - {period_title}</title>
            <script src="https://cdn.plot.ly/plotly-latest.min.js"></script>
            <style>
                body {{ font-family: 'Segoe UI', sans-serif; background: linear-gradient(135deg, #1e1e2e 0%, #2a2d47 100%); color: #e0e0e0; margin: 0; padding: 20px; }}
                .container {{ max-width: 1400px; margin: 0 auto; }}
                .header {{ text-align: center; background: rgba(23, 23, 35, 0.8); padding: 30px; border-radius: 15px; margin-bottom: 30px; }}
                .header h1 {{ color: #00d4aa; margin: 0; font-size: 2.5em; }}
                .metrics-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: 20px; margin-bottom: 30px; }}
                .metric-card {{ background: rgba(23, 23, 35, 0.8); padding: 25px; border-radius: 15px; text-align: center; border-left: 4px solid #00d4aa; }}
                .metric-value {{ font-size: 2.2em; font-weight: bold; color: #00d4aa; }}
                .metric-label {{ color: #a0a0a0; margin-top: 8px; }}
                .comparison-card {{ background: rgba(23, 23, 35, 0.8); padding: 25px; border-radius: 15px; margin-bottom: 20px; }}
                .chart-container {{ background: rgba(23, 23, 35, 0.8); padding: 25px; border-radius: 15px; margin-bottom: 20px; }}
                .insight {{ padding: 10px; margin: 5px 0; background: rgba(0, 212, 170, 0.1); border-left: 3px solid #00d4aa; border-radius: 5px; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>👤 {agent_name} vs Team Performance</h1>
                    <div style="font-size: 1.2em; color: #a0a0a0;">{period_title}</div>
                    <div style="color: #00d4aa; font-weight: bold;">📅 {date_range}</div>
                </div>
                
                <!-- Individual Agent Metrics -->
                <div style="margin-bottom: 20px;">
                    <h3 style="color: #00d4aa; text-align: center; margin-bottom: 15px;">👤 {agent_name} Performance</h3>
                    <div class="metrics-grid">
                        <div class="metric-card" style="border-left: 4px solid #00d4aa;">
                            <div class="metric-value">{individual['volume']}</div>
                            <div class="metric-label">📋 Tickets Handled</div>
                            <div style="color: #00d4aa; margin-top: 5px;">{individual['volume_percentage']:.1f}% of team</div>
                        </div>
                        <div class="metric-card" style="border-left: 4px solid #00d4aa;">
                            <div class="metric-value">{individual['avg_response_hours']:.2f}h</div>
                            <div class="metric-label">⚡ Avg Response Time</div>
                            <div style="color: #00d4aa; margin-top: 5px;">{individual['avg_response_hours']*60:.0f} minutes</div>
                        </div>
                        <div class="metric-card" style="border-left: 4px solid #00d4aa;">
                            <div class="metric-value">{individual['median_response_hours']:.2f}h</div>
                            <div class="metric-label">🎯 Median Response</div>
                            <div style="color: #00d4aa; margin-top: 5px;">{individual['median_response_hours']*60:.0f} minutes</div>
                        </div>
                    </div>
                </div>

                <!-- Team Average Metrics -->
                <div style="margin-bottom: 30px;">
                    <h3 style="color: #3498db; text-align: center; margin-bottom: 15px;">👥 Team Average Performance</h3>
                    <div class="metrics-grid">
                        <div class="metric-card" style="border-left: 4px solid #3498db;">
                            <div class="metric-value" style="color: #3498db;">{team['total_tickets']}</div>
                            <div class="metric-label">📋 Total Team Tickets</div>
                            <div style="color: #3498db; margin-top: 5px;">All agents combined</div>
                        </div>
                        <div class="metric-card" style="border-left: 4px solid #3498db;">
                            <div class="metric-value" style="color: #3498db;">{team['avg_response_hours']:.2f}h</div>
                            <div class="metric-label">⚡ Team Avg Response</div>
                            <div style="color: #3498db; margin-top: 5px;">{team['avg_response_hours']*60:.0f} minutes</div>
                        </div>
                        <div class="metric-card" style="border-left: 4px solid #3498db;">
                            <div class="metric-value" style="color: #3498db;">{team['median_response_hours']:.2f}h</div>
                            <div class="metric-label">🎯 Team Median Response</div>
                            <div style="color: #3498db; margin-top: 5px;">{team['median_response_hours']*60:.0f} minutes</div>
                        </div>
                    </div>
                </div>
                
                <div class="comparison-card">
                    <h3 style="color: #00d4aa; margin-bottom: 15px;">🔍 Performance Comparison</h3>
                    <div style="padding: 10px; background: rgba(0, 212, 170, 0.1); border-radius: 8px; margin: 10px 0;">
                        {comparison['speed']}
                    </div>
                    <div style="padding: 10px; background: rgba(0, 212, 170, 0.1); border-radius: 8px; margin: 10px 0;">
                        {comparison['median']}
                    </div>
                    <div style="padding: 10px; background: rgba(0, 212, 170, 0.1); border-radius: 8px; margin: 10px 0;">
                        {comparison['volume']}
                    </div>
                </div>
                
                <div class="chart-container">
                    <h3 style="color: #00d4aa; margin-bottom: 15px;">📊 Performance Visualization</h3>
                    <div id="performanceChart"></div>
                </div>
                
                <div class="chart-container">
                    <h3 style="color: #00d4aa; margin-bottom: 15px;">📈 Weekly Performance Breakdown</h3>
                    <div id="weeklyChart"></div>
                </div>
                
                <div class="comparison-card">
                    <h3 style="color: #00d4aa; margin-bottom: 15px;">💡 Key Insights</h3>
                    {''.join([f'<div class="insight">{insight}</div>' for insight in insights])}
                </div>
                
            </div>
            
            <script>
                {chart_data}
            </script>
        </body>
        </html>
        """
        
        return html
        
    def _create_weekly_data(self, agent_name: str) -> List[Dict]:
        """Aggregate performance data by week for time series analysis."""
        if self.processed_data is None:
            return []
            
        data = self.processed_data.copy()
        
        # Remove SPAM tickets and LiveChat for response time calculations
        clean_data = data[
            (data['Pipeline'] != 'SPAM Tickets') & 
            (data['Weekend_Ticket'] == False)
        ].copy()
        
        # Filter out LiveChat for response time analysis
        response_data = clean_data[clean_data['Pipeline'] != 'Live Chat '].copy()
        
        if response_data.empty:
            return []
            
        # Convert to datetime and add week column
        response_data['Create date'] = pd.to_datetime(response_data['Create date'])
        response_data['Week'] = response_data['Create date'].dt.to_period('W-MON')
        
        # Get individual agent data
        agent_data = response_data[response_data['Case Owner'] == agent_name].copy()
        
        weekly_data = []
        
        for week in sorted(response_data['Week'].unique()):
            week_data = response_data[response_data['Week'] == week]
            agent_week_data = agent_data[agent_data['Week'] == week]
            
            # Calculate team median for this week
            team_response_times = week_data['First Response Time (Hours)'].dropna()
            team_median = team_response_times.median() if len(team_response_times) > 0 else 0
            
            # Calculate individual median for this week
            if len(agent_week_data) > 0:
                agent_response_times = agent_week_data['First Response Time (Hours)'].dropna()
                agent_median = agent_response_times.median() if len(agent_response_times) > 0 else 0
                agent_tickets = len(agent_week_data)
            else:
                agent_median = 0
                agent_tickets = 0
                
            weekly_data.append({
                'week': str(week),
                'week_start': week.start_time.strftime('%m/%d'),
                'agent_median': agent_median,
                'agent_tickets': agent_tickets,
                'team_median': team_median,
                'total_tickets': len(week_data)
            })
            
        return weekly_data
    
    def _create_chart_data(self, individual: Dict, team: Dict, agent_name: str) -> str:
        """Create JavaScript for performance comparison chart."""
        # Get weekly data for the second chart
        weekly_data = self._create_weekly_data(agent_name)
        
        # Create weekly chart data using median times
        weekly_chart_js = ""
        if weekly_data:
            weeks = [w['week_start'] for w in weekly_data]
            agent_medians = [w['agent_median'] for w in weekly_data]
            team_medians = [w['team_median'] for w in weekly_data]
            agent_labels = [f"{median:.2f}h" if median > 0 else "0h" for median in agent_medians]
            team_labels = [f"{median:.2f}h" if median > 0 else "0h" for median in team_medians]
            
            weekly_chart_js = f"""
            var weeklyTrace1 = {{
                x: {weeks},
                y: {agent_medians},
                text: {agent_labels},
                textposition: 'inside',
                textfont: {{ color: 'black', size: 12, family: 'Arial Black' }},
                name: '{agent_name}',
                type: 'bar',
                marker: {{ color: '#00d4aa' }}
            }};
            
            var weeklyTrace2 = {{
                x: {weeks},
                y: {team_medians},
                text: {team_labels},
                textposition: 'inside',
                textfont: {{ color: 'black', size: 12, family: 'Arial Black' }},
                name: 'Team Median',
                type: 'bar',
                marker: {{ color: '#3498db' }}
            }};
            
            var weeklyLayout = {{
                title: {{
                    text: 'Weekly Performance Breakdown (Median Response Times)',
                    font: {{ color: '#e0e0e0' }}
                }},
                xaxis: {{
                    title: 'Week Starting',
                    color: '#e0e0e0'
                }},
                yaxis: {{
                    title: 'Median Response Hours',
                    color: '#e0e0e0'
                }},
                paper_bgcolor: 'rgba(23, 23, 35, 0.8)',
                plot_bgcolor: 'rgba(23, 23, 35, 0.8)',
                font: {{ color: '#e0e0e0' }},
                barmode: 'group'
            }};
            
            Plotly.newPlot('weeklyChart', [weeklyTrace1, weeklyTrace2], weeklyLayout);
            """
        
        return f"""
        var trace1 = {{
            x: ['Average Response', 'Median Response'],
            y: [{individual['avg_response_hours']:.3f}, {individual['median_response_hours']:.3f}],
            text: ['{individual['avg_response_hours']:.2f}h', '{individual['median_response_hours']:.2f}h'],
            textposition: 'inside',
            textfont: {{ color: 'black', size: 14, family: 'Arial Black' }},
            name: '{agent_name}',
            type: 'bar',
            marker: {{ color: '#00d4aa' }}
        }};
        
        var trace2 = {{
            x: ['Average Response', 'Median Response'],
            y: [{team['avg_response_hours']:.3f}, {team['median_response_hours']:.3f}],
            text: ['{team['avg_response_hours']:.2f}h', '{team['median_response_hours']:.2f}h'],
            textposition: 'inside',
            textfont: {{ color: 'black', size: 14, family: 'Arial Black' }},
            name: 'Team Average',
            type: 'bar',
            marker: {{ color: '#3498db' }}
        }};
        
        var layout = {{
            title: {{
                text: 'Individual vs Team Performance Comparison',
                font: {{ color: '#e0e0e0' }}
            }},
            xaxis: {{
                title: 'Metrics',
                color: '#e0e0e0'
            }},
            yaxis: {{
                title: 'Hours',
                color: '#e0e0e0'
            }},
            paper_bgcolor: 'rgba(23, 23, 35, 0.8)',
            plot_bgcolor: 'rgba(23, 23, 35, 0.8)',
            font: {{ color: '#e0e0e0' }},
            barmode: 'group'
        }};
        
        Plotly.newPlot('performanceChart', [trace1, trace2], layout);
        
        {weekly_chart_js}
        """