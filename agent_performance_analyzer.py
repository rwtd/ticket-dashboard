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
    
    def analyze_performance(self, period: str = 'all', custom_start_date: str = None, custom_end_date: str = None) -> Dict:
        """Generate agent performance analysis for specified period"""
        if self.df is None:
            raise ValueError("No data loaded. Call load_data() and process_data() first.")
        
        # Filter by time period
        filtered_df = self._filter_by_period(self.df, period, custom_start_date, custom_end_date)
        
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
        
        # Calculate weekly data for charts
        weekly_data = self._calculate_weekly_data(filtered_df, agents)

        # Calculate pipeline breakdown data
        pipeline_data = self._calculate_pipeline_breakdown(filtered_df, agents)

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
            'weekly_data': weekly_data,
            'pipeline_data': pipeline_data,
            'summary': self._generate_insights(stats_df, period)
        }
    
    def _filter_by_period(self, df: pd.DataFrame, period: str, custom_start_date: str = None, custom_end_date: str = None) -> pd.DataFrame:
        """Filter dataframe by time period"""
        if period == 'custom':
            # Handle custom date range
            filtered_df = df.copy()

            if custom_start_date:
                start_date = pd.to_datetime(custom_start_date)
                # Make timezone-aware if needed
                if start_date.tz is None and filtered_df['Create date'].dt.tz is not None:
                    start_date = start_date.tz_localize(filtered_df['Create date'].dt.tz)
                elif start_date.tz is not None and filtered_df['Create date'].dt.tz is None:
                    start_date = start_date.tz_localize(None)
                filtered_df = filtered_df[filtered_df['Create date'] >= start_date]

            if custom_end_date:
                end_date = pd.to_datetime(custom_end_date) + timedelta(days=1)  # Include the end date
                # Make timezone-aware if needed
                if end_date.tz is None and filtered_df['Create date'].dt.tz is not None:
                    end_date = end_date.tz_localize(filtered_df['Create date'].dt.tz)
                elif end_date.tz is not None and filtered_df['Create date'].dt.tz is None:
                    end_date = end_date.tz_localize(None)
                filtered_df = filtered_df[filtered_df['Create date'] < end_date]

            return filtered_df

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

    def _calculate_weekly_data(self, df: pd.DataFrame, agents: List[str]) -> Dict:
        """Calculate weekly response times and volumes by agent"""
        # Create week column
        df_weekly = df.copy()
        df_weekly['Week'] = df_weekly['Create date'].dt.to_period('W-MON')

        # Filter weekday non-livechat data for response times
        weekday_df = df_weekly[df_weekly['Weekend_Ticket'] == False]
        non_livechat_df = weekday_df[weekday_df['Pipeline'] != 'Live Chat ']

        weekly_response_data = []
        weekly_volume_data = []

        # Get all weeks in the data
        all_weeks = sorted(df_weekly['Week'].unique())

        for week in all_weeks:
            week_str = str(week.start_time.date())

            # Volume data (all tickets including LiveChat)
            week_volume_data = {'week': week_str}
            week_total = 0

            for agent in agents:
                agent_week_data = df_weekly[(df_weekly['Week'] == week) & (df_weekly['Case Owner'] == agent)]
                count = len(agent_week_data)
                week_volume_data[agent] = count
                week_total += count

            week_volume_data['total'] = week_total
            weekly_volume_data.append(week_volume_data)

            # Response time data (weekday non-livechat only)
            week_response_data = {'week': week_str}

            for agent in agents:
                agent_week_data = non_livechat_df[(non_livechat_df['Week'] == week) & (non_livechat_df['Case Owner'] == agent)]
                response_times = agent_week_data['First Response Time (Hours)'].dropna()

                if len(response_times) > 0:
                    week_response_data[agent] = response_times.median()
                else:
                    week_response_data[agent] = None

            weekly_response_data.append(week_response_data)

        return {
            'response_times': weekly_response_data,
            'volumes': weekly_volume_data,
            'agents': agents,
            'weeks': [str(week.start_time.date()) for week in all_weeks]
        }

    def _calculate_pipeline_breakdown(self, df: pd.DataFrame, agents: List[str]) -> Dict:
        """Calculate pipeline distribution and performance by agent"""
        # Exclude SPAM tickets for cleaner analysis
        clean_df = df[df['Pipeline'] != 'SPAM Tickets'].copy()

        # Get top pipelines (excluding SPAM)
        pipeline_counts = clean_df['Pipeline'].value_counts()
        top_pipelines = pipeline_counts.head(6).index.tolist()  # Top 6 pipelines

        # Agent pipeline distribution
        pipeline_distribution = []
        pipeline_performance = []

        for agent in agents:
            agent_data = clean_df[clean_df['Case Owner'] == agent]

            if len(agent_data) > 0:
                # Distribution data
                distribution = {'agent': agent}
                total_agent_tickets = len(agent_data)

                for pipeline in top_pipelines:
                    pipeline_tickets = len(agent_data[agent_data['Pipeline'] == pipeline])
                    distribution[pipeline] = pipeline_tickets
                    # Also calculate percentage
                    distribution[f"{pipeline}_pct"] = (pipeline_tickets / total_agent_tickets * 100) if total_agent_tickets > 0 else 0

                pipeline_distribution.append(distribution)

                # Performance data (response times by pipeline)
                performance = {'agent': agent}
                for pipeline in top_pipelines:
                    pipeline_data = agent_data[agent_data['Pipeline'] == pipeline]
                    # Exclude LiveChat for response time analysis
                    if pipeline != 'Live Chat ':
                        response_times = pipeline_data['First Response Time (Hours)'].dropna()
                        if len(response_times) > 0:
                            performance[f"{pipeline}_median"] = response_times.median()
                            performance[f"{pipeline}_count"] = len(response_times)
                        else:
                            performance[f"{pipeline}_median"] = None
                            performance[f"{pipeline}_count"] = 0
                    else:
                        # LiveChat has fixed 30-second response
                        performance[f"{pipeline}_median"] = 0.008  # 30 seconds in hours
                        performance[f"{pipeline}_count"] = len(pipeline_data)

                pipeline_performance.append(performance)

        # Overall pipeline summary
        pipeline_summary = []
        for pipeline in top_pipelines:
            pipeline_tickets = clean_df[clean_df['Pipeline'] == pipeline]
            summary = {
                'pipeline': pipeline,
                'total_tickets': len(pipeline_tickets),
                'percentage': (len(pipeline_tickets) / len(clean_df) * 100) if len(clean_df) > 0 else 0
            }

            # Median response time for this pipeline (non-LiveChat)
            if pipeline != 'Live Chat ':
                response_times = pipeline_tickets['First Response Time (Hours)'].dropna()
                if len(response_times) > 0:
                    summary['avg_response_hours'] = response_times.mean()
                    summary['median_response_hours'] = response_times.median()
                else:
                    summary['avg_response_hours'] = None
                    summary['median_response_hours'] = None
            else:
                summary['avg_response_hours'] = 0.008
                summary['median_response_hours'] = 0.008

            pipeline_summary.append(summary)

        return {
            'distribution': pipeline_distribution,
            'performance': pipeline_performance,
            'summary': pipeline_summary,
            'pipelines': top_pipelines
        }

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
            '8_weeks': 'Last 8 Weeks',
            'custom': 'Custom Date Range'
        }
        return descriptions.get(period, period)
    
    def generate_dashboard_html(self, analysis: Dict) -> str:
        """Generate HTML dashboard from analysis results"""
        if 'error' in analysis:
            return f"<html><body><h1>Error</h1><p>{analysis['error']}</p></body></html>"
        
        period = analysis['period']
        date_info = analysis['date_info']
        agent_stats = analysis['agent_stats']
        weekly_data = analysis['weekly_data']
        pipeline_data = analysis['pipeline_data']
        insights = analysis['summary']

        # Generate the dashboard HTML using the same template as our standalone dashboards
        template = self._get_dashboard_template()

        # Prepare data for the template
        dashboard_data = {
            'period_title': self._get_period_description(period),
            'date_range': f"{date_info['start_date']} to {date_info['end_date']}",
            'agent_cards': self._generate_agent_cards(agent_stats),
            'chart_data': self._generate_chart_data(agent_stats),
            'weekly_charts': self._generate_weekly_charts(weekly_data),
            'pipeline_charts': self._generate_pipeline_charts(pipeline_data),
            'insights': self._generate_insights_html(insights, agent_stats)
        }
        
        return template.format(**dashboard_data)

    def _generate_weekly_charts(self, weekly_data: Dict) -> str:
        """Generate JavaScript for weekly response time and volume charts with trend lines"""
        try:
            import numpy as np
            from scipy import stats
        except ImportError:
            # Fall back to simple linear trend calculation
            def linregress(x, y):
                n = len(x)
                if n < 2:
                    return 0, 0, 0, 0, 0  # slope, intercept, r_value, p_value, std_err
                sum_x = sum(x)
                sum_y = sum(y)
                sum_xy = sum(xi * yi for xi, yi in zip(x, y))
                sum_x2 = sum(xi * xi for xi in x)
                slope = (n * sum_xy - sum_x * sum_y) / (n * sum_x2 - sum_x * sum_x)
                intercept = (sum_y - slope * sum_x) / n
                return slope, intercept, 0, 0, 0

            class stats:
                linregress = staticmethod(linregress)

        agents = weekly_data['agents']
        weeks = weekly_data['weeks']
        response_data = weekly_data['response_times']
        volume_data = weekly_data['volumes']

        # Colors for each agent
        colors = {'Nova': '#4ecdc4', 'Girly': '#ff6b6b', 'Francis': '#feca57', 'Bhushan': '#a29bfe'}

        js_code = f"""
        // Weekly Response Time Chart Data
        const weeks = {weeks};
        const agentColors = {colors};
        """

        # Generate response time traces for each agent
        js_code += "\nconst responseTraces = [];\n"
        for agent in agents:
            agent_response_times = []
            for week_data in response_data:
                value = week_data.get(agent)
                agent_response_times.append(value if value is not None else None)

            # Calculate trend line
            valid_points = [(i, val) for i, val in enumerate(agent_response_times) if val is not None]
            if len(valid_points) > 1:
                x_vals, y_vals = zip(*valid_points)
                slope, intercept, r_value, p_value, std_err = stats.linregress(x_vals, y_vals)
                trend_line = [slope * i + intercept for i in range(len(weeks))]
            else:
                trend_line = [None] * len(weeks)

            js_code += f"""
responseTraces.push({{
    x: weeks,
    y: {agent_response_times},
    name: '{agent}',
    type: 'scatter',
    mode: 'lines+markers',
    line: {{ color: agentColors['{agent}'], width: 3 }},
    marker: {{ size: 8, color: agentColors['{agent}'] }},
    connectgaps: false
}});

responseTraces.push({{
    x: weeks,
    y: {trend_line},
    name: '{agent} Trend',
    type: 'scatter',
    mode: 'lines',
    line: {{ color: agentColors['{agent}'], width: 2, dash: 'dash' }},
    showlegend: false,
    hoverinfo: 'skip'
}});
"""

        # Generate volume traces for each agent
        js_code += "\nconst volumeTraces = [];\n"
        for agent in agents:
            agent_volumes = [week_data.get(agent, 0) for week_data in volume_data]

            # Calculate trend line
            x_vals = list(range(len(agent_volumes)))
            slope, intercept, r_value, p_value, std_err = stats.linregress(x_vals, agent_volumes)
            trend_line = [slope * i + intercept for i in range(len(weeks))]

            js_code += f"""
volumeTraces.push({{
    x: weeks,
    y: {agent_volumes},
    name: '{agent}',
    type: 'scatter',
    mode: 'lines+markers',
    line: {{ color: agentColors['{agent}'], width: 3 }},
    marker: {{ size: 8, color: agentColors['{agent}'] }}
}});

volumeTraces.push({{
    x: weeks,
    y: {trend_line},
    name: '{agent} Trend',
    type: 'scatter',
    mode: 'lines',
    line: {{ color: agentColors['{agent}'], width: 2, dash: 'dash' }},
    showlegend: false,
    hoverinfo: 'skip'
}});
"""

        # Generate the actual charts
        js_code += """
// Create Weekly Response Time Chart
Plotly.newPlot('weeklyResponseChart', responseTraces, {
    title: {
        text: 'Weekly Median Response Times by Agent',
        font: { size: 20, color: '#e0e0e0' }
    },
    xaxis: {
        title: 'Week',
        color: '#e0e0e0',
        gridcolor: '#444',
        tickangle: -45
    },
    yaxis: {
        title: 'Median Response Time (Hours)',
        color: '#e0e0e0',
        gridcolor: '#444'
    },
    plot_bgcolor: 'rgba(0,0,0,0)',
    paper_bgcolor: 'rgba(0,0,0,0)',
    font: { color: '#e0e0e0' },
    legend: {
        font: { color: '#e0e0e0' }
    }
}, {responsive: true});

// Create Weekly Volume Chart
Plotly.newPlot('weeklyVolumeChart', volumeTraces, {
    title: {
        text: 'Weekly Ticket Volume by Agent',
        font: { size: 20, color: '#e0e0e0' }
    },
    xaxis: {
        title: 'Week',
        color: '#e0e0e0',
        gridcolor: '#444',
        tickangle: -45
    },
    yaxis: {
        title: 'Number of Tickets',
        color: '#e0e0e0',
        gridcolor: '#444'
    },
    plot_bgcolor: 'rgba(0,0,0,0)',
    paper_bgcolor: 'rgba(0,0,0,0)',
    font: { color: '#e0e0e0' },
    legend: {
        font: { color: '#e0e0e0' }
    }
}, {responsive: true});
"""

        return js_code

    def _generate_pipeline_charts(self, pipeline_data: Dict) -> str:
        """Generate JavaScript for pipeline breakdown charts"""
        agents = [d['agent'] for d in pipeline_data['distribution']]
        pipelines = pipeline_data['pipelines']
        distribution_data = pipeline_data['distribution']
        performance_data = pipeline_data['performance']

        # Colors for pipelines
        pipeline_colors = {
            'Support Pipeline': '#4ecdc4',
            'Live Chat ': '#ff6b6b',
            'Dev Tickets': '#feca57',
            'Enterprise and VIP Tickets': '#a29bfe',
            'Marketing, Finance': '#fd79a8',
            'Success': '#00b894'
        }

        js_code = f"""
        // Pipeline Distribution Chart Data
        const pipelineAgents = {agents};
        const pipelines = {pipelines};
        const pipelineColors = {pipeline_colors};
        """

        # Generate stacked bar chart for pipeline distribution
        js_code += "\nconst distributionTraces = [];\n"
        for pipeline in pipelines:
            pipeline_counts = []
            for dist_data in distribution_data:
                pipeline_counts.append(dist_data.get(pipeline, 0))

            color = pipeline_colors.get(pipeline, '#95a5a6')
            js_code += f"""
distributionTraces.push({{
    x: pipelineAgents,
    y: {pipeline_counts},
    name: '{pipeline}',
    type: 'bar',
    marker: {{ color: '{color}' }}
}});
"""

        # Generate pipeline performance heatmap data
        js_code += "\nconst performanceData = [];\n"
        js_code += "const performanceAgents = [];\n"
        js_code += "const performancePipelines = [];\n"
        js_code += "const performanceValues = [];\n"

        for perf_data in performance_data:
            agent = perf_data['agent']
            for pipeline in pipelines:
                if pipeline != 'Live Chat ':  # Skip LiveChat for response time heatmap
                    median_key = f"{pipeline}_median"
                    if median_key in perf_data and perf_data[median_key] is not None:
                        js_code += f"performanceAgents.push('{agent}');\n"
                        js_code += f"performancePipelines.push('{pipeline}');\n"
                        js_code += f"performanceValues.push({perf_data[median_key]:.3f});\n"

        # Create the charts
        js_code += """
// Create Pipeline Distribution Chart (Stacked Bar)
Plotly.newPlot('pipelineDistributionChart', distributionTraces, {
    title: {
        text: 'Pipeline Distribution by Agent',
        font: { size: 20, color: '#e0e0e0' }
    },
    xaxis: {
        title: 'Agent',
        color: '#e0e0e0',
        gridcolor: '#444'
    },
    yaxis: {
        title: 'Number of Tickets',
        color: '#e0e0e0',
        gridcolor: '#444'
    },
    barmode: 'stack',
    plot_bgcolor: 'rgba(0,0,0,0)',
    paper_bgcolor: 'rgba(0,0,0,0)',
    font: { color: '#e0e0e0' },
    legend: {
        font: { color: '#e0e0e0' }
    }
}, {responsive: true});

// Create Pipeline Performance Heatmap
const uniqueAgents = [...new Set(performanceAgents)];
const uniquePipelines = [...new Set(performancePipelines)];

// Create matrix for heatmap
const heatmapZ = [];
const heatmapText = [];

for (let i = 0; i < uniquePipelines.length; i++) {
    heatmapZ[i] = [];
    heatmapText[i] = [];
    for (let j = 0; j < uniqueAgents.length; j++) {
        const agent = uniqueAgents[j];
        const pipeline = uniquePipelines[i];

        // Find the performance value
        let value = null;
        for (let k = 0; k < performanceAgents.length; k++) {
            if (performanceAgents[k] === agent && performancePipelines[k] === pipeline) {
                value = performanceValues[k];
                break;
            }
        }

        heatmapZ[i][j] = value;
        heatmapText[i][j] = value ? `${value.toFixed(2)}h` : 'N/A';
    }
}

Plotly.newPlot('pipelinePerformanceChart', [{
    z: heatmapZ,
    x: uniqueAgents,
    y: uniquePipelines,
    text: heatmapText,
    texttemplate: '%{text}',
    textfont: { color: 'white', size: 12 },
    type: 'heatmap',
    colorscale: [
        [0, '#2c3e50'],
        [0.5, '#f39c12'],
        [1, '#e74c3c']
    ],
    showscale: true,
    colorbar: {
        title: 'Response Time (Hours)',
        titlefont: { color: '#e0e0e0' },
        tickfont: { color: '#e0e0e0' }
    }
}], {
    title: {
        text: 'Response Time by Agent and Pipeline',
        font: { size: 20, color: '#e0e0e0' }
    },
    xaxis: {
        title: 'Agent',
        color: '#e0e0e0',
        gridcolor: '#444'
    },
    yaxis: {
        title: 'Pipeline',
        color: '#e0e0e0',
        gridcolor: '#444'
    },
    plot_bgcolor: 'rgba(0,0,0,0)',
    paper_bgcolor: 'rgba(0,0,0,0)',
    font: { color: '#e0e0e0' }
}, {responsive: true});
"""

        return js_code

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
                .chart-container {{ background: rgba(23, 23, 35, 0.8); border-radius: 15px; padding: 20px; margin-bottom: 40px; }}
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
                    <h2 style="color: #00d4aa; margin-bottom: 20px;">📊 Weekly Median Response Times</h2>
                    <div id="weeklyResponseChart" style="height: 500px;"></div>
                </div>

                <div class="chart-container">
                    <h2 style="color: #00d4aa; margin-bottom: 20px;">📈 Weekly Ticket Volume</h2>
                    <div id="weeklyVolumeChart" style="height: 500px;"></div>
                </div>

                <div class="chart-container">
                    <h2 style="color: #00d4aa; margin-bottom: 20px;">🎯 Performance vs Volume Overview</h2>
                    <div id="comparisonChart" style="height: 400px;"></div>
                </div>

                <div class="chart-container">
                    <h2 style="color: #00d4aa; margin-bottom: 20px;">🔀 Pipeline Distribution by Agent</h2>
                    <div id="pipelineDistributionChart" style="height: 500px;"></div>
                </div>

                <div class="chart-container">
                    <h2 style="color: #00d4aa; margin-bottom: 20px;">🌡️ Response Time Heatmap by Pipeline</h2>
                    <div id="pipelinePerformanceChart" style="height: 400px;"></div>
                </div>

                <div class="insights">
                    {insights}
                </div>
            </div>

            <script>
                {weekly_charts}
                {pipeline_charts}
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