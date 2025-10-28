# GitHub Actions Automated Deployment Guide

This guide explains how to set up automated deployment to Google Cloud Run using GitHub Actions.

## Overview

The deployment workflow automatically:
- ✅ Triggers on every push to the `main` branch
- ✅ Builds a Docker container using Google Cloud Build
- ✅ Pushes the image to Artifact Registry
- ✅ Deploys to Cloud Run with all required secrets
- ✅ Provides deployment status and service URL

## Prerequisites

1. **Google Cloud Project** with billing enabled
2. **Cloud Run API** enabled
3. **Artifact Registry API** enabled
4. **Cloud Build API** enabled
5. **Service Account** with appropriate permissions
6. **GitHub repository** with admin access

## Required GitHub Secrets

You must configure the following secrets in your GitHub repository:

### Navigate to Repository Settings
1. Go to your repository on GitHub
2. Click **Settings** → **Secrets and variables** → **Actions**
3. Click **New repository secret** for each of the following:

### Secret Configuration

| Secret Name | Description | How to Obtain |
|-------------|-------------|---------------|
| `GCP_PROJECT_ID` | Your GCP project ID | From GCP Console project selector |
| `GCP_REGION` | Deployment region (e.g., `us-central1`) | Choose from [GCP regions](https://cloud.google.com/compute/docs/regions-zones) |
| `GCP_SA_KEY` | Service account JSON key | See "Service Account Setup" below |

### Service Account Setup

The service account needs these IAM roles:

```bash
# Create service account
gcloud iam service-accounts create github-actions-deployer \
  --display-name="GitHub Actions Cloud Run Deployer"

# Get project ID
PROJECT_ID=$(gcloud config get-value project)

# Grant required roles
gcloud projects add-iam-policy-binding ${PROJECT_ID} \
  --member="serviceAccount:github-actions-deployer@${PROJECT_ID}.iam.gserviceaccount.com" \
  --role="roles/run.admin"

gcloud projects add-iam-policy-binding ${PROJECT_ID} \
  --member="serviceAccount:github-actions-deployer@${PROJECT_ID}.iam.gserviceaccount.com" \
  --role="roles/storage.admin"

gcloud projects add-iam-policy-binding ${PROJECT_ID} \
  --member="serviceAccount:github-actions-deployer@${PROJECT_ID}.iam.gserviceaccount.com" \
  --role="roles/artifactregistry.admin"

gcloud projects add-iam-policy-binding ${PROJECT_ID} \
  --member="serviceAccount:github-actions-deployer@${PROJECT_ID}.iam.gserviceaccount.com" \
  --role="roles/cloudbuild.builds.builder"

gcloud projects add-iam-policy-binding ${PROJECT_ID} \
  --member="serviceAccount:github-actions-deployer@${PROJECT_ID}.iam.gserviceaccount.com" \
  --role="roles/iam.serviceAccountUser"

# Create and download key
gcloud iam service-accounts keys create github-actions-key.json \
  --iam-account=github-actions-deployer@${PROJECT_ID}.iam.gserviceaccount.com

# Display key (copy this to GitHub secret GCP_SA_KEY)
cat github-actions-key.json

# IMPORTANT: Delete the local key file after copying to GitHub
rm github-actions-key.json
```

## Cloud Run Secrets (Already Configured)

The workflow expects these secrets to exist in Google Cloud Secret Manager:

| Secret Name | Purpose |
|-------------|---------|
| `google-sheets-credentials` | Service account for Google Sheets API |
| `GOOGLE_SHEETS_SPREADSHEET_ID` | Target spreadsheet ID |
| `HUBSPOT_API_KEY` | HubSpot API access |
| `LIVECHAT_PAT` | LiveChat Personal Access Token |
| `GEMINI_API_KEY` | Google Gemini API key |
| `ADMIN_PASSWORD` | Admin panel authentication password |

These should already be configured if you've deployed manually before. If not, create them:

```bash
# Example: Create a secret from a file
gcloud secrets create google-sheets-credentials \
  --data-file=service_account_credentials.json

# Example: Create a secret from a string
echo -n "your-api-key-here" | gcloud secrets create HUBSPOT_API_KEY --data-file=-

# Grant Cloud Run access to secrets
PROJECT_NUMBER=$(gcloud projects describe ${PROJECT_ID} --format="value(projectNumber)")
SERVICE_ACCOUNT="${PROJECT_NUMBER}-compute@developer.gserviceaccount.com"

for secret in google-sheets-credentials GOOGLE_SHEETS_SPREADSHEET_ID HUBSPOT_API_KEY LIVECHAT_PAT GEMINI_API_KEY; do
  gcloud secrets add-iam-policy-binding ${secret} \
    --member="serviceAccount:${SERVICE_ACCOUNT}" \
    --role="roles/secretmanager.secretAccessor"
done
```

## Workflow Configuration

The workflow is defined in `.github/workflows/deploy-cloud-run.yml` and includes:

### Triggers
- **Automatic**: Every push to `main` branch
- **Manual**: Via "Actions" tab → "Deploy to Cloud Run" → "Run workflow"

### Environment Variables
Located at the top of the workflow file:
```yaml
env:
  PROJECT_ID: ${{ secrets.GCP_PROJECT_ID }}
  REGION: ${{ secrets.GCP_REGION }}
  SERVICE_NAME: ticket-dashboard
  AR_REPO: apps
```

### Deployment Steps
1. **Checkout code** from repository
2. **Authenticate** to Google Cloud using service account
3. **Configure Docker** for Artifact Registry
4. **Create Artifact Registry repository** if it doesn't exist
5. **Build container image** using Cloud Build
6. **Deploy to Cloud Run** with all configurations
7. **Output service URL** in deployment summary

## Deployment Resources

The workflow deploys with these specifications:

| Resource | Value |
|----------|-------|
| Memory | 2 GiB |
| CPU | 2 cores |
| Concurrency | 80 requests per instance |
| Min Instances | 0 (scales to zero) |
| Max Instances | 3 |
| Timeout | 900 seconds (15 minutes) |
| Authentication | Allow unauthenticated |

## Usage

### Automatic Deployment
Simply push to the `main` branch:
```bash
git add .
git commit -m "feat: add new feature"
git push origin main
```

The deployment will start automatically. Monitor progress in:
- GitHub: **Actions** tab
- GCP: **Cloud Build** history
- GCP: **Cloud Run** services

### Manual Deployment
1. Go to **Actions** tab in GitHub
2. Select **Deploy to Cloud Run** workflow
3. Click **Run workflow** button
4. Select branch (usually `main`)
5. Click **Run workflow**

### Monitoring Deployment

#### GitHub Actions
- Navigate to **Actions** tab
- Click on the running workflow
- View real-time logs for each step
- See deployment summary with service URL

#### Google Cloud Console
```bash
# View Cloud Build history
gcloud builds list --limit=5

# View Cloud Run services
gcloud run services list

# View service details
gcloud run services describe ticket-dashboard --region=us-central1

# View service logs
gcloud run services logs read ticket-dashboard --region=us-central1
```

## Troubleshooting

### Build Fails
1. Check Cloud Build logs in GCP Console
2. Verify Dockerfile is valid
3. Ensure all dependencies are in requirements.txt

### Deployment Fails
1. Verify all secrets exist in Secret Manager
2. Check service account has required permissions
3. Ensure Cloud Run API is enabled

### Service Won't Start
1. View service logs: `gcloud run services logs read ticket-dashboard`
2. Check for missing environment variables
3. Verify secrets are mounted correctly
4. Test container locally: `docker build -t test . && docker run -p 8080:8080 test`

### Permission Denied Errors
```bash
# Verify service account roles
gcloud projects get-iam-policy ${PROJECT_ID} \
  --flatten="bindings[].members" \
  --filter="bindings.members:serviceAccount:github-actions-deployer@*"
```

## Cost Optimization

The workflow uses:
- **Cloud Build**: ~$0.003/build-minute (first 120 minutes/day free)
- **Cloud Run**: Pay per request and compute time
- **Artifact Registry**: $0.10/GB/month storage

With these settings:
- Min instances = 0: No charges when idle
- Max instances = 3: Limits maximum concurrent cost
- Scales to zero: Only pay for actual usage

## Advanced Configuration

### Custom Build Settings
Modify the Cloud Build step in `.github/workflows/deploy-cloud-run.yml`:
```yaml
- name: Build Image with Cloud Build
  run: |
    gcloud builds submit \
      --tag "${IMAGE}" \
      --timeout=20m \
      --machine-type=E2_HIGHCPU_8
```

### Custom Deployment Settings
Modify the Cloud Run deploy step:
```yaml
gcloud run deploy ${{ env.SERVICE_NAME }} \
  --memory=4Gi \              # Increase memory
  --cpu=4 \                   # Increase CPU
  --max-instances=10          # Allow more scaling
```

### Environment-Specific Deployments
Create separate workflows for staging/production:
```yaml
# .github/workflows/deploy-staging.yml
on:
  push:
    branches: [develop]
env:
  SERVICE_NAME: ticket-dashboard-staging
```

## Security Best Practices

1. ✅ **Never commit credentials** to repository
2. ✅ **Use Secret Manager** for all sensitive data
3. ✅ **Rotate service account keys** regularly
4. ✅ **Limit service account permissions** to minimum required
5. ✅ **Enable binary authorization** for production
6. ✅ **Review Cloud Run IAM policies** periodically
7. ✅ **Monitor Cloud Build logs** for suspicious activity

## Additional Resources

- [Cloud Run Documentation](https://cloud.google.com/run/docs)
- [Cloud Build Documentation](https://cloud.google.com/build/docs)
- [GitHub Actions Documentation](https://docs.github.com/actions)
- [Artifact Registry Documentation](https://cloud.google.com/artifact-registry/docs)
- [Secret Manager Documentation](https://cloud.google.com/secret-manager/docs)

## Support

For issues with:
- **This workflow**: Create an issue in the repository
- **Cloud Run**: Check [Cloud Run troubleshooting](https://cloud.google.com/run/docs/troubleshooting)
- **GitHub Actions**: Check [Actions troubleshooting](https://docs.github.com/actions/monitoring-and-troubleshooting-workflows)