# Autopilot Analysis
An infrastructure for experimenting with GKE Autopilot.

## Monitor Compute Engine

The Compute Engine instance is used to retrieve metrics data for running applications in the cluster.

### Initial Setup

1. Navigate to the `init` folder and run the following scripts in order:
   - `create-monitor.sh`
   - `create-firewall-rule.sh`

2. Connect to the newly created Compute Engine instance using SSH:
   ```bash
   gcloud compute ssh --zone "northamerica-northeast1-a" "instance-1" --project "syda-autopilot"
   ```

3. Once connected, execute the following commands:
   ```bash
   sudo apt update
   sudo apt install git -y
   ```

4. Clone this project repository:
   ```bash
   git clone <repository-url>
   cd autopilot-analysis
   ```

5. Run the `install-docker.sh` script:
   ```bash
   ./install-docker.sh
   ```

6. Start Prometheus by running:
   ```bash
   ./run-prometheus.sh
   ```

### Regular Usage

- To start the monitor Compute Engine, use:
  ```bash
  ./start-monitor.sh
  ```

- To stop the monitor Compute Engine, use:
  ```bash
  ./stop-monitor.sh
  ```

- Remember to run `run-prometheus.sh` from the Compute Engine every time after starting it.

## Autopilot Cluster

To create the Autopilot Cluster, execute the `deploy-autopilot-cluster.sh` script.

### Viewing the List of Nodes (with Node Type)

To view the list of nodes along with their types, run:

```bash
kubectl get nodes -L cloud.google.com/gke-machine-type,node.kubernetes.io/instance-type
```

## Workload
### Scaling the Number of Replicas

To scale the number of replicas for a deployment, use:

```bash
kubectl scale deployment stress-ng-deployment --replicas=<NUMBER_OF_REPLICAS>
```

## Authors

* [Roberto Pizziol](https://github.com/rpizziol)
