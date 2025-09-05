#!/usr/bin/env python3
"""
Chat Data Processor for LiveChat Analytics
Processes chat CSV exports and generates comprehensive analytics
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import pytz
from pathlib import Path
from typing import Dict, List, Tuple, Optional, Any
import logging

try:
    import plotly.graph_objects as go
    from plotly.subplots import make_subplots
    PLOTLY_AVAILABLE = True
except ImportError:
    PLOTLY_AVAILABLE = False
    print("Plotly not available for interactive charts")

class ChatDataProcessor:
    """Process chat data CSV files and generate analytics"""
    
    def __init__(self):
        """Initialize the processor"""
        self.df = None
        self.original_count = 0
        
        # Define known bots and human agents
        self.bots = ['Wynn AI', 'Sales Agent', 'Traject Data Live Chat', 'Traject Data Customer Support', 'Agent Scrape', 'ChatBot', 'Customer Support TEST Bot']
        self.human_agents = ['Shan', 'Girly', 'Chris', 'Nora', 'Gillie', 'Bill jones', 'Bhushan', 'Francis', 'Nova', 'Richie Waugh', 'Spencer Dupee']
        
        # Human agent name mapping (pseudonym → real name)
        self.human_agent_mapping = {
            'Shan': 'Bhushan',
            'Chris': 'Francis', 
            'Nora': 'Nova',
            'Gillie': 'Girly',
            'Girly': 'Girly',  # Keep real name
            'Bhushan': 'Bhushan',  # Keep real name
            'Francis': 'Francis',  # Keep real name
            'Nova': 'Nova'  # Keep real name
        }
        
        # Bot display name mapping
        self.bot_display_names = {
            'Wynn AI': 'Wynn AI',
            'Sales Agent': 'Wynn AI',  # Sales Agent is same as Wynn AI
            'Traject Data Live Chat': 'Agent Scrape',
            'Traject Data Customer Support': 'Agent Scrape',
            'Agent Scrape': 'Agent Scrape',
            'ChatBot': 'Agent Scrape',  # ChatBot is same as Agent Scrape
            'Customer Support TEST Bot': 'Test Bot'
        }
        
        # Setup logging
        logging.basicConfig(level=logging.INFO)
        self.logger = logging.getLogger(__name__)
    
    def load_data(self, file_paths: List[Path]) -> None:
        """Load chat data from CSV files"""
        dfs = []
        
        for file_path in file_paths:
            if not file_path.exists():
                self.logger.warning(f"File not found: {file_path}")
                continue
                
            try:
                df = pd.read_csv(file_path)
                self.logger.info(f"Loaded {len(df)} records from {file_path.name}")
                dfs.append(df)
            except Exception as e:
                self.logger.error(f"Error loading {file_path}: {e}")
                continue
        
        if not dfs:
            error_msg = f"No valid chat data files found from {len(file_paths)} files. "
            if file_paths:
                error_msg += f"Files attempted: {[f.name for f in file_paths]}"
            raise ValueError(error_msg)
        
        # Combine all dataframes
        self.df = pd.concat(dfs, ignore_index=True)
        self.original_count = len(self.df)
        self.logger.info(f"Total records loaded: {self.original_count}")
    
    def process_data(self) -> None:
        """Process and clean chat data"""
        if self.df is None:
            raise ValueError("No data loaded. Call load_data() first.")
        
        # Detect and normalize column names
        self._normalize_columns()
        
        # Convert date columns to datetime
        self.df['chat_creation_date'] = pd.to_datetime(self.df['chat_creation_date_raw'])
        self.df['chat_start_date'] = pd.to_datetime(self.df['chat_start_date_raw'])
        
        # Convert to Atlantic timezone
        atlantic = pytz.timezone("Canada/Atlantic")
        
        # Handle timezone conversion based on detected source timezone
        if hasattr(self, 'source_timezone') and self.source_timezone == 'America/Moncton':
            # Data is already in Atlantic time zone (Moncton), just localize
            self.df['chat_creation_date_adt'] = self.df['chat_creation_date'].dt.tz_localize(atlantic, ambiguous=False, nonexistent='shift_forward')
        else:
            # Data is in UTC, convert to Atlantic
            self.df['chat_creation_date_adt'] = self.df['chat_creation_date'].dt.tz_localize('UTC').dt.tz_convert(atlantic)
        
        # Extract date components for grouping
        self.df['date'] = self.df['chat_creation_date_adt'].dt.date
        self.df['hour'] = self.df['chat_creation_date_adt'].dt.hour
        self.df['day_of_week'] = self.df['chat_creation_date_adt'].dt.day_name()
        
        # Process agent information
        self.df['primary_agent'] = self.df['primary_agent_raw'].fillna('Unknown')
        self.df['secondary_agent'] = self.df['secondary_agent_raw'].fillna('')
        
        # Apply display name mapping for bots
        self.df['display_agent'] = self.df['primary_agent'].apply(self._get_display_name)
        
        # Identify agent types
        self.df['agent_type'] = self.df['primary_agent'].apply(self._classify_agent)
        
        # Process satisfaction ratings
        self.df['has_rating'] = ~self.df['rate_raw'].isin(['not rated', '', None]).fillna(True)
        self.df['rating_value'] = self.df['rate_raw'].apply(self._normalize_rating)
        
        # Identify transfers from bot to human
        self.df['bot_transfer'] = (
            (self.df['tag1_raw'] == 'chatbot-transfer') |
            (self.df['tag2_raw'] == 'chatbot-transfer') |
            (self.df['secondary_agent'] != '')
        ).fillna(False)
        
        # Convert duration to numeric
        self.df['duration_seconds'] = pd.to_numeric(self.df['duration_raw'], errors='coerce').fillna(0)
        self.df['duration_minutes'] = self.df['duration_seconds'] / 60
        
        # Response time metrics
        self.df['first_response_time'] = pd.to_numeric(self.df['first_response_raw'], errors='coerce').fillna(0)
        self.df['avg_response_time'] = pd.to_numeric(self.df['avg_response_raw'], errors='coerce').fillna(0)
        
        self.logger.info("Data processing completed")
    
    def _normalize_columns(self) -> None:
        """Normalize column names to handle different CSV formats"""
        columns = self.df.columns.tolist()
        
        # Find date columns with flexible matching (new format is primary)
        date_patterns = [
            ('chat_creation_date_raw', ['chat creation date America/Moncton', 'chat creation date UTC']),
            ('chat_start_date_raw', ['chat start date America/Moncton', 'chat start date UTC']),
            ('primary_agent_raw', ['operator 1 nick']),
            ('secondary_agent_raw', ['operator 2 nick']),
            ('rate_raw', ['rate']),
            ('duration_raw', ['chat duration in seconds']),
            ('first_response_raw', ['first response time']),
            ('avg_response_raw', ['average response time']),
            ('country_raw', ['visitor country code']),
            ('tag1_raw', ['tag 1']),
            ('tag2_raw', ['tag 2'])
        ]
        
        # Map columns
        for target, patterns in date_patterns:
            found = False
            for pattern in patterns:
                if pattern in columns:
                    self.df[target] = self.df[pattern]
                    found = True
                    break
            if not found:
                self.logger.warning(f"Column not found for {target}, patterns: {patterns}")
                self.df[target] = None
        
        # Detect timezone from column name
        if 'chat creation date America/Moncton' in columns:
            self.source_timezone = 'America/Moncton'
            self.logger.info("Detected source timezone: America/Moncton")
        else:
            self.source_timezone = 'UTC'
            self.logger.info("Detected source timezone: UTC")
    
    def _classify_agent(self, agent_name: str) -> str:
        """Classify agent as bot, human, or unknown"""
        if agent_name in self.bots:
            return 'bot'
        elif agent_name in self.human_agents:
            return 'human'
        else:
            return 'unknown'
    
    def _get_display_name(self, agent_name: str) -> str:
        """Get display name for agent (handles bot and human name mapping)"""
        # Check bot mapping first
        if agent_name in self.bot_display_names:
            return self.bot_display_names[agent_name]
        # Check human agent mapping
        elif agent_name in self.human_agent_mapping:
            return self.human_agent_mapping[agent_name]
        # Return original name if no mapping found
        else:
            return agent_name
    
    def _normalize_rating(self, rating: str) -> Optional[int]:
        """Convert rating text to numeric value (1=bad, 5=good)"""
        if pd.isna(rating) or rating == 'not rated':
            return None
        elif 'bad' in rating.lower():
            return 1
        elif 'good' in rating.lower():
            return 5
        else:
            return None
    
    def filter_date_range(self, start_date: Optional[datetime], end_date: Optional[datetime]) -> Tuple[pd.DataFrame, int, int]:
        """Filter data by date range"""
        if self.df is None:
            raise ValueError("No data loaded")
        
        original_count = len(self.df)
        
        if start_date is None and end_date is None:
            return self.df.copy(), original_count, original_count
        
        filtered_df = self.df.copy()
        
        if start_date:
            filtered_df = filtered_df[filtered_df['chat_creation_date_adt'] >= start_date]
        
        if end_date:
            filtered_df = filtered_df[filtered_df['chat_creation_date_adt'] <= end_date]
        
        filtered_count = len(filtered_df)
        
        return filtered_df, original_count, filtered_count
    
    def generate_analytics(self, df: pd.DataFrame, args: Any) -> Dict[str, Any]:
        """Generate comprehensive chat analytics"""
        analytics = {}
        
        # Basic metrics
        analytics['total_chats'] = len(df)
        analytics['date_range'] = {
            'start': df['date'].min(),
            'end': df['date'].max()
        }
        
        # Volume metrics
        analytics['volume_by_date'] = self._calculate_volume_metrics(df)
        analytics['volume_by_hour'] = self._calculate_hourly_volume(df)
        analytics['volume_trends'] = self._calculate_volume_trends(df)
        
        # Agent performance
        analytics['bot_metrics'] = self._calculate_bot_metrics(df)
        analytics['human_metrics'] = self._calculate_human_metrics(df)
        analytics['agent_performance'] = self._calculate_agent_performance(df)
        
        # Satisfaction ratings
        analytics['satisfaction_metrics'] = self._calculate_satisfaction_metrics(df)
        
        # Transfer metrics
        analytics['transfer_metrics'] = self._calculate_transfer_metrics(df)
        
        # Response time metrics
        analytics['response_time_metrics'] = self._calculate_response_time_metrics(df)
        
        # Geographic metrics
        analytics['geographic_metrics'] = self._calculate_geographic_metrics(df)
        
        # Generate interactive charts
        analytics['charts'] = []
        if PLOTLY_AVAILABLE:
            # Weekly volume chart with bot performance
            weekly_chart = self._create_weekly_volume_chart(df)
            if weekly_chart:
                analytics['charts'].append(weekly_chart)
            
            # Weekly satisfaction chart
            weekly_satisfaction_chart = self._create_weekly_satisfaction_chart(df)
            if weekly_satisfaction_chart:
                analytics['charts'].append(weekly_satisfaction_chart)
            
            # Individual agent volume and duration charts
            agent_charts = self._create_individual_agent_charts(df)
            analytics['charts'].extend(agent_charts)
            
            # Bot performance comparison charts
            bot_charts = self._create_bot_performance_charts(df)
            analytics['charts'].extend(bot_charts)
            
            # Chat volume and satisfaction trends
            trends_chart = self._create_chat_trends_chart(df)
            if trends_chart:
                analytics['charts'].append(trends_chart)
        
        return analytics
    
    def _calculate_volume_metrics(self, df: pd.DataFrame) -> Dict[str, Any]:
        """Calculate volume metrics by date"""
        daily_volume = df.groupby('date').size().reset_index(name='count')
        daily_volume['date_str'] = daily_volume['date'].astype(str)
        
        # Calculate weekly volumes (Monday to Sunday)
        df_with_week = df.copy()
        # Remove timezone before converting to period to avoid warning
        df_with_week['week_start'] = df_with_week['chat_creation_date_adt'].dt.tz_localize(None).dt.to_period('W-MON').dt.start_time
        weekly_volume = df_with_week.groupby('week_start').size().reset_index(name='count')
        weekly_volume['week_str'] = weekly_volume['week_start'].dt.strftime('%Y-%m-%d')
        
        return {
            'daily': daily_volume.to_dict('records'),
            'weekly': weekly_volume.to_dict('records'),
            'total_days': len(daily_volume),
            'avg_daily': daily_volume['count'].mean(),
            'peak_day': daily_volume.loc[daily_volume['count'].idxmax()].to_dict() if len(daily_volume) > 0 else None
        }
    
    def _calculate_hourly_volume(self, df: pd.DataFrame) -> Dict[str, Any]:
        """Calculate volume by hour of day"""
        hourly_volume = df.groupby('hour').size().reset_index(name='count')
        
        return {
            'hourly_distribution': hourly_volume.to_dict('records'),
            'peak_hour': hourly_volume.loc[hourly_volume['count'].idxmax()]['hour'] if len(hourly_volume) > 0 else None,
            'business_hours_ratio': len(df[(df['hour'] >= 9) & (df['hour'] <= 17)]) / len(df) if len(df) > 0 else 0
        }
    
    def _calculate_volume_trends(self, df: pd.DataFrame) -> Dict[str, Any]:
        """Calculate volume trends"""
        if len(df) < 2:
            return {'trend': 'insufficient_data'}
        
        daily_volume = df.groupby('date').size()
        
        # Simple linear trend calculation
        x = np.arange(len(daily_volume))
        y = daily_volume.values
        trend_slope = np.polyfit(x, y, 1)[0] if len(x) > 1 else 0
        
        return {
            'trend_slope': trend_slope,
            'trend_direction': 'increasing' if trend_slope > 0 else 'decreasing' if trend_slope < 0 else 'stable',
            'growth_rate': (daily_volume.iloc[-1] - daily_volume.iloc[0]) / daily_volume.iloc[0] * 100 if daily_volume.iloc[0] > 0 else 0
        }
    
    def _calculate_bot_metrics(self, df: pd.DataFrame) -> Dict[str, Any]:
        """Calculate bot-specific metrics"""
        bot_chats = df[df['agent_type'] == 'bot']
        
        if len(bot_chats) == 0:
            return {'total': 0, 'bots': {}}
        
        bot_performance = {}
        # Use display_agent for consistency with charts
        for bot in self.bots:
            bot_data = bot_chats[bot_chats['primary_agent'] == bot]
            if len(bot_data) > 0:  # Only include bots that have chats
                # Use display name for consistency
                display_name = self._get_display_name(bot)
                bot_performance[display_name] = {
                    'total_chats': len(bot_data),
                    'avg_duration': bot_data['duration_minutes'].mean(),
                    'satisfaction_count': len(bot_data[bot_data['has_rating']]),
                    'avg_satisfaction': bot_data['rating_value'].mean() if bot_data['rating_value'].notna().any() else None
                }
        
        return {
            'total': len(bot_chats),
            'percentage': len(bot_chats) / len(df) * 100,
            'bots': bot_performance,
            'avg_duration': bot_chats['duration_minutes'].mean()
        }
    
    def _calculate_human_metrics(self, df: pd.DataFrame) -> Dict[str, Any]:
        """Calculate human agent metrics"""
        human_chats = df[df['agent_type'] == 'human']
        
        if len(human_chats) == 0:
            return {'total': 0, 'percentage': 0, 'agents': {}, 'avg_duration': 0}
        
        agent_performance = {}
        for agent in self.human_agents:
            # Check both primary and secondary agent fields
            agent_data = df[(df['primary_agent'] == agent) | (df['secondary_agent'] == agent)]
            if len(agent_data) > 0:  # Only include agents with chats
                # Get standardized display name
                display_name = self.human_agent_mapping.get(agent, agent)
                agent_performance[display_name] = {
                    'total_chats': len(agent_data),
                    'avg_duration': agent_data['duration_minutes'].mean(),
                    'satisfaction_count': len(agent_data[agent_data['has_rating']]),
                    'avg_satisfaction': agent_data['rating_value'].mean() if agent_data['rating_value'].notna().any() else None,
                    'transfers_received': len(agent_data[agent_data['bot_transfer']])
                }
        
        return {
            'total': len(human_chats),
            'percentage': len(human_chats) / len(df) * 100 if len(df) > 0 else 0,
            'agents': agent_performance,
            'avg_duration': human_chats['duration_minutes'].mean() if len(human_chats) > 0 else 0
        }
    
    def _calculate_agent_performance(self, df: pd.DataFrame) -> Dict[str, Any]:
        """Calculate overall agent performance comparison"""
        performance = {}
        
        for agent_type in ['bot', 'human']:
            type_data = df[df['agent_type'] == agent_type]
            if len(type_data) > 0:
                performance[agent_type] = {
                    'total_chats': len(type_data),
                    'avg_duration': type_data['duration_minutes'].mean(),
                    'avg_response_time': type_data['first_response_time'].mean(),
                    'satisfaction_rate': len(type_data[type_data['rating_value'] == 5]) / len(type_data[type_data['has_rating']]) * 100 if len(type_data[type_data['has_rating']]) > 0 else 0
                }
        
        return performance
    
    def _calculate_satisfaction_metrics(self, df: pd.DataFrame) -> Dict[str, Any]:
        """Calculate satisfaction rating metrics"""
        rated_chats = df[df['has_rating']]
        
        if len(rated_chats) == 0:
            return {
                'total_rated': 0,
                'overall_satisfaction_rate': 0,
                'overall_good': 0,
                'overall_bad': 0,
                'bot_satisfaction': {},
                'human_satisfaction': {},
                'rating_distribution': {}
            }
        
        # Overall satisfaction
        overall_good = len(rated_chats[rated_chats['rating_value'] == 5])
        overall_bad = len(rated_chats[rated_chats['rating_value'] == 1])
        
        # Bot satisfaction
        bot_rated = rated_chats[rated_chats['agent_type'] == 'bot']
        bot_satisfaction = {}
        for bot in self.bots:
            bot_data = bot_rated[bot_rated['primary_agent'] == bot]
            if len(bot_data) > 0:
                bot_satisfaction[bot] = {
                    'total_rated': len(bot_data),
                    'good_ratings': len(bot_data[bot_data['rating_value'] == 5]),
                    'bad_ratings': len(bot_data[bot_data['rating_value'] == 1]),
                    'satisfaction_rate': len(bot_data[bot_data['rating_value'] == 5]) / len(bot_data) * 100
                }
        
        # Human satisfaction  
        human_rated = rated_chats[rated_chats['agent_type'] == 'human']
        human_satisfaction = {}
        for agent in self.human_agents:
            agent_data = rated_chats[(rated_chats['primary_agent'] == agent) | (rated_chats['secondary_agent'] == agent)]
            if len(agent_data) > 0:
                human_satisfaction[agent] = {
                    'total_rated': len(agent_data),
                    'good_ratings': len(agent_data[agent_data['rating_value'] == 5]),
                    'bad_ratings': len(agent_data[agent_data['rating_value'] == 1]),
                    'satisfaction_rate': len(agent_data[agent_data['rating_value'] == 5]) / len(agent_data) * 100
                }
        
        return {
            'total_rated': len(rated_chats),
            'overall_satisfaction_rate': (overall_good / len(rated_chats) * 100) if len(rated_chats) > 0 else 0,
            'overall_good': overall_good,
            'overall_bad': overall_bad,
            'bot_satisfaction': bot_satisfaction,
            'human_satisfaction': human_satisfaction,
            'rating_distribution': rated_chats['rating_value'].value_counts().to_dict()
        }
    
    def _calculate_transfer_metrics(self, df: pd.DataFrame) -> Dict[str, Any]:
        """Calculate bot-to-human transfer metrics"""
        total_chats = len(df)
        bot_chats = df[df['agent_type'] == 'bot']
        transfers = df[df['bot_transfer']]
        
        # Daily transfer rates
        daily_transfers = df.groupby('date').agg({
            'bot_transfer': 'sum',
            'chat_creation_date': 'count'
        }).rename(columns={'chat_creation_date': 'total_chats'})
        daily_transfers['transfer_rate'] = daily_transfers['bot_transfer'] / daily_transfers['total_chats'] * 100
        daily_transfers['date_str'] = daily_transfers.index.astype(str)
        
        return {
            'total_transfers': len(transfers),
            'transfer_rate': len(transfers) / total_chats * 100 if total_chats > 0 else 0,
            'bot_only_chats': len(bot_chats) - len(transfers),
            'bot_only_rate': (len(bot_chats) - len(transfers)) / total_chats * 100 if total_chats > 0 else 0,
            'daily_transfer_rates': daily_transfers.reset_index().to_dict('records'),
            'avg_transfer_rate': daily_transfers['transfer_rate'].mean()
        }
    
    def _calculate_response_time_metrics(self, df: pd.DataFrame) -> Dict[str, Any]:
        """Calculate response time metrics"""
        return {
            'avg_first_response': df['first_response_time'].mean(),
            'avg_response_time': df['avg_response_time'].mean(),
            'bot_response_time': df[df['agent_type'] == 'bot']['first_response_time'].mean(),
            'human_response_time': df[df['agent_type'] == 'human']['first_response_time'].mean()
        }
    
    def _calculate_geographic_metrics(self, df: pd.DataFrame) -> Dict[str, Any]:
        """Calculate geographic distribution metrics"""
        country_dist = df['visitor country code'].value_counts().head(10)
        
        return {
            'top_countries': country_dist.to_dict(),
            'total_countries': df['visitor country code'].nunique(),
            'top_country': country_dist.index[0] if len(country_dist) > 0 else None
        }
    
    def create_summary_text(self, df: pd.DataFrame, label: str) -> str:
        """Create text summary of chat analytics"""
        analytics = self.generate_analytics(df, None)
        
        summary = f"""
