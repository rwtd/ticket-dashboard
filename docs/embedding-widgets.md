# Embedding Ticket Dashboard Widgets

This developer guide covers how to embed and integrate the widget system exposed by the Flask app ([app.py](app.py)). It includes iframe snippets, JSON usage, parameters, security headers, troubleshooting, and local testing.


## Overview

- Widgets are registered chart builders defined in ([widgets/registry.py](widgets/registry.py)) and exposed via routes in ([widgets/routes.py](widgets/routes.py)).
- Directory listing for all widgets: GET /widgets
- Two endpoint flavors per widget name:
  - HTML: GET /widget/<name> — returns a complete HTML page suitable for iframe embedding (uses template ([templates/widgets/widget_base.html](templates/widgets/widget_base.html))).
  - JSON: GET /widget/<name>.json — returns a Plotly figure as pure JSON (fig.to_dict()) for custom rendering.

Notes:
- The HTML endpoint handles presentation-only params (theme, width, height).
- The JSON endpoint ignores presentation-only params; it only reflects chart parameters and returns the figure data and layout.


## Quick Start (iframe)

Minimal embed that works out of the box (uses defaults: theme=dark, width=100% via CSS, height=420px):

```html
<iframe
  src="https://YOUR-WIDGET-HOST/widget/weekly_response_time_trends"
  style="width: 100%; height: 420px; border: 0;"
  loading="lazy"
  referrerpolicy="no-referrer"
  sandbox="allow-scripts allow-same-origin">
</iframe>
```

Light theme variant:

```html
<iframe
  src="https://YOUR-WIDGET-HOST/widget/weekly_response_time_trends?theme=light"
  style="width: 100%; height: 420px; border: 0;"
  loading="lazy"
  sandbox="allow-scripts allow-same-origin">
</iframe>
```

Custom height (e.g., 600px):

```html
<iframe
  src="https://YOUR-WIDGET-HOST/widget/weekly_response_time_trends"
  style="width: 100%; height: 600px; border: 0;"
  loading="lazy"
  sandbox="allow-scripts allow-same-origin">
</iframe>
```

Sizing guidance:
- Width is governed by the container/iframe width. The widget page sets width: 100% by default.
- Height is fixed to the iframe’s CSS height (default 420px). Increase for dense plots or legends.
- The inner Plotly chart is responsive to the iframe’s size. Make your outer container responsive for best results.


## Available Widgets and URL Examples

Current registry entries (static list for docs):
- demo_timeseries
- weekly_response_time_trends
- volume_daily_historic
- tickets_by_pipeline
- weekday_weekend_distribution
- chat_weekly_volume_breakdown
- weekly_bot_satisfaction
- agent_ticket_volume_distribution
- agent_response_time_comparison
- bot_volume_duration
- human_volume_duration
- bot_performance_comparison
- weekly_response_breakdown
- daily_chat_trends_performance
- pipeline_distribution_by_agent
- pipeline_response_time_heatmap
- performance_vs_volume
- agent_weekly_response_by_agent
- agent_weekly_ticket_volume_by_agent

Examples below assume a local server started with ([start_ui.py](start_ui.py)) on http://localhost:5000. Replace host as needed in production.

### demo_timeseries
- HTML: http://localhost:5000/widget/demo_timeseries
- JSON: http://localhost:5000/widget/demo_timeseries.json

### weekly_response_time_trends
Base: /widget/weekly_response_time_trends with defaults source=tickets, stat=median, range=12w.

- HTML (default): http://localhost:5000/widget/weekly_response_time_trends
- HTML (tickets, median, 12w): http://localhost:5000/widget/weekly_response_time_trends?source=tickets&stat=median&range=12w
- HTML (chats, mean, 26w): http://localhost:5000/widget/weekly_response_time_trends?source=chats&stat=mean&range=26w
- HTML (tickets, median, 4w, light): http://localhost:5000/widget/weekly_response_time_trends?source=tickets&stat=median&range=4w&theme=light
- JSON (chats, median, 8w): http://localhost:5000/widget/weekly_response_time_trends.json?source=chats&stat=median&range=8w

### volume_daily_historic
Base: /widget/volume_daily_historic with defaults source=tickets, range=26w, include_weekends=true.

