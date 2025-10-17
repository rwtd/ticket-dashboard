# HubSpot Metrics Cards Embed Guide

Quick copy-paste embed codes for the new `/metrics` endpoint that displays metric cards (not charts).

## 🎯 What Are Metrics Cards?

The `/metrics` endpoint returns HTML metric cards showing key performance indicators:
- **Ticket Metrics**: Median response time, total tickets, weekday/weekend breakdown
- **Chat Metrics**: Total chats, bot transfer rate, satisfaction rate (from LiveChat Reports API), bot resolution rate

## 📋 HubSpot Embed Code Templates

Replace `YOUR-CLOUD-RUN-URL` with your actual Cloud Run URL (e.g., `https://ticket-dashboard-xxxxx-uc.a.run.app`)

### All Metrics (Default - 90 days tickets, 30 days chats)

```html
<iframe
  src="YOUR-CLOUD-RUN-URL/metrics"
  style="width: 100%; height: 600px; border: 0;"
  loading="lazy"
  referrerpolicy="no-referrer"
  sandbox="allow-scripts allow-same-origin">
</iframe>
```

### Tickets Only - Last 13 Weeks

```html
<iframe
  src="YOUR-CLOUD-RUN-URL/metrics?type=tickets&range=13w"
  style="width: 100%; height: 400px; border: 0;"
  loading="lazy"
  referrerpolicy="no-referrer"
  sandbox="allow-scripts allow-same-origin">
</iframe>
```

### Chats Only - Last 8 Weeks

```html
<iframe
  src="YOUR-CLOUD-RUN-URL/metrics?type=chats&range=8w"
  style="width: 100%; height: 400px; border: 0;"
  loading="lazy"
  referrerpolicy="no-referrer"
  sandbox="allow-scripts allow-same-origin">
</iframe>
```

### All Metrics - Last 30 Days

```html
<iframe
  src="YOUR-CLOUD-RUN-URL/metrics?range=30d"
  style="width: 100%; height: 600px; border: 0;"
  loading="lazy"
  referrerpolicy="no-referrer"
  sandbox="allow-scripts allow-same-origin">
</iframe>
```

### All Metrics - Last 7 Days

```html
<iframe
  src="YOUR-CLOUD-RUN-URL/metrics?range=7d"
  style="width: 100%; height: 600px; border: 0;"
  loading="lazy"
  referrerpolicy="no-referrer"
  sandbox="allow-scripts allow-same-origin">
</iframe>
```

### All Metrics - Quarterly (Last 13 Weeks)

```html
<iframe
  src="YOUR-CLOUD-RUN-URL/metrics?range=quarterly"
  style="width: 100%; height: 600px; border: 0;"
  loading="lazy"
  referrerpolicy="no-referrer"
  sandbox="allow-scripts allow-same-origin">
</iframe>
```

## 🎨 Parameters

### `type` - Which metrics to show
- `all` (default) - Both ticket and chat metrics
- `tickets` - Only ticket metrics
- `chats` - Only chat metrics

### `range` - Time period
- `7d` - Last 7 days
- `30d` - Last 30 days (default for chats)
- `90d` - Last 90 days (default for tickets)
- `8w` - Last 8 weeks
- `13w` or `quarterly` - Last 13 weeks (displays as "Last 13 Weeks")
- `52w` - Last 52 weeks

### `theme` - Visual theme
- `dark` (default) - Dark theme
- `light` - Light theme

## 📐 Height Recommendations

- **All metrics** (tickets + chats): `600px`
- **Tickets only**: `400px`
- **Chats only**: `400px`

Adjust based on your layout needs.

## 🔧 Example Combinations

### Executive Dashboard - Quarterly Overview
```html
<iframe
  src="YOUR-CLOUD-RUN-URL/metrics?range=13w"
  style="width: 100%; height: 600px; border: 0;"
  loading="lazy"
  sandbox="allow-scripts allow-same-origin">
</iframe>
```

### Weekly Team Review - Last 7 Days
```html
<iframe
  src="YOUR-CLOUD-RUN-URL/metrics?range=7d"
  style="width: 100%; height: 600px; border: 0;"
  loading="lazy"
  sandbox="allow-scripts allow-same-origin">
</iframe>
```

### Chat Performance Focus - 8 Weeks
```html
<iframe
  src="YOUR-CLOUD-RUN-URL/metrics?type=chats&range=8w"
  style="width: 100%; height: 400px; border: 0;"
  loading="lazy"
  sandbox="allow-scripts allow-same-origin">
</iframe>
```

### Light Theme for Bright Pages
```html
<iframe
  src="YOUR-CLOUD-RUN-URL/metrics?theme=light&range=30d"
  style="width: 100%; height: 600px; border: 0;"
  loading="lazy"
  sandbox="allow-scripts allow-same-origin">
</iframe>
```

## 📊 What Data Is Shown?

### Ticket Metrics
- ⚡ **Median Response Time** - Weekday only, excludes LiveChat pipeline
- **Total Tickets** - With daily average
- **Weekday Tickets** - With daily average
- **Weekend Tickets** - With daily average

### Chat Metrics
- **Total Chats** - With daily average
- **Bot Transfer Rate** - Goal: < 30%
- **Satisfaction Rate** - Goal: > 70% (from LiveChat Reports API)
- **Bot Resolution Rate** - Goal: > 70%

## 🔒 Security

The metrics endpoint uses the same security headers as widgets:
- `X-Frame-Options: SAMEORIGIN` (configurable via `WIDGETS_XFO`)
- `Content-Security-Policy: frame-ancestors 'self' https://*.hubspot.com` (configurable via `WIDGETS_FRAME_ANCESTORS`)

These are already configured to allow HubSpot embedding.

## 🚀 Quick Test

Before embedding in HubSpot, test locally:

```bash
# Start server
python start_ui.py

# Visit in browser
http://localhost:5000/metrics?range=30d
```

## 📝 Notes

- The satisfaction rate uses the **LiveChat Reports API** (same reliable source as the `weekly_bot_satisfaction` widget)
- If the Reports API is unavailable, it automatically falls back to CSV data
- All timeframes show user-friendly labels (e.g., "Last 13 Weeks" instead of "91 Days")
- Metric cards are responsive and work well in HubSpot's layout system