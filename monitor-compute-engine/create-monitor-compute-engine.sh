#!/bin/bash

# Script to create a Google Compute Engine instance named instance-1
# using Ubuntu 24.04 LTS Minimal.

# Define variables for clarity and easier modification
INSTANCE_NAME="instance-1"
PROJECT_ID="syda-autopilot"
ZONE="northamerica-northeast1-a"
MACHINE_TYPE="e2-medium"
SERVICE_ACCOUNT_EMAIL="1036682486306-compute@developer.gserviceaccount.com"

# Image details for Ubuntu 24.04 LTS Minimal
IMAGE="projects/ubuntu-os-cloud/global/images/ubuntu-minimal-2404-noble-amd64-v20250523"

DISK_SIZE="10" # GB
DISK_TYPE="pd-balanced"
DISK_RESOURCE_POLICY="projects/syda-autopilot/regions/northamerica-northeast1/resourcePolicies/default-schedule-1"

# Scopes for the service account
SCOPES="https://www.googleapis.com/auth/devstorage.read_only,https://www.googleapis.com/auth/logging.write,https://www.googleapis.com/auth/monitoring.write,https://www.googleapis.com/auth/service.management.readonly,https://www.googleapis.com/auth/servicecontrol,https://www.googleapis.com/auth/trace.append"

echo "Attempting to create GCE instance: $INSTANCE_NAME in project $PROJECT_ID zone $ZONE..."
echo "Using Ubuntu 24.04 LTS Minimal (latest from family: $IMAGE_FAMILY, project: $IMAGE_PROJECT)"

gcloud compute instances create "$INSTANCE_NAME" \
  --project="$PROJECT_ID" \
  --zone="$ZONE" \
  --machine-type="$MACHINE_TYPE" \
  --network-interface=network-tier=PREMIUM,stack-type=IPV4_ONLY,subnet=default \
  --metadata=enable-osconfig=TRUE \
  --maintenance-policy=MIGRATE \
  --provisioning-model=STANDARD \
  --service-account="$SERVICE_ACCOUNT_EMAIL" \
  --scopes="$SCOPES" \
  --create-disk=auto-delete=yes,boot=yes,device-name="$INSTANCE_NAME",disk-resource-policy="$DISK_RESOURCE_POLICY",image="$IMAGE",mode=rw,size="${DISK_SIZE}",type="$DISK_TYPE" \
  --no-shielded-secure-boot \
  --shielded-vtpm \
  --shielded-integrity-monitoring \
  --labels=goog-ops-agent-policy=v2-x86-template-1-4-0,goog-ec-src=vm_add-gcloud \
  --reservation-affinity=any

# Check the exit status of the gcloud command
if [ $? -eq 0 ]; then
    echo "Instance $INSTANCE_NAME creation command submitted successfully."
    echo "It might take a few minutes for the instance to be ready."
    echo "You can check its status with: gcloud compute instances describe $INSTANCE_NAME --project $PROJECT_ID --zone $ZONE"
else
    echo "Error creating instance $INSTANCE_NAME. Please check the output above for details."
fi