# Chat Analytics Summary - {label}

## Overview
- Total Chats: {analytics['total_chats']:,}
- Date Range: {analytics['date_range']['start']} to {analytics['date_range']['end']}
- Average Daily Volume: {analytics['volume_by_date']['avg_daily']:.1f} chats

## Agent Performance
- Bot Chats: {analytics['bot_metrics']['total']:,} ({analytics['bot_metrics']['percentage']:.1f}%)
- Human Agent Chats: {analytics['human_metrics']['total']:,} ({analytics['human_metrics']['percentage']:.1f}%)

## Bot Performance
"""
        
        for bot, metrics in analytics['bot_metrics']['bots'].items():
            summary += f"- {bot}: {metrics['total_chats']:,} chats, {metrics['avg_duration']:.1f} min avg duration\n"
        
        summary += "\n## Human Agent Performance\n"
        for agent, metrics in analytics['human_metrics']['agents'].items():
            summary += f"- {agent}: {metrics['total_chats']:,} chats, {metrics['transfers_received']:,} transfers\n"
        
        summary += f"""
## Transfer Metrics
- Bot-to-Human Transfers: {analytics['transfer_metrics']['total_transfers']:,} ({analytics['transfer_metrics']['transfer_rate']:.1f}%)
- Bot-Only Resolutions: {analytics['transfer_metrics']['bot_only_chats']:,} ({analytics['transfer_metrics']['bot_only_rate']:.1f}%)

