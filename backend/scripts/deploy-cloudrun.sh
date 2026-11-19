#! /usr/bin/env bash
# Deploys the site on Google Cloud Run from this computer.
#
# Needs: Docker running, the gcloud CLI logged in (gcloud auth login), and
# an env file (never committed) with DATABASE_URL, SECRET_KEY,
# GEMINI_API_KEY and PROJECT_NAME, one KEY: "value" per line (YAML).
#
#   bash backend/scripts/deploy-cloudrun.sh <google-project-id> <env-file.yaml>
#
# Cost control: one instance at most, CPU billed only while a request is
# handled (the free tier covers 180 000 vCPU-seconds a month), and a spend
# cap set in the console. Readings happen inside the request
# (READ_IN_REQUEST), because the CPU is throttled once the answer is sent.

set -euo pipefail

PROJECT="$1"
ENV_FILE="$2"
REGION="europe-west1"
SERVICE="factures-ia"
REPO="factures-ia"
IMAGE="$REGION-docker.pkg.dev/$PROJECT/$REPO/$SERVICE:$(git rev-parse --short HEAD)"

cd "$(dirname "$0")/../.."

gcloud config set project "$PROJECT"
gcloud services enable run.googleapis.com artifactregistry.googleapis.com \
  cloudscheduler.googleapis.com

gcloud artifacts repositories describe "$REPO" --location "$REGION" >/dev/null 2>&1 ||
  gcloud artifacts repositories create "$REPO" --location "$REGION" \
    --repository-format docker

gcloud auth configure-docker "$REGION-docker.pkg.dev" --quiet
docker build -f backend/Dockerfile -t "$IMAGE" .
docker push "$IMAGE"

gcloud run deploy "$SERVICE" \
  --image "$IMAGE" \
  --region "$REGION" \
  --allow-unauthenticated \
  --cpu 1 \
  --memory 1Gi \
  --min-instances 0 \
  --max-instances 1 \
  --concurrency 20 \
  --timeout 600 \
  --env-vars-file "$ENV_FILE" \
  --update-env-vars READ_IN_REQUEST=true

URL=$(gcloud run services describe "$SERVICE" --region "$REGION" --format 'value(status.url)')
gcloud run services update "$SERVICE" --region "$REGION" \
  --update-env-vars "FRONTEND_HOST=$URL"

# A visit every 10 minutes keeps the instance warm: idle instances are kept
# for a while, so visitors never wait for a cold start.
gcloud scheduler jobs describe keep-warm --location "$REGION" >/dev/null 2>&1 ||
  gcloud scheduler jobs create http keep-warm \
    --location "$REGION" \
    --schedule "*/10 * * * *" \
    --http-method GET \
    --uri "$URL/api/v1/utils/health-check/"

# Only the latest image is kept, to stay under the free storage.
gcloud artifacts docker images list "$REGION-docker.pkg.dev/$PROJECT/$REPO/$SERVICE" \
  --sort-by ~CREATE_TIME --format 'value(version)' | tail -n +2 |
  while read -r digest; do
    gcloud artifacts docker images delete \
      "$REGION-docker.pkg.dev/$PROJECT/$REPO/$SERVICE@$digest" --quiet --delete-tags
  done

echo "En ligne : $URL"
