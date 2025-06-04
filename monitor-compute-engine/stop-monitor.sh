#!/bin/bash

# Import environment variables
source "$(dirname "$0")/../environment.sh"

# Check if required variables are set
if [[ -z "$INSTANCE_NAME" || -z "$PROJECT_ID" || -z "$ZONE" ]]; then
  echo "Error: INSTANCE_NAME, PROJECT_ID, and ZONE must be set in environment.sh"
  exit 1
fi

# Stop the compute instance
gcloud compute instances stop "$INSTANCE_NAME" --project "$PROJECT_ID" --zone "$ZONE"