## Satisfaction Ratings
- Total Rated Chats: {analytics['satisfaction_metrics']['total_rated']:,}
- Overall Satisfaction Rate: {analytics['satisfaction_metrics']['overall_satisfaction_rate']:.1f}%

## Geographic Distribution
- Top Country: {analytics['geographic_metrics']['top_country']}
- Total Countries: {analytics['geographic_metrics']['total_countries']}
"""
        
        return summary
    
    def _create_weekly_volume_chart(self, df: pd.DataFrame) -> str:
        """Create weekly chat volume chart showing all available weeks from full dataset"""
        try:
            if not PLOTLY_AVAILABLE:
                return ""
            
            # IMPORTANT: Use full original dataset instead of filtered df for weekly trends
            # This ensures we see all historical weeks, not just the filtered period
            if self.df is not None and len(self.df) > 0:
                full_df = self.df.copy()
                print(f"DEBUG: Using full dataset with {len(full_df)} total records for weekly analysis")
            else:
                full_df = df.copy()
                print(f"DEBUG: Using filtered dataset with {len(full_df)} records for weekly analysis")
            
            # Calculate weekly volumes using full dataset
            full_df['week_start'] = full_df['chat_creation_date_adt'].dt.tz_localize(None).dt.to_period('W-MON').dt.start_time
            
            # Debug: Show date range in the data
            min_date = full_df['chat_creation_date_adt'].min()
            max_date = full_df['chat_creation_date_adt'].max()
            print(f"DEBUG: Date range in data: {min_date} to {max_date}")
            
            # Get weekly aggregated data with detailed debugging
            print("DEBUG: Calculating weekly aggregations...")
            weekly_all = full_df.groupby('week_start').size().reset_index(name='All_Chats')
            print(f"DEBUG: weekly_all shape: {weekly_all.shape}")
            
            weekly_bot = full_df[full_df['agent_type'] == 'bot'].groupby('week_start').size().reset_index(name='Bot_Chats')
            print(f"DEBUG: weekly_bot shape: {weekly_bot.shape}")
            
            weekly_human = full_df[full_df['agent_type'] == 'human'].groupby('week_start').size().reset_index(name='Human_Chats')
            print(f"DEBUG: weekly_human shape: {weekly_human.shape}")
            
            # Merge data with outer join to preserve all weeks
            print("DEBUG: Merging weekly data...")
            weekly_stats = weekly_all.merge(weekly_bot, on='week_start', how='outer')
            weekly_stats = weekly_stats.merge(weekly_human, on='week_start', how='outer')
            weekly_stats = weekly_stats.fillna(0)
            
            # Verify math integrity
            weekly_stats['Calculated_Total'] = weekly_stats['Bot_Chats'] + weekly_stats['Human_Chats']
            weekly_stats['Math_Check'] = weekly_stats['All_Chats'] == weekly_stats['Calculated_Total']
            
            # Calculate transfer rates
            weekly_transfers = full_df[full_df['bot_transfer'] == True].groupby('week_start').size().reset_index(name='Transfers')
            weekly_stats = weekly_stats.merge(weekly_transfers, on='week_start', how='left').fillna(0)
            weekly_stats['Transfer_Rate'] = (weekly_stats['Transfers'] / weekly_stats['All_Chats'] * 100).fillna(0)
            
            # Sort by week and show all available weeks
            weekly_stats = weekly_stats.sort_values('week_start')
            total_weeks = len(weekly_stats)
            
            # Debug: Print detailed analysis to identify data integrity issues
            print(f"DEBUG: Weekly volume data has {total_weeks} weeks")
            print("DEBUG: Data integrity check:")
            for _, row in weekly_stats.iterrows():
                week_str = row['week_start'].strftime('%Y-%m-%d (%b %d)')
                all_chats = int(row['All_Chats'])
                bot_chats = int(row['Bot_Chats']) 
                human_chats = int(row['Human_Chats'])
                calculated = int(row['Calculated_Total'])
                math_ok = row['Math_Check']
                print(f"  Week {week_str}: {all_chats} total, {bot_chats} bot + {human_chats} human = {calculated} [Math OK: {math_ok}]")
                if not math_ok:
                    print(f"    ❌ DATA INTEGRITY ERROR: {all_chats} ≠ {calculated}")
            
            # Take last 12 weeks for display if we have more than 12
            if len(weekly_stats) > 12:
                weekly_stats = weekly_stats.tail(12).reset_index(drop=True)
                weeks_shown = 12
                print(f"DEBUG: Showing last 12 weeks out of {total_weeks} available")
            else:
                weeks_shown = total_weeks
                print(f"DEBUG: Showing all {weeks_shown} available weeks")
            
            # Format dates for display with clearer week labels
            weekly_stats['Week_Label'] = weekly_stats['week_start'].dt.strftime('%b %d')
            
            # Create figure with weekly bars only
            fig = go.Figure()
            
            # Add weekly chat volume bars
            fig.add_trace(go.Bar(
                x=weekly_stats['Week_Label'],
                y=weekly_stats['All_Chats'],
                name='Total Weekly Chats',
                marker_color='rgba(78, 205, 196, 0.8)',
                text=weekly_stats['All_Chats'],
                textposition='outside'
            ))
            
            fig.add_trace(go.Bar(
                x=weekly_stats['Week_Label'],
                y=weekly_stats['Bot_Chats'],
                name='Bot Chats',
                marker_color='rgba(162, 155, 254, 0.8)',
                text=weekly_stats['Bot_Chats'],
                textposition='inside'
            ))
            
            fig.add_trace(go.Bar(
                x=weekly_stats['Week_Label'],
                y=weekly_stats['Human_Chats'],
                name='Human Chats',
                marker_color='rgba(255, 107, 107, 0.8)',
                text=weekly_stats['Human_Chats'],
                textposition='inside'
            ))
            
            # Add trend line for total chats
            fig.add_trace(go.Scatter(
                x=weekly_stats['Week_Label'],
                y=weekly_stats['All_Chats'],
                mode='lines+markers',
                name='Total Trend',
                line=dict(color='rgba(0, 212, 170, 0.9)', width=3, dash='solid'),
                marker=dict(size=8, color='rgba(0, 212, 170, 0.9)'),
                yaxis='y'
            ))
            
            # Update layout for weekly view
            title_text = f'📈 Weekly Chat Volume ({weeks_shown} Week{"s" if weeks_shown != 1 else ""} Available)'
            fig.update_layout(
                title=title_text,
                xaxis_title='Week Starting',
                yaxis_title='Number of Chats',
                title_font_size=20,
                xaxis_title_font_size=16,
                yaxis_title_font_size=16,
                barmode='group',
                template='plotly_dark',
                plot_bgcolor='rgba(30, 30, 46, 0.8)',
                paper_bgcolor='rgba(23, 23, 35, 0.9)',
                font=dict(color='#e0e0e0', size=16),
                height=450,
                width=None,  # Allow full width
                margin=dict(l=50, r=50, t=60, b=50),
                xaxis=dict(gridcolor='rgba(102, 126, 234, 0.2)', showgrid=True),
                yaxis=dict(gridcolor='rgba(102, 126, 234, 0.2)', showgrid=True),
                showlegend=True
            )
            
            return f"""
            <div class="section" style="width: 100%;">
                <h3>📈 Weekly Chat Volume</h3>
                <div class="chat-chart-container" style="width: 100%;">
                    {fig.to_html(include_plotlyjs="cdn", div_id="weekly-volume-chart", config={'responsive': True})}
                </div>
            </div>
            """
            
        except Exception as e:
            print(f"Error creating weekly volume chart: {e}")
            return ""
    
    def _create_weekly_satisfaction_chart(self, df: pd.DataFrame) -> str:
        """Create weekly satisfaction chart showing all available weeks from full dataset"""
        try:
            if not PLOTLY_AVAILABLE:
                return ""
            
            # Use full original dataset instead of filtered df for weekly trends
            if self.df is not None and len(self.df) > 0:
                full_df = self.df.copy()
                print(f"DEBUG: Using full dataset with {len(full_df)} total records for weekly satisfaction analysis")
            else:
                full_df = df.copy()
                print(f"DEBUG: Using filtered dataset with {len(full_df)} records for weekly satisfaction analysis")
            
            # Calculate weekly satisfaction for both bots and humans
            full_df['week_start'] = full_df['chat_creation_date_adt'].dt.tz_localize(None).dt.to_period('W-MON').dt.start_time
            
            # Filter chats with ratings
            rated_chats = full_df[full_df['has_rating']]
            if len(rated_chats) == 0:
                return ""
            
            # Calculate weekly satisfaction by agent type
            weekly_satisfaction = rated_chats.groupby(['week_start', 'agent_type']).agg({
                'rating_value': ['mean', 'count']
            }).reset_index()
            
            weekly_satisfaction.columns = ['week_start', 'agent_type', 'avg_rating', 'rating_count']
            weekly_satisfaction['satisfaction_pct'] = (weekly_satisfaction['avg_rating'] - 1) / 4 * 100  # Convert 1-5 to 0-100%
            
            # Sort by week
            weekly_satisfaction = weekly_satisfaction.sort_values('week_start')
            unique_weeks = weekly_satisfaction['week_start'].unique()
            total_weeks = len(unique_weeks)
            
            # Take last 12 weeks if we have more than 12
            if total_weeks > 12:
                last_12_weeks = unique_weeks[-12:]
                weekly_satisfaction = weekly_satisfaction[weekly_satisfaction['week_start'].isin(last_12_weeks)]
                weeks_shown = 12
                print(f"DEBUG: Satisfaction showing last 12 weeks out of {total_weeks} available")
            else:
                weeks_shown = total_weeks
                print(f"DEBUG: Satisfaction showing all {weeks_shown} available weeks")
            
            # Debug: Print bot satisfaction data for chart
            print(f"DEBUG: Weekly bot satisfaction data has {weeks_shown} weeks")
            bot_data = weekly_satisfaction[weekly_satisfaction['agent_type'] == 'bot']
            if len(bot_data) > 0:
                print(f"  Bot satisfaction:")
                for _, row in bot_data.iterrows():
                    week_str = row['week_start'].strftime('%Y-%m-%d (%b %d)')
                    print(f"    Week {week_str}: {row['satisfaction_pct']:.1f}% ({row['rating_count']} ratings)")
            
            weekly_satisfaction['Week_Label'] = weekly_satisfaction['week_start'].dt.strftime('%b %d')
            
            fig = go.Figure()
            
            # Create trace for bot satisfaction only
            bot_data = weekly_satisfaction[weekly_satisfaction['agent_type'] == 'bot']
            if len(bot_data) > 0:
                fig.add_trace(go.Bar(
                    x=bot_data['Week_Label'],
                    y=bot_data['satisfaction_pct'],
                    name='Bot Satisfaction',
                    marker_color='rgba(162, 155, 254, 0.8)',
                    text=[f"{val:.1f}%" for val in bot_data['satisfaction_pct']],
                    textposition='outside'
                ))
                
                # Add trend line for bot satisfaction
                fig.add_trace(go.Scatter(
                    x=bot_data['Week_Label'],
                    y=bot_data['satisfaction_pct'],
                    mode='lines+markers',
                    name='Satisfaction Trend',
                    line=dict(color='rgba(0, 212, 170, 0.9)', width=3, dash='solid'),
                    marker=dict(size=8, color='rgba(0, 212, 170, 0.9)'),
                    yaxis='y'
                ))
            
            # Update layout for weekly bars
            title_text = f'📊 Weekly Bot Satisfaction Rate ({weeks_shown} Week{"s" if weeks_shown != 1 else ""} Shown)'
            fig.update_layout(
                title=title_text,
                xaxis_title='Week Starting',
                yaxis_title='Satisfaction Rate (%)',
                title_font_size=20,
                xaxis_title_font_size=16,
                yaxis_title_font_size=16,
                template='plotly_dark',
                plot_bgcolor='rgba(30, 30, 46, 0.8)',
                paper_bgcolor='rgba(23, 23, 35, 0.9)',
                font=dict(color='#e0e0e0', size=16),
                margin=dict(l=50, r=50, t=60, b=50),
                height=450,
                width=None,  # Allow full width
                yaxis=dict(range=[0, 100]),
                showlegend=True
            )
            
            return f"""
            <div class="section" style="width: 100%;">
                <h3>📊 Weekly Bot Satisfaction Rate</h3>
                <div class="chat-chart-container" style="width: 100%;">
                    {fig.to_html(include_plotlyjs="cdn", div_id="weekly-satisfaction-chart", config={'responsive': True})}
                </div>
            </div>
            """
            
        except Exception as e:
            print(f"Error creating weekly satisfaction chart: {e}")
            return ""
    
    def _create_individual_agent_charts(self, df: pd.DataFrame) -> List[str]:
        """Create separate clean charts for bot and human agent performance"""
        try:
            if not PLOTLY_AVAILABLE:
                return []
            
            charts = []
            
            # Get bot stats (exclude agents with 0 chats)
            bot_stats = []
            bot_agents = df[df['agent_type'] == 'bot']['display_agent'].unique()
            for display_name in bot_agents:
                bot_data = df[df['display_agent'] == display_name]
                if len(bot_data) > 0:  # Only include agents with chats
                    bot_stats.append({
                        'agent': display_name,
                        'total_chats': len(bot_data),
                        'avg_duration': bot_data['duration_minutes'].mean(),
                        'satisfaction_rate': (bot_data[bot_data['rating_value'] == 5].shape[0] / 
                                            bot_data[bot_data['has_rating']].shape[0] * 100) if bot_data[bot_data['has_rating']].shape[0] > 0 else 0
                    })
            
            # Get human agent stats (exclude agents with 0 chats)
            # Use same logic as Agent Performance table - count both primary and secondary agent appearances
            human_stats = []
            for agent in self.human_agents:
                # Check both primary and secondary agent fields (same as Agent Performance table)
                agent_data = df[(df['primary_agent'] == agent) | (df['secondary_agent'] == agent)]
                if len(agent_data) > 0:  # Only include agents with chats
                    # Get standardized display name  
                    display_name_clean = self.human_agent_mapping.get(agent, agent)
                    human_stats.append({
                        'agent': display_name_clean,
                        'total_chats': len(agent_data),
                        'avg_duration': agent_data['duration_minutes'].mean(),
                        'satisfaction_rate': (agent_data[agent_data['rating_value'] == 5].shape[0] / 
                                            agent_data[agent_data['has_rating']].shape[0] * 100) if agent_data[agent_data['has_rating']].shape[0] > 0 else 0
                    })
            
            # Create Bot Volume & Duration Chart
            if bot_stats:
                bot_df = pd.DataFrame(bot_stats)
                fig_bot_vol_dur = make_subplots(
                    rows=1, cols=2,
                    subplot_titles=('Bot Chat Volume', 'Bot Average Duration'),
                    specs=[[{"secondary_y": False}, {"secondary_y": False}]]
                )
                
                # Bot volume bars
                fig_bot_vol_dur.add_trace(
                    go.Bar(
                        x=bot_df['agent'],
                        y=bot_df['total_chats'],
                        name='Chat Volume',
                        marker_color='rgba(162, 155, 254, 0.8)',
                        text=bot_df['total_chats'],
                        textposition='outside',
                        showlegend=False
                    ),
                    row=1, col=1
                )
                
                # Bot duration bars
                fig_bot_vol_dur.add_trace(
                    go.Bar(
                        x=bot_df['agent'],
                        y=bot_df['avg_duration'],
                        name='Avg Duration (min)',
                        marker_color='rgba(78, 205, 196, 0.8)',
                        text=[f"{val:.1f}min" for val in bot_df['avg_duration']],
                        textposition='outside',
                        showlegend=False
                    ),
                    row=1, col=2
                )
                
                fig_bot_vol_dur.update_layout(
                    title='🤖 Bot Volume & Duration Analysis',
                    title_font_size=20,
                    template='plotly_dark',
                    plot_bgcolor='rgba(30, 30, 46, 0.8)',
                    paper_bgcolor='rgba(23, 23, 35, 0.9)',
                    font=dict(color='#e0e0e0', size=16),
                    height=400,
                    margin=dict(l=50, r=50, t=80, b=50),
                    showlegend=False
                )
                
                fig_bot_vol_dur.update_xaxes(title_text="Bot", title_font_size=16, row=1, col=1)
                fig_bot_vol_dur.update_xaxes(title_text="Bot", title_font_size=16, row=1, col=2)
                fig_bot_vol_dur.update_yaxes(title_text="Number of Chats", title_font_size=16, row=1, col=1)
                fig_bot_vol_dur.update_yaxes(title_text="Minutes", title_font_size=16, row=1, col=2)
                
                charts.append(f"""
                <div class="section">
                    <h3>🤖 Bot Volume & Duration</h3>
                    <div class="chat-chart-container">
                        {fig_bot_vol_dur.to_html(include_plotlyjs="cdn")}
                    </div>
                </div>
                """)
                
                # Create Bot Satisfaction Chart  
                fig_bot_sat = go.Figure()
                fig_bot_sat.add_trace(
                    go.Bar(
                        x=bot_df['agent'],
                        y=bot_df['satisfaction_rate'],
                        name='Satisfaction Rate',
                        marker_color='rgba(255, 234, 167, 0.8)',
                        text=[f"{val:.1f}%" for val in bot_df['satisfaction_rate']],
                        textposition='outside'
                    )
                )
                
                fig_bot_sat.update_layout(
                    title='🤖 Bot Satisfaction Rates',
                    title_font_size=20,
                    xaxis_title='Bot',
                    yaxis_title='Satisfaction Rate (%)',
                    xaxis_title_font_size=16,
                    yaxis_title_font_size=16,
                    template='plotly_dark',
                    plot_bgcolor='rgba(30, 30, 46, 0.8)',
                    paper_bgcolor='rgba(23, 23, 35, 0.9)',
                    font=dict(color='#e0e0e0', size=16),
                    height=400,
                    margin=dict(l=50, r=50, t=80, b=50),
                    yaxis=dict(range=[0, 100]),
                    showlegend=False
                )
                
                charts.append(f"""
                <div class="section">
                    <h3>🤖 Bot Satisfaction</h3>
                    <div class="chat-chart-container">
                        {fig_bot_sat.to_html(include_plotlyjs="cdn")}
                    </div>
                </div>
                """)
            
            # Create Human Agent Volume & Duration Chart
            if human_stats:
                human_df = pd.DataFrame(human_stats)
                fig_human_vol_dur = make_subplots(
                    rows=1, cols=2,
                    subplot_titles=('Human Agent Chat Volume', 'Human Agent Average Duration'),
                    specs=[[{"secondary_y": False}, {"secondary_y": False}]]
                )
                
                # Human volume bars
                fig_human_vol_dur.add_trace(
                    go.Bar(
                        x=human_df['agent'],
                        y=human_df['total_chats'],
                        name='Chat Volume',
                        marker_color='rgba(255, 107, 107, 0.8)',
                        text=human_df['total_chats'],
                        textposition='outside',
                        showlegend=False
                    ),
                    row=1, col=1
                )
                
                # Human duration bars
                fig_human_vol_dur.add_trace(
                    go.Bar(
                        x=human_df['agent'],
                        y=human_df['avg_duration'],
                        name='Avg Duration (min)',
                        marker_color='rgba(253, 121, 168, 0.8)',
                        text=[f"{val:.1f}min" for val in human_df['avg_duration']],
                        textposition='outside',
                        showlegend=False
                    ),
                    row=1, col=2
                )
                
                fig_human_vol_dur.update_layout(
                    title='👥 Human Agent Volume & Duration Analysis',
                    title_font_size=20,
                    template='plotly_dark',
                    plot_bgcolor='rgba(30, 30, 46, 0.8)',
                    paper_bgcolor='rgba(23, 23, 35, 0.9)',
                    font=dict(color='#e0e0e0', size=16),
                    height=400,
                    margin=dict(l=50, r=50, t=80, b=50),
                    showlegend=False
                )
                
                fig_human_vol_dur.update_xaxes(title_text="Agent", title_font_size=16, row=1, col=1)
                fig_human_vol_dur.update_xaxes(title_text="Agent", title_font_size=16, row=1, col=2)
                fig_human_vol_dur.update_yaxes(title_text="Number of Chats", title_font_size=16, row=1, col=1)
                fig_human_vol_dur.update_yaxes(title_text="Minutes", title_font_size=16, row=1, col=2)
                
                charts.append(f"""
                <div class="section">
                    <h3>👥 Human Agent Volume & Duration</h3>
                    <div class="chat-chart-container">
                        {fig_human_vol_dur.to_html(include_plotlyjs="cdn")}
                    </div>
                </div>
                """)
                
            
            return charts
            
        except Exception as e:
            print(f"Error creating individual agent charts: {e}")
            return []
    
    def _create_bot_performance_charts(self, df: pd.DataFrame) -> List[str]:
        """Create bot performance comparison charts"""
        try:
            if not PLOTLY_AVAILABLE:
                return []
            
            charts = []
            bot_chats = df[df['agent_type'] == 'bot']
            
            if len(bot_chats) == 0:
                return []
            
            # Bot volume and satisfaction comparison using display names
            bot_stats = []
            bot_agents = bot_chats['display_agent'].unique()
            for display_name in bot_agents:
                bot_data = bot_chats[bot_chats['display_agent'] == display_name]
                if len(bot_data) > 0:
                    rated_data = bot_data[bot_data['has_rating']]
                    satisfaction_rate = (rated_data['rating_value'].mean() * 20) if len(rated_data) > 0 else 0  # Convert to percentage
                    
                    bot_stats.append({
                        'bot': display_name,
                        'total_chats': len(bot_data),
                        'satisfaction_rate': satisfaction_rate,
                        'transfer_rate': (bot_data['bot_transfer'].sum() / len(bot_data) * 100) if len(bot_data) > 0 else 0,
                        'avg_duration': bot_data['duration_minutes'].mean()
                    })
            
            if not bot_stats:
                return []
            
            # Chart 1: Bot Volume & Satisfaction
            fig1 = make_subplots(
                rows=1, cols=2,
                column_widths=[0.6, 0.4],
                subplot_titles=('🤖 Bot Performance Comparison', '📊 Chat Volume Distribution'),
                specs=[[{"secondary_y": True}, {"type": "pie"}]]
            )
            
            bot_names = [stat['bot'] for stat in bot_stats]
            volumes = [stat['total_chats'] for stat in bot_stats]
            satisfaction = [stat['satisfaction_rate'] for stat in bot_stats]
            
            # Bar chart for volume
            fig1.add_trace(
                go.Bar(
                    x=bot_names,
                    y=volumes,
                    name="Chat Volume",
                    marker_color='rgba(162, 155, 254, 0.8)',
                    yaxis='y'
                ),
                row=1, col=1
            )
            
            # Line for satisfaction
            fig1.add_trace(
                go.Scatter(
                    x=bot_names,
                    y=satisfaction,
                    mode='lines+markers',
                    name="Satisfaction Rate (%)",
                    line=dict(color='rgba(255, 234, 167, 1)', width=3),
                    yaxis='y2'
                ),
                row=1, col=1, secondary_y=True
            )
            
            # Pie chart for distribution
            fig1.add_trace(
                go.Pie(
                    labels=bot_names,
                    values=volumes,
                    name="Volume Distribution",
                    marker_colors=['rgba(162, 155, 254, 0.8)', 'rgba(253, 121, 168, 0.8)'][:len(bot_names)],
                    textinfo='label+percent'
                ),
                row=1, col=2
            )
            
            fig1.update_layout(
                title_text="🤖 Bot Performance Analysis",
                title_font_size=20,
                template='plotly_dark',
                plot_bgcolor='rgba(30, 30, 46, 0.8)',
                paper_bgcolor='rgba(23, 23, 35, 0.9)',
                font=dict(color='#e0e0e0', size=16),
                height=400,
                showlegend=True
            )
            
            fig1.update_xaxes(title_text="Bot", title_font_size=16, row=1, col=1)
            fig1.update_yaxes(title_text="Number of Chats", title_font_size=16, row=1, col=1)
            fig1.update_yaxes(title_text="Satisfaction Rate (%)", title_font_size=16, secondary_y=True, row=1, col=1)
            
            chart1_html = f'''
            <div class="chat-chart-container">
                {fig1.to_html(include_plotlyjs="cdn")}
                <div style="margin-top: 10px; padding: 10px; background: rgba(162, 155, 254, 0.05); border-radius: 6px; border-left: 4px solid #a29bfe;">
                    <div style="color: #a29bfe; font-weight: bold; font-size: 0.9em; margin-bottom: 5px;">🤖 Bot Performance Insights:</div>
                    <div style="color: #e0e0e0; font-size: 0.85em; line-height: 1.4;">
                        • <b>Higher satisfaction + lower transfers</b> = Effective bot performance<br>
                        • <b>High volume + good satisfaction</b> = Bot handling routine queries well<br>
                        • <b>High transfer rate</b> = Bot may need training or escalation tuning
                    </div>
                </div>
            </div>
            '''
            charts.append(chart1_html)
            
            return charts
            
        except Exception as e:
            print(f"Error creating bot performance charts: {e}")
            return []
    
    def _create_chat_trends_chart(self, df: pd.DataFrame) -> str:
        """Create daily chat trends with satisfaction overlay"""
        try:
            if not PLOTLY_AVAILABLE:
                return ""
            
            # Daily volume and satisfaction
            daily_stats = df.groupby('date').agg({
                'chat_creation_date_adt': 'count',
                'rating_value': 'mean',
                'bot_transfer': 'sum'
            }).reset_index()
            
            daily_stats.columns = ['date', 'chat_count', 'avg_satisfaction', 'transfers']
            daily_stats['transfer_rate'] = (daily_stats['transfers'] / daily_stats['chat_count'] * 100).fillna(0)
            daily_stats['satisfaction_pct'] = (daily_stats['avg_satisfaction'] * 20).fillna(0)  # Convert to percentage
            
            # Create figure
            fig = make_subplots(specs=[[{"secondary_y": True}]])
            
            # Chat volume bars
            fig.add_trace(
                go.Bar(
                    x=daily_stats['date'],
                    y=daily_stats['chat_count'],
                    name='Daily Chat Volume',
                    marker_color='rgba(78, 205, 196, 0.7)',
                    yaxis='y'
                )
            )
            
            # Satisfaction line
            fig.add_trace(
                go.Scatter(
                    x=daily_stats['date'],
                    y=daily_stats['satisfaction_pct'],
                    mode='lines+markers',
                    name='Satisfaction Rate (%)',
                    line=dict(color='rgba(255, 234, 167, 1)', width=2),
                    yaxis='y2'
                ),
                secondary_y=True
            )
            
            # Transfer rate line
            fig.add_trace(
                go.Scatter(
                    x=daily_stats['date'],
                    y=daily_stats['transfer_rate'],
                    mode='lines+markers',
                    name='Transfer Rate (%)',
                    line=dict(color='rgba(255, 107, 107, 1)', width=2, dash='dot'),
                    yaxis='y2'
                ),
                secondary_y=True
            )
            
            fig.update_layout(
                title='📊 Daily Chat Trends & Performance Metrics',
                title_font_size=20,
                template='plotly_dark',
                plot_bgcolor='rgba(30, 30, 46, 0.8)',
                paper_bgcolor='rgba(23, 23, 35, 0.9)',
                font=dict(color='#e0e0e0', size=16),
                height=400,
                margin=dict(l=50, r=50, t=50, b=50),
                xaxis=dict(gridcolor='rgba(102, 126, 234, 0.2)', showgrid=True)
            )
            
            fig.update_xaxes(title_text="Date", title_font_size=16)
            fig.update_yaxes(title_text="Number of Chats", secondary_y=False, title_font_size=16)
            fig.update_yaxes(title_text="Percentage (%)", secondary_y=True, title_font_size=16)
            
            return f"""
            <div class="section">
                <h3>📊 Daily Chat Trends & Performance</h3>
                <div class="chat-chart-container">
                    {fig.to_html(include_plotlyjs="cdn")}
                </div>
            </div>
            """
            
        except Exception as e:
            print(f"Error creating chat trends chart: {e}")
            return ""