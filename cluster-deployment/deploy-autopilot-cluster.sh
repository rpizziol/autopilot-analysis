#!/bin/bash

# This script automates the full setup of an experiment environment.
# It creates a GKE Autopilot cluster and then deploys the necessary
# monitoring tools (kube-state-metrics) using Helm.

# Exit immediately if a command exits with a non-zero status.
set -e

# --- Configuration ---
# Import environment variables from an external file.
source "$(dirname "$0")/../environment.sh"

# Name of the custom values file for the Helm chart.
# This file should be in the same directory as the script.
KSM_VALUES_FILE="ksm-values.yml" 

# --- Phase 1: Create GKE Autopilot Cluster ---
echo ">>> Phase 1: Creating or verifying GKE Autopilot cluster '$CLUSTER_NAME'..."

# Check if the cluster already exists to make the script re-runnable.
if ! gcloud container clusters describe "$CLUSTER_NAME" --region "$REGION" --project "$PROJECT_ID" > /dev/null 2>&1; then
    echo "Cluster not found. Creating a new cluster..."
    gcloud beta container --project "$PROJECT_ID" clusters create-auto "$CLUSTER_NAME" \
      --region "$REGION" \
      --release-channel "$RELEASE_CHANNEL" \
      --tier "$TIER" \
      --network "projects/$PROJECT_ID/global/networks/default" \
      --subnetwork "projects/$PROJECT_ID/regions/$REGION/subnetworks/default"
    echo "Cluster '$CLUSTER_NAME' created successfully."
else
    echo "Cluster '$CLUSTER_NAME' already exists. Skipping creation."
fi

# --- Phase 2: Configure kubectl ---
echo -e "\n>>> Phase 2: Configuring kubectl to connect to the cluster..."
gcloud container clusters get-credentials "$CLUSTER_NAME" --region "$REGION" --project "$PROJECT_ID"
echo "kubectl is now configured to use context for '$CLUSTER_NAME'."

# --- Phase 3: Deploy kube-state-metrics via Helm ---
echo -e "\n>>> Phase 3: Installing monitoring components (kube-state-metrics)..."

# Add the required Helm repository. It's safe to run this multiple times.
echo "Adding prometheus-community Helm repo..."
helm repo add prometheus-community https://prometheus-community.github.io/helm-charts
helm repo update

# Check if the custom values file exists before proceeding.
if [ ! -f "$KSM_VALUES_FILE" ]; then
    echo "ERROR: The Helm values file '$KSM_VALUES_FILE' was not found. Please create it first."
    exit 1
fi

# Use 'helm upgrade --install' which is idempotent.
# It installs the chart if it's not present, or upgrades it if it already is.
echo "Installing/upgrading kube-state-metrics chart using '$KSM_VALUES_FILE'..."
helm upgrade --install kube-state-metrics prometheus-community/kube-state-metrics \
  --namespace default \
  -f "$KSM_VALUES_FILE"

echo -e "\n--- Setup Complete ---"
echo "Your GKE cluster environment is ready for experiments."
echo "You can check the status of the kube-state-metrics service with:"
echo "kubectl get service kube-state-metrics --namespace default"
