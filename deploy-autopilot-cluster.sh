#!/bin/bash

# Exit immediately if a command exits with a non-zero status
set -e

# Variables for configuration
PROJECT_ID="syda-autopilot"
CLUSTER_NAME="autopilot-cluster-1"
REGION="northamerica-northeast1"
RELEASE_CHANNEL="regular"
TIER="standard"
NETWORK="projects/$PROJECT_ID/global/networks/default"
SUBNETWORK="projects/$PROJECT_ID/regions/$REGION/subnetworks/default"

# Create an Autopilot cluster
gcloud beta container --project "$PROJECT_ID" clusters create-auto "$CLUSTER_NAME" \
  --region "$REGION" \
  --release-channel "$RELEASE_CHANNEL" \
  --tier "$TIER" \
  --enable-ip-access \
  --network "$NETWORK" \
  --subnetwork "$SUBNETWORK"

echo "Autopilot cluster '$CLUSTER_NAME' created successfully in project '$PROJECT_ID' and region '$REGION'."