# API Access Requirements for Ticket Dashboard

This document outlines the API access requirements needed to enable direct programmatic data fetching from HubSpot and LiveChat, eliminating manual CSV exports.

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                   AUTOMATED DATA PIPELINE                        │
└─────────────────────────────────────────────────────────────────┘

HubSpot API          LiveChat API
(Tickets)            (Chats)
    │                    │
    ├─────────┬──────────┤
              │
         Data Fetcher Service
         (Scheduled: every 1-6 hours)
              │
              ├─→ Process & Transform
              ├─→ Timezone Conversion (CDT→ADT / UTC→ADT)
              ├─→ Agent Name Standardization
              ├─→ Weekend Detection
              │
              ↓
         Google Sheets
         (365-day rolling window)
              │
              ├─→ Main Dashboard
              ├─→ Widgets (HubSpot embed)
              ├─→ AI Query Engine
              └─→ Manual Analysis
```

## Benefits of API Integration

✅ **Eliminates Manual Work**: No more CSV exports from HubSpot/LiveChat
✅ **Real-Time Data**: Automated sync every 1-6 hours (configurable)
✅ **Always Up-to-Date**: Dashboards and widgets show current data
✅ **Consistent Source**: Single pipeline for all analytics
✅ **Audit Trail**: Complete sync logs and error tracking
✅ **Scalable**: Handles growing data volumes automatically

---

## 1. HubSpot API Access Requirements

### **What to Request from HubSpot Admin:**

#### A. Private App or OAuth App Access

**Option 1: Private App (Recommended for Internal Use)**
- Navigate to: HubSpot Settings → Integrations → Private Apps
- Create a new Private App named: "Ticket Dashboard Analytics"
- Description: "Automated ticket data fetching for analytics dashboard"

**Option 2: OAuth App (If you need external access)**
- For server-to-server access or if Private Apps aren't available

#### B. Required Scopes (Permissions)

Request these specific scopes for the Private App:

**Core Ticket Access:**
- ✅ `crm.objects.tickets.read` - Read ticket data
- ✅ `crm.schemas.tickets.read` - Read ticket properties schema

**Owner/User Information:**
- ✅ `crm.objects.owners.read` - Read ticket owner details (agent names)

**Optional but Recommended:**
- ✅ `crm.objects.contacts.read` - Read associated contact info (if needed)
- ✅ `crm.objects.companies.read` - Read associated company info (if needed)

#### C. API Endpoints You'll Use

```
Base URL: https://api.hubapi.com

1. List Tickets (with pagination):
   GET /crm/v3/objects/tickets

2. Search/Filter Tickets:
   POST /crm/v3/objects/tickets/search

3. Get Ticket Properties:
   GET /crm/v3/properties/tickets

4. Get Specific Tickets with Properties:
   GET /crm/v3/objects/tickets?properties=subject,hs_pipeline,hs_pipeline_stage,hs_ticket_priority,createdate,hs_lastmodifieddate,hubspot_owner_id,time_to_first_agent_email_reply
```

#### D. Key Properties to Fetch

Based on your current CSV columns, request these properties:

**Essential:**
- `subject` - Ticket subject/title
- `hs_pipeline` - Support pipeline name
- `hs_pipeline_stage` - Current stage
- `createdate` - Ticket creation date (CDT)
- `hs_lastmodifieddate` - Last modified date
- `hubspot_owner_id` - Assigned agent ID
- `content` - Ticket description/content
- `hs_ticket_priority` - Priority level

**Response Time Metrics:**
- `time_to_first_agent_email_reply` - First response time (your key metric!)
- `time_to_close` - Time to resolution
- `hs_time_to_first_response` - Alternative first response metric

**Additional Context:**
- `hs_ticket_category` - Ticket category
- `source_type` - How ticket was created
- `closed_date` - When ticket was closed

#### E. Rate Limits

- **Rate Limit**: 100 requests per 10 seconds for Private Apps
- **Daily Limit**: Check your HubSpot tier (Professional/Enterprise have higher limits)
- **Best Practice**: Use pagination with `limit=100` per request, add 100ms delay between requests

#### F. Authentication Format

Once you have the Private App token, authenticate like this:

```bash
Authorization: Bearer YOUR_PRIVATE_APP_TOKEN
```

---

## 2. LiveChat API Access Requirements

### **What to Request from LiveChat Admin:**

#### A. Personal Access Token (PAT)

- Navigate to: LiveChat Developer Console → Tools → Personal Access Tokens
- Create a new PAT named: "Ticket Dashboard Analytics"
- Description: "Automated chat data fetching for support analytics"

#### B. Required Scopes (Permissions)

Request these specific scopes:

**Chat History Access:**
- ✅ `chats--all:ro` - Read all chat conversations (read-only)
- ✅ `chats--access:ro` - Access chat data (read-only)
- ✅ `chats.conversation--all:ro` - Read conversation details

**Agent Information:**
- ✅ `agents--all:ro` - Read agent information
- ✅ `agents-bot--all:ro` - Read bot agent information

**Optional but Recommended:**
- ✅ `customers:ro` - Read customer information
- ✅ `properties.configuration:ro` - Read property configurations

#### C. API Endpoints You'll Use

```
Base URL: https://api.livechatinc.com/v3.5

