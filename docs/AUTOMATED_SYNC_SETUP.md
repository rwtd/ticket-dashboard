# Automated Data Sync Setup for Cloud Run

This guide sets up automated data synchronization from HubSpot/LiveChat APIs to Firestore using Google Cloud Scheduler.

## Architecture

```
Cloud Scheduler (cron) → Cloud Run /sync endpoint → Firestore
Every 4 hours              Incremental sync      ↓
                                            Export to Sheets (optional)
```

## Current Issue

Your Firestore data is stale (last sync: Oct 17, 2025). You need automated syncs running to keep data current.

## Solution: Cloud Scheduler Setup

### Step 1: Verify Your Cloud Run Service is Deployed

```bash
# Check if service is running
gcloud run services describe ticket-dashboard --region=us-central1

# Should show: Status: Ready
```

### Step 2: Create Cloud Scheduler Job

```bash
# Set variables
export GCP_PROJECT_ID="your-project-id"
export GCP_REGION="us-central1"
export SERVICE_URL="https://ticket-dashboard-xxxxx-uc.a.run.app"  # Your Cloud Run URL

# Create scheduler job for incremental sync (every 4 hours)
gcloud scheduler jobs create http firestore-sync \
  --location=${GCP_REGION} \
  --schedule="0 */4 * * *" \
  --uri="${SERVICE_URL}/sync" \
  --http-method=POST \
  --oidc-service-account-email=ticket-dashboard-sa@${GCP_PROJECT_ID}.iam.gserviceaccount.com \
  --oidc-token-audience="${SERVICE_URL}" \
  --time-zone="America/New_York" \
  --description="Incremental sync from HubSpot/LiveChat to Firestore every 4 hours"
```

### Step 3: Test the Scheduler Job

```bash
# Manually trigger the job to test
gcloud scheduler jobs run firestore-sync --location=${GCP_REGION}

# Check logs
gcloud run services logs read ticket-dashboard --region=${GCP_REGION} --limit=50
```

### Step 4: Verify Data is Syncing

```bash
# Check Firestore via gcloud
gcloud firestore operations list

# Or use the admin panel
# Navigate to: https://your-service.com/admin
# Login with ADMIN_PASSWORD
# Check "Data Status" section
```

## Schedule Options

### Recommended: Every 4 Hours
```
Schedule: 0 */4 * * *
Description: Balanced - fresh data without excessive API calls
Runs at: 00:00, 04:00, 08:00, 12:00, 16:00, 20:00 (your timezone)
```

### Alternative: Every 2 Hours (High Frequency)
```bash
gcloud scheduler jobs update http firestore-sync \
  --location=${GCP_REGION} \
  --schedule="0 */2 * * *"
```

### Alternative: Once Daily (Low Frequency)
```bash
gcloud scheduler jobs update http firestore-sync \
  --location=${GCP_REGION} \
  --schedule="0 2 * * *"
  # Runs at 2 AM daily
```

## Manual Sync Options

### Option 1: Via Admin Panel
1. Navigate to `https://your-service.com/admin`
2. Login with ADMIN_PASSWORD
3. Click "Trigger Incremental Sync" or "Trigger Full Sync"

### Option 2: Via CLI (Incremental)
```bash
curl -X POST https://your-service.com/sync \
  -H "Authorization: Bearer $(gcloud auth print-identity-token)"
```

### Option 3: Via CLI (Full Sync - Initial Setup Only)
```bash
curl -X POST https://your-service.com/sync/full \
  -H "Authorization: Bearer $(gcloud auth print-identity-token)"
```

## Monitoring

### View Scheduler Job Status
```bash
# List all jobs
gcloud scheduler jobs list --location=${GCP_REGION}

# Describe specific job
gcloud scheduler jobs describe firestore-sync --location=${GCP_REGION}

# View recent executions
gcloud logging read "resource.type=cloud_scheduler_job AND resource.labels.job_id=firestore-sync" \
  --limit=10 \
  --format=json
```

### View Sync Logs
```bash
# Recent sync activity
gcloud run services logs read ticket-dashboard \
  --region=${GCP_REGION} \
  --limit=100 \
  --filter="textPayload:sync"

# Errors only
gcloud run services logs read ticket-dashboard \
  --region=${GCP_REGION} \
  --limit=50 \
  --filter="severity>=ERROR"
```

