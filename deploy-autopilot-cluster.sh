#!/bin/bash

# Exit immediately if a command exits with a non-zero status
set -e

# Import environment variables
source "$(dirname "$0")/environment.sh"

# Create an Autopilot cluster
gcloud beta container --project "$PROJECT_ID" clusters create-auto "$CLUSTER_NAME" \
  --region "$REGION" \
  --release-channel "$RELEASE_CHANNEL" \
  --tier "$TIER" \
  --enable-ip-access \
  --network "projects/$PROJECT_ID/global/networks/default" \
  --subnetwork "projects/$PROJECT_ID/regions/$REGION/subnetworks/default"

echo "Autopilot cluster '$CLUSTER_NAME' created successfully in project '$PROJECT_ID' and region '$REGION'."