- HTML (default): http://localhost:5000/widget/volume_daily_historic
- HTML (tickets, 8w, weekdays only): http://localhost:5000/widget/volume_daily_historic?source=tickets&range=8w&include_weekends=false
- HTML (chats, 52w): http://localhost:5000/widget/volume_daily_historic?source=chats&range=52w
- JSON (tickets, 4w, weekdays only): http://localhost:5000/widget/volume_daily_historic.json?source=tickets&range=4w&include_weekends=false


## Parameter Reference

Common (HTML endpoint only; presentation controls handled by ([templates/widgets/widget_base.html](templates/widgets/widget_base.html))):
- theme: dark (default) | light
- width: integer px (optional; default 100% via template CSS)
- height: integer px (optional; default 420)

Note: width/height are applied via HTML/CSS; JSON endpoints return pure figure data unaffected by these.

Chart-specific parameters (as implemented in ([widgets/registry.py](widgets/registry.py))):

weekly_response_time_trends
- source: tickets | chats (default tickets)
- stat: median | mean (default median)
- range: all | 52w | 26w | 12w | 8w | 4w (default 12w)

volume_daily_historic
- source: tickets | chats (default tickets)
- range: all | 52w | 26w | 12w | 8w | 4w (default 26w)
- include_weekends: true | false (default true)

tickets_by_pipeline
- source: tickets (fixed)
- range: all | 52w | 26w | 12w | 8w | 4w (default 12w)
- pipelines: CSV list of pipeline names (optional)

weekday_weekend_distribution
- source: tickets (fixed)
- range: all | 52w | 26w | 12w | 8w | 4w (default 12w)

chat_weekly_volume_breakdown
- source: chats (fixed)
- range: all | 52w | 26w | 12w | 8w | 4w (default 12w)
- series: CSV list of total | bot | human | trend (default total,bot,human,trend)

weekly_bot_satisfaction
- source: chats (fixed)
- range: all | 52w | 26w | 12w | 8w | 4w (default 12w)

agent_ticket_volume_distribution
- source: tickets (fixed)
- range: all | 52w | 26w | 12w | 8w | 4w (default 12w)
- agents: CSV list of agent names (optional)

agent_response_time_comparison
- source: tickets (fixed)
- range: all | 52w | 26w | 12w | 8w | 4w (default 12w)
- stat: median | mean | both (default both)
- agents: CSV list of agent names (optional)
- exclude_pipelines: CSV list (default includes "Live Chat ")

bot_volume_duration
- source: chats (fixed)
- range: all | 52w | 26w | 12w | 8w | 4w (default 12w)
- bots: CSV list of bot display names (optional)

human_volume_duration
- source: chats (fixed)
- range: all | 52w | 26w | 12w | 8w | 4w (default 12w)
- agents: CSV list of primary agent names (optional)

weekly_response_breakdown
- source: tickets (fixed)
- stat: median | mean (default median)
- range: all | 12w | 8w (default all)
- include_weekend_series: true | false (default false)
- show_trend: true | false (default true)

daily_chat_trends_performance
- source: chats (fixed)
- range: all | 52w | 26w | 12w | 8w | 4w (default 12w)

pipeline_distribution_by_agent
- source: tickets (fixed)
- range: all | 12w | 8w (default 12w)
- agents: CSV list (optional)
- pipelines: CSV list (optional)

pipeline_response_time_heatmap
- source: tickets (fixed)
- range: all | 12w | 8w (default 12w)
- agents: CSV list (optional)
- pipelines: CSV list (optional)
- stat: median (fixed)

performance_vs_volume
- source: tickets (fixed)
- range: all | 12w | 8w (default 12w)
- agents: CSV list (optional)

agent_weekly_response_by_agent
- source: tickets (fixed)
- range: all | 12w | 8w (default 12w)
- agents: CSV list (optional)
- stat: median (fixed)

agent_weekly_ticket_volume_by_agent
- source: tickets (fixed)
- range: all | 12w | 8w (default 12w)
- agents: CSV list (optional)

Behavior on invalid parameters:
- The system silently falls back to each parameter’s default (see normalize/validation in ([widgets/registry.py](widgets/registry.py)) and parsing in ([widgets/routes.py](widgets/routes.py))).


## Security and Embedding Headers

The app sets global headers after each request in ([app.py](app.py)):
- X-Frame-Options (env: WIDGETS_XFO; default SAMEORIGIN)
- Content-Security-Policy with frame-ancestors (env: WIDGETS_FRAME_ANCESTORS; default `'self' https://*.hubspot.com`)

