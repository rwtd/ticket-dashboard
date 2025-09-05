# 🚀 Google Cloud Run Deployment Guide

Complete step-by-step guide to deploy the Ticket Dashboard with AI Assistant to Google Cloud Run.

## 🎯 Why Cloud Run?

✅ **Free Tier Compatible** - 2M requests/month, 360k GB-seconds compute  
✅ **Google Workspace Integration** - Built-in OAuth, domain restrictions  
✅ **Enterprise Security** - Secret Manager, encrypted data, audit logs  
✅ **Auto-scaling** - Scale to zero when not used, handle traffic spikes  
✅ **$0/month** - Expected usage stays within free tier limits  

## 📋 Prerequisites

- Google Cloud account with billing enabled (free tier)
- Google Workspace domain (for company-restricted access)
- Gemini API key
- Git repository access
- `gcloud` CLI installed

## 🚀 Quick Start (30 Minutes)

### Step 1: Set up Google Cloud Project (5 minutes)

```bash
# Set your project details
export PROJECT_ID="ticket-dashboard-prod"
export REGION="us-central1"
export SERVICE_NAME="ticket-dashboard"

# Create project
gcloud projects create $PROJECT_ID
gcloud config set project $PROJECT_ID

# Enable billing (required even for free tier)
# Visit: https://console.cloud.google.com/billing/linkedaccount?project=$PROJECT_ID

# Enable required APIs
gcloud services enable cloudbuild.googleapis.com
gcloud services enable run.googleapis.com
gcloud services enable secretmanager.googleapis.com
gcloud services enable sheets.googleapis.com
gcloud services enable oauth2.googleapis.com
gcloud services enable containerregistry.googleapis.com
```

### Step 2: Configure Secrets (5 minutes)

```bash
# Store your Gemini API key securely
echo -n "YOUR_ACTUAL_GEMINI_API_KEY" | gcloud secrets create gemini-api-key --data-file=-

# Grant Cloud Run access to secrets
gcloud projects add-iam-policy-binding $PROJECT_ID \
    --member="serviceAccount:$(gcloud projects describe $PROJECT_ID --format='value(projectNumber)')-compute@developer.gserviceaccount.com" \
    --role="roles/secretmanager.secretAccessor"
```

### Step 3: Build and Deploy (20 minutes)

```bash
# Clone your repository (if not already local)
git clone https://github.com/rwtd/ticket-dashboard.git
cd ticket-dashboard

# Build using Cloud Build (automatic from cloudbuild.yaml)
gcloud builds submit --config cloudbuild.yaml

# Your service will be automatically deployed!
# Get the service URL
gcloud run services describe $SERVICE_NAME --region=$REGION --format='value(status.url)'
```

## 🔐 Security Setup

### Google OAuth Configuration

1. **Create OAuth Consent Screen**:
   ```bash
   # Visit Google Cloud Console > APIs & Services > OAuth consent screen
   # https://console.cloud.google.com/apis/credentials/consent?project=$PROJECT_ID
   ```
   
2. **Configure OAuth Application**:
   - Application type: Web application
   - Authorized domains: Add your company domain
   - Scopes: `openid`, `email`, `profile`

3. **Create OAuth Credentials**:
   ```bash
   # Visit Google Cloud Console > APIs & Services > Credentials
   # Create OAuth 2.0 Client ID
   # Add your Cloud Run URL to authorized redirect URIs
   ```

4. **Restrict to Company Domain**:
   ```bash
   # In OAuth consent screen, set:
   # - User type: Internal (G Suite/Google Workspace only)
   # - Authorized domains: yourdomain.com
   ```

### Environment Variables for Production

```bash
# Update Cloud Run service with additional environment variables
gcloud run services update $SERVICE_NAME \
    --region=$REGION \
    --set-env-vars="FLASK_ENV=production,ENABLE_OAUTH=true,COMPANY_DOMAIN=yourdomain.com"
```

## 💰 Cost Optimization

### Free Tier Limits
- **Cloud Run**: 2M requests/month, 360k GB-seconds
- **Cloud Build**: 120 build-minutes/day
- **Container Registry**: 0.5GB storage
- **Secret Manager**: 6 active secrets
- **Cloud Storage**: 5GB (for file uploads)

