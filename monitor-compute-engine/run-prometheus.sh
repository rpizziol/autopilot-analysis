#!/bin/bash

# Exit immediately if a command exits with a non-zero status
set -e

# --- Configuration ---
# Import environment variables
source "$(dirname "$0")/../environment.sh"

# Define container and network names
PROMETHEUS_CONTAINER_NAME="prometheus"
STACKDRIVER_EXPORTER_NAME="stackdriver-exporter"
NETWORK_NAME="prometheus_network"
KSM_SERVICE_NAME="kube-state-metrics"
PROMETHEUS_CONFIG_FILE="prometheus.yml"

# --- Phase 1: Dynamic IP Discovery for kube-state-metrics ---
echo ">>> Phase 1: Discovering External IP for service '$KSM_SERVICE_NAME'..."

KSM_IP=""
# Retry for up to 3 minutes (18 retries * 10 seconds) to find the IP
for i in {1..18}; do
    # Query for the external IP of the LoadBalancer service.
    # The '|| true' part prevents the script from exiting if kubectl fails temporarily (e.g., service not found yet).
    KSM_IP=$(kubectl get service "$KSM_SERVICE_NAME" --namespace default -o=jsonpath='{.status.loadBalancer.ingress[0].ip}' 2>/dev/null || true)
    
    if [ -n "$KSM_IP" ]; then
        echo "Successfully found IP for '$KSM_SERVICE_NAME': $KSM_IP"
        break
    else
        echo "Waiting for '$KSM_SERVICE_NAME' external IP (attempt $i/18)..."
        sleep 10
    fi
done

if [ -z "$KSM_IP" ]; then
    echo "ERROR: Failed to get external IP for '$KSM_SERVICE_NAME' after 3 minutes. Aborting."
    exit 1
fi

# --- Phase 2: Generate Prometheus Configuration File ---
echo -e "\n>>> Phase 2: Generating Prometheus configuration file '$PROMETHEUS_CONFIG_FILE'..."

# Use a "here document" (cat <<EOF) to write the config file dynamically.
cat <<EOF > $PROMETHEUS_CONFIG_FILE
global:
  scrape_interval: 15s
  evaluation_interval: 15s

scrape_configs:
  - job_name: 'stackdriver-exporter'
    honor_labels: true
    static_configs:
      - targets: ['${STACKDRIVER_EXPORTER_NAME}:9255']

  - job_name: 'kube-state-metrics'
    # Give this job a longer timeout as it can be slow to respond
    scrape_timeout: 2m
    static_configs:
      - targets: ['${KSM_IP}:8080'] # The IP is dynamically injected here
EOF

echo "Prometheus configuration generated successfully."


# --- Docker Network Setup ---
echo -e "\n--- Setting up Docker network..."
if ! sudo docker network ls --format '{{.Name}}' | grep -q "^${NETWORK_NAME}$"; then
    echo "Creating Docker network '${NETWORK_NAME}'..."
    sudo docker network create "${NETWORK_NAME}"
else
    echo "Docker network '${NETWORK_NAME}' already exists."
fi

# --- Stop and Remove Existing Containers ---
echo -e "\n--- Cleaning up old containers..."
for container_name in "$PROMETHEUS_CONTAINER_NAME" "$STACKDRIVER_EXPORTER_NAME"; do
    if sudo docker ps -a --format '{{.Names}}' | grep -q "^${container_name}$"; then
        echo "Stopping and removing existing container '${container_name}'..."
        sudo docker stop "${container_name}" && sudo docker rm "${container_name}"
    fi
done

# --- Run New Containers ---
echo -e "\n--- Starting new containers..."

# Run Stackdriver Exporter (your custom command is preserved)
echo "Starting container '${STACKDRIVER_EXPORTER_NAME}'..."
sudo docker run -d \
    --name "${STACKDRIVER_EXPORTER_NAME}" \
    -p 9255:9255 \
    --restart=unless-stopped \
    --network "${NETWORK_NAME}" \
    prometheuscommunity/stackdriver-exporter:latest \
    --google.project-ids="$PROJECT_ID" \
    --monitoring.metrics-prefixes="kubernetes.io/node/cpu/allocatable_cores" \
    --monitoring.filters="resource.type = \"k8s_node\" AND resource.labels.project_id = \"$PROJECT_ID\" AND resource.labels.cluster_name = \"$CLUSTER_NAME\"" \
    --monitoring.metrics-prefixes="prometheus.googleapis.com/kube_deployment_spec_replicas" \
    --monitoring.filters="resource.type = \"prometheus_target\" AND resource.labels.project_id = \"$PROJECT_ID\" AND resource.labels.cluster = \"$CLUSTER_NAME\" AND resource.labels.location = \"$LOCATION\"" \
    --web.listen-address=":9255"


# Run Prometheus with the dynamically generated configuration
echo "Starting container '${PROMETHEUS_CONTAINER_NAME}'..."
sudo docker run --name "${PROMETHEUS_CONTAINER_NAME}" --network "${NETWORK_NAME}" -d \
  -p 9090:9090 \
  -v "$(pwd)/prometheus.yml:/etc/prometheus/prometheus.yml:ro" \
  -v prometheus_data:/prometheus \
  prom/prometheus \
  --config.file=/etc/prometheus/prometheus.yml \
  --storage.tsdb.path=/prometheus \
  --web.enable-lifecycle

echo ""
echo "--- Status ---"
echo "Prometheus and Stackdriver Exporter are starting."
echo "Prometheus is now configured to scrape kube-state-metrics at http://${KSM_IP}:8080"