Examples for permissive embedding (development or controlled allowlists):

```bash
# Allow all framing (not recommended for production)
export WIDGETS_XFO="ALLOWALL"

# Expand allowed ancestors for CSP frame-ancestors
export WIDGETS_FRAME_ANCESTORS="'self' https://*.hubspot.com https://example.com"
```

Notes:
- The per-route widget responses also apply the same headers for extra safety (see ([widgets/routes.py](widgets/routes.py))).
- JSON endpoints, when accessed cross-origin via fetch, may require CORS configuration on your widget host. Iframes do not require CORS.


## JSON-based Embedding (optional pattern)

You can render a widget directly in your page by fetching /widget/<name>.json and passing it to Plotly.

```html
<div id="widget-container" style="width:100%;max-width:900px;height:420px;"></div>
<script src="https://cdn.plot.ly/plotly-2.32.0.min.js"></script>
<script>
  (async function() {
    const url = "https://YOUR-WIDGET-HOST/widget/weekly_response_time_trends.json?source=tickets&stat=median&range=12w";
    try {
      const res = await fetch(url, { credentials: "omit" });
      if (!res.ok) throw new Error("Request failed: " + res.status);
      const fig = await res.json(); // expects {data, layout, ...}
      await Plotly.newPlot("widget-container", fig.data || [], fig.layout || {}, {responsive: true});
      window.addEventListener("resize", () => Plotly.Plots.resize("widget-container"));
    } catch (err) {
      console.error("Failed to render widget:", err);
      const el = document.getElementById("widget-container");
      if (el) el.innerHTML = "<em>Failed to load widget data.</em>";
    }
  })();
</script>
```

Implementation notes:
- Include Plotly via CDN (shown above) or your own bundle.
- Ensure the container has an explicit height (e.g., 420px) and a responsive width.
- Cross-origin fetch may be blocked without CORS on the widget host. For pure iframes, CORS is not needed.


## Troubleshooting

- Iframe shows blank or 403: Verify CSP frame-ancestors and X-Frame-Options allow your embedding origin.
- “No data for selected range/params”: The dataset is empty for the requested range/filters.
- Mixed content in HTTPS site: Ensure the widget host is served over HTTPS.
- Performance: Server-side caching is not yet implemented; Phase 3 will add Flask-Caching.
- Security: Signed URLs/tokens are not yet implemented; Phase 4 will introduce tokenized access.


## Local Testing

1) Start the server:

```bash
python3 start_ui.py
```

2) Explore and test:
- Widgets index: http://localhost:5000/widgets
- Weekly response time (HTML): http://localhost:5000/widget/weekly_response_time_trends?source=tickets&stat=median&range=12w
- Weekly response time (JSON): http://localhost:5000/widget/weekly_response_time_trends.json?source=chats&stat=mean&range=26w
- Volume daily (HTML): http://localhost:5000/widget/volume_daily_historic?source=tickets&range=8w&include_weekends=false
- Volume daily (JSON): http://localhost:5000/widget/volume_daily_historic.json?source=tickets&range=8w&include_weekends=false


---

For implementation details, see:
- Registry and parameter schemas: ([widgets/registry.py](widgets/registry.py))
- Routes and parameter parsing: ([widgets/routes.py](widgets/routes.py))
- Widget HTML template: ([templates/widgets/widget_base.html](templates/widgets/widget_base.html))
- App-wide security headers: ([app.py](app.py))

## Additional Widget Examples

The following widgets are available via the same HTML and JSON endpoint patterns. Replace host as needed.

### tickets_by_pipeline
- HTML (default): http://localhost:5000/widget/tickets_by_pipeline
- HTML (8w, filter pipelines): http://localhost:5000/widget/tickets_by_pipeline?range=8w&amp;pipelines=Support,Live%20Chat%20
- JSON (26w): http://localhost:5000/widget/tickets_by_pipeline.json?range=26w

### weekday_weekend_distribution
- HTML (default): http://localhost:5000/widget/weekday_weekend_distribution
- HTML (4w): http://localhost:5000/widget/weekday_weekend_distribution?range=4w
- JSON (12w): http://localhost:5000/widget/weekday_weekend_distribution.json?range=12w

