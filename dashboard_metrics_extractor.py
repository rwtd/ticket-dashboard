#!/usr/bin/env python3
"""
Dashboard Metrics Extractor
Extracts high-level metrics from ticket and chat data for dashboard summary cards
"""

import pandas as pd
import numpy as np
from typing import Dict, Any, Optional
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

class DashboardMetricsExtractor:
    """Extract high-level dashboard metrics from processed data"""
    
    def __init__(self):
        self.ticket_data = None
        self.chat_data = None
        
    def extract_ticket_metrics(self, df: pd.DataFrame, run_id: str, date_range: str = "") -> Dict[str, Any]:
        """Extract ticket analytics metrics (like dashboard cards)"""
        self.ticket_data = df
        
        if df.empty:
            return self._empty_ticket_metrics(run_id, date_range)
        
        metrics = {
            'run_id': run_id,
            'analytics_type': 'tickets',
            'date_range': date_range,
            'period_description': self._get_period_description(date_range),
        }
        
        try:
            # Volume metrics
            metrics.update(self._extract_ticket_volume_metrics(df))
            
            # Response time metrics
            metrics.update(self._extract_response_time_metrics(df))
            
            # Agent performance metrics
            metrics.update(self._extract_agent_performance_metrics(df))
            
            # Quality and business metrics
            metrics.update(self._extract_quality_metrics(df))
            
            # Data quality metrics
            metrics.update(self._extract_data_quality_metrics(df))
            
        except Exception as e:
            logger.error(f"Error extracting ticket metrics: {e}")
            
        return metrics
    
    def extract_chat_metrics(self, df: pd.DataFrame, run_id: str, date_range: str = "") -> Dict[str, Any]:
        """Extract chat analytics metrics"""
        self.chat_data = df
        
        if df.empty:
            return self._empty_chat_metrics(run_id, date_range)
        
        metrics = {
            'run_id': run_id,
            'analytics_type': 'chats',
            'date_range': date_range,
            'period_description': self._get_period_description(date_range),
        }
        
        try:
            # Volume metrics
            metrics.update(self._extract_chat_volume_metrics(df))
            
            # Bot vs Human metrics
            metrics.update(self._extract_bot_human_metrics(df))
            
            # Satisfaction metrics
            metrics.update(self._extract_satisfaction_metrics(df))
            
            # Geographic and time metrics
            metrics.update(self._extract_geographic_time_metrics(df))
            
            # Chat duration metrics
            metrics.update(self._extract_duration_metrics(df))
            
        except Exception as e:
            logger.error(f"Error extracting chat metrics: {e}")
            
        return metrics
    
    def _extract_ticket_volume_metrics(self, df: pd.DataFrame) -> Dict[str, Any]:
        """Extract ticket volume metrics"""
        return {
            'total_records': len(df),
            'total_tickets': len(df),
            'total_chats': 0,
            'weekday_records': len(df[df.get('Weekend_Ticket', pd.Series([False] * len(df))) == False]),
            'weekend_records': len(df[df.get('Weekend_Ticket', pd.Series([False] * len(df))) == True]),
        }
    
    def _extract_response_time_metrics(self, df: pd.DataFrame) -> Dict[str, Any]:
        """Extract response time metrics"""
        response_col = 'First Response Time (Hours)'
        
        if response_col not in df.columns:
            return {
                'avg_response_time_hours': '',
                'median_response_time_hours': '',
                'min_response_time_hours': '',
                'max_response_time_hours': '',
                'weekend_avg_response_hours': '',
                'weekday_avg_response_hours': '',
            }
        
        # Filter valid response times
        response_times = df[response_col].dropna()
        response_times = response_times[response_times > 0]  # Remove negative/zero times
        
        if len(response_times) == 0:
            return {
                'avg_response_time_hours': '',
                'median_response_time_hours': '',
                'min_response_time_hours': '',
                'max_response_time_hours': '',
                'weekend_avg_response_hours': '',
                'weekday_avg_response_hours': '',
            }
        
        # Overall metrics
        avg_response = response_times.mean()
        median_response = response_times.median()
        min_response = response_times.min()
        max_response = response_times.max()
        
        # Weekend vs weekday
        weekend_mask = df.get('Weekend_Ticket', pd.Series([False] * len(df))) == True
        weekday_mask = df.get('Weekend_Ticket', pd.Series([False] * len(df))) == False
        
        weekend_responses = df.loc[weekend_mask, response_col].dropna()
        weekday_responses = df.loc[weekday_mask, response_col].dropna()
        
        weekend_avg = weekend_responses.mean() if len(weekend_responses) > 0 else None
        weekday_avg = weekday_responses.mean() if len(weekday_responses) > 0 else None
        
        return {
            'avg_response_time_hours': round(avg_response, 2),
            'median_response_time_hours': round(median_response, 2),
            'min_response_time_hours': round(min_response, 3),
            'max_response_time_hours': round(max_response, 2),
            'weekend_avg_response_hours': round(weekend_avg, 2) if weekend_avg else '',
            'weekday_avg_response_hours': round(weekday_avg, 2) if weekday_avg else '',
        }
    
    def _extract_agent_performance_metrics(self, df: pd.DataFrame) -> Dict[str, Any]:
        """Extract agent performance metrics"""
        owner_col = 'Case Owner'
        
        if owner_col not in df.columns:
            owner_col = 'Ticket owner'
        
        if owner_col not in df.columns:
            return {
                'top_volume_agent': '',
                'top_volume_count': 0,
                'fastest_agent': '',
                'fastest_response_hours': '',
                'agent_count': 0,
                'agents_list': '',
            }
        
        # Agent volume analysis
        agent_counts = df[owner_col].value_counts()
        
        # Filter to main agents (not system/automated)
        main_agents = ['Nova', 'Girly', 'Francis', 'Bhushan']
        filtered_counts = agent_counts[agent_counts.index.isin(main_agents)]
        
        if len(filtered_counts) == 0:
            return {
                'top_volume_agent': '',
                'top_volume_count': 0,
                'fastest_agent': '',
                'fastest_response_hours': '',
                'agent_count': 0,
                'agents_list': '',
            }
        
        top_volume_agent = filtered_counts.index[0]
        top_volume_count = filtered_counts.iloc[0]
        
        # Fastest response analysis
        response_col = 'First Response Time (Hours)'
        fastest_agent = ''
        fastest_response = ''
        
        if response_col in df.columns:
            # Calculate median response time per agent
            agent_response_medians = df.groupby(owner_col)[response_col].median()
            agent_response_medians = agent_response_medians[agent_response_medians.index.isin(main_agents)]
            agent_response_medians = agent_response_medians.dropna()
            
            if len(agent_response_medians) > 0:
                fastest_agent = agent_response_medians.idxmin()
                fastest_response = round(agent_response_medians.min(), 2)
        
        return {
            'top_volume_agent': top_volume_agent,
            'top_volume_count': int(top_volume_count),
            'fastest_agent': fastest_agent,
            'fastest_response_hours': fastest_response,
            'agent_count': len(filtered_counts),
            'agents_list': ', '.join(filtered_counts.index.tolist()),
        }
    
    def _extract_quality_metrics(self, df: pd.DataFrame) -> Dict[str, Any]:
        """Extract quality and business metrics"""
        metrics = {}
        
        # Business hours percentage
        if 'Created_During_Business_Hours' in df.columns:
            business_hours_count = df['Created_During_Business_Hours'].sum()
            business_hours_pct = (business_hours_count / len(df)) * 100
            metrics['business_hours_percentage'] = round(business_hours_pct, 1)
        else:
            metrics['business_hours_percentage'] = ''
        
        # Response time categories
        response_col = 'First Response Time (Hours)'
        if response_col in df.columns:
            response_times = df[response_col].dropna()
            response_times = response_times[response_times > 0]
            
            if len(response_times) > 0:
                under_1h = (response_times <= 1).sum()
                under_4h = (response_times <= 4).sum()
                
                under_1h_pct = (under_1h / len(response_times)) * 100
                under_4h_pct = (under_4h / len(response_times)) * 100
                
                metrics['response_under_1hour_percentage'] = round(under_1h_pct, 1)
                metrics['response_under_4hour_percentage'] = round(under_4h_pct, 1)
            else:
                metrics['response_under_1hour_percentage'] = ''
                metrics['response_under_4hour_percentage'] = ''
        else:
            metrics['response_under_1hour_percentage'] = ''
            metrics['response_under_4hour_percentage'] = ''
        
        return metrics
    
    def _extract_data_quality_metrics(self, df: pd.DataFrame) -> Dict[str, Any]:
        """Extract data quality metrics"""
        response_col = 'First Response Time (Hours)'
        
        records_with_response = 0
        records_missing_data = 0
        
        if response_col in df.columns:
            records_with_response = df[response_col].notna().sum()
            records_missing_data = len(df) - records_with_response
        
        # Calculate data quality score
        if len(df) > 0:
            quality_score = (records_with_response / len(df)) * 100
        else:
            quality_score = 0
        
        return {
            'records_with_response_time': int(records_with_response),
            'records_missing_data': int(records_missing_data),
            'data_quality_score': round(quality_score, 1),
        }
    
    def _extract_chat_volume_metrics(self, df: pd.DataFrame) -> Dict[str, Any]:
        """Extract chat volume metrics"""
        return {
            'total_records': len(df),
            'total_tickets': 0,
            'total_chats': len(df),
            'weekday_records': len(df[df.get('Is_Weekend', pd.Series([False] * len(df))) == False]),
            'weekend_records': len(df[df.get('Is_Weekend', pd.Series([False] * len(df))) == True]),
        }
    
    def _extract_bot_human_metrics(self, df: pd.DataFrame) -> Dict[str, Any]:
        """Extract bot vs human chat metrics"""
        # Detect bot chats (this depends on your chat data structure)
        # Common bot indicators: agent names like 'Wynn AI', 'Agent Scrape'
        bot_names = ['Wynn AI', 'Agent Scrape', 'Bot', 'Chatbot']
        human_agents = ['Bhushan', 'Girly', 'Francis', 'Nova']
        
        agent_col = 'agent_name'  # Adjust based on your chat data structure
        if agent_col not in df.columns:
            # Try common alternatives
            for col in ['agent', 'Agent', 'staff_name', 'agent_display_name']:
                if col in df.columns:
                    agent_col = col
                    break
        
        bot_chats = 0
        human_chats = 0
        
        if agent_col in df.columns:
            for bot_name in bot_names:
                bot_chats += df[df[agent_col].str.contains(bot_name, na=False, case=False)].shape[0]
            
            for human_name in human_agents:
                human_chats += df[df[agent_col].str.contains(human_name, na=False, case=False)].shape[0]
        
        # Calculate rates
        total_chats = len(df)
        bot_transfer_rate = ''
        bot_resolution_rate = ''
        
        if total_chats > 0:
            if bot_chats > 0:
                bot_resolution_rate = round((bot_chats / total_chats) * 100, 1)
            
            # Transfer rate would need specific transfer detection logic
            # This is a placeholder
            bot_transfer_rate = round((human_chats / total_chats) * 100, 1) if human_chats > 0 else 0
        
        return {
            'total_bot_chats': bot_chats,
            'total_human_chats': human_chats,
            'bot_transfer_rate': bot_transfer_rate,
            'bot_resolution_rate': bot_resolution_rate,
        }
    
    def _extract_satisfaction_metrics(self, df: pd.DataFrame) -> Dict[str, Any]:
        """Extract satisfaction metrics from chat data"""
        # This depends on your chat data structure
        # Look for satisfaction rating columns
        satisfaction_cols = ['satisfaction', 'rating', 'score', 'customer_satisfaction']
        
        bot_satisfaction = ''
        human_satisfaction = ''
        
        for col in satisfaction_cols:
            if col in df.columns:
                # Process satisfaction data
                # This is a placeholder - adjust based on your data format
                satisfaction_data = df[col].dropna()
                if len(satisfaction_data) > 0:
                    # Assuming ratings are 1-5 or similar
                    avg_satisfaction = satisfaction_data.mean()
                    bot_satisfaction = round(avg_satisfaction, 1)
                    human_satisfaction = round(avg_satisfaction, 1)  # Would need to split by agent type
                break
        
        return {
            'bot_satisfaction_rate': bot_satisfaction,
            'human_satisfaction_rate': human_satisfaction,
        }
    
    def _extract_geographic_time_metrics(self, df: pd.DataFrame) -> Dict[str, Any]:
        """Extract geographic and time-based metrics"""
        metrics = {
            'top_country': '',
            'top_country_count': 0,
            'peak_hour': '',
            'peak_hour_count': 0,
        }
        
        # Geographic analysis
        country_cols = ['country', 'Country', 'visitor_country', 'customer_country']
        for col in country_cols:
            if col in df.columns:
                country_counts = df[col].value_counts()
                if len(country_counts) > 0:
                    metrics['top_country'] = country_counts.index[0]
                    metrics['top_country_count'] = int(country_counts.iloc[0])
                break
        
        # Time analysis
        if 'Hour_of_Day' in df.columns:
            hour_counts = df['Hour_of_Day'].value_counts()
            if len(hour_counts) > 0:
                peak_hour = hour_counts.index[0]
                peak_count = hour_counts.iloc[0]
                metrics['peak_hour'] = f"{peak_hour:02d}:00"
                metrics['peak_hour_count'] = int(peak_count)
        
        return metrics
    
    def _extract_duration_metrics(self, df: pd.DataFrame) -> Dict[str, Any]:
        """Extract chat duration metrics"""
        duration_cols = ['Duration_Minutes', 'duration_minutes', 'chat_duration', 'session_duration']
        
        for col in duration_cols:
            if col in df.columns:
                durations = df[col].dropna()
                if len(durations) > 0:
                    avg_duration = durations.mean()
                    return {'avg_chat_duration_minutes': round(avg_duration, 1)}
        
        return {'avg_chat_duration_minutes': ''}
    
    def _empty_ticket_metrics(self, run_id: str, date_range: str) -> Dict[str, Any]:
        """Return empty ticket metrics structure"""
        return {
            'run_id': run_id,
            'analytics_type': 'tickets',
            'date_range': date_range,
            'period_description': self._get_period_description(date_range),
            'total_records': 0,
            'total_tickets': 0,
            'total_chats': 0,
            'weekday_records': 0,
            'weekend_records': 0,
            'avg_response_time_hours': '',
            'median_response_time_hours': '',
            'min_response_time_hours': '',
            'max_response_time_hours': '',
            'weekend_avg_response_hours': '',
            'weekday_avg_response_hours': '',
            'top_volume_agent': '',
            'top_volume_count': 0,
            'fastest_agent': '',
            'fastest_response_hours': '',
            'agent_count': 0,
            'agents_list': '',
            'business_hours_percentage': '',
            'response_under_1hour_percentage': '',
            'response_under_4hour_percentage': '',
            'records_with_response_time': 0,
            'records_missing_data': 0,
            'data_quality_score': 0,
        }
    
    def _empty_chat_metrics(self, run_id: str, date_range: str) -> Dict[str, Any]:
        """Return empty chat metrics structure"""
        return {
            'run_id': run_id,
            'analytics_type': 'chats',
            'date_range': date_range,
            'period_description': self._get_period_description(date_range),
            'total_records': 0,
            'total_tickets': 0,
            'total_chats': 0,
            'weekday_records': 0,
            'weekend_records': 0,
            'total_bot_chats': 0,
            'total_human_chats': 0,
            'bot_transfer_rate': '',
            'bot_resolution_rate': '',
            'avg_chat_duration_minutes': '',
            'bot_satisfaction_rate': '',
            'human_satisfaction_rate': '',
            'top_country': '',
            'top_country_count': 0,
            'peak_hour': '',
            'peak_hour_count': 0,
        }
    
    def _get_period_description(self, date_range: str) -> str:
        """Get human-readable period description"""
        if not date_range:
            return 'Unknown Period'
        
        # Parse date range formats
        if '-' in date_range and len(date_range) > 10:
            return f"Custom Range: {date_range}"
        elif len(date_range) == 8:  # DDMMYYYY
            try:
                day = date_range[:2]
                month = date_range[2:4]
                year = date_range[4:8]
                date_obj = datetime.strptime(f"{year}-{month}-{day}", "%Y-%m-%d")
                return date_obj.strftime("Single Day: %B %d, %Y")
            except:
                pass
        
        return f"Period: {date_range}"

def extract_dashboard_metrics(df: pd.DataFrame, analytics_type: str, run_id: str, date_range: str = "") -> Dict[str, Any]:
    """Convenience function to extract dashboard metrics"""
    extractor = DashboardMetricsExtractor()
    
    if analytics_type.lower() == 'tickets':
        return extractor.extract_ticket_metrics(df, run_id, date_range)
    elif analytics_type.lower() in ['chats', 'chat']:
        return extractor.extract_chat_metrics(df, run_id, date_range)
    else:
        # Default to ticket metrics
        return extractor.extract_ticket_metrics(df, run_id, date_range)