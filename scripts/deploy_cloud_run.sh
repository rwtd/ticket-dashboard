#!/usr/bin/env bash
# deploy_cloud_run.sh - Build and deploy to Cloud Run via gcloud in one command
# Requirements: gcloud CLI authenticated and configured with appropriate permissions
# Usage examples:
#   bash scripts/deploy_cloud_run.sh
#   PROJECT_ID=my-proj REGION=us-central1 SERVICE_NAME=ticket-dashboard AR_REPO=apps bash scripts/deploy_cloud_run.sh
#   bash scripts/deploy_cloud_run.sh --project-id my-proj --region us-central1 --service ticket-dashboard --ar-repo apps --image-tag test1 --no-allow-unauth
#
# Environment variables (or flags):
#   PROJECT_ID (required)
#   REGION (required)
#   SERVICE_NAME (default: ticket-dashboard)
#   AR_REPO (required)
#   IMAGE_TAG (default: current git sha)
#   ALLOW_UNAUTH (default: true)
#   WIDGETS_XFO (default: SAMEORIGIN)
#   WIDGETS_FRAME_ANCESTORS (default: 'self' https://*.hubspot.com)

set -euo pipefail

# Defaults
PROJECT_ID="${PROJECT_ID:-}"
REGION="${REGION:-}"
SERVICE_NAME="${SERVICE_NAME:-ticket-dashboard}"
AR_REPO="${AR_REPO:-}"
IMAGE_TAG="${IMAGE_TAG:-}"
ALLOW_UNAUTH="${ALLOW_UNAUTH:-true}"
WIDGETS_XFO="${WIDGETS_XFO:-SAMEORIGIN}"
WIDGETS_FRAME_ANCESTORS="${WIDGETS_FRAME_ANCESTORS:-'self' https://*.hubspot.com}"

usage() {
  cat >&2 <<'EOF'
Build and deploy to Cloud Run using gcloud.

Flags:
  -p, --project-id VALUE          GCP Project ID (required if env PROJECT_ID not set)
  -r, --region VALUE              GCP Region (required if env REGION not set)
  -s, --service VALUE             Cloud Run service name (default: ticket-dashboard)
  -a, --ar-repo VALUE             Artifact Registry repo name (required if env AR_REPO not set)
  -t, --image-tag VALUE           Container image tag (default: current git sha)
      --allow-unauth              Allow unauthenticated invocations (default)
      --no-allow-unauth           Disable unauthenticated invocations
      --widgets-xfo VALUE         WIDGETS_XFO env var (default: SAMEORIGIN)
      --widgets-frame-ancestors VALUE
                                  WIDGETS_FRAME_ANCESTORS env var (default: 'self' https://*.hubspot.com)
  -h, --help                      Show help

Environment variables alternative:
  PROJECT_ID, REGION, SERVICE_NAME, AR_REPO, IMAGE_TAG, ALLOW_UNAUTH, WIDGETS_XFO, WIDGETS_FRAME_ANCESTORS
EOF
}

# Parse arguments
while [[ $# -gt 0 ]]; do
  case "$1" in
    -p|--project-id) PROJECT_ID="${2:-}"; shift 2 ;;
    -r|--region) REGION="${2:-}"; shift 2 ;;
    -s|--service) SERVICE_NAME="${2:-}"; shift 2 ;;
    -a|--ar-repo) AR_REPO="${2:-}"; shift 2 ;;
    -t|--image-tag) IMAGE_TAG="${2:-}"; shift 2 ;;
    --allow-unauth) ALLOW_UNAUTH="true"; shift 1 ;;
    --no-allow-unauth) ALLOW_UNAUTH="false"; shift 1 ;;
    --widgets-xfo) WIDGETS_XFO="${2:-}"; shift 2 ;;
    --widgets-frame-ancestors) WIDGETS_FRAME_ANCESTORS="${2:-}"; shift 2 ;;
    -h|--help) usage; exit 0 ;;
    *) echo "Unknown option: $1" >&2; usage; exit 2 ;;
  esac
done

# Compute defaults
if [[ -z "${IMAGE_TAG}" ]]; then
  if command -v git >/dev/null 2>&1; then
    IMAGE_TAG="$(git rev-parse --short=12 HEAD 2>/dev/null || date +%s)"
  else
    IMAGE_TAG="$(date +%s)"
  fi
fi

# Validate required variables
if [[ -z "${PROJECT_ID}" || -z "${REGION}" || -z "${AR_REPO}" ]]; then
  echo "Error: PROJECT_ID, REGION, and AR_REPO are required." >&2
  echo "Example: PROJECT_ID=my-proj REGION=us-central1 AR_REPO=apps bash scripts/deploy_cloud_run.sh" >&2
  exit 1
fi

IMAGE="${REGION}-docker.pkg.dev/${PROJECT_ID}/${AR_REPO}/${SERVICE_NAME}:${IMAGE_TAG}"

echo "Configuration:"
echo "  PROJECT_ID=${PROJECT_ID}"
echo "  REGION=${REGION}"
echo "  SERVICE_NAME=${SERVICE_NAME}"
echo "  AR_REPO=${AR_REPO}"
echo "  IMAGE_TAG=${IMAGE_TAG}"
echo "  IMAGE=${IMAGE}"
echo "  ALLOW_UNAUTH=${ALLOW_UNAUTH}"
echo "  WIDGETS_XFO=${WIDGETS_XFO}"
echo "  WIDGETS_FRAME_ANCESTORS=${WIDGETS_FRAME_ANCESTORS}"

# Ensure Artifact Registry repo exists
if ! gcloud artifacts repositories describe "${AR_REPO}" --location="${REGION}" >/dev/null 2>&1; then
  echo "Creating Artifact Registry repo ${AR_REPO} in ${REGION}..."
  gcloud artifacts repositories create "${AR_REPO}" \
    --repository-format=docker \
    --location="${REGION}" \
    --description="Application containers"
else
  echo "Artifact Registry repo ${AR_REPO} already exists in ${REGION}"
fi

# Build
echo "Building image with Cloud Build..."
gcloud builds submit --tag "${IMAGE}" .

# Deploy
AUTH_FLAG=()
if [[ "${ALLOW_UNAUTH}" == "true" ]]; then
  AUTH_FLAG=(--allow-unauthenticated)
fi

echo "Deploying to Cloud Run..."
gcloud run deploy "${SERVICE_NAME}" \
  --region "${REGION}" \
  --image "${IMAGE}" \
  --platform managed \
  "${AUTH_FLAG[@]}" \
  --min-instances=0 \
  --max-instances=3 \
  --concurrency=80 \
  --cpu=1 \
  --memory=512Mi \
  --set-env-vars "WIDGETS_XFO=${WIDGETS_XFO},WIDGETS_FRAME_ANCESTORS=${WIDGETS_FRAME_ANCESTORS}"

# Print URL
SERVICE_URL="$(gcloud run services describe "${SERVICE_NAME}" --region="${REGION}" --format='value(status.url)')"
echo "Service URL: ${SERVICE_URL}"