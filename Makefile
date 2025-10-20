# Convenience Makefile for Cloud Run build & deploy
# Usage example:
#   make PROJECT_ID=my-proj REGION=us-central1 SERVICE_NAME=ticket-dashboard AR_REPO=apps all

# Variables
PROJECT_ID ?=
REGION ?=
SERVICE_NAME ?= ticket-dashboard
AR_REPO ?= apps
IMAGE_TAG ?= $(shell git rev-parse --short=12 HEAD)
IMAGE := $(REGION)-docker.pkg.dev/$(PROJECT_ID)/$(AR_REPO)/$(SERVICE_NAME):$(IMAGE_TAG)
WIDGETS_XFO ?= SAMEORIGIN
WIDGETS_FRAME_ANCESTORS ?= 'self' https://*.hubspot.com

# Internal guard for required vars
guard-%:
	@ if [ -z "$(${*})" ]; then echo "Error: $* is not set. Pass '$(*)=...'\nExample: make PROJECT_ID=my-proj REGION=us-central1 all" >&2; exit 1; fi

.PHONY: info ar-create build deploy url all

info:
	@ echo "Config:"
	@ echo "  PROJECT_ID=$(PROJECT_ID)"
	@ echo "  REGION=$(REGION)"
	@ echo "  SERVICE_NAME=$(SERVICE_NAME)"
	@ echo "  AR_REPO=$(AR_REPO)"
	@ echo "  IMAGE_TAG=$(IMAGE_TAG)"
	@ echo "  IMAGE=$(IMAGE)"
	@ echo "  WIDGETS_XFO=$(WIDGETS_XFO)"
	@ echo "  WIDGETS_FRAME_ANCESTORS=$(WIDGETS_FRAME_ANCESTORS)"

ar-create: guard-PROJECT_ID guard-REGION
	@ echo "Ensuring Artifact Registry repo '$(AR_REPO)' exists in '$(REGION)'..."
	@ gcloud artifacts repositories describe "$(AR_REPO)" --location="$(REGION)" >/dev/null 2>&1 || \
	  gcloud artifacts repositories create "$(AR_REPO)" --repository-format=docker --location="$(REGION)" --description="Application containers"

build: guard-PROJECT_ID guard-REGION
	@ echo "Building image with Cloud Build: $(IMAGE)"
	gcloud builds submit --tag "$(IMAGE)" .

deploy: guard-PROJECT_ID guard-REGION
	@ echo "Deploying to Cloud Run: service=$(SERVICE_NAME), image=$(IMAGE)"
	gcloud run deploy "$(SERVICE_NAME)" \
	  --image "$(IMAGE)" \
	  --region "$(REGION)" \
	  --platform managed \
	  --allow-unauthenticated \
	  --min-instances=0 \
	  --max-instances=3 \
	  --concurrency=80 \
	  --cpu=2 \
	  --memory=2Gi \
	  --timeout=900 \
	  --set-env-vars WIDGETS_XFO="$(WIDGETS_XFO)",WIDGETS_FRAME_ANCESTORS="$(WIDGETS_FRAME_ANCESTORS)",GOOGLE_SHEETS_CREDENTIALS_PATH="/app/credentials/service_account_credentials.json" \
	  --update-secrets=/app/credentials/service_account_credentials.json=google-sheets-credentials:latest,GOOGLE_SHEETS_SPREADSHEET_ID=GOOGLE_SHEETS_SPREADSHEET_ID:latest,HUBSPOT_API_KEY=HUBSPOT_API_KEY:latest,LIVECHAT_PAT=LIVECHAT_PAT:latest,GEMINI_API_KEY=GEMINI_API_KEY:latest

url: guard-PROJECT_ID guard-REGION
	@ gcloud run services describe "$(SERVICE_NAME)" --region="$(REGION)" --format='value(status.url)'

all: ar-create build deploy url