#!/usr/bin/env python3
"""
Ticket Data Processor for Unified Analytics
Handles ticket CSV files and generates ticket-specific analytics
"""

import pandas as pd
import numpy as np
import pytz
from datetime import datetime, timedelta
import yaml
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import matplotlib.pyplot as plt
import seaborn as sns

from common_utils import (
    fig_to_html, create_metric_card, create_time_series_chart,
    create_bar_chart, is_interactive_mode, chart_to_html,
    render_chart_with_fallback
)

class TicketDataProcessor:
    """Processes support ticket data and generates analytics"""
    
    def __init__(self, schedule_file: str = 'config/schedule.yaml'):
        self.df = None
        self.original_df = None
        self.processed_files = []
        self.schedule_file = schedule_file
        
    def load_data(self, ticket_files: List[Path]) -> pd.DataFrame:
        """Load and validate ticket CSV files"""
        if not ticket_files:
            raise FileNotFoundError("No ticket CSV files found")

        all_data = []
        for file_path in ticket_files:
            # Skip only specific problematic files, not all archive files
            if file_path.name.endswith('.processed') and file_path.stat().st_size < 1000:
                print(f"⚠️  Skipping small processed file: {file_path.name}")
                continue
            try:
                # Improved CSV loading for complex files with mixed data types
                df = pd.read_csv(file_path, 
                               low_memory=False,  # Handle mixed types properly
                               dtype=str,         # Read all as strings initially
                               na_values=['', 'NULL', 'null', 'None'])
                all_data.append(df)
                self.processed_files.append(file_path)
                print(f"✅ Loaded {len(df):,} records from {file_path.name} ({len(df.columns)} columns)")
            except Exception as e:
                print(f"⚠️  Could not load {file_path.name}: {e}")

        if not all_data:
            error_msg = f"No valid ticket data could be loaded from {len(ticket_files)} files. "
            if ticket_files:
                error_msg += f"Files attempted: {[f.name for f in ticket_files]}"
            raise ValueError(error_msg)

        self.df = pd.concat(all_data, ignore_index=True)
        self.original_df = self.df.copy()
        
        print(f"✅ Total ticket records loaded: {len(self.df):,}")
        return self.df
    
    def process_data(self) -> pd.DataFrame:
        """Apply all ticket data transformations"""
        if self.df is None:
            raise ValueError("No data loaded. Call load_data() first.")
            
        self.df = self._convert_timezone(self.df)
        self.df = self._map_staff_names(self.df)
        self.df = self._map_pipeline_names(self.df)
        self.df = self._add_weekend_flag(self.df)
        self.df = self._calc_first_response(self.df)
        self.df = self._remove_spam(self.df)
        self.df = self._remove_manager_tickets(self.df)

        return self.df
    
    def filter_date_range(self, start_dt: Optional[datetime], end_dt: Optional[datetime]) -> Tuple[pd.DataFrame, int, int]:
        """Filter data by date range"""
        if start_dt is None or end_dt is None:
            return self.df, len(self.df), len(self.df)
            
        mask = (self.df["Create date"] >= start_dt) & (self.df["Create date"] <= end_dt)
        filtered = self.df[mask].copy()
        return filtered, len(self.df), len(filtered)
    
    def _convert_timezone(self, df: pd.DataFrame) -> pd.DataFrame:
        """Convert CDT timestamps to EDT"""
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
                df[col] = pd.to_datetime(df[col], errors="coerce")

                # Skip if conversion failed and column is still object dtype
                if not pd.api.types.is_datetime64_any_dtype(df[col]):
                    continue

                # Check if already timezone-aware
                if df[col].dt.tz is None:
                    # Not timezone-aware, localize to CDT first
                    df[col] = df[col].dt.tz_localize(central, ambiguous=False, nonexistent="shift_forward")
                elif df[col].dt.tz != eastern:
                    # Already timezone-aware but not in eastern, convert to eastern
                    df[col] = df[col].dt.tz_convert(eastern)
                # If already in eastern timezone, no conversion needed
        
        print("Converted CDT → EDT (+1h)")
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

        # Check which column name exists (could be "Ticket owner" or "Case Owner")
        owner_col = None
        if "Ticket owner" in df.columns:
            owner_col = "Ticket owner"
        elif "Case Owner" in df.columns:
            owner_col = "Case Owner"

        if owner_col:
            df["Case Owner"] = df[owner_col].map(mapping).fillna(df[owner_col])
            print("Mapped staff names.")
        else:
            print("Warning: No owner column found to map staff names")

        return df

    def _map_pipeline_names(self, df: pd.DataFrame) -> pd.DataFrame:
        """Map pipeline IDs to readable labels"""
        # Pipeline mapping from HubSpot
        pipeline_mapping = {
            '0': 'Support Pipeline',
            '147307289': 'Live Chat',
            '648529801': 'Upgrades/Downgrades',
            '667370066': 'Success',
            '724973238': 'Customer Onboarding',
            '76337708': 'Dev Tickets',
            '77634704': 'Marketing, Finance',
            '803109779': 'Product Testing Requests - Enterprise',
            '803165721': 'Trial Account Requests - Enterprise',
            '95256452': 'Enterprise and VIP Tickets',
            '95947431': 'SPAM Tickets'
        }

        if "Pipeline" in df.columns:
            # Convert to string first (in case they're numeric)
            df["Pipeline"] = df["Pipeline"].astype(str).map(pipeline_mapping).fillna(df["Pipeline"])
            print("Mapped pipeline IDs to readable names.")
        else:
            print("Warning: No Pipeline column found")

        return df

    def _add_weekend_flag(self, df: pd.DataFrame) -> pd.DataFrame:
        """Flag tickets created during off-hours using agent-specific schedules with EDT timezone and buffer periods"""
        try:
            with open(self.schedule_file, 'r') as f:
                schedule = yaml.safe_load(f)
            agents_config = schedule.get('agents', {})
            shifts_config = schedule.get('shifts', {})  # Fallback for backward compatibility
        except Exception as e:
            raise RuntimeError(
                f"❌ Failed to load schedule configuration from {self.schedule_file}: {e}\n"
                "Please check the file exists and has valid YAML format"
            ) from e

        edt_tz = pytz.timezone('US/Eastern')
        
        def _is_agent_off_shift(row):
            """Check if ticket was created during agent's off-shift hours with buffer logic"""
            if pd.isna(row["Create date"]):
                return False
                
            # Convert to EDT timezone
            dt_edt = row["Create date"].astimezone(edt_tz)
            weekday = dt_edt.weekday()  # Monday=0, Sunday=6
            day_name = ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday'][weekday]
            
            # Check weekend definition first: Friday after 6PM EDT until Monday at 5AM EDT
            if _is_weekend_period(dt_edt):
                return True
            
            # Get agent from ticket
            agent_name = row.get("Case Owner", row.get("Ticket owner", "")).strip()
            
            # Use agent-specific schedule if available, otherwise fallback to global shifts
            if agent_name in agents_config:
                agent_schedule = agents_config[agent_name]
            else:
                # Fallback to global shifts for backward compatibility
                agent_schedule = shifts_config
                if agent_name:  # Only print warning if agent name exists
                    print(f"⚠️  No agent-specific schedule found for '{agent_name}', using global shifts")
            
            # Check if day has any shifts defined
            if day_name not in agent_schedule:
                return True  # No shifts defined = off-shift
                
            day_schedule = agent_schedule[day_name]
            
            # Handle full coverage days
            if day_schedule == 'full':
                return False
                
            # Handle empty schedule (no shifts)
            if not day_schedule:
                return True
                
            # Check if during any scheduled shift (with 30-minute buffer)
            current_time = dt_edt.time()
            on_shift = False
            
            for shift in day_schedule:
                try:
                    start_time = datetime.strptime(shift['start'], '%H:%M').time()
                    end_time = datetime.strptime(shift['end'], '%H:%M').time()
                    
                    # Apply 30-minute buffer: include tickets 30min before shift starts
                    start_with_buffer = (datetime.combine(dt_edt.date(), start_time) - timedelta(minutes=30)).time()
                    
                    # Handle overnight shifts (end < start)
                    if end_time < start_time:
                        # Overnight shift logic with buffer
                        if current_time >= start_with_buffer or current_time < end_time:
                            on_shift = True
                            break
                    else:
                        # Normal shift logic with buffer
                        if start_with_buffer <= current_time < end_time:
                            on_shift = True
                            break
                            
                except (KeyError, TypeError, ValueError) as e:
                    print(f"⚠️  Invalid shift format for {agent_name} on {day_name}: {shift}")
                    continue
                    
            return not on_shift
        
        def _is_weekend_period(dt_edt):
            """Check if timestamp falls within weekend period: Friday 6PM EDT - Monday 5AM EDT"""
            weekday = dt_edt.weekday()  # Monday=0, Sunday=6
            current_time = dt_edt.time()
            
            # Friday after 6PM
            if weekday == 4 and current_time >= datetime.strptime('18:00', '%H:%M').time():
                return True
                
            # Saturday and Sunday (all day)
            if weekday in [5, 6]:
                return True
                
            # Monday before 5AM
            if weekday == 0 and current_time < datetime.strptime('05:00', '%H:%M').time():
                return True
                
            return False

        # Apply the weekend flag logic (calendar-based only, not agent-specific)
        def _is_calendar_weekend(row):
            """Check if ticket was created during actual weekend period (Friday 6PM EDT - Monday 5AM EDT)"""
            if pd.isna(row["Create date"]):
                return False
            # Convert to EDT timezone
            dt_edt = row["Create date"].astimezone(edt_tz)
            return _is_weekend_period(dt_edt)
        
        df["Weekend_Ticket"] = df.apply(_is_calendar_weekend, axis=1)
        
        # Statistics
        weekend_count = df['Weekend_Ticket'].sum()
        total_count = len(df)
        weekend_pct = (weekend_count / total_count * 100) if total_count > 0 else 0
        
        print(f"✅ Flagged {weekend_count:,} weekend tickets ({weekend_pct:.1f}%) using calendar-based classification")
        print(f"   Weekend definition: Friday 6PM EDT - Monday 5AM EDT")
        
        return df

    
    def _calc_first_response(self, df: pd.DataFrame) -> pd.DataFrame:
        """Calculate first response times"""

        # Check if we have the required columns for first response calculation
        has_response_col = "First agent email response date" in df.columns
        has_create_col = "Create date" in df.columns
        has_pipeline_col = "Pipeline" in df.columns

        if not has_create_col:
            print("Warning: 'Create date' column not found, skipping first response calculation")
            df["First Response Time"] = pd.NaT
            df["First Response Time (Hours)"] = pd.NA
            return df

        def _delta(row):
            # Handle Live Chat pipeline
            if has_pipeline_col and row.get("Pipeline") == "Live Chat ":
                return pd.Timedelta(seconds=30)

            # Check if response date column exists and has value
            if not has_response_col or pd.isna(row.get("First agent email response date")) or pd.isna(row["Create date"]):
                return pd.NaT

            # Calculate response time
            response_time = row["First agent email response date"] - row["Create date"]

            # Validate that response time is positive (response after ticket creation)
            if response_time.total_seconds() <= 0:
                return pd.NaT  # Treat negative/zero response times as invalid

            return response_time

        df["First Response Time"] = df.apply(_delta, axis=1)
        # Convert Timedelta to hours (use .total_seconds() on the values, not .dt accessor)
        df["First Response Time (Hours)"] = df["First Response Time"].apply(
            lambda x: x.total_seconds() / 3600 if pd.notna(x) else pd.NA
        )
        
        # Log validation results
        total_records = len(df)
        negative_count = (df["First Response Time (Hours)"] < 0).sum()
        zero_count = (df["First Response Time (Hours)"] == 0).sum()
        valid_count = df["First Response Time (Hours)"].notna().sum()
        
        if negative_count > 0:
            print(f"⚠️  Found and excluded {negative_count} tickets with negative response times")
        if zero_count > 0:
            print(f"⚠️  Found and excluded {zero_count} tickets with zero response times")
        
        print(f"✅ Calculated first-response times for {valid_count:,} of {total_records:,} tickets")
        return df
    
    def _remove_spam(self, df: pd.DataFrame) -> pd.DataFrame:
        """Remove SPAM tickets"""
        pre_count = len(df)
        df = df[df["Pipeline"] != "SPAM Tickets"].copy()
        removed_count = pre_count - len(df)
        print(f"Removed {removed_count:,} SPAM tickets.")
        return df

    def _remove_manager_tickets(self, df: pd.DataFrame) -> pd.DataFrame:
        """Remove manager tickets (Richie) - only include support team agents"""
        pre_count = len(df)
        # Only include tickets from support team: Bhushan, Girly, Nova, Francis
        support_agents = ['Bhushan', 'Girly', 'Nova', 'Francis']

        # Get the owner column name (could be "Case Owner" or "Ticket owner")
        owner_col = None
        for col in ['Case Owner', 'Ticket owner']:
            if col in df.columns:
                owner_col = col
                break

        if owner_col:
            df = df[df[owner_col].isin(support_agents)].copy()
            removed_count = pre_count - len(df)
            print(f"Removed {removed_count:,} manager tickets (non-support team).")
        else:
            print("Warning: Could not find owner column to filter manager tickets.")

        return df
    
    def generate_analytics(self, analysis_df: pd.DataFrame, args) -> Dict:
        """Generate ticket analytics and charts"""
        analytics = {
            'charts': [],
            'tables': [],
            'metrics': [],
            'summary': {}
        }
        
        # 1. Tickets by Pipeline - Convert to Plotly
        analytics['charts'].append(self._create_pipeline_chart(analysis_df))
        
        # 2. Weekend vs Weekday Distribution - Convert to Plotly
        analytics['charts'].append(self._create_weekend_distribution_chart(analysis_df))
        
        # 3. Daily Ticket Volume - Removed per requirements
        #    The "Daily Ticket Volume" chart has been intentionally excluded from the dashboard.
        #    We keep "Historic Daily Ticket Volume" below.
        
        # 4. Historic Daily Volume (back to start of 2025) - Use full dataset
        if self.df is not None and len(self.df) > 0:
            full_df = self.df.copy()
            full_df["Day"] = full_df["Create date"].dt.date
            historic_day_counts = full_df["Day"].value_counts().sort_index()
            if len(historic_day_counts) > 0:
                analytics['charts'].append(self._create_historic_daily_volume_chart(historic_day_counts))
        
        # Summary metrics
        total_tickets = len(analysis_df)
        weekend_tickets = analysis_df["Weekend_Ticket"].sum()
        weekday_tickets = total_tickets - weekend_tickets
        
        # Response time analysis (weekdays only, excluding LiveChat)
        weekday_df = analysis_df[analysis_df["Weekend_Ticket"] == False]
        weekday_non_livechat = weekday_df[weekday_df["Pipeline"] != "Live Chat "]
        avg_response_weekday = weekday_non_livechat["First Response Time (Hours)"].median()
        
        # Find owner column for agent analysis
        owner_col = None
        for col in ["Case Owner", "Ticket owner", "Owner", "Assigned Agent"]:
            if col in weekday_df.columns:
                owner_col = col
                break
        
        weekend_df = analysis_df[analysis_df["Weekend_Ticket"] == True]
        avg_response_weekend = weekend_df["First Response Time (Hours)"].mean()
        
        # Calculate daily averages for subtext
        date_range_days = (analysis_df['Create date'].max() - analysis_df['Create date'].min()).days + 1
        daily_avg_total = total_tickets / date_range_days if date_range_days > 0 else 0
        daily_avg_weekday = weekday_tickets / date_range_days if date_range_days > 0 else 0
        daily_avg_weekend = weekend_tickets / date_range_days if date_range_days > 0 else 0
        
        analytics['metrics'] = [
            # Make weekday response time prominent and larger
            create_metric_card(f"{avg_response_weekday:.3f}h" if pd.notna(avg_response_weekday) else "N/A", 
                             "⚡ Median Response (Weekday)", "satisfaction-card-ultra"),
            # Add daily averages as subtext for count cards - alternating colors
            create_metric_card(total_tickets, "Total Tickets", "transfer-card-ultra", 
                             f"{daily_avg_total:.1f} per day"),
            create_metric_card(weekday_tickets, "Weekday Tickets", "satisfaction-card-ultra",
                             f"{daily_avg_weekday:.1f} per day"), 
            create_metric_card(weekend_tickets, "Weekend Tickets", "transfer-card-ultra",
                             f"{daily_avg_weekend:.1f} per day"),
        ]
        
        # Agent performance table and charts
        analytics['tables'].append(self._create_agent_table(weekday_df))
        
        # Agent performance charts
        agent_charts = self._create_agent_performance_charts(weekday_df)
        if agent_charts:
            analytics['charts'].extend(agent_charts)
        
        # Weekly response time trend chart
        weekly_chart = self._create_weekly_response_time_chart(analysis_df)
        if weekly_chart:
            analytics['charts'].append(weekly_chart)
        
        # Optional delayed response table
        if args.include_delayed_table:
            analytics['tables'].append(self._create_delayed_table(analysis_df))
        
        analytics['summary'] = {
            'total_tickets': total_tickets,
            'weekend_tickets': weekend_tickets,
            'avg_response_weekday': avg_response_weekday,
            'avg_response_weekend': avg_response_weekend,
            'agent_count': len(weekday_df[owner_col].unique()) if owner_col else 0
        }
        
        return analytics
    
    def _create_pipeline_chart(self, analysis_df: pd.DataFrame) -> str:
        """Create modern Plotly pipeline distribution chart"""
        try:
            import plotly.graph_objects as go
            
            # Get pipeline counts
            pipeline_counts = analysis_df["Pipeline"].value_counts()
            
            # Create horizontal bar chart for better readability
            fig = go.Figure(data=[
                go.Bar(
                    y=pipeline_counts.index,
                    x=pipeline_counts.values,
                    orientation='h',
                    marker_color='rgba(102, 126, 234, 0.8)',
                    text=pipeline_counts.values,
                    textposition='auto',
                    hovertemplate='<b>%{y}</b><br>Tickets: %{x}<extra></extra>'
                )
            ])
            
            fig.update_layout(
                title='🎯 Tickets by Pipeline',
                xaxis_title='Number of Tickets',
                yaxis_title='Pipeline',
                template='plotly_dark',
                plot_bgcolor='rgba(30, 30, 46, 0.8)',
                paper_bgcolor='rgba(23, 23, 35, 0.9)',
                font=dict(color='#e0e0e0'),
                height=400,
                margin=dict(l=150, r=50, t=50, b=50),
                xaxis=dict(gridcolor='rgba(102, 126, 234, 0.2)', showgrid=True),
                yaxis=dict(gridcolor='rgba(102, 126, 234, 0.2)', showgrid=True)
            )
            
            return f'''
            <div class="chart-container">
                {fig.to_html(include_plotlyjs="cdn")}
            </div>
            '''
            
        except ImportError:
            # Fallback to matplotlib if Plotly not available
            import matplotlib.pyplot as plt
            import seaborn as sns
            
            fig, ax = plt.subplots(figsize=(8, 6))
            sns.countplot(
                y="Pipeline",
                data=analysis_df,
                order=analysis_df["Pipeline"].value_counts().index,
                ax=ax,
            )
            ax.set_title("Tickets by Pipeline")
            plt.tight_layout()
            return fig_to_html(fig)
    
    def _create_weekend_distribution_chart(self, analysis_df: pd.DataFrame) -> str:
        """Create modern Plotly weekend/weekday distribution pie chart"""
        try:
            import plotly.graph_objects as go
            
            # Get weekend distribution
            weekend_counts = analysis_df["Weekend_Ticket"].value_counts()
            labels = ["Weekday" if not k else "Weekend" for k in weekend_counts.index]
            values = weekend_counts.values
            
            # Create pie chart with modern styling
            fig = go.Figure(data=[
                go.Pie(
                    labels=labels,
                    values=values,
                    hole=0.3,  # Donut chart for modern look
                    marker_colors=['rgba(78, 205, 196, 0.8)', 'rgba(255, 107, 107, 0.8)'],
                    textinfo='label+percent+value',
                    textposition='auto',
                    hovertemplate='<b>%{label}</b><br>Tickets: %{value}<br>Percentage: %{percent}<extra></extra>'
                )
            ])
            
            fig.update_layout(
                title='📅 Weekday vs Weekend Distribution',
                template='plotly_dark',
                plot_bgcolor='rgba(30, 30, 46, 0.8)',
                paper_bgcolor='rgba(23, 23, 35, 0.9)',
                font=dict(color='#e0e0e0'),
                height=400,
                showlegend=True,
                legend=dict(
                    orientation="v",
                    yanchor="middle",
                    y=0.5,
                    xanchor="left",
                    x=1.05
                )
            )
            
            return f'''
            <div class="chart-container">
                {fig.to_html(include_plotlyjs="cdn")}
            </div>
            '''
            
        except ImportError:
            # Fallback to matplotlib if Plotly not available
            import matplotlib.pyplot as plt
            
            fig, ax = plt.subplots(figsize=(6, 6))
            weekend_counts = analysis_df["Weekend_Ticket"].value_counts()
            ax.pie(
                weekend_counts,
                labels=["Weekday" if not k else "Weekend" for k in weekend_counts.index],
                autopct="%.1f%%",
                colors=["#7fcdbb", "#fc8d62"],
                startangle=90,
            )
            ax.set_title("Weekday/Weekend Distribution")
            plt.tight_layout()
            return fig_to_html(fig)
    
    def _create_agent_table(self, weekday_df: pd.DataFrame) -> str:
        """Create agent performance table"""
        # Find ticket ID column
        ticket_id_col = None
        for col in ["Ticket number", "Ticket ID", "ID"]:
            if col in weekday_df.columns:
                ticket_id_col = col
                break
        
        if not ticket_id_col:
            return "<p>No ticket ID column found for agent analysis</p>"
        
        # Find owner column
        owner_col = None
        for col in ["Case Owner", "Ticket owner", "Owner", "Assigned Agent"]:
            if col in weekday_df.columns:
                owner_col = col
                break
        
        if not owner_col:
            return "<p>No owner column found for agent analysis</p>"
        
        # Filter out LiveChat tickets for response time calculations
        non_livechat_df = weekday_df[weekday_df["Pipeline"] != "Live Chat "].copy()
        
        # Enhanced agent statistics with volume breakdowns (excluding LiveChat for response times)
        agent_stats = weekday_df.groupby(owner_col).agg({
            ticket_id_col: "count",
            "Pipeline": lambda x: x.value_counts().to_dict()  # Pipeline breakdown
        })
        
        # Calculate response time stats excluding LiveChat tickets
        if len(non_livechat_df) > 0:
            # Convert pd.NA to np.nan for aggregation compatibility
            non_livechat_df = non_livechat_df.copy()
            non_livechat_df["First Response Time (Hours)"] = non_livechat_df["First Response Time (Hours)"].replace({pd.NA: np.nan})

            response_stats = non_livechat_df.groupby(owner_col)["First Response Time (Hours)"].agg(["mean", "median", "std"])
            response_stats.columns = ["Avg_Response_Time", "Median_Response_Time", "Response_Time_Std"]
            agent_stats = agent_stats.join(response_stats, how='left')
        else:
            agent_stats["Avg_Response_Time"] = float('nan')
            agent_stats["Median_Response_Time"] = float('nan')
            agent_stats["Response_Time_Std"] = float('nan')
        
        # Flatten column names - now they should already be flat
        if isinstance(agent_stats.columns, pd.MultiIndex):
            agent_stats.columns = agent_stats.columns.droplevel(1)
        agent_stats.columns = ["Tickets_Handled", "Pipeline_Breakdown", "Avg_Response_Time", "Median_Response_Time", "Response_Time_Std"]
        
        # Add percentage of total tickets
        total_tickets = len(weekday_df)
        agent_stats["Percentage_of_Total"] = (agent_stats["Tickets_Handled"] / total_tickets * 100).round(1)
        
        # Add daily average (assumes data spans multiple days)
        date_range_days = (weekday_df["Create date"].max() - weekday_df["Create date"].min()).days + 1
        agent_stats["Daily_Average"] = (agent_stats["Tickets_Handled"] / date_range_days).round(1)
        
        # Clean up data types
        agent_stats["Tickets_Handled"] = agent_stats["Tickets_Handled"].astype(int)
        agent_stats["Avg_Response_Time"] = agent_stats["Avg_Response_Time"].round(2)
        agent_stats["Median_Response_Time"] = agent_stats["Median_Response_Time"].round(2)
        agent_stats["Response_Time_Std"] = agent_stats["Response_Time_Std"].round(2)
        
        # Sort by tickets handled
        agent_stats = agent_stats.sort_values("Tickets_Handled", ascending=False)
        
        rows = []
        for agent, row in agent_stats.iterrows():
            # Format response time data
            avg_time = f"{row['Avg_Response_Time']:.2f}h" if pd.notna(row['Avg_Response_Time']) else "No data"
            median_time = f"{row['Median_Response_Time']:.2f}h" if pd.notna(row['Median_Response_Time']) else "No data"
            
            # Format pipeline breakdown
            pipeline_breakdown = row['Pipeline_Breakdown']
            if isinstance(pipeline_breakdown, dict) and pipeline_breakdown:
                top_pipeline = max(pipeline_breakdown, key=pipeline_breakdown.get)
                top_count = pipeline_breakdown[top_pipeline]
                pipeline_text = f"{top_pipeline} ({top_count})"
                if len(pipeline_breakdown) > 1:
                    pipeline_text += f" +{len(pipeline_breakdown)-1} more"
            else:
                pipeline_text = "No data"
            
            rows.append(f"""
            <tr>
                <td style="font-weight:bold">{agent}</td>
                <td style="text-align:center">{row['Tickets_Handled']}</td>
                <td style="text-align:center">{row['Percentage_of_Total']:.1f}%</td>
                <td style="text-align:center">{row['Daily_Average']:.1f}</td>
                <td style="text-align:center">{avg_time}</td>
                <td style="text-align:center">{median_time}</td>
                <td style="font-size:0.85em; max-width:200px; overflow:hidden; text-overflow:ellipsis;">{pipeline_text}</td>
            </tr>
            """)
        
        # Create summary row
        total_summary = f"""
        <tr style="border-top: 2px solid #667eea; background-color: rgba(102, 126, 234, 0.1); font-weight:bold;">
            <td>TOTAL</td>
            <td style="text-align:center">{total_tickets}</td>
            <td style="text-align:center">100.0%</td>
            <td style="text-align:center">{(total_tickets / date_range_days):.1f}</td>
            <td colspan="3" style="text-align:center; font-style:italic;">Summary across {len(agent_stats)} agents</td>
        </tr>
        """
        
        return f"""
        <div class="section">
            <h2>Agent Performance & Volume Breakdown (Weekdays Only)</h2>
            <div style="margin-bottom: 10px; color: #e0e0e0; font-size: 0.9em;">
                📊 Volume analysis across {date_range_days} day(s) • {len(agent_stats)} active agents • Response times exclude LiveChat tickets
            </div>
            <div class="table-container">
                <table class="performance-table">
                    <thead>
                        <tr>
                            <th>Agent</th>
                            <th>Total<br>Tickets</th>
                            <th>% of<br>Total</th>
                            <th>Daily<br>Avg</th>
                            <th>Avg Response<br>Time (excl. LiveChat)</th>
                            <th>Median Response<br>Time (excl. LiveChat)</th>
                            <th>Top Pipeline</th>
                        </tr>
                    </thead>
                    <tbody>
                        {''.join(rows)}
                        {total_summary}
                    </tbody>
                </table>
            </div>
            <div style="margin-top: 10px; color: #999; font-size: 0.8em; font-style: italic;">
                💡 Tip: Higher volume agents may show different response time patterns due to workload distribution.
            </div>
        </div>
        """
    
    def _create_agent_performance_charts(self, weekday_df: pd.DataFrame) -> List[str]:
        """Create enhanced agent performance charts with volume breakdowns - Always use Plotly for consistency"""
        try:
            # Always use Plotly for consistency with chat analytics
            import plotly.graph_objects as go
            from plotly.subplots import make_subplots
            return self._create_interactive_agent_charts(weekday_df)
            
        except ImportError:
            print("Plotly not available for agent charts, falling back to matplotlib")
            return self._create_matplotlib_agent_charts_fallback(weekday_df)
        except Exception as e:
            print(f"Error creating agent performance charts: {e}")
            return []
    
    def _create_matplotlib_agent_charts_fallback(self, weekday_df: pd.DataFrame) -> List[str]:
        """Fallback matplotlib agent charts (only used if Plotly unavailable)"""
        try:
            import numpy as np
            import matplotlib.pyplot as plt
            
            # Find ticket ID column
            ticket_id_col = None
            for col in ["Ticket number", "Ticket ID", "ID"]:
                if col in weekday_df.columns:
                    ticket_id_col = col
                    break
            
            if not ticket_id_col:
                return []
            
            # Find owner column
            owner_col = None
            for col in ["Case Owner", "Ticket owner", "Owner", "Assigned Agent"]:
                if col in weekday_df.columns:
                    owner_col = col
                    break
            
            if not owner_col:
                return []
            
            # Filter out LiveChat tickets for response time calculations
            non_livechat_df = weekday_df[weekday_df["Pipeline"] != "Live Chat "].copy()
            
            # Calculate enhanced agent statistics for charts (volume from all tickets, response times excluding LiveChat)
            agent_stats = weekday_df.groupby(owner_col).agg({
                ticket_id_col: "count",
                "Pipeline": lambda x: x.value_counts().to_dict()
            })
            
            # Calculate response time stats excluding LiveChat tickets
            if len(non_livechat_df) > 0:
                # Convert pd.NA to np.nan for aggregation compatibility
                non_livechat_df = non_livechat_df.copy()
                non_livechat_df["First Response Time (Hours)"] = non_livechat_df["First Response Time (Hours)"].replace({pd.NA: np.nan})

                response_stats = non_livechat_df.groupby(owner_col)["First Response Time (Hours)"].agg(["mean", "median"])
                response_stats.columns = ["Avg_Response_Time", "Median_Response_Time"]
                agent_stats = agent_stats.join(response_stats, how='left')
            else:
                agent_stats["Avg_Response_Time"] = float('nan')
                agent_stats["Median_Response_Time"] = float('nan')
            
            # Flatten columns - now they should already be flat
            if isinstance(agent_stats.columns, pd.MultiIndex):
                agent_stats.columns = agent_stats.columns.droplevel(1)
            agent_stats.columns = ["Tickets_Handled", "Pipeline_Breakdown", "Avg_Response_Time", "Median_Response_Time"]
            agent_stats["Tickets_Handled"] = agent_stats["Tickets_Handled"].astype(int)
            agent_stats["Avg_Response_Time"] = agent_stats["Avg_Response_Time"].round(2)
            agent_stats["Median_Response_Time"] = agent_stats["Median_Response_Time"].round(2)
            
            # Add percentage calculation
            total_tickets = len(weekday_df)
            agent_stats["Percentage"] = (agent_stats["Tickets_Handled"] / total_tickets * 100).round(1)
            
            agent_stats = agent_stats.sort_values("Tickets_Handled", ascending=False)
            
            if len(agent_stats) == 0:
                return []
            
            charts = []
            
            # Chart 1: Enhanced Volume Distribution with Percentages
            fig1, (ax1a, ax1b) = plt.subplots(1, 2, figsize=(16, 6))
            
            # Left: Ticket count bars
            bars1a = ax1a.bar(agent_stats.index, agent_stats["Tickets_Handled"], color='#6366f1', alpha=0.8)
            ax1a.set_title('📊 Ticket Volume by Agent', fontsize=12, fontweight='bold')
            ax1a.set_xlabel('Agent', fontsize=10)
            ax1a.set_ylabel('Number of Tickets', fontsize=10)
            ax1a.grid(axis='y', alpha=0.3)
            
            # Add value labels with percentages
            for bar, (agent, row) in zip(bars1a, agent_stats.iterrows()):
                height = bar.get_height()
                percentage = row["Percentage"]
                ax1a.text(bar.get_x() + bar.get_width()/2., height + 0.5,
                        f'{int(height)}\n({percentage:.1f}%)',
                        ha='center', va='bottom', fontweight='bold', fontsize=9)
            
            ax1a.tick_params(axis='x', rotation=45, labelsize=9)
            
            # Right: Pie chart of percentage distribution
            colors = ['#6366f1', '#ec4899', '#10b981', '#f59e0b', '#8b5cf6', '#06b6d4', '#84cc16', '#f97316']
            pie_colors = colors[:len(agent_stats)]
            
            wedges, texts, autotexts = ax1b.pie(agent_stats["Percentage"],
                                              labels=agent_stats.index,
                                              colors=pie_colors,
                                              autopct='%1.1f%%',
                                              startangle=90)
            ax1b.set_title('📈 Volume Distribution', fontsize=12, fontweight='bold')
            
            # Adjust text properties
            for autotext in autotexts:
                autotext.set_color('white')
                autotext.set_fontweight('bold')
                autotext.set_fontsize(8)
            for text in texts:
                text.set_fontsize(8)
            
            plt.tight_layout()
            charts.append(fig_to_html(fig1))
            
            # Chart 2: Response Time Comparison (Average vs Median)
            fig2, ax2 = plt.subplots(figsize=(12, 6))
            x_pos = np.arange(len(agent_stats))
            width = 0.35

            # Fill NA values with 0 for plotting
            avg_times = agent_stats["Avg_Response_Time"].fillna(0)
            median_times = agent_stats["Median_Response_Time"].fillna(0)

            bars2a = ax2.bar(x_pos - width/2, avg_times, width,
                           label='Average', color='#ec4899', alpha=0.8)
            bars2b = ax2.bar(x_pos + width/2, median_times, width,
                           label='Median', color='#10b981', alpha=0.8)
            
            ax2.set_title('⏱️ Response Time Analysis: Average vs Median by Agent', fontsize=14, fontweight='bold', pad=20)
            ax2.set_xlabel('Agent', fontsize=12)
            ax2.set_ylabel('Response Time (Hours)', fontsize=12)
            ax2.set_xticks(x_pos)
            ax2.set_xticklabels(agent_stats.index, rotation=45, ha='right')
            ax2.grid(axis='y', alpha=0.3)
            ax2.legend()
            
            # Add value labels on bars
            for bars, values in [(bars2a, avg_times), (bars2b, median_times)]:
                for bar, value in zip(bars, values):
                    height = bar.get_height()
                    if height > 0:  # Only show label if value exists
                        ax2.text(bar.get_x() + bar.get_width()/2., height + 0.01,
                                f'{height:.2f}h', ha='center', va='bottom', fontweight='bold', fontsize=8)
            
            plt.tight_layout()
            charts.append(fig_to_html(fig2))
            
            return charts
            
        except Exception as e:
            print(f"Error creating matplotlib fallback agent charts: {e}")
            return []
    
    def _create_daily_volume_chart(self, day_counts: pd.Series) -> str:
        """Create daily ticket volume chart"""
        try:
            import plotly.graph_objects as go
            
            # Convert the series to a format suitable for plotting
            dates = day_counts.index
            volumes = day_counts.values
            
            # Create the Plotly bar chart
            fig = go.Figure(data=go.Bar(
                x=dates,
                y=volumes,
                name='Daily Ticket Volume',
                marker_color='rgba(78, 205, 196, 0.8)',
                text=volumes,
                textposition='outside'
            ))
            
            fig.update_layout(
                title='📊 Daily Ticket Volume',
                xaxis_title='Date',
                yaxis_title='Number of Tickets',
                template='plotly_dark',
                plot_bgcolor='rgba(30, 30, 46, 0.8)',
                paper_bgcolor='rgba(23, 23, 35, 0.9)',
                font=dict(color='#e0e0e0'),
                height=400,
                margin=dict(l=50, r=50, t=50, b=50),
                xaxis=dict(gridcolor='rgba(102, 126, 234, 0.2)', showgrid=True),
                yaxis=dict(gridcolor='rgba(102, 126, 234, 0.2)', showgrid=True),
                showlegend=False
            )
            
            return f"""
            <div class="section">
                <h3>📊 Daily Ticket Volume</h3>
                <div class="chart">
                    {fig.to_html(include_plotlyjs="cdn")}
                </div>
            </div>
            """
            
        except ImportError:
            print("Plotly not available, falling back to static chart")
            return self._create_matplotlib_daily_volume_fallback(day_counts)
        except Exception as e:
            print(f"Error creating daily volume chart: {e}")
            return ""

    def _create_matplotlib_daily_volume_fallback(self, day_counts: pd.Series) -> str:
        """Fallback matplotlib daily volume chart"""
        try:
            import matplotlib.pyplot as plt
            import numpy as np
            
            fig, ax = plt.subplots(figsize=(12, 6))
            dates = day_counts.index
            volumes = day_counts.values
            
            # Create bar chart
            bars = ax.bar(dates, volumes, color='#4ecdc4', alpha=0.8)
            
            # Add value labels on bars
            for bar in bars:
                height = bar.get_height()
                ax.text(bar.get_x() + bar.get_width()/2., height + 0.1,
                       f'{int(height)}', ha='center', va='bottom')
            
            ax.set_title('Daily Ticket Volume', fontsize=16, fontweight='bold')
            ax.set_xlabel('Date')
            ax.set_ylabel('Number of Tickets')
            ax.grid(True, alpha=0.3)
            
            # Rotate x-axis labels for better readability
            plt.xticks(rotation=45)
            plt.tight_layout()
            
            from common_utils import fig_to_html
            return f"""
            <div class="section">
                <h3>📊 Daily Ticket Volume</h3>
                {fig_to_html(fig, "chart")}
            </div>
            """
            
        except Exception as e:
            print(f"Error creating fallback daily volume chart: {e}")
            return ""

    def _create_daily_volume_chart(self, day_counts: pd.Series) -> str:
        """Create daily ticket volume chart"""
        try:
            import plotly.graph_objects as go
            
            # Convert the series to a format suitable for plotting
            dates = day_counts.index
            volumes = day_counts.values
            
            # Create the Plotly bar chart
            fig = go.Figure(data=go.Bar(
                x=dates,
                y=volumes,
                name='Daily Ticket Volume',
                marker_color='rgba(78, 205, 196, 0.8)',
                text=volumes,
                textposition='outside'
            ))
            
            fig.update_layout(
                title='📊 Daily Ticket Volume',
                xaxis_title='Date',
                yaxis_title='Number of Tickets',
                template='plotly_dark',
                plot_bgcolor='rgba(30, 30, 46, 0.8)',
                paper_bgcolor='rgba(23, 23, 35, 0.9)',
                font=dict(color='#e0e0e0'),
                height=400,
                margin=dict(l=50, r=50, t=50, b=50),
                xaxis=dict(gridcolor='rgba(102, 126, 234, 0.2)', showgrid=True),
                yaxis=dict(gridcolor='rgba(102, 126, 234, 0.2)', showgrid=True),
                showlegend=False
            )
            
            return f"""
            <div class="section">
                <h3>📊 Daily Ticket Volume</h3>
                <div class="chart">
                    {fig.to_html(include_plotlyjs="cdn")}
                </div>
            </div>
            """
            
        except ImportError:
            print("Plotly not available, falling back to static chart")
            return self._create_matplotlib_daily_volume_fallback(day_counts)
        except Exception as e:
            print(f"Error creating daily volume chart: {e}")
            return ""

    def _create_matplotlib_daily_volume_fallback(self, day_counts: pd.Series) -> str:
        """Fallback matplotlib daily volume chart"""
        try:
            import matplotlib.pyplot as plt
            import numpy as np
            
            fig, ax = plt.subplots(figsize=(12, 6))
            dates = day_counts.index
            volumes = day_counts.values
            
            # Create bar chart
            bars = ax.bar(dates, volumes, color='#4ecdc4', alpha=0.8)
            
            # Styling
            ax.set_title('📊 Daily Ticket Volume', fontsize=16, fontweight='bold')
            ax.set_xlabel('Date', fontsize=12)
            ax.set_ylabel('Number of Tickets', fontsize=12)
            ax.grid(True, alpha=0.3)
            
            # Add value labels on bars
            for bar, value in zip(bars, volumes):
                height = bar.get_height()
                ax.text(bar.get_x() + bar.get_width()/2., height + 0.1,
                       f'{int(value)}', ha='center', va='bottom')
            
            # Format x-axis dates
            fig.autofmt_xdate()
            plt.tight_layout()
            
            # Convert to HTML
            html = fig_to_html(fig)
            plt.close(fig)
            
            return f"""
            <div class="section">
                <h3>📊 Daily Ticket Volume</h3>
                <div class="chart">
                    {html}
                </div>
            </div>
            """
            
        except Exception as e:
            print(f"Error creating fallback daily volume chart: {e}")
            return ""

    def _create_historic_daily_volume_chart(self, historic_day_counts: pd.Series) -> str:
        """Create historic daily volume chart showing all data back to start of 2025"""
        try:
            import plotly.graph_objects as go
            
            # Convert the series to a format suitable for plotting
            dates = historic_day_counts.index
            volumes = historic_day_counts.values
            
            # Create the Plotly bar chart with trend line
            fig = go.Figure()
            
            # Add daily volume bars
            fig.add_trace(go.Bar(
                x=dates,
                y=volumes,
                name='Daily Tickets',
                marker_color='rgba(78, 205, 196, 0.8)',
                text=volumes,
                textposition='outside'
            ))
            
            # Add trend line
            import numpy as np
            x_values = np.arange(len(dates))
            if len(dates) > 1:
                slope, intercept = np.polyfit(x_values, volumes, 1)
                trend_y = slope * x_values + intercept
                
                fig.add_trace(go.Scatter(
                    x=dates,
                    y=trend_y,
                    mode='lines',
                    name='Trend Line',
                    line=dict(color='rgba(255, 107, 107, 0.9)', width=3, dash='solid'),
                    yaxis='y'
                ))
            
            fig.update_layout(
                title=f'📈 Historic Daily Ticket Volume (Since 2025)',
                xaxis_title='Date',
                yaxis_title='Number of Tickets',
                template='plotly_dark',
                plot_bgcolor='rgba(30, 30, 46, 0.8)',
                paper_bgcolor='rgba(23, 23, 35, 0.9)',
                font=dict(color='#e0e0e0'),
                height=450,
                margin=dict(l=50, r=50, t=60, b=50),
                xaxis=dict(gridcolor='rgba(102, 126, 234, 0.2)', showgrid=True),
                yaxis=dict(gridcolor='rgba(102, 126, 234, 0.2)', showgrid=True),
                showlegend=True
            )
            
            return f"""
            <div class="section">
                <h3>📈 Historic Daily Ticket Volume</h3>
                <div class="chart">
                    {fig.to_html(include_plotlyjs="cdn")}
                </div>
            </div>
            """
            
        except ImportError:
            print("Plotly not available, falling back to static chart for historic volume")
            return self._create_matplotlib_historic_daily_fallback(historic_day_counts)
        except Exception as e:
            print(f"Error creating historic daily volume chart: {e}")
            return ""

    def _create_matplotlib_historic_daily_fallback(self, historic_day_counts: pd.Series) -> str:
        """Fallback matplotlib historic daily volume chart"""
        try:
            import matplotlib.pyplot as plt
            import numpy as np
            
            fig, ax = plt.subplots(figsize=(14, 6))
            dates = historic_day_counts.index
            volumes = historic_day_counts.values
            
            # Create bar chart
            bars = ax.bar(dates, volumes, color='#4ecdc4', alpha=0.8, width=0.8)
            
            # Add trend line
            x_values = np.arange(len(dates))
            if len(dates) > 1:
                slope, intercept = np.polyfit(x_values, volumes, 1)
                trend_y = slope * x_values + intercept
                ax.plot(dates, trend_y, color='#ff6b6b', linewidth=2, label='Trend Line')
            
            # Styling
            ax.set_title('📈 Historic Daily Ticket Volume (Since 2025)', fontsize=16, fontweight='bold')
            ax.set_xlabel('Date', fontsize=12)
            ax.set_ylabel('Number of Tickets', fontsize=12)
            ax.grid(True, alpha=0.3)
            ax.legend()
            
            # Format x-axis dates
            fig.autofmt_xdate()
            plt.tight_layout()
            
            # Convert to HTML
            html = fig_to_html(fig)
            plt.close(fig)
            
            return f"""
            <div class="section">
                <h3>📈 Historic Daily Ticket Volume</h3>
                <div class="chart">
                    {html}
                </div>
            </div>
            """
            
        except Exception as e:
            print(f"Error creating matplotlib historic daily volume chart: {e}")
            return ""

    def _create_weekly_response_time_chart(self, analysis_df: pd.DataFrame) -> str:
        """Create a single weekly response chart with Mean/Median toggle (Median default)."""
        try:
            # Always use Plotly for consistency with chat analytics
            import plotly.graph_objects as go

            # Build both chart variants but show only one via UI (Median by default).
            # Note: weekend series/bars are hidden by default; toggles remain visible.
            median_chart = self._create_interactive_weekly_chart(
                analysis_df,
                stat_type='median',
                visible=True,
                container_id='weekly-stat-median'
            )
            mean_chart = self._create_interactive_weekly_chart(
                analysis_df,
                stat_type='mean',
                visible=False,
                container_id='weekly-stat-mean'
            )

            # Simple radio controls to switch between Median and Mean without re-rendering.
            # We only toggle container visibility here. Median is the default selection.
            return f"""
            <div class="section">
                <div style="display:flex;justify-content:space-between;align-items:center;gap:10px;flex-wrap:wrap;">
                    <h3 style="margin:0;">📈 Weekly Response Time Trends</h3>
                    <div style="display:flex;align-items:center;gap:14px;">
                        <!-- UI toggle for statistic type (Median default) -->
                        <!-- Default must be Median per requirements -->
                        <label style="display:flex;align-items:center;gap:6px;color:#e0e0e0;">
                            <input type="radio" name="stat-type-toggle" value="median" checked
                                   onclick="toggleWeeklyStatType('median')" />
                            Median
                        </label>
                        <label style="display:flex;align-items:center;gap:6px;color:#e0e0e0;">
                            <input type="radio" name="stat-type-toggle" value="mean"
                                   onclick="toggleWeeklyStatType('mean')" />
                            Mean
                        </label>
                    </div>
                </div>

                <!-- Chart containers: rendered once, toggled via radios -->
                {median_chart}
                {mean_chart}
            </div>

            <script>
            // Toggle between median and mean variants by showing/hiding containers
            function toggleWeeklyStatType(stat) {{
                const medianEl = document.getElementById('weekly-stat-median');
                const meanEl = document.getElementById('weekly-stat-mean');
                if (!medianEl || !meanEl) return;

                if (stat === 'median') {{
                    medianEl.style.display = 'block';
                    meanEl.style.display = 'none';
                    // Apply current visibility settings for median variant
                    if (typeof updateChartDisplay_median === 'function') {{
                        updateChartDisplay_median();
                    }}
                }} else {{
                    medianEl.style.display = 'none';
                    meanEl.style.display = 'block';
                    // Apply current visibility settings for mean variant
                    if (typeof updateChartDisplay_mean === 'function') {{
                        updateChartDisplay_mean();
                    }}
                }}
            }}
            </script>
            """
        except ImportError:
            print("Plotly not available, falling back to static chart with simplified controls")
            return self._create_matplotlib_weekly_chart_fallback(analysis_df)
        except Exception as e:
            print(f"Error creating weekly response time chart: {e}")
            return ""
    
    def _create_matplotlib_weekly_chart_fallback(self, analysis_df: pd.DataFrame) -> str:
        """Fallback matplotlib weekly chart (only used if Plotly unavailable)"""
        try:
            from datetime import datetime, timedelta
            import numpy as np
            from scipy import stats
            import matplotlib.pyplot as plt
            
            # Use the filtered analysis_df for the selected period, not the full dataset
            if analysis_df is None or len(analysis_df) == 0:
                return ""
            
            # Use the full dataset to show all weeks of 2025, regardless of analysis period
            df_all = self.df.copy()
            
            # Get actual date range from full data
            min_date = df_all["Create date"].min()
            max_date = df_all["Create date"].max()
            
            if pd.isna(min_date) or pd.isna(max_date):
                return ""
            
            # Get Monday of each week - use naive datetime for consistency
            df_all['Monday'] = df_all["Create date"].dt.normalize().apply(
                lambda x: x - timedelta(days=x.weekday())
            )
            
            # Calculate comprehensive weekly stats for ALL ticket types (mean for consistency)
            weekly_stats_all = df_all.groupby('Monday').agg({
                'First Response Time (Hours)': 'median'
            }).reset_index()
            weekly_stats_all.columns = ['Monday', 'All_Tickets']
            
            # Calculate weekly stats for WEEKDAY ONLY tickets (mean for consistency)
            df_weekday = df_all[df_all["Weekend_Ticket"] == False].copy()
            weekly_stats_weekday = df_weekday.groupby('Monday').agg({
                'First Response Time (Hours)': 'median'
            }).reset_index()
            weekly_stats_weekday.columns = ['Monday', 'Weekday_Only']
            
            # Calculate weekly stats for WEEKEND ONLY tickets (mean for consistency)
            df_weekend = df_all[df_all["Weekend_Ticket"] == True].copy()
            weekly_stats_weekend = df_weekend.groupby('Monday').agg({
                'First Response Time (Hours)': 'median'
            }).reset_index()
            weekly_stats_weekend.columns = ['Monday', 'Weekend_Only']
            
            # Calculate overall means (constant lines across all weeks)
            overall_mean_all = df_all['First Response Time (Hours)'].median()
            overall_mean_weekday = df_weekday['First Response Time (Hours)'].median()
            overall_mean_weekend = df_weekend['First Response Time (Hours)'].median() if len(df_weekend) > 0 else None
            
            # Merge all datasets
            weekly_stats = weekly_stats_all.merge(weekly_stats_weekday, on='Monday', how='left')
            weekly_stats = weekly_stats.merge(weekly_stats_weekend, on='Monday', how='left')
            
            # Add overall mean columns (constant values for trend lines)
            weekly_stats['Median_All_Tickets'] = overall_mean_all
            weekly_stats['Median_Weekday_Only'] = overall_mean_weekday
            if overall_mean_weekend is not None:
                weekly_stats['Median_Weekend_Only'] = overall_mean_weekend
            
            if len(weekly_stats) == 0:
                return ""
            
            # Sort by Monday date
            weekly_stats = weekly_stats.sort_values('Monday')
            
            # Generate charts for different week ranges
            chart_all = self._generate_weekly_chart_variant(weekly_stats, "all", min_date, max_date)
            chart_8 = self._generate_weekly_chart_variant(weekly_stats.tail(8), "8", min_date, max_date)
            chart_12 = self._generate_weekly_chart_variant(weekly_stats.tail(12), "12", min_date, max_date)
            
            # Create enhanced toggleable chart container with bar type controls
            weekend_available = 'Mean_Weekend_Only' in weekly_stats.columns
            weekend_controls = f'''
                <label class="bar-control">
                    <input type="checkbox" class="bar-toggle" data-bar-type="weekend" checked> Weekend Average
                </label>
                <label class="bar-control">
                    <input type="checkbox" class="bar-toggle" data-bar-type="mean-weekend" checked> Mean Weekend
                </label>
            ''' if weekend_available else ''
            
            return f"""
            <div class="section">
                <div style="display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 15px; flex-wrap: wrap;">
                    <div>
                        <h3>📈 Weekly Response Time Trends</h3>
                        <div class="week-toggle-controls" style="margin-top: 8px;">
                            <label style="color: #e0e0e0; margin-right: 15px; font-size: 0.9em;">Time Range:</label>
                            <button class="week-toggle-btn active" onclick="showWeeklyChart('all')" data-weeks="all">All Weeks ({len(weekly_stats)})</button>
                            <button class="week-toggle-btn" onclick="showWeeklyChart('12')" data-weeks="12">Last 12 Weeks</button>
                            <button class="week-toggle-btn" onclick="showWeeklyChart('8')" data-weeks="8">Last 8 Weeks</button>
                        </div>
                    </div>
                    
                    <div class="bar-type-controls">
                        <div style="color: #e0e0e0; margin-bottom: 8px; font-size: 0.9em; font-weight: bold;">📊 Show/Hide Bar Types:</div>
                        <div class="bar-controls-grid">
                            <label class="bar-control">
                                <input type="checkbox" class="bar-toggle" data-bar-type="all" checked> All Tickets
                            </label>
                            <label class="bar-control">
                                <input type="checkbox" class="bar-toggle" data-bar-type="weekday" checked> Weekday Average
                            </label>
                            {weekend_controls}
                            <label class="bar-control">
                                <input type="checkbox" class="bar-toggle" data-bar-type="trend-all" checked> Overall Trend Line
                            </label>
                            <label class="bar-control">
                                <input type="checkbox" class="bar-toggle" data-bar-type="trend-weekday" checked> Weekday Trend Line
                            </label>
                        </div>
                        <div style="margin-top: 10px;">
                            <button id="chart-update-btn" style="
                                background: linear-gradient(135deg, #00d4aa 0%, #36d1dc 100%);
                                color: white;
                                border: none;
                                padding: 8px 16px;
                                border-radius: 6px;
                                cursor: pointer;
                                font-size: 0.85em;
                                font-weight: bold;
                                box-shadow: 0 2px 4px rgba(0,0,0,0.3);
                                transition: all 0.2s ease;
                            " onmouseover="this.style.transform='translateY(-1px)'; this.style.boxShadow='0 4px 8px rgba(0,0,0,0.4)'" 
                               onmouseout="this.style.transform='translateY(0px)'; this.style.boxShadow='0 2px 4px rgba(0,0,0,0.3)'">
                                🔄 Update Chart
                            </button>
                        </div>
                    </div>
                </div>
                
                <div id="weekly-chart-all" class="weekly-chart-container" style="display: block;">
                    {chart_all}
                </div>
                <div id="weekly-chart-12" class="weekly-chart-container" style="display: none;">
                    {chart_12}
                </div>
                <div id="weekly-chart-8" class="weekly-chart-container" style="display: none;">
                    {chart_8}
                </div>
            </div>
            
            <style>
            .week-toggle-controls {{
                display: flex;
                gap: 8px;
                align-items: center;
            }}
            .week-toggle-btn {{
                background: linear-gradient(135deg, #667eea, #764ba2);
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 6px;
                font-size: 0.85em;
                cursor: pointer;
                transition: all 0.2s ease;
                opacity: 0.7;
                font-weight: 500;
                box-shadow: 0 2px 4px rgba(0,0,0,0.2);
            }}
            .week-toggle-btn:hover {{
                opacity: 1;
                transform: translateY(-1px);
                box-shadow: 0 4px 8px rgba(0,0,0,0.3);
            }}
            .week-toggle-btn.active {{
                opacity: 1;
                background: linear-gradient(135deg, #00d4aa, #36d1dc);
                box-shadow: 0 3px 6px rgba(0,212,170,0.4);
                font-weight: bold;
                transform: translateY(-1px);
            }}
            .weekly-chart-container {{
                margin: 15px 0;
                background: rgba(23, 23, 35, 0.6);
                border-radius: 10px;
                padding: 15px;
                border: 1px solid rgba(102, 126, 234, 0.2);
                box-shadow: 0 4px 8px rgba(0,0,0,0.3);
            }}
            .bar-type-controls {{
                background: rgba(45, 52, 54, 0.8);
                padding: 15px;
                border-radius: 10px;
                border: 1px solid rgba(255,255,255,0.15);
                min-width: 300px;
                box-shadow: 0 2px 6px rgba(0,0,0,0.2);
            }}
            .bar-controls-grid {{
                display: grid;
                grid-template-columns: 1fr 1fr;
                gap: 10px;
                font-size: 0.85em;
            }}
            .bar-control {{
                display: flex;
                align-items: center;
                gap: 8px;
                color: #e0e0e0;
                cursor: pointer;
                padding: 6px 8px;
                border-radius: 6px;
                transition: all 0.2s ease;
                font-weight: 500;
            }}
            .bar-control:hover {{
                background-color: rgba(255,255,255,0.15);
                transform: translateX(2px);
            }}
            .bar-toggle {{
                accent-color: #00d4aa;
                width: 16px;
                height: 16px;
                cursor: pointer;
            }}
            </style>
            
            <script>
            function showWeeklyChart(weeks) {{
                // Hide all charts
                document.querySelectorAll('.weekly-chart-container').forEach(container => {{
                    container.style.display = 'none';
                }});
                
                // Show selected chart
                document.getElementById('weekly-chart-' + weeks).style.display = 'block';
                
                // Update button states
                document.querySelectorAll('.week-toggle-btn').forEach(btn => {{
                    btn.classList.remove('active');
                }});
                document.querySelector('.week-toggle-btn[data-weeks="' + weeks + '"]').classList.add('active');
                
                // Apply current bar visibility settings
                applyBarVisibility();
            }}
            
            function applyBarVisibility() {{
                const checkboxes = document.querySelectorAll('.bar-toggle');
                checkboxes.forEach(checkbox => {{
                    const barType = checkbox.dataset.barType;
                    const isVisible = checkbox.checked;
                    
                    // Apply to all visible charts
                    document.querySelectorAll('.weekly-chart-container').forEach(container => {{
                        if (container.style.display !== 'none') {{
                            // Find and toggle bars/lines based on type
                            const chartElements = container.querySelectorAll(`[data-bar-type="${{barType}}"]`);
                            chartElements.forEach(element => {{
                                element.style.display = isVisible ? 'block' : 'none';
                            }});
                        }}
                    }});
                }});
            }}
            
            // Update chart immediately when toggles change
            function updateChartDisplay() {{
                applyBarVisibility();
            }}
            
            // Add event listeners for bar toggles
            document.addEventListener('DOMContentLoaded', function() {{
                document.querySelectorAll('.bar-toggle').forEach(checkbox => {{
                    checkbox.addEventListener('change', updateChartDisplay);
                }});
                
                // Add update button functionality if present
                const updateBtn = document.getElementById('chart-update-btn');
                if (updateBtn) {{
                    updateBtn.addEventListener('click', updateChartDisplay);
                }}
            }});
            </script>
            """
            
        except Exception as e:
            print(f"Error creating weekly response time chart: {e}")
            return ""
    
    def _create_interactive_weekly_chart(self, analysis_df: pd.DataFrame, stat_type: str = 'median', visible: bool = True, container_id: str = None) -> str:
        """Create interactive Plotly weekly chart with specified statistic type.

        Parameters:
        - stat_type: 'median' or 'mean'
        - visible: whether the outer container is initially shown
        - container_id: optional id for the outer container (for UI toggling)
        """
        try:
            import plotly.graph_objects as go
            from datetime import datetime, timedelta
            
            # Use the full dataset to show all weeks of 2025, regardless of analysis period
            df_all = self.df.copy()
            
            # Get actual date range from full data
            min_date = df_all["Create date"].min()
            max_date = df_all["Create date"].max()
            
            if pd.isna(min_date) or pd.isna(max_date):
                return ""
            
            # Get Monday of each week - use naive datetime for consistency
            df_all['Monday'] = df_all["Create date"].dt.normalize().apply(
                lambda x: x - timedelta(days=x.weekday())
            )
            
            # Debug: Check for data issues
            print(f"Debug: Total tickets in analysis_df: {len(df_all)}")
            print(f"Debug: Date range: {min_date} to {max_date}")
            print(f"Debug: Unique Mondays: {df_all['Monday'].nunique()}")
            
            # Determine chart title and y-axis label based on stat_type
            stat_label = stat_type.title()
            
            # Calculate comprehensive weekly stats for ALL ticket types (using specified stat_type)
            weekly_stats_all = df_all.groupby('Monday').agg({
                'First Response Time (Hours)': [stat_type, 'count']
            }).reset_index()
            weekly_stats_all.columns = ['Monday', 'All_Tickets', 'All_Count']
            
            # Calculate weekly stats for WEEKDAY ONLY tickets (using specified stat_type)
            df_weekday = df_all[df_all["Weekend_Ticket"] == False].copy()
            print(f"Debug: Weekday tickets: {len(df_weekday)}")
            if len(df_weekday) > 0:
                weekly_stats_weekday = df_weekday.groupby('Monday').agg({
                    'First Response Time (Hours)': [stat_type, 'count']
                }).reset_index()
                weekly_stats_weekday.columns = ['Monday', 'Weekday_Only', 'Weekday_Count']
            else:
                weekly_stats_weekday = pd.DataFrame(columns=['Monday', 'Weekday_Only', 'Weekday_Count'])
            
            # Calculate weekly stats for WEEKEND ONLY tickets (using specified stat_type)
            df_weekend = df_all[df_all["Weekend_Ticket"] == True].copy()
            print(f"Debug: Weekend tickets: {len(df_weekend)}")
            if len(df_weekend) > 0:
                print(f"Debug: Weekend response times: {df_weekend['First Response Time (Hours)'].describe()}")
                weekly_stats_weekend = df_weekend.groupby('Monday').agg({
                    'First Response Time (Hours)': [stat_type, 'count']
                }).reset_index()
                weekly_stats_weekend.columns = ['Monday', 'Weekend_Only', 'Weekend_Count']
            else:
                weekly_stats_weekend = pd.DataFrame(columns=['Monday', 'Weekend_Only', 'Weekend_Count'])
            
            # Merge all data
            weekly_stats = weekly_stats_all.merge(weekly_stats_weekday, on='Monday', how='left')
            if len(df_weekend) > 0:
                weekly_stats = weekly_stats.merge(weekly_stats_weekend, on='Monday', how='left')
            
            # Calculate overall statistics for trend lines (using specified stat_type)
            stat_func = getattr(df_all['First Response Time (Hours)'], stat_type)
            overall_stat_all = stat_func()
            overall_stat_weekday = getattr(df_weekday['First Response Time (Hours)'], stat_type)()
            overall_stat_weekend = getattr(df_weekend['First Response Time (Hours)'], stat_type)() if len(df_weekend) > 0 else None
            
            # Create Plotly figure
            fig = go.Figure()
            
            # Format dates for display
            weekly_stats['Week_Label'] = weekly_stats['Monday'].dt.strftime('%b %d')
            
            # Add bars with proper IDs for toggle functionality
            fig.add_trace(go.Bar(
                x=weekly_stats['Week_Label'],
                y=weekly_stats['All_Tickets'],
                name=f'All Tickets {stat_label}',
                marker_color='rgba(78, 205, 196, 0.8)',
                visible=True,
                customdata=['all'] * len(weekly_stats),
                legendgroup='all',
                uid='bar-all'
            ))
            
            fig.add_trace(go.Bar(
                x=weekly_stats['Week_Label'],
                y=weekly_stats['Weekday_Only'],
                name=f'Weekday {stat_label}',
                marker_color='rgba(255, 107, 107, 0.8)',
                visible=True,
                customdata=['weekday'] * len(weekly_stats),
                legendgroup='weekday',
                uid='bar-weekday'
            ))
            
            if 'Weekend_Only' in weekly_stats.columns:
                fig.add_trace(go.Bar(
                    x=weekly_stats['Week_Label'],
                    y=weekly_stats['Weekend_Only'],
                    name=f'Weekend {stat_label}',
                    marker_color='rgba(255, 234, 167, 0.8)',
                    # Default hidden per requirements; user can enable via toggle
                    visible=False,
                    customdata=['weekend'] * len(weekly_stats),
                    legendgroup='weekend',
                    uid='bar-weekend'
                ))
            
            # Add trend lines using linear regression
            import numpy as np
            x_values = np.arange(len(weekly_stats))
            
            # Calculate trend for all tickets
            if len(weekly_stats) > 1:
                slope_all, intercept_all = np.polyfit(x_values, weekly_stats['All_Tickets'].values, 1)
                trend_y_all = slope_all * x_values + intercept_all
            else:
                trend_y_all = [overall_stat_all] * len(weekly_stats)
            
            fig.add_trace(go.Scatter(
                x=weekly_stats['Week_Label'],
                y=trend_y_all,
                mode='lines',
                name='Trend Line (All)',
                line=dict(color='rgba(102, 126, 234, 1)', width=2, dash='dash'),
                visible=True,
                customdata=['trend-all'] * len(weekly_stats),
                legendgroup='trend-all',
                uid='line-trend-all'
            ))
            
            # Calculate trend for weekday tickets
            if len(weekly_stats) > 1:
                slope_weekday, intercept_weekday = np.polyfit(x_values, weekly_stats['Weekday_Only'].values, 1)
                trend_y_weekday = slope_weekday * x_values + intercept_weekday
            else:
                trend_y_weekday = [overall_stat_weekday] * len(weekly_stats)
            
            fig.add_trace(go.Scatter(
                x=weekly_stats['Week_Label'],
                y=trend_y_weekday,
                mode='lines',
                name='Trend Line (Weekday)',
                line=dict(color='rgba(255, 107, 107, 1)', width=2, dash='dot'),
                visible=True,
                customdata=['trend-weekday'] * len(weekly_stats),
                legendgroup='trend-weekday',
                uid='line-trend-weekday'
            ))
            
            # Calculate trend for weekend tickets
            if overall_stat_weekend is not None and len(weekly_stats) > 1:
                slope_weekend, intercept_weekend = np.polyfit(x_values, weekly_stats['Weekend_Only'].values, 1)
                trend_y_weekend = slope_weekend * x_values + intercept_weekend
                
                fig.add_trace(go.Scatter(
                    x=weekly_stats['Week_Label'],
                    y=trend_y_weekend,
                    mode='lines',
                    name='Trend Line (Weekend)',
                    line=dict(color='rgba(255, 234, 167, 1)', width=2, dash='dashdot'),
                    # Default hidden per requirements; user can enable via toggle
                    visible=False,
                    customdata=['trend-weekend'] * len(weekly_stats),
                    legendgroup='trend-weekend',
                    uid='line-trend-weekend'
                ))
            
            # Unified title per requirements (no '- Mean/Median Values' suffix)
            chart_title = '📈 Weekly Response Time Trends'
            y_axis_title = f'{stat_label} Response Time (Hours)'
            
            # Update layout with better contrast
            fig.update_layout(
                title=chart_title,
                xaxis_title='Week Starting',
                yaxis_title=y_axis_title,
                barmode='group',
                template='plotly_dark',
                plot_bgcolor='rgba(30, 30, 46, 0.8)',  # Darker background with contrast
                paper_bgcolor='rgba(23, 23, 35, 0.9)',  # Even darker paper background
                font=dict(color='#e0e0e0'),
                height=400,
                margin=dict(l=50, r=50, t=50, b=50),
                # Add grid lines for better readability
                xaxis=dict(
                    gridcolor='rgba(102, 126, 234, 0.2)',
                    showgrid=True
                ),
                yaxis=dict(
                    gridcolor='rgba(102, 126, 234, 0.2)',
                    showgrid=True
                )
            )
            
            # Generate different timespan variants
            charts_html = []
            
            # All weeks chart
            chart_all_html = fig.to_html(include_plotlyjs="cdn", div_id=f"plotly-div-{stat_type}-all")
            charts_html.append(('all', chart_all_html))
            
            # 12 weeks chart
            if len(weekly_stats) > 12:
                fig_12 = go.Figure(fig)
                # Slice x/y to last 12 points; preserve per-trace visibility
                for tr in fig_12.data:
                    try:
                        if hasattr(tr, "x"):
                            tr.x = list(weekly_stats['Week_Label'][-12:])
                        if hasattr(tr, "y") and tr.y is not None and len(tr.y) == len(weekly_stats):
                            tr.y = tr.y[-12:]
                    except Exception:
                        pass
                chart_12_html = fig_12.to_html(include_plotlyjs="cdn", div_id=f"plotly-div-{stat_type}-12")
                charts_html.append(('12', chart_12_html))
            
            # 8 weeks chart
            if len(weekly_stats) > 8:
                fig_8 = go.Figure(fig)
                # Slice x/y to last 8 points; preserve per-trace visibility
                for tr in fig_8.data:
                    try:
                        if hasattr(tr, "x"):
                            tr.x = list(weekly_stats['Week_Label'][-8:])
                        if hasattr(tr, "y") and tr.y is not None and len(tr.y) == len(weekly_stats):
                            tr.y = tr.y[-8:]
                    except Exception:
                        pass
                chart_8_html = fig_8.to_html(include_plotlyjs="cdn", div_id=f"plotly-div-{stat_type}-8")
                charts_html.append(('8', chart_8_html))
            
            # Create enhanced toggleable chart container with proper JavaScript
            weekend_available = 'Weekend_Only' in weekly_stats.columns
            weekend_controls = f'''
                <label class="bar-control">
                    <input type="checkbox" class="bar-toggle-{stat_type}" data-bar-type="weekend"> Weekend {stat_label}
                </label>
                <label class="bar-control">
                    <input type="checkbox" class="bar-toggle-{stat_type}" data-bar-type="trend-weekend"> Weekend Trend Line
                </label>
            ''' if weekend_available else ''
            
            chart_containers = '\n'.join([
                f'<div id="weekly-chart-{stat_type}-{variant}" class="weekly-chart-{stat_type}-container" style="display: {"block" if variant == "all" else "none"};">{html}</div>'
                for variant, html in charts_html
            ])
            
            # Enhanced JavaScript with proper Plotly integration
            javascript = f"""
            <script>
            function showWeeklyChart_{stat_type}(weeks) {{
                // Hide all charts for this stat type
                document.querySelectorAll('.weekly-chart-{stat_type}-container').forEach(container => {{
                    container.style.display = 'none';
                }});
                
                // Show selected chart
                const targetChart = document.getElementById('weekly-chart-{stat_type}-' + weeks);
                if (targetChart) {{
                    targetChart.style.display = 'block';
                }}
                
                // Update button states
                document.querySelectorAll('.week-toggle-btn-{stat_type}').forEach(btn => {{
                    btn.classList.remove('active');
                }});
                const activeBtn = document.querySelector('.week-toggle-btn-{stat_type}[data-weeks="' + weeks + '"]');
                if (activeBtn) {{
                    activeBtn.classList.add('active');
                }}
                
                // Apply current bar visibility settings
                applyBarVisibility_{stat_type}();
            }}

            // Explicit defaults: weekend series off by default; others on
            const WEEKLY_DEFAULTS_{stat_type} = {{ all: true, weekday: true, 'trend-all': true, 'trend-weekday': true, weekend: false, 'trend-weekend': false }};

            function initControls_{stat_type}() {{
                // Force initial checkbox states to defaults (prevents any accidental auto-checking)
                const defaults = WEEKLY_DEFAULTS_{stat_type};
                document.querySelectorAll('.bar-toggle-{stat_type}').forEach(cb => {{
                    const t = cb.dataset.barType;
                    if (Object.prototype.hasOwnProperty.call(defaults, t)) {{
                        cb.checked = defaults[t];
                    }}
                }});
            }}
            
            function applyBarVisibility_{stat_type}() {{
                const defaults = WEEKLY_DEFAULTS_{stat_type};
                // Start from defaults, then override with live checkbox states
                const visibilityMap = Object.assign({{}}, defaults);

                // Build visibility map from checkboxes
                document.querySelectorAll('.bar-toggle-{stat_type}').forEach(checkbox => {{
                    const barType = checkbox.dataset.barType;
                    visibilityMap[barType] = checkbox.checked;
                }});
                
                // Apply to all visible Plotly charts for this stat type
                document.querySelectorAll('.weekly-chart-{stat_type}-container').forEach(container => {{
                    if (container.style.display !== 'none') {{
                        const plotlyDiv = container.querySelector('[id^="plotly-div-{stat_type}-"]');
                        if (plotlyDiv && window.Plotly && plotlyDiv._fullData) {{
                            const updates = {{ visible: [] }};
                            
                            // Get the current trace data from Plotly's internal data
                            plotlyDiv._fullData.forEach((trace) => {{
                                if (trace.customdata && trace.customdata.length > 0) {{
                                    const traceType = trace.customdata[0];
                                    const shouldBeVisible = Object.prototype.hasOwnProperty.call(visibilityMap, traceType) ? visibilityMap[traceType] : true;
                                    updates.visible.push(shouldBeVisible);
                                }} else {{
                                    updates.visible.push(true); // Default to visible for traces without customdata
                                }}
                            }});
                            
                            // Apply the visibility updates
                            window.Plotly.restyle(plotlyDiv, updates);
                        }}
                    }}
                }});
            }}
            
            // Update chart immediately when toggles change for this stat type
            function updateChartDisplay_{stat_type}() {{
                applyBarVisibility_{stat_type}();
            }}
            
            // Add event listeners for bar toggles for this stat type
            document.addEventListener('DOMContentLoaded', function() {{
                // Ensure default-off logic for weekend before first render pass
                initControls_{stat_type}();

                document.querySelectorAll('.bar-toggle-{stat_type}').forEach(checkbox => {{
                    checkbox.addEventListener('change', updateChartDisplay_{stat_type});
                }});
                
                // Apply once after initializing defaults
                setTimeout(updateChartDisplay_{stat_type}, 300);
            }});
            </script>
            """
            
            # Generate unique IDs for this chart instance
            chart_id = f"weekly-{stat_type}"

            buttons = [
                f"<button class=\"week-toggle-btn-{stat_type} active\" data-weeks=\"all\" onclick=\"showWeeklyChart_{stat_type}('all')\">All Weeks</button>"
            ]
            if len(weekly_stats) > 12:
                buttons.append(
                    f"<button class=\"week-toggle-btn-{stat_type}\" data-weeks=\"12\" onclick=\"showWeeklyChart_{stat_type}('12')\">Last 12 Weeks</button>"
                )
            if len(weekly_stats) > 8:
                buttons.append(
                    f"<button class=\"week-toggle-btn-{stat_type}\" data-weeks=\"8\" onclick=\"showWeeklyChart_{stat_type}('8')\">Last 8 Weeks</button>"
                )

            buttons_html = ''.join(buttons)

            return f"""
        <div class="subsection" id="{container_id or f'weekly-{stat_type}'}" style="margin-bottom: 30px; display: {'block' if visible else 'none'};">
            <div style="display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 15px; flex-wrap: wrap;">
                <div>
                    <h4 style="color: #00d4aa; margin: 0;">{chart_title}</h4>
                    <div class="week-toggle-controls" style="margin-top: 8px;">
                        <label style="color: #e0e0e0; margin-right: 15px; font-size: 0.9em;">Time Range:</label>
                        {buttons_html}
                    </div>
                </div>

                <div class="bar-type-controls">
                    <div style="color: #e0e0e0; margin-bottom: 8px; font-size: 0.9em; font-weight: bold;">📊 Show/Hide Bar Types:</div>
                    <div class="bar-controls-grid">
                        <label class="bar-control">
                            <input type="checkbox" class="bar-toggle-{stat_type}" data-bar-type="all" checked> All Tickets
                        </label>
                        <label class="bar-control">
                            <input type="checkbox" class="bar-toggle-{stat_type}" data-bar-type="weekday" checked> Weekday {stat_label}
                        </label>
                        {weekend_controls}
                        <label class="bar-control">
                            <input type="checkbox" class="bar-toggle-{stat_type}" data-bar-type="trend-all" checked> Overall Trend Line
                        </label>
                        <label class="bar-control">
                            <input type="checkbox" class="bar-toggle-{stat_type}" data-bar-type="trend-weekday" checked> Weekday Trend Line
                        </label>
                    </div>
                </div>
            </div>

            {chart_containers}

            {javascript}
        </div>
        """
            
        except Exception as e:
            print(f"Error creating interactive weekly response time chart: {e}")
            return ""
    
    def _create_interactive_agent_charts(self, weekday_df: pd.DataFrame) -> List[str]:
        """Create interactive Plotly agent performance charts"""
        try:
            import plotly.graph_objects as go
            from plotly.subplots import make_subplots
            import numpy as np
            
            # Find ticket ID column
            ticket_id_col = None
            for col in ["Ticket number", "Ticket ID", "ID"]:
                if col in weekday_df.columns:
                    ticket_id_col = col
                    break
            
            if not ticket_id_col:
                return []
            
            # Find owner column
            owner_col = None
            for col in ["Case Owner", "Ticket owner", "Owner", "Assigned Agent"]:
                if col in weekday_df.columns:
                    owner_col = col
                    break
            
            if not owner_col:
                return []
            
            # Filter out LiveChat tickets for response time calculations
            non_livechat_df = weekday_df[weekday_df["Pipeline"] != "Live Chat "].copy()
            
            # Calculate agent statistics (volume from all tickets, response times excluding LiveChat)
            agent_stats = weekday_df.groupby(owner_col).agg({
                ticket_id_col: "count",
                "Pipeline": lambda x: x.value_counts().to_dict()
            })
            
            # Calculate response time stats excluding LiveChat tickets
            if len(non_livechat_df) > 0:
                # Convert pd.NA to np.nan for aggregation compatibility
                non_livechat_df = non_livechat_df.copy()
                non_livechat_df["First Response Time (Hours)"] = non_livechat_df["First Response Time (Hours)"].replace({pd.NA: np.nan})

                response_stats = non_livechat_df.groupby(owner_col)["First Response Time (Hours)"].agg(["mean", "median"])
                response_stats.columns = ["Avg_Response_Time", "Median_Response_Time"]
                agent_stats = agent_stats.join(response_stats, how='left')
            else:
                agent_stats["Avg_Response_Time"] = float('nan')
                agent_stats["Median_Response_Time"] = float('nan')
            
            # Flatten columns - now they should already be flat
            if isinstance(agent_stats.columns, pd.MultiIndex):
                agent_stats.columns = agent_stats.columns.droplevel(1)
            agent_stats.columns = ["Tickets_Handled", "Pipeline_Breakdown", "Avg_Response_Time", "Median_Response_Time"]
            agent_stats["Tickets_Handled"] = agent_stats["Tickets_Handled"].astype(int)
            agent_stats["Avg_Response_Time"] = agent_stats["Avg_Response_Time"].round(2)
            agent_stats["Median_Response_Time"] = agent_stats["Median_Response_Time"].round(2)
            
            # Add percentage calculation
            total_tickets = len(weekday_df)
            agent_stats["Percentage"] = (agent_stats["Tickets_Handled"] / total_tickets * 100).round(1)
            agent_stats = agent_stats.sort_values("Tickets_Handled", ascending=False)
            
            if len(agent_stats) == 0:
                return []
            
            charts = []
            
            # Chart 1: Volume Distribution Bar Chart & Pie Chart
            fig1 = make_subplots(
                rows=1, cols=2,
                column_widths=[0.6, 0.4],
                subplot_titles=('📊 Ticket Volume by Agent', '🍰 Volume Distribution'),
                specs=[[{"type": "bar"}, {"type": "pie"}]]
            )
            
            # Bar chart
            fig1.add_trace(
                go.Bar(
                    x=agent_stats.index,
                    y=agent_stats["Tickets_Handled"],
                    name="Tickets Handled",
                    marker_color=['rgba(78, 205, 196, 0.8)', 'rgba(255, 107, 107, 0.8)', 
                                 'rgba(255, 234, 167, 0.8)', 'rgba(162, 155, 254, 0.8)'][:len(agent_stats)],
                    text=[f"{row['Tickets_Handled']}<br>({row['Percentage']}%)" 
                          for _, row in agent_stats.iterrows()],
                    textposition='auto',
                    hovertemplate='<b>%{x}</b><br>Tickets: %{y}<br>Percentage: %{customdata}%<extra></extra>',
                    customdata=agent_stats["Percentage"]
                ),
                row=1, col=1
            )
            
            # Pie chart
            fig1.add_trace(
                go.Pie(
                    labels=agent_stats.index,
                    values=agent_stats["Tickets_Handled"],
                    name="Distribution",
                    marker_colors=['rgba(78, 205, 196, 0.8)', 'rgba(255, 107, 107, 0.8)', 
                                  'rgba(255, 234, 167, 0.8)', 'rgba(162, 155, 254, 0.8)'][:len(agent_stats)],
                    textinfo='label+percent',
                    textposition='auto'
                ),
                row=1, col=2
            )
            
            fig1.update_layout(
                title_text="📊 Agent Performance: Volume Analysis",
                template='plotly_dark',
                plot_bgcolor='rgba(30, 30, 46, 0.8)',
                paper_bgcolor='rgba(23, 23, 35, 0.9)',
                font=dict(color='#e0e0e0'),
                height=400,
                showlegend=False
            )
            
            fig1.update_xaxes(title_text="Agent", row=1, col=1)
            fig1.update_yaxes(title_text="Number of Tickets", row=1, col=1)
            
            chart1_html = f'''
            <div class="weekly-chart-container">
                {fig1.to_html(include_plotlyjs="cdn")}
            </div>
            '''
            charts.append(chart1_html)
            
            # Chart 2: Response Time Comparison (Average vs Median)
            fig2 = go.Figure()

            x_agents = agent_stats.index
            x_pos = np.arange(len(x_agents))

            # Fill NA values with None for Plotly (will show gaps instead of 0)
            avg_times = agent_stats["Avg_Response_Time"].replace({pd.NA: None})
            median_times = agent_stats["Median_Response_Time"].replace({pd.NA: None})

            fig2.add_trace(go.Bar(
                x=x_agents,
                y=avg_times,
                name='Average Response Time',
                marker_color='rgba(102, 126, 234, 0.8)',
                offsetgroup=1
            ))

            fig2.add_trace(go.Bar(
                x=x_agents,
                y=median_times,
                name='Median Response Time',
                marker_color='rgba(255, 107, 107, 0.8)',
                offsetgroup=2
            ))
            
            fig2.update_layout(
                title='⏱️ Response Time Comparison: Average vs Median',
                xaxis_title='Agent',
                yaxis_title='Response Time (Hours)',
                template='plotly_dark',
                plot_bgcolor='rgba(30, 30, 46, 0.8)',
                paper_bgcolor='rgba(23, 23, 35, 0.9)',
                font=dict(color='#e0e0e0'),
                height=400,
                barmode='group',
                xaxis=dict(gridcolor='rgba(102, 126, 234, 0.2)', showgrid=True),
                yaxis=dict(gridcolor='rgba(102, 126, 234, 0.2)', showgrid=True),
                annotations=[
                    dict(
                        text="💡 <b>Average vs Median:</b> When median is much lower than average, the agent has consistent fast responses but occasional long delays",
                        xref="paper", yref="paper",
                        x=0.5, y=1.15, xanchor='center', yanchor='bottom',
                        showarrow=False,
                        font=dict(size=11, color='#00d4aa'),
                        bgcolor='rgba(0, 212, 170, 0.1)',
                        bordercolor='rgba(0, 212, 170, 0.3)',
                        borderwidth=1
                    )
                ]
            )
            
            chart2_html = f'''
            <div class="weekly-chart-container">
                {fig2.to_html(include_plotlyjs="cdn")}
                <div style="margin-top: 10px; padding: 10px; background: rgba(0, 212, 170, 0.05); border-radius: 6px; border-left: 4px solid #00d4aa;">
                    <div style="color: #00d4aa; font-weight: bold; font-size: 0.9em; margin-bottom: 5px;">📖 Understanding Average vs Median:</div>
                    <div style="color: #e0e0e0; font-size: 0.85em; line-height: 1.4;">
                        • <b>Similar values</b> = Consistent performance<br>
                        • <b>Average >> Median</b> = Usually fast, but some very slow responses<br>
                        • <b>Median >> Average</b> = Usually slow, but some very fast responses (rare)
                    </div>
                </div>
            </div>
            '''
            charts.append(chart2_html)
            
            return charts
            
        except Exception as e:
            print(f"Error creating interactive agent charts: {e}")
            return []
    
    def _generate_weekly_chart_variant(self, weekly_stats, variant_type, min_date, max_date):
        """Generate a specific variant of the weekly chart (all, 8 weeks, 12 weeks)"""
        try:
            from datetime import datetime, timedelta
            import numpy as np
            from scipy import stats
            
            if len(weekly_stats) == 0:
                return "<p>No data available for this time range.</p>"
            
            # Create the chart with wider figure for dual bars
            fig, ax = plt.subplots(figsize=(16, 8))
            
            # Prepare data for multiple bar types
            weeks = weekly_stats['Monday']
            x_pos = np.arange(len(weeks))
            
            # Define bar types and their properties
            bar_types = [
                ('all', 'All Tickets', weekly_stats['All_Tickets'], '#6366f1', 0.8),
                ('weekday', 'Weekday Average', weekly_stats['Weekday_Only'], '#10b981', 0.8),
            ]
            
            # Add weekend bars if available
            if 'Weekend_Only' in weekly_stats.columns:
                bar_types.append(('weekend', 'Weekend Average', weekly_stats['Weekend_Only'], '#ec4899', 0.8))
            
            # Calculate bar positioning
            num_bar_types = len(bar_types)
            bar_width = 0.7 / num_bar_types  # Adjust width based on number of bar types
            bar_positions = [x_pos + (i - (num_bar_types-1)/2) * bar_width for i in range(num_bar_types)]
            
            # Create bars for each type
            bar_objects = []
            for i, (bar_type, label, data, color, alpha) in enumerate(bar_types):
                bars = ax.bar(bar_positions[i], data, bar_width, 
                             label=label, color=color, alpha=alpha)
                
                # Add data attributes for JavaScript control
                for bar in bars:
                    bar.set_gid(f'bar-{bar_type}')
                
                bar_objects.append((bar_type, bars, data))
                
                # Highlight most recent week
                if len(bars) > 0:
                    bars[-1].set_edgecolor('#000')
                    bars[-1].set_linewidth(2)
            
            # Add mean lines (horizontal lines across the chart)
            mean_lines = []
            if 'Mean_All_Tickets' in weekly_stats.columns:
                mean_all = weekly_stats['Mean_All_Tickets'].iloc[0]
                line_all = ax.axhline(y=mean_all, color='#6366f1', linestyle=':', linewidth=2, alpha=0.7, label='Mean Overall')
                line_all.set_gid('line-mean-all')
                mean_lines.append(('mean-all', line_all))
            
            if 'Mean_Weekday_Only' in weekly_stats.columns:
                mean_weekday = weekly_stats['Mean_Weekday_Only'].iloc[0]
                line_weekday = ax.axhline(y=mean_weekday, color='#10b981', linestyle=':', linewidth=2, alpha=0.7, label='Mean Weekday')
                line_weekday.set_gid('line-mean-weekday')
                mean_lines.append(('mean-weekday', line_weekday))
            
            if 'Mean_Weekend_Only' in weekly_stats.columns:
                mean_weekend = weekly_stats['Mean_Weekend_Only'].iloc[0]
                line_weekend = ax.axhline(y=mean_weekend, color='#ec4899', linestyle=':', linewidth=2, alpha=0.7, label='Mean Weekend')
                line_weekend.set_gid('line-mean-weekend')
                mean_lines.append(('mean-weekend', line_weekend))
            
            # Styling with variant-specific title
            if variant_type == "all":
                title = f'📈 Weekly Response Time Trends: All Weeks ({len(weeks)} total)'
            else:
                title = f'📈 Weekly Response Time Trends: Last {variant_type} Weeks'
                
            ax.set_title(title, fontsize=16, fontweight='bold', pad=20)
            ax.set_xlabel('Week (Monday)', fontsize=12, fontweight='bold')
            ax.set_ylabel('Median Response Time (Hours)', fontsize=12, fontweight='bold')
            ax.grid(axis='y', alpha=0.3, linestyle='-', linewidth=0.5)
            
            # Format x-axis labels
            week_labels = [w.strftime('%m/%d') for w in weeks]
            ax.set_xticks(x_pos)
            ax.set_xticklabels(week_labels, rotation=45, ha='right')
            
            # Add value labels on bars
            for bar_type, bars, data in bar_objects:
                for i, (bar, value) in enumerate(zip(bars, data)):
                    if pd.notna(value):
                        height = bar.get_height()
                        weight = 'bold' if i == len(bars) - 1 else 'normal'
                        # Use dark color for better visibility - avoid white text
                        color = '#000' if i == len(bars) - 1 else '#333'
                        ax.text(bar.get_x() + bar.get_width()/2., height + 0.05,
                                f'{height:.2f}h', ha='center', va='bottom',
                                fontweight=weight, color=color, fontsize=8)
            
            # Add legend
            ax.legend(loc='upper right', fontsize=11)
            
            # Add subtitle with data info
            weekday_data = weekly_stats['Weekday_Only'] if 'Weekday_Only' in weekly_stats.columns else pd.Series([])
            weekday_count = len(weekday_data.dropna()) if len(weekday_data) > 0 else 0
            
            date_range_str = f"{min_date.strftime('%m/%d/%Y')} - {max_date.strftime('%m/%d/%Y')}"
            subtitle = f"{len(weeks)} weeks • {weekday_count} weeks with weekday data • Data range: {date_range_str}"
            ax.text(0.5, 0.98, subtitle, transform=ax.transAxes, ha='center', va='top',
                   fontsize=10, style='italic', color='#666')
            
            plt.tight_layout()
            return fig_to_html(fig)
            
        except Exception as e:
            print(f"Error creating weekly chart variant {variant_type}: {e}")
            return f"<p>Error generating {variant_type} weeks chart.</p>"
    
    def _create_delayed_table(self, df: pd.DataFrame) -> str:
        """Create delayed response table"""
        ticket_id_col = None
        for col in ["Ticket number", "Ticket ID", "ID"]:
            if col in df.columns:
                ticket_id_col = col
                break
        
        if not ticket_id_col:
            return ""
        
        valid_response_df = df[df["First Response Time (Hours)"].notna() & 
                              (df["First Response Time (Hours)"] > 0)].copy()
        top_delayed = valid_response_df.nlargest(5, "First Response Time (Hours)")
        
        rows = []
        for _, row in top_delayed.iterrows():
            ticket_id = row.get(ticket_id_col, "N/A")
            response_hours = row["First Response Time (Hours)"]
            response_time_display = f"{response_hours:.2f}h"
            agent = row.get("Ticket owner", row.get("Case Owner", "Unknown"))
            create_date = row["Create date"].strftime("%Y-%m-%d %H:%M") if pd.notna(row["Create date"]) else "N/A"
            pipeline = row.get("Pipeline", "N/A")
            
            rows.append(f"""
            <tr>
                <td style="font-weight:bold">{ticket_id}</td>
                <td style="text-align:center;color:#d9534f;font-weight:bold">{response_time_display}</td>
                <td style="text-align:center">{agent}</td>
                <td style="text-align:center">{create_date}</td>
                <td style="text-align:center">{pipeline}</td>
            </tr>
            """)
        
        return f"""
        <div class="section">
            <h2>Top 5 Longest Delayed Response Tickets</h2>
            <table>
                <thead>
                    <tr style="background:#d9534f;color:white;">
                        <th>Ticket ID</th>
                        <th>Response Delay</th>
                        <th>Agent</th>
                        <th>Created Date</th>
                        <th>Pipeline</th>
                    </tr>
                </thead>
                <tbody>
                    {''.join(rows)}
                </tbody>
            </table>
        </div>
        """
    
    def create_summary_text(self, analysis_df: pd.DataFrame, label: str) -> str:
        """Create text summary"""
        weekday_df = analysis_df[analysis_df["Weekend_Ticket"] == False]
        # Find owner column for summary
        owner_col = "Ticket owner" if "Ticket owner" in weekday_df.columns else "Case Owner"
        if owner_col in weekday_df.columns:
            response_stats = weekday_df.groupby(owner_col)["First Response Time (Hours)"].mean().dropna().sort_values()
        else:
            response_stats = pd.Series(dtype=float)
        
        summary = f"""
TICKET ANALYTICS SUMMARY
========================
Period: {label}

PROCESSING SUMMARY:
- Original records: {len(self.original_df):,}
- After SPAM removal: {len(self.df):,}
- Support team only: Bhushan, Girly, Nova, Francis
- Analyzed records: {len(analysis_df):,}
- Weekend tickets: {analysis_df['Weekend_Ticket'].sum():,}

AGENT PERFORMANCE (WEEKDAYS):
"""
        
        for agent, hours in response_stats.items():
            summary += f"- {agent:<12}: {hours:5.2f}h avg response\n"
        
        summary += f"\nFiles processed: {[f.name for f in self.processed_files]}\n"
        
        return summary
