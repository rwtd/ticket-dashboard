#!/bin/bash
# Quick setup script for Cloud Scheduler automated sync
# Run after deploying to Cloud Run

set -e

echo "🚀 Setting up Cloud Scheduler for Automated Data Sync"
echo "======================================================"
echo ""

# Check if required env vars are set
if [ -z "$GCP_PROJECT_ID" ]; then
    echo "❌ Error: GCP_PROJECT_ID environment variable not set"
    echo "Please run: export GCP_PROJECT_ID=your-project-id"
    exit 1
fi

if [ -z "$GCP_REGION" ]; then
    echo "⚠️  GCP_REGION not set, using default: us-central1"
    GCP_REGION="us-central1"
fi

if [ -z "$SERVICE_URL" ]; then
    echo "❌ Error: SERVICE_URL environment variable not set"
    echo "Please run: export SERVICE_URL=https://your-cloud-run-url"
    echo "Get it from: gcloud run services describe ticket-dashboard --region=\$GCP_REGION --format='value(status.url)'"
    exit 1
fi

SERVICE_ACCOUNT="ticket-dashboard-sa@${GCP_PROJECT_ID}.iam.gserviceaccount.com"

echo "Configuration:"
echo "  Project: $GCP_PROJECT_ID"
echo "  Region: $GCP_REGION"
echo "  Service URL: $SERVICE_URL"
echo "  Service Account: $SERVICE_ACCOUNT"
echo ""

# Check if Cloud Run service exists
echo "🔍 Verifying Cloud Run service..."
if ! gcloud run services describe ticket-dashboard --region=$GCP_REGION --project=$GCP_PROJECT_ID &> /dev/null; then
    echo "❌ Error: Cloud Run service 'ticket-dashboard' not found"
    echo "Please deploy the service first with: git push origin main"
    exit 1
fi
echo "✅ Cloud Run service found"
echo ""

# Enable required APIs
echo "🔌 Enabling required APIs..."
gcloud services enable cloudscheduler.googleapis.com --project=$GCP_PROJECT_ID
echo "✅ Cloud Scheduler API enabled"
echo ""

# Grant Cloud Run Invoker role to service account
echo "🔐 Granting permissions..."
gcloud run services add-iam-policy-binding ticket-dashboard \
  --region=$GCP_REGION \
  --member="serviceAccount:$SERVICE_ACCOUNT" \
  --role="roles/run.invoker" \
  --project=$GCP_PROJECT_ID
echo "✅ Permissions granted"
echo ""

# Create Cloud Scheduler job for incremental sync
echo "📅 Creating Cloud Scheduler job for incremental sync..."
if gcloud scheduler jobs describe firestore-sync --location=$GCP_REGION --project=$GCP_PROJECT_ID &> /dev/null; then
    echo "⚠️  Job 'firestore-sync' already exists. Updating..."
    gcloud scheduler jobs update http firestore-sync \
      --location=$GCP_REGION \
      --schedule="0 */4 * * *" \
      --uri="${SERVICE_URL}/sync" \
      --http-method=POST \
      --oidc-service-account-email=$SERVICE_ACCOUNT \
      --oidc-token-audience="${SERVICE_URL}" \
      --time-zone="America/New_York" \
      --project=$GCP_PROJECT_ID
else
    gcloud scheduler jobs create http firestore-sync \
      --location=$GCP_REGION \
      --schedule="0 */4 * * *" \
      --uri="${SERVICE_URL}/sync" \
      --http-method=POST \
      --oidc-service-account-email=$SERVICE_ACCOUNT \
      --oidc-token-audience="${SERVICE_URL}" \
      --time-zone="America/New_York" \
      --description="Incremental sync from HubSpot/LiveChat to Firestore every 4 hours" \
      --project=$GCP_PROJECT_ID
fi
echo "✅ Scheduler job configured (runs every 4 hours)"
echo ""

# Test the job
echo "🧪 Testing sync job..."
echo "Triggering manual test run..."
gcloud scheduler jobs run firestore-sync --location=$GCP_REGION --project=$GCP_PROJECT_ID

echo ""
echo "⏳ Waiting 10 seconds for sync to start..."
sleep 10

echo ""
echo "📊 Recent logs from Cloud Run:"
gcloud run services logs read ticket-dashboard \
  --region=$GCP_REGION \
  --limit=20 \
  --project=$GCP_PROJECT_ID \
  --format="table(timestamp,severity,textPayload)" || true

echo ""
echo "✅ Setup Complete!"
echo ""
echo "Next Steps:"
echo "1. Monitor the test sync in Cloud Run logs"
echo "2. Check your admin panel at ${SERVICE_URL}/admin to verify data"
echo "3. If test successful, sync will run automatically every 4 hours"
echo ""
echo "Useful Commands:"
echo "  # View scheduler jobs"
echo "  gcloud scheduler jobs list --location=$GCP_REGION"
echo ""
echo "  # Manually trigger sync"
echo "  gcloud scheduler jobs run firestore-sync --location=$GCP_REGION"
echo ""
echo "  # View Cloud Run logs"
echo "  gcloud run services logs read ticket-dashboard --region=$GCP_REGION --limit=50"
echo ""
echo "  # Check Firestore data"
echo "  Visit: ${SERVICE_URL}/admin/data-status"
echo ""