### Expected Usage (Stays Free!)
- **Requests**: ~50k/month (well under 2M limit)
- **Compute**: ~30k GB-seconds/month (under 360k limit)  
- **Storage**: ~2GB data files (under 5GB limit)
- **Secrets**: 3 secrets (under 6 limit)

## 📊 Monitoring Setup

### Basic Monitoring (Included Free)
```bash
# Enable Cloud Monitoring
gcloud services enable monitoring.googleapis.com

# Create uptime check
gcloud alpha monitoring uptime create-config \
    --display-name="Ticket Dashboard Uptime" \
    --monitored-resource-type="url" \
    --monitored-resource-labels="url=https://your-service-url.run.app"
```

### Performance Monitoring
```bash
# View logs
gcloud logs read "resource.type=cloud_run_revision AND resource.labels.service_name=$SERVICE_NAME" --limit 50

# Monitor resource usage  
gcloud run services describe $SERVICE_NAME --region=$REGION --format="table(metadata.name,status.latestReadyRevisionName,spec.template.spec.containers[0].resources.limits.memory,spec.template.spec.containers[0].resources.limits.cpu)"
```

## 🔧 Production Configuration

### Environment Variables
```bash
# Production environment setup
gcloud run services update $SERVICE_NAME \
    --region=$REGION \
    --set-env-vars="
FLASK_ENV=production,
PORT=8080,
ENABLE_OAUTH=true,
COMPANY_DOMAIN=yourdomain.com,
LOG_LEVEL=INFO,
MAX_UPLOAD_SIZE=10485760
" \
    --memory=1Gi \
    --cpu=1 \
    --max-instances=10 \
    --min-instances=0 \
    --concurrency=80 \
    --timeout=300s
```

### Custom Domain (Optional)
```bash
# Map custom domain
gcloud run domain-mappings create --service=$SERVICE_NAME --domain=dashboard.yourdomain.com --region=$REGION

# Add SSL certificate (automatic with Google-managed certificates)
```

## 🚨 Troubleshooting

### Common Issues

1. **Build Fails**:
   ```bash
   # Check build logs
   gcloud builds list --limit=5
   gcloud builds log [BUILD_ID]
   ```

2. **Service Won't Start**:
   ```bash
   # Check service logs
   gcloud logs read "resource.type=cloud_run_revision" --limit=20
   ```

3. **Authentication Issues**:
   ```bash
   # Verify secrets
   gcloud secrets list
   gcloud secrets versions access latest --secret="gemini-api-key"
   ```

4. **Memory Issues**:
   ```bash
   # Increase memory limit
   gcloud run services update $SERVICE_NAME --memory=2Gi --region=$REGION
   ```

## 🎯 Success Metrics

After deployment, you should see:
- ✅ Service responding at your Cloud Run URL
- ✅ AI Assistant working with Gemini API
- ✅ File uploads processing correctly
- ✅ Google Sheets integration functional
- ✅ OAuth restricting access to company domain
- ✅ Response times under 2 seconds
- ✅ Zero errors in Cloud Logs

## 📱 Next Steps

1. **Test the deployment** with your team
2. **Set up monitoring alerts** for errors/downtime
3. **Configure automated backups** for conversation data
4. **Set up CI/CD pipeline** for automatic deployments
5. **Share the URL** with your colleagues

## 🔗 Useful Commands

```bash
# Get service URL
gcloud run services describe $SERVICE_NAME --region=$REGION --format='value(status.url)'

# View logs in real-time
gcloud logs tail "resource.type=cloud_run_revision AND resource.labels.service_name=$SERVICE_NAME"

# Update service
gcloud run services update $SERVICE_NAME --region=$REGION [OPTIONS]

# Delete service (if needed)
gcloud run services delete $SERVICE_NAME --region=$REGION
```

## 🎉 You're Live!

Once deployed, your team will have access to:
- **Conversational AI** that understands your support data
- **Interactive dashboards** with advanced analytics  
- **Google Sheets integration** for collaborative workflows
- **Enterprise security** with domain-restricted access
- **Auto-scaling performance** that handles any workload

**Estimated Total Deployment Time**: 30-45 minutes  
**Monthly Cost**: $0 (within free tier)  
**Team Impact**: Immediate access to AI-powered support analytics! 🚀