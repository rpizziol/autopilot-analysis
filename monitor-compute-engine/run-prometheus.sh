#!/bin/bash

# Import environment variables
source "$(dirname "$0")/../environment.sh"

# Define container and network names
PROMETHEUS_CONTAINER_NAME="prometheus"
STACKDRIVER_EXPORTER_NAME="stackdriver-exporter"
NETWORK_NAME="prometheus_network"

# --- Docker Network Setup ---
# Create the Docker network if it doesn't exist
if ! sudo docker network ls --format '{{.Name}}' | grep -q "^${NETWORK_NAME}$"; then
    echo "Creating Docker network '${NETWORK_NAME}'..."
    sudo docker network create "${NETWORK_NAME}"
else
    echo "Docker network '${NETWORK_NAME}' already exists."
fi

# --- Stop and Remove Existing Containers ---

# Stop and remove the Stackdriver Exporter container if it exists
if sudo docker ps -a --format '{{.Names}}' | grep -q "^${STACKDRIVER_EXPORTER_NAME}$"; then
    echo "Stopping and removing existing container '${STACKDRIVER_EXPORTER_NAME}'..."
    sudo docker stop "${STACKDRIVER_EXPORTER_NAME}" && sudo docker rm "${STACKDRIVER_EXPORTER_NAME}"
else
    echo "No existing container named '${STACKDRIVER_EXPORTER_NAME}' found."
fi

# Stop and remove the Prometheus container if it exists
if sudo docker ps -a --format '{{.Names}}' | grep -q "^${PROMETHEUS_CONTAINER_NAME}$"; then
    echo "Stopping and removing existing container '${PROMETHEUS_CONTAINER_NAME}'..."
    sudo docker stop "${PROMETHEUS_CONTAINER_NAME}" && sudo docker rm "${PROMETHEUS_CONTAINER_NAME}"
else
    echo "No existing container named '${PROMETHEUS_CONTAINER_NAME}' found."
fi

# --- Run New Containers ---

# Run Stackdriver Exporter
echo "Starting container '${STACKDRIVER_EXPORTER_NAME}'..."
# Note: The metrics-prefixes and filters below are examples for Cloud Run.
# You should customize them for the Kubernetes metrics or other metrics you need.

sudo docker run -d \
    --name "${STACKDRIVER_EXPORTER_NAME}" \
    -p 9255:9255 \
    --restart=unless-stopped \
    --network "${NETWORK_NAME}" \
    prometheuscommunity/stackdriver-exporter:latest \
    --google.project-ids="$PROJECT_ID" \
    --monitoring.metrics-prefixes="kubernetes.io/,container.googleapis.com/" \
    --monitoring.filters="resource.type = \"k8s_node\" AND resource.labels.project_id = \"$PROJECT_ID\" AND resource.labels.cluster_name = \"$CLUSTER_NAME\"" \
    --web.listen-address=":9255"


# Run Prometheus
echo "Starting container '${PROMETHEUS_CONTAINER_NAME}'..."
sudo docker run --name "${PROMETHEUS_CONTAINER_NAME}" --network "${NETWORK_NAME}" -d \
  -p 9090:9090 \
  -v "$(dirname "$0")/prometheus.yml:/etc/prometheus/prometheus.yml:ro" \
  -v prometheus_data:/prometheus \
  prom/prometheus \
  --config.file=/etc/prometheus/prometheus.yml \
  --storage.tsdb.path=/prometheus \
  --web.enable-lifecycle

echo ""
echo "--- Status ---"
echo "Prometheus container '${PROMETHEUS_CONTAINER_NAME}' setup process initiated."
echo "Stackdriver Exporter container '${STACKDRIVER_EXPORTER_NAME}' setup process initiated."
echo ""
echo "To check status:"
echo "  Prometheus: sudo docker ps -f name=${PROMETHEUS_CONTAINER_NAME}  && sudo docker logs ${PROMETHEUS_CONTAINER_NAME}"
echo "  Stackdriver Exporter: sudo docker ps -f name=${STACKDRIVER_EXPORTER_NAME} && sudo docker logs ${STACKDRIVER_EXPORTER_NAME}"
echo ""
echo "Remember to configure your prometheus.yml to scrape the Stackdriver Exporter on port 9255 if you haven't already."
echo "Example prometheus.yml job:"
echo "  - job_name: 'stackdriver_exporter'"
echo "    static_configs:"
echo "      - targets: ['${STACKDRIVER_EXPORTER_NAME}:9255'] # If Prometheus is on the same Docker network"
echo "      # Or use 'localhost:9255' if scraping from the host perspective, though container name is better"