#!/usr/bin/env python3
"""
Unified Dashboard Builder
Creates HTML dashboards for ticket, chat, or combined analytics
"""

from typing import Dict, List, Optional
from common_utils import get_dashboard_css, create_metric_card

class DashboardBuilder:
    """Builds unified HTML dashboards for analytics data"""
    
    def __init__(self):
        self.css = get_dashboard_css()
        
    def _create_data_flow_explanation(self, source_type: str) -> str:
        """Create expandable data flow explanation section"""
        if source_type == "tickets":
            content = """
            <h4 style="color: #00d4aa; margin-top: 0;">🔗 Understanding the Live Chat Pipeline</h4>
            <p style="color: #e0e0e0;"><strong>Why do you see "Live Chat" in your ticket pipeline breakdown?</strong></p>
            <div style="background: rgba(108, 92, 231, 0.2); padding: 15px; border-radius: 8px; margin: 10px 0; border-left: 4px solid #6c5ce7;">
                <p style="color: #e0e0e0;"><strong>The Complete Customer Journey:</strong></p>
                <ol style="margin-left: 20px; color: #e0e0e0;">
                    <li><strong style="color: #00d4aa;">Customer starts chat</strong> on your website widget</li>
                    <li><strong style="color: #00d4aa;">Bot handles simple queries</strong> (typically ~67% resolution rate)</li>
                    <li><strong style="color: #00d4aa;">Complex issues transfer to human agents</strong> (~33% transfer rate)</li>
                    <li><strong style="color: #00d4aa;">Some transfers need ticket tracking</strong> → Create "Live Chat" pipeline tickets</li>
                    <li><strong style="color: #00d4aa;">Remaining transfers resolved in chat</strong> without creating tickets</li>
                </ol>
                <p style="margin-top: 15px; color: #e0e0e0;"><strong style="color: #00d4aa;">Live Chat Pipeline = Follow-up tickets from transferred chat conversations</strong></p>
                <p style="font-style: italic; color: #b0b0b0;">This bridges your chat and ticketing systems for comprehensive support tracking.</p>
            </div>
            """
        elif source_type == "chats":
            content = """
            <h4 style="color: #00d4aa; margin-top: 0;">🎫 How Chat Transfers Become Tickets</h4>
            <p style="color: #e0e0e0;"><strong>What happens when your bot transfers a chat to a human agent?</strong></p>
            <div style="background: rgba(108, 92, 231, 0.2); padding: 15px; border-radius: 8px; margin: 10px 0; border-left: 4px solid #6c5ce7;">
                <p style="color: #e0e0e0;"><strong>Transfer-to-Ticket Flow:</strong></p>
                <ul style="margin-left: 20px; color: #e0e0e0;">
                    <li><strong style="color: #00d4aa;">33% of chats are transferred</strong> from bot to human agents</li>
                    <li><strong style="color: #00d4aa;">~55% of transfers create tickets</strong> in the "Live Chat" pipeline</li>
                    <li><strong style="color: #00d4aa;">Remaining transfers are resolved</strong> directly in the chat interface</li>
                </ul>
                <p style="margin-top: 15px; color: #e0e0e0;"><strong>Why create tickets from chats?</strong></p>
                <ul style="margin-left: 20px; color: #e0e0e0;">
                    <li>Complex issues requiring detailed documentation</li>
                    <li>Multi-step resolutions spanning multiple interactions</li>
                    <li>Escalations beyond what chat can handle</li>
                    <li>Quality tracking and compliance requirements</li>
                </ul>
                <p style="font-style: italic; color: #b0b0b0; margin-top: 15px;">Your chat and ticket systems work together for comprehensive customer support.</p>
            </div>
            """
        else:
            content = """
            <h4 style="color: #00d4aa; margin-top: 0;">🔗 Chat-to-Ticket Data Flow</h4>
            <p style="color: #e0e0e0;"><strong>Understanding how your chat and ticket systems connect:</strong></p>
            <div style="background: rgba(108, 92, 231, 0.2); padding: 15px; border-radius: 8px; margin: 10px 0; border-left: 4px solid #6c5ce7;">
                <p style="color: #e0e0e0;"><strong>Two-Channel Support System:</strong></p>
                <ul style="margin-left: 20px; color: #e0e0e0;">
                    <li><strong style="color: #00d4aa;">Chat System:</strong> Website widget for immediate assistance</li>
                    <li><strong style="color: #00d4aa;">Ticket System:</strong> Email, forms, and escalated chats</li>
                    <li><strong style="color: #00d4aa;">Live Chat Pipeline:</strong> Tickets created from transferred chats</li>
                </ul>
                <p style="font-style: italic; color: #b0b0b0; margin-top: 15px;">This integrated approach provides seamless customer support across multiple touchpoints.</p>
            </div>
            """
            
        return f"""
        <div class="section" style="margin-top: 20px;">
            <div class="data-flow-toggle" onclick="toggleDataFlow()" style="cursor: pointer; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 12px 20px; border-radius: 8px; text-align: center; transition: all 0.3s ease;">
                <strong>💡 Understanding Your Data Flow</strong> <span id="toggle-arrow">▼</span>
            </div>
            <div id="data-flow-content" style="display: none; padding: 20px; background: rgba(23, 23, 35, 0.9); border-radius: 0 0 8px 8px; border: 1px solid #3a3a4a; border-top: none; color: #e0e0e0;">
                {content}
            </div>
        </div>
        
        <script>
        function toggleDataFlow() {{
            const content = document.getElementById('data-flow-content');
            const arrow = document.getElementById('toggle-arrow');
            if (content.style.display === 'none') {{
                content.style.display = 'block';
                arrow.textContent = '▲';
            }} else {{
                content.style.display = 'none';
                arrow.textContent = '▼';
            }}
        }}
        </script>
        """
    
    def build_ticket_dashboard(self, analytics: Dict, label: str, args) -> str:
        """Build ticket-specific dashboard"""
        return self._build_dashboard(
            title=f"Support Ticket Analytics – {label}",
            analytics=analytics,
            source_type="tickets",
            source_badge="ticket-badge"
        )
    
    def build_chat_dashboard(self, analytics: Dict, label: str, args) -> str:
        """Build chat-specific dashboard"""
        # Generate chat-specific visualizations
        chat_analytics = self._process_chat_analytics(analytics)
        
        return self._build_dashboard(
            title=f"Chat Analytics – {label}",
            analytics=chat_analytics,
            source_type="chats",
            source_badge="chat-badge"
        )
    
    def build_combined_dashboard(self, ticket_analytics: Dict, chat_analytics: Dict, label: str, args) -> str:
        """Build combined dashboard with both data sources"""
        # Combine metrics from both sources
        combined_metrics = []
        
        # Add ticket metrics with different styling
        if ticket_analytics.get('metrics'):
            combined_metrics.append('<div class="section"><h3>📋 Ticket Metrics</h3><div class="metric-grid">')
            combined_metrics.extend(ticket_analytics['metrics'])
            combined_metrics.append('</div></div>')
        
        # Add chat metrics with different styling  
        if chat_analytics.get('metrics'):
            combined_metrics.append('<div class="section"><h3>💬 Chat Metrics</h3><div class="metric-grid">')
            combined_metrics.extend(chat_analytics['metrics'])
            combined_metrics.append('</div></div>')
        
        # Combine charts
        combined_charts = []
        if ticket_analytics.get('charts'):
            combined_charts.append('<div class="section"><h2>📋 Ticket Analytics</h2>')
            combined_charts.extend(ticket_analytics['charts'])
            combined_charts.append('</div>')
        
        if chat_analytics.get('charts'):
            combined_charts.append('<div class="section"><h2>💬 Chat Analytics</h2>')
            combined_charts.extend(chat_analytics['charts'])
            combined_charts.append('</div>')
        
        # Combine tables
        combined_tables = []
        if ticket_analytics.get('tables'):
            combined_tables.extend(ticket_analytics['tables'])
        if chat_analytics.get('tables'):
            combined_tables.extend(chat_analytics['tables'])
        
        # Create cross-analysis section
        cross_analysis = self._create_cross_analysis(ticket_analytics, chat_analytics)
        
        combined_analytics = {
            'metrics': combined_metrics,
            'charts': combined_charts,
            'tables': combined_tables + [cross_analysis],
            'summary': {
                'tickets': ticket_analytics.get('summary', {}),
                'chats': chat_analytics.get('summary', {})
            }
        }
        
        return self._build_dashboard(
            title=f"Unified Analytics Dashboard – {label}",
            analytics=combined_analytics,
            source_type="combined",
            source_badge="combined-badge"
        )
    
    def _build_dashboard(self, title: str, analytics: Dict, source_type: str, source_badge: str) -> str:
        """Build HTML dashboard from analytics data optimized for 1920x1024"""
        # Create source badge
        source_badges = {
            'tickets': '📋 Tickets',
            'chats': '💬 Chats', 
            'combined': '📊 Combined'
        }
        
        badge_html = f'<span class="data-source-badge {source_badge}">{source_badges.get(source_type, source_type.title())}</span>'
        
        # Build compact layout for chat analytics
        if source_type == "chats":
            return self._build_compact_chat_dashboard(title, analytics, badge_html)
        
        # Build content sections for other types
        content_sections = []
        
        # Summary metrics section
        if analytics.get('metrics'):
            if source_type == "combined":
                # Metrics are already wrapped in sections for combined view
                content_sections.extend(analytics['metrics'])
            else:
                content_sections.append(f"""
                <div class="section">
                    <h2>Summary Metrics</h2>
                    <div class="metric-grid">
                        {''.join(analytics['metrics'])}
                    </div>
                </div>
                """)
        
        # Charts section
        if analytics.get('charts'):
            if source_type == "combined":
                # Charts are already wrapped in sections for combined view
                content_sections.extend(analytics['charts'])
            else:
                # For tickets, charts are already individually wrapped in sections
                content_sections.extend(analytics['charts'])
        
        # Tables section
        if analytics.get('tables'):
            content_sections.extend(analytics['tables'])
        
        # Add data flow explanation
        content_sections.append(self._create_data_flow_explanation(source_type))
        
        return f"""
<!DOCTYPE html>
<html>
<head>
    <title>{title}</title>
    <meta charset="utf-8">
    <style>
        {self.css}
    </style>
</head>
<body>
    <h1>{title.split(' – ')[0]}<br>
        <small style="font-size:0.6em;color:#666">{title.split(' – ')[1] if ' – ' in title else ''}</small><br>
        {badge_html}
    </h1>
    {''.join(content_sections)}
    <div class="section" style="text-align:center;color:#666;font-size:0.8em;">
        <p>Generated on {self._get_timestamp()} by Unified Analytics Tool</p>
    </div>
</body>
</html>
        """
    
    def _build_compact_chat_dashboard(self, title: str, analytics: Dict, badge_html: str) -> str:
        """Build compact chat dashboard optimized for single viewport"""
        return f"""
<!DOCTYPE html>
<html>
<head>
    <title>{title}</title>
    <meta charset="utf-8">
    <style>
        {self.css}
    </style>
</head>
<body>
    <h1>{title.split(' – ')[0]}<br>
        <small style="font-size:0.5em;color:#666">{title.split(' – ')[1] if ' – ' in title else ''}</small><br>
        {badge_html}
    </h1>
    
    <!-- Summary Metrics -->
    <div class="section">
        <h2>Key Metrics</h2>
        <div class="metric-grid">
            {''.join(analytics.get('metrics', []))}
        </div>
    </div>
    
    <!-- Full Width Weekly Charts -->
    {''.join(analytics.get('charts', [])[:2])}
    
    <!-- Bot Charts & Agent Performance Row -->
    <div class="main-grid">
        <div class="left-panel">
            <!-- Bot Volume & Duration Charts -->
            {''.join(analytics.get('charts', [])[4:6])}
            
            <!-- Bot Satisfaction Charts -->
            {''.join(analytics.get('charts', [])[2:4])}
        </div>
        
        <div class="right-panel">
            <!-- Agent Performance Table -->
            {''.join(analytics.get('tables', []))}
        </div>
    </div>
    
    <!-- Human Agent Volume & Duration Charts (Full Width) -->
    {''.join(analytics.get('charts', [])[6:8])}
    
    <!-- Weekly Bot Satisfaction Chart (Full Width) -->
    {''.join(analytics.get('charts', [])[8:])}
    
    <!-- Data Flow Explanation -->
    {self._create_data_flow_explanation("chats")}
    
    <div style="position:fixed;bottom:4px;right:12px;color:#666;font-size:0.7em;">
        Generated {self._get_timestamp()}
    </div>
</body>
</html>
        """
    
    def _process_chat_analytics(self, analytics: Dict) -> Dict:
        """Process chat analytics data and create visualizations"""
        processed = {
            'metrics': [],
            'charts': [],
            'tables': [],
            'summary': {}
        }
        
        # Create summary metrics cards with enhanced prominent styling - alternating colors
        processed['metrics'].extend([
            create_metric_card(analytics['total_chats'], "Total Chats", "transfer-card-ultra"),
            create_metric_card(f"{analytics['volume_by_date']['avg_daily']:.1f}", "Avg Daily Chats", "satisfaction-card-ultra"),
            create_metric_card(f"{analytics['transfer_metrics']['transfer_rate']:.1f}%", "Bot Transfer Rate", "transfer-card-ultra", "Goal: < 30%"),
            create_metric_card(f"{analytics['satisfaction_metrics']['overall_satisfaction_rate']:.1f}%", "Satisfaction Rate", "satisfaction-card-ultra", "Goal: > 70%"),
            create_metric_card(analytics['transfer_metrics']['total_transfers'], "Total Transfers", "transfer-card-ultra"),
            create_metric_card(f"{analytics['transfer_metrics']['bot_only_rate']:.1f}%", "Bot Resolution", "satisfaction-card-ultra", "Goal: > 70%")
        ])
        
        # Add interactive charts first if available
        if analytics.get('charts'):
            processed['charts'].extend(analytics['charts'])
        
        # Create summary charts as HTML tables as fallback
        processed['charts'].append(self._create_volume_summary(analytics['volume_by_date']))
        processed['charts'].append(self._create_bot_satisfaction_summary(analytics['satisfaction_metrics']['bot_satisfaction']))
        
        # Agent performance comparison
        agent_performance_data = []
        
        # Add bot data (only agents with chats)
        for bot, metrics in analytics['bot_metrics']['bots'].items():
            if metrics['total_chats'] > 0:  # Exclude agents with 0 chats
                agent_performance_data.append({
                    'agent': 'Agent Scrape' if 'Traject Data' in bot else bot.replace(' Chat', ''),
                    'type': 'Bot',
                    'total_chats': metrics['total_chats'],
                    'avg_duration': metrics['avg_duration'],
                    'satisfaction_rate': metrics.get('avg_satisfaction', 0) * 20 if metrics.get('avg_satisfaction') else 0  # Convert 1-5 to 0-100
                })
        
        # Add human data (only agents with chats)
        for agent, metrics in analytics['human_metrics']['agents'].items():
            if metrics['total_chats'] > 0:  # Exclude agents with 0 chats
                # Apply agent name mapping (pseudonym → real name)
                agent_mapping = {
                    'Shan': 'Bhushan',
                    'Chris': 'Francis', 
                    'Nora': 'Nova',
                    'Gillie': 'Girly'
                }
                display_name = agent_mapping.get(agent, agent)
                agent_performance_data.append({
                    'agent': display_name,
                    'type': 'Human',
                    'total_chats': metrics['total_chats'],
                    'avg_duration': metrics['avg_duration'],
                    'satisfaction_rate': metrics.get('avg_satisfaction', 0) * 20 if metrics.get('avg_satisfaction') else 0  # Convert 1-5 to 0-100
                })
        
        # Agent performance table
        if agent_performance_data:
            performance_table = self._create_agent_performance_table(agent_performance_data)
            processed['tables'].append(performance_table)
        
        # Store summary for cross-analysis
        processed['summary'] = {
            'total_chats': analytics['total_chats'],
            'bot_percentage': analytics['bot_metrics'].get('percentage', 0),
            'human_percentage': analytics['human_metrics'].get('percentage', 0),
            'transfer_rate': analytics['transfer_metrics']['transfer_rate'],
            'satisfaction_rate': analytics['satisfaction_metrics']['overall_satisfaction_rate'],
            'total_agents': len([a for a in analytics['human_metrics']['agents'].keys() if analytics['human_metrics']['agents'][a]['total_chats'] > 0])
        }
        
        return processed
    
    def _create_volume_summary(self, volume_data: Dict) -> str:
        """Create compact volume summary"""
        return f"""
        <div class="section">
            <h3>📈 Volume Summary</h3>
            <div class="compact-section">
                <div class="metric-card">
                    <div class="metric-value">{volume_data['total_days']}</div>
                    <div class="metric-label">Days</div>
                </div>
                <div class="metric-card">
                    <div class="metric-value">{volume_data['peak_day']['count'] if volume_data['peak_day'] else 'N/A'}</div>
                    <div class="metric-label">Peak Day</div>
                </div>
            </div>
        </div>
        """
    
    def _create_bot_satisfaction_summary(self, bot_satisfaction: Dict) -> str:
        """Create bot satisfaction summary"""
        if not bot_satisfaction:
            return '<div class="section"><h3>🤖 Bot Satisfaction</h3><p>No satisfaction data available</p></div>'
        
        rows = []
        for bot, metrics in bot_satisfaction.items():
            bot_name = 'Agent Scrape' if 'Traject Data' in bot else bot.replace(' Chat', '')
            satisfaction_rate = f"{metrics['satisfaction_rate']:.1f}%" if metrics['total_rated'] > 0 else 'N/A'
            rows.append(f"""
            <tr>
                <td>{bot_name}</td>
                <td>{metrics['total_rated']}</td>
                <td>{metrics['good_ratings']}</td>
                <td>{metrics['bad_ratings']}</td>
                <td><strong>{satisfaction_rate}</strong></td>
            </tr>
            """)
        
        return f"""
        <div class="section">
            <h3>🤖 Bot Satisfaction Ratings</h3>
            <div class="table-container">
                <table class="performance-table">
                    <thead>
                        <tr>
                            <th>Bot</th>
                            <th>Total Rated</th>
                            <th>Good Ratings</th>
                            <th>Bad Ratings</th>
                            <th>Satisfaction Rate</th>
                        </tr>
                    </thead>
                    <tbody>
                        {''.join(rows)}
                    </tbody>
                </table>
            </div>
        </div>
        """
    
    def _create_transfer_summary(self, transfer_metrics: Dict) -> str:
        """Create compact transfer summary"""
        return f"""
        <div class="section">
            <h3>🔄 Transfer Analysis</h3>
            <div class="compact-section">
                <div class="transfer-card">
                    <div class="metric-value">{transfer_metrics['total_transfers']}</div>
                    <div class="metric-label">Transfers</div>
                </div>
                <div class="success-card">
                    <div class="metric-value">{transfer_metrics['bot_only_rate']:.1f}%</div>
                    <div class="metric-label">Bot Resolution</div>
                </div>
            </div>
        </div>
        """
    
    def _create_agent_performance_table(self, agent_data: List[Dict]) -> str:
        """Create agent performance table"""
        rows = []
        for agent in sorted(agent_data, key=lambda x: x['total_chats'], reverse=True):
            satisfaction_display = f"{agent['satisfaction_rate']:.1f}%" if agent['satisfaction_rate'] > 0 else "N/A"
            duration_display = f"{agent['avg_duration']:.1f} min" if agent['avg_duration'] > 0 else "N/A"
            
            rows.append(f"""
            <tr>
                <td>{agent['agent']}</td>
                <td><span class="badge {agent['type'].lower()}-badge">{agent['type']}</span></td>
                <td>{agent['total_chats']:,}</td>
                <td>{duration_display}</td>
                <td>{satisfaction_display}</td>
            </tr>
            """)
        
        return f"""
        <div class="section">
            <h3>👥 Agent Performance</h3>
            <div class="table-container">
                <table class="performance-table">
                    <thead>
                        <tr>
                            <th>Agent</th>
                            <th>Type</th>
                            <th>Chats</th>
                            <th>Duration</th>
                            <th>Satisfaction</th>
                        </tr>
                    </thead>
                    <tbody>
                        {''.join(rows)}
                    </tbody>
                </table>
            </div>
        </div>
        """
    
    def _create_cross_analysis(self, ticket_analytics: Dict, chat_analytics: Dict) -> str:
        """Create cross-analysis section for combined dashboard"""
        if not ticket_analytics.get('summary') or not chat_analytics.get('summary'):
            return ""
        
        ticket_summary = ticket_analytics['summary']
        chat_summary = chat_analytics['summary']
        
        # Calculate cross-metrics
        cross_metrics = []
        
        # Total customer interactions
        total_interactions = ticket_summary.get('total_tickets', 0) + chat_summary.get('total_chats', 0)
        chat_percentage = (chat_summary.get('total_chats', 0) / total_interactions * 100) if total_interactions > 0 else 0
        ticket_percentage = (ticket_summary.get('total_tickets', 0) / total_interactions * 100) if total_interactions > 0 else 0
        
        cross_metrics.extend([
            create_metric_card(total_interactions, "Total Customer Interactions", "metric-card"),
            create_metric_card(f"{chat_percentage:.1f}%", "Chat Channel Share", "chat-card"),
            create_metric_card(f"{ticket_percentage:.1f}%", "Ticket Channel Share", "ticket-card")
        ])
        
        # Agent efficiency comparison
        if ticket_summary.get('agent_count') and chat_summary.get('total_agents'):
            total_agents = ticket_summary['agent_count'] + chat_summary['total_agents']
            cross_metrics.append(
                create_metric_card(total_agents, "Total Support Agents", "metric-card")
            )
        
        return f"""
        <div class="section">
            <h2>🔄 Cross-Channel Analysis</h2>
            <div class="metric-grid">
                {''.join(cross_metrics)}
            </div>
            <div style="margin-top:20px;">
                <h3>Channel Distribution</h3>
                <p style="text-align:center;font-size:1.1em;">
                    Your customers are using <strong>chats</strong> for {chat_percentage:.1f}% of interactions 
                    and <strong>tickets</strong> for {ticket_percentage:.1f}% of interactions.
                </p>
            </div>
        </div>
        """
    
    def _get_timestamp(self) -> str:
        """Get formatted timestamp"""
        from datetime import datetime
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    def create_index_dashboard(self, available_sources: Dict, output_dir) -> str:
        """Create index dashboard showing available analyses"""
        sources_html = []
        
        if available_sources.get('tickets'):
            sources_html.append(f"""
            <div class="section">
                <h2>📋 Ticket Analytics Available</h2>
                <p>Found {len(available_sources['tickets'])} ticket CSV file(s)</p>
                <p><strong>Features:</strong> Response time analysis, agent performance, weekend detection, pipeline analysis</p>
            </div>
            """)
        
        if available_sources.get('chats'):
            sources_html.append(f"""
            <div class="section">
                <h2>💬 Chat Analytics Available</h2>
                <p>Found {len(available_sources['chats'])} chat CSV file(s)</p>
                <p><strong>Features:</strong> Bot performance, agent classification, volume trends, satisfaction ratings</p>
            </div>
            """)
        
        usage_examples = """
        <div class="section">
            <h2>📖 Usage Examples</h2>
            <div style="background:#f5f5f5;padding:15px;border-radius:5px;font-family:monospace;">
                <p><strong># Analyze all available data:</strong><br>
                python unified_analytics.py</p>
                
                <p><strong># Analyze specific source:</strong><br>
                python unified_analytics.py --source tickets<br>
                python unified_analytics.py --source chats</p>
                
                <p><strong># Date-specific analysis:</strong><br>
                python unified_analytics.py --week 22072025<br>
                python unified_analytics.py --day 22072025<br>
                python unified_analytics.py --custom 15072025-22072025</p>
                
                <p><strong># Combined analysis:</strong><br>
                python unified_analytics.py --source both --combined-dashboard</p>
            </div>
        </div>
        """
        
        return f"""
<!DOCTYPE html>
<html>
<head>
    <title>Unified Analytics - Available Data Sources</title>
    <meta charset="utf-8">
    <style>{self.css}</style>
</head>
<body>
    <h1>🔍 Unified Analytics Tool<br>
        <small style="font-size:0.6em;color:#666">Data Source Overview</small>
    </h1>
    
    {''.join(sources_html)}
    
    <div class="section">
        <h2>📁 Data Directory Structure</h2>
        <div style="background:#f5f5f5;padding:15px;border-radius:5px;font-family:monospace;">
            📂 unified-analytics/<br>
            ├── 📂 tickets/ ← Place ticket CSV files here<br>
            ├── 📂 chats/ ← Place chat CSV files here<br>
            └── 📂 results/ ← Generated dashboards and reports
        </div>
    </div>
    
    {usage_examples}
    
    <div class="section" style="text-align:center;color:#666;font-size:0.9em;">
        <p>Generated on {self._get_timestamp()}</p>
    </div>
</body>
</html>
        """