1. List Chats (with filtering):
   POST /agent/action/list_chats

2. Get Chat Details:
   POST /agent/action/get_chat

3. List Archives (historical chats):
   POST /agent/action/list_archives

4. Get Agent Details:
   GET /configuration/action/list_agents
```

#### D. Key Data Fields to Fetch

Based on your current CSV columns, fetch these fields:

**Essential:**
- `id` - Chat ID
- `created_at` - Chat creation timestamp (UTC)
- `thread.created_at` - Thread start time
- `users` - Array of agents who participated
  - `user.name` - Agent name
  - `user.type` - "agent" vs "customer"
- `properties.routing.bot` - Bot identifier (Wynn AI, Agent Scrape)

**Performance Metrics:**
- `properties.rating` - Customer satisfaction rating (1-5)
- `properties.rating.comment` - Rating comment
- `properties.source` - Chat source
- `thread.events` - All chat messages (for response time calculation)

**Transfer Detection:**
- `thread.events[].type` - Look for "agent_joined" events
- `users[].type` - Multiple agents indicate transfers
- `tags` - Look for "chatbot-transfer" tag

#### E. Filtering Parameters

For date range filtering in `list_chats`:

```json
{
  "filters": {
    "created_at": {
      "from": "2025-01-01T00:00:00Z",
      "to": "2025-12-31T23:59:59Z"
    },
    "include_active": true,
    "include_archived": true
  },
  "limit": 100,
  "page_id": "optional_pagination_token"
}
```

#### F. Rate Limits

- **Rate Limit**: 180 requests per minute per API key
- **Best Practice**: Add 350ms delay between requests to stay well under limit
- **Pagination**: Use `page_id` for pagination, each response includes `next_page_id`

#### G. Authentication Format

Once you have the PAT token, authenticate like this:

```bash
Authorization: Bearer YOUR_PERSONAL_ACCESS_TOKEN
```

---

## 3. Implementation Timeline

### Phase 1: API Access Setup (Week 1)
- [ ] Request HubSpot Private App creation
- [ ] Request necessary HubSpot scopes (listed above)
- [ ] Generate LiveChat Personal Access Token
- [ ] Request necessary LiveChat scopes (listed above)
- [ ] Test API authentication and basic queries
- [ ] Verify all required properties/fields are accessible

### Phase 2: Data Fetcher Development (Week 1-2)
- [ ] Build HubSpot ticket fetcher with pagination
- [ ] Build LiveChat chat fetcher with pagination
- [ ] Implement timezone conversion logic
- [ ] Add agent name standardization
- [ ] Create Google Sheets sync module
- [ ] Add error handling and retry logic

### Phase 3: Automation & Scheduling (Week 2)
- [ ] Create scheduled sync service (Cloud Run job or cron)
- [ ] Add sync logging and monitoring
- [ ] Implement incremental sync (only fetch new/updated data)
- [ ] Set up alerting for sync failures

### Phase 4: Integration & Testing (Week 2-3)
- [ ] Update widgets to use Google Sheets data
- [ ] Update main dashboard to use Google Sheets data
- [ ] Update AI query engine to use Google Sheets data
- [ ] Test end-to-end data flow
- [ ] Deploy to production

---

## 4. Required Environment Variables

Once you have API access, configure these:

```bash
# HubSpot Configuration
HUBSPOT_API_KEY=your_private_app_token_here
HUBSPOT_PORTAL_ID=your_portal_id_here  # Optional, usually in URL