### chat_weekly_volume_breakdown
- HTML (default): http://localhost:5000/widget/chat_weekly_volume_breakdown
- HTML (26w, total+trend only): http://localhost:5000/widget/chat_weekly_volume_breakdown?range=26w&amp;series=total,trend
- JSON (12w): http://localhost:5000/widget/chat_weekly_volume_breakdown.json?range=12w

### weekly_bot_satisfaction
- HTML (default): http://localhost:5000/widget/weekly_bot_satisfaction
- HTML (52w): http://localhost:5000/widget/weekly_bot_satisfaction?range=52w
- JSON (8w): http://localhost:5000/widget/weekly_bot_satisfaction.json?range=8w

### agent_ticket_volume_distribution
- HTML (default): http://localhost:5000/widget/agent_ticket_volume_distribution
- HTML (filter agents): http://localhost:5000/widget/agent_ticket_volume_distribution?agents=Nova,Girly
- JSON (26w): http://localhost:5000/widget/agent_ticket_volume_distribution.json?range=26w

### agent_response_time_comparison
- HTML (default): http://localhost:5000/widget/agent_response_time_comparison
- HTML (median only, filtered agents): http://localhost:5000/widget/agent_response_time_comparison?stat=median&amp;agents=Nova,Girly
- JSON (exclude Live Chat): http://localhost:5000/widget/agent_response_time_comparison.json?exclude_pipelines=Live%20Chat%20

### bot_volume_duration
- HTML (default): http://localhost:5000/widget/bot_volume_duration
- HTML (filtered bots): http://localhost:5000/widget/bot_volume_duration?bots=Wynn%20AI,Agent%20Scrape
- JSON (12w): http://localhost:5000/widget/bot_volume_duration.json?range=12w

### human_volume_duration
- HTML (default): http://localhost:5000/widget/human_volume_duration
- HTML (filtered agents): http://localhost:5000/widget/human_volume_duration?agents=Nova,Girly
- JSON (12w): http://localhost:5000/widget/human_volume_duration.json?range=12w

### weekly_response_breakdown
- HTML (default): http://localhost:5000/widget/weekly_response_breakdown
- HTML (8w, include weekend series): http://localhost:5000/widget/weekly_response_breakdown?range=8w&amp;include_weekend_series=true
- JSON (mean, trends off): http://localhost:5000/widget/weekly_response_breakdown.json?stat=mean&amp;show_trend=false

### daily_chat_trends_performance
- HTML (default): http://localhost:5000/widget/daily_chat_trends_performance
- HTML (8w): http://localhost:5000/widget/daily_chat_trends_performance?range=8w
- JSON (12w): http://localhost:5000/widget/daily_chat_trends_performance.json?range=12w

### pipeline_distribution_by_agent
- HTML (default): http://localhost:5000/widget/pipeline_distribution_by_agent
- HTML (8w, filter agents and pipelines): http://localhost:5000/widget/pipeline_distribution_by_agent?range=8w&amp;agents=Nova,Girly&amp;pipelines=Support,Sales
- JSON: http://localhost:5000/widget/pipeline_distribution_by_agent.json

### pipeline_response_time_heatmap
- HTML (default): http://localhost:5000/widget/pipeline_response_time_heatmap
- HTML (8w, subset): http://localhost:5000/widget/pipeline_response_time_heatmap?range=8w&amp;agents=Nova,Girly&amp;pipelines=Support,Sales
- JSON: http://localhost:5000/widget/pipeline_response_time_heatmap.json

### performance_vs_volume
- HTML (default): http://localhost:5000/widget/performance_vs_volume
- HTML (8w, subset): http://localhost:5000/widget/performance_vs_volume?range=8w&amp;agents=Nova,Girly
- JSON: http://localhost:5000/widget/performance_vs_volume.json

### agent_weekly_response_by_agent
- HTML (default): http://localhost:5000/widget/agent_weekly_response_by_agent
- HTML (8w, subset): http://localhost:5000/widget/agent_weekly_response_by_agent?range=8w&amp;agents=Nova,Girly
- JSON: http://localhost:5000/widget/agent_weekly_response_by_agent.json?range=12w

### agent_weekly_ticket_volume_by_agent
- HTML (default): http://localhost:5000/widget/agent_weekly_ticket_volume_by_agent
- HTML (8w, subset): http://localhost:5000/widget/agent_weekly_ticket_volume_by_agent?range=8w&amp;agents=Nova,Girly
- JSON: http://localhost:5000/widget/agent_weekly_ticket_volume_by_agent.json?range=12w