## Troubleshooting

### Issue: "Permission Denied" when Scheduler Triggers
**Solution:** Ensure service account has proper permissions:

```bash
# Grant Cloud Run Invoker role to service account
gcloud run services add-iam-policy-binding ticket-dashboard \
  --region=${GCP_REGION} \
  --member="serviceAccount:ticket-dashboard-sa@${GCP_PROJECT_ID}.iam.gserviceaccount.com" \
  --role="roles/run.invoker"
```

### Issue: Sync Runs But No Data Updates
**Solution:** Check API credentials are correctly mounted:

```bash
# Verify secrets are mounted
gcloud run services describe ticket-dashboard \
  --region=${GCP_REGION} \
  --format="value(spec.template.spec.containers[0].env)"

# Should show: HUBSPOT_API_KEY, LIVECHAT_PAT, etc.
```

### Issue: Sync Times Out
**Solution:** Increase Cloud Run timeout:

```bash
gcloud run services update ticket-dashboard \
  --region=${GCP_REGION} \
  --timeout=900  # 15 minutes
```

### Issue: Too Many API Calls
**Solution:** Reduce sync frequency or implement rate limiting:

```bash
# Change to every 6 hours
gcloud scheduler jobs update http firestore-sync \
  --location=${GCP_REGION} \
  --schedule="0 */6 * * *"
```

## Cost Considerations

### Cloud Scheduler
- **Free tier:** 3 jobs per month
- **Paid:** $0.10 per job per month
- **Executions:** Free (included)

**Your cost:** $0.10/month (1 job)

### Cloud Run
- **Sync duration:** ~30 seconds (incremental), ~5 minutes (full)
- **Frequency:** 6 times/day = 180 times/month
- **CPU/Memory:** Minimal during sync
- **Network:** API calls to HubSpot/LiveChat (within your API limits)

**Estimated cost:** $0.50-$2.00/month additional

### Firestore
- **Document writes:** ~100-500 per sync (incremental)
- **Document reads:** Minimal (dashboard queries)
- **Storage:** ~1-5 GB

**Estimated cost:** $1-3/month

**Total additional cost:** ~$1.60-$5.10/month for automated sync

## Initial Setup Checklist

- [ ] Cloud Run service deployed with all secrets
- [ ] Service account has Cloud Run Invoker role
- [ ] Created Cloud Scheduler job
- [ ] Tested manual trigger
- [ ] Verified data appears in Firestore
- [ ] Confirmed admin panel shows updated data
- [ ] Set up monitoring/alerting (optional)

## Next Steps

After setup:
1. **Run initial full sync** via admin panel or `/sync/full` endpoint
2. **Verify data** in admin panel Data Status section
3. **Monitor first few automated runs** to ensure they complete successfully
4. **Set up optional Sheets export** if you want automated Google Sheets updates

## Optional: Automated Sheets Export

If you want to also export to Google Sheets automatically:

```bash
# Create second scheduler job for Sheets export (daily)
gcloud scheduler jobs create http firestore-to-sheets-export \
  --location=${GCP_REGION} \
  --schedule="0 3 * * *" \
  --uri="${SERVICE_URL}/admin/trigger-sheets-export" \
  --http-method=POST \
  --oidc-service-account-email=ticket-dashboard-sa@${GCP_PROJECT_ID}.iam.gserviceaccount.com \
  --oidc-token-audience="${SERVICE_URL}" \
  --time-zone="America/New_York" \
  --description="Daily export from Firestore to Google Sheets"
```

## Support

For issues:
1. Check Cloud Run logs: `gcloud run services logs read ticket-dashboard`
2. Check Scheduler execution history
3. Verify API credentials in secrets
4. Test manual sync via admin panel
5. Review Firestore data directly in console

## References

- [Cloud Scheduler Documentation](https://cloud.google.com/scheduler/docs)
- [Cloud Run Authentication](https://cloud.google.com/run/docs/authenticating/service-to-service)
- [Firestore Documentation](https://cloud.google.com/firestore/docs)