# LiveChat Configuration
LIVECHAT_PAT=your_personal_access_token_here
LIVECHAT_LICENSE_ID=your_license_id_here  # Found in LiveChat settings

# Google Sheets Configuration (existing)
GOOGLE_SHEETS_SPREADSHEET_ID=your_spreadsheet_id_here
GOOGLE_SHEETS_CREDENTIALS_PATH=/path/to/service_account.json

# Sync Configuration
DATA_SYNC_INTERVAL_HOURS=4  # How often to sync (1-24 hours)
DATA_RETENTION_DAYS=365  # Rolling window for Google Sheets
TIMEZONE_SOURCE=America/Chicago  # CDT timezone for tickets
TIMEZONE_TARGET=America/Halifax  # ADT timezone for analytics
```

---

## 5. What to Ask Your Admin

### For HubSpot Admin:

> Hi [Admin Name],
>
> I need API access to automate our support analytics dashboard. This will eliminate manual CSV exports and provide real-time insights.
>
> **Request:**
> 1. Create a Private App in HubSpot Settings → Integrations → Private Apps
> 2. Name: "Ticket Dashboard Analytics"
> 3. Required Scopes:
>    - crm.objects.tickets.read
>    - crm.schemas.tickets.read
>    - crm.objects.owners.read
> 4. Share the generated Access Token securely (via password manager or encrypted channel)
>
> **Why:** This enables automated ticket data sync to our analytics platform every 4 hours, eliminating manual work and ensuring always-current dashboards.
>
> Let me know if you need any clarification!

### For LiveChat Admin:

> Hi [Admin Name],
>
> I need API access to automate our chat analytics dashboard. This will provide real-time chat performance insights.
>
> **Request:**
> 1. Navigate to LiveChat Developer Console → Tools → Personal Access Tokens
> 2. Create a new PAT named "Ticket Dashboard Analytics"
> 3. Required Scopes:
>    - chats--all:ro
>    - chats--access:ro
>    - agents--all:ro
>    - agents-bot--all:ro
> 4. Share the generated token securely (via password manager or encrypted channel)
>
> **Why:** This enables automated chat data sync to our analytics platform every 4 hours, providing real-time bot performance and agent metrics.
>
> Let me know if you need any clarification!

---

## 6. Testing API Access

Once you receive the credentials, test them:

### Test HubSpot Access:

```bash
curl -X GET "https://api.hubapi.com/crm/v3/objects/tickets?limit=10&properties=subject,createdate" \
  -H "Authorization: Bearer YOUR_HUBSPOT_TOKEN"
```

Expected: JSON response with up to 10 tickets

### Test LiveChat Access:

```bash
curl -X POST "https://api.livechatinc.com/v3.5/agent/action/list_chats" \
  -H "Authorization: Bearer YOUR_LIVECHAT_PAT" \
  -H "Content-Type: application/json" \
  -d '{"limit": 10}'
```

Expected: JSON response with up to 10 chats

---

## 7. Cost & Quota Considerations

### HubSpot:
- **Free/Starter**: Limited API calls, may need to upgrade
- **Professional**: 160,000 API calls per day (sufficient for most use cases)
- **Enterprise**: 500,000+ API calls per day

**Estimated Usage:**
- ~500 tickets/day × 1 API call = 500 calls
- With pagination: ~5-10 calls per sync
- 6 syncs/day = 60 API calls/day (well within limits)

### LiveChat:
- **Rate Limit**: 180 requests/minute (sufficient)
- No daily cap mentioned

**Estimated Usage:**
- ~200 chats/day × pagination = 5-10 API calls per sync
- 6 syncs/day = 60 API calls/day (well within limits)

---

## 8. Security Best Practices

✅ **Store tokens securely**: Use Google Secret Manager or environment variables, never commit to git
✅ **Rotate regularly**: Update API tokens every 90 days
✅ **Limit scope**: Only request minimum necessary permissions
✅ **Monitor usage**: Track API call patterns to detect anomalies
✅ **Log securely**: Never log tokens or sensitive customer data
✅ **Use HTTPS**: All API calls must use HTTPS (enforced by both APIs)

---

## Next Steps

1. **Review this document** with your team
2. **Request API access** using the templates above
3. **Share credentials** securely via password manager or encrypted channel
4. **I'll build** the automated data fetcher and sync service
5. **Test end-to-end** before production deployment

**Questions?** Let me know if you need any clarification on the requirements!