# Environment variables for the project
PROJECT_ID="syda-autopilot"
REGION="northamerica-northeast1"
ZONE="northamerica-northeast1-a"
SERVICE_ACCOUNT_EMAIL="1036682486306-compute@developer.gserviceaccount.com"

# Cluster configuration
CLUSTER_NAME="autopilot-cluster-1"
RELEASE_CHANNEL="regular"
TIER="standard"

# Compute Engine instance configuration
INSTANCE_NAME="instance-1"
MACHINE_TYPE="e2-medium"
# Image details for Ubuntu 24.04 LTS Minimal
IMAGE="projects/ubuntu-os-cloud/global/images/ubuntu-minimal-2404-noble-amd64-v20250523"
DISK_SIZE="10" # GB
DISK_TYPE="pd-balanced"
DISK_RESOURCE_POLICY="projects/$PROJECT_ID/regions/$REGION/resourcePolicies/default-schedule-1"
#SCOPES="https://www.googleapis.com/auth/devstorage.read_only,https://www.googleapis.com/auth/logging.write,https://www.googleapis.com/auth/monitoring.write,https://www.googleapis.com/auth/monitoring.read,https://www.googleapis.com/auth/service.management.readonly,https://www.googleapis.com/auth/servicecontrol,https://www.googleapis.com/auth/trace.append"


TARGET_TAG="prometheus-server"