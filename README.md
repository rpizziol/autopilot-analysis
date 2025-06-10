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
   sudo apt install python3-pip -y
   sudo apt install python3-venv -y
   sudo apt install nano
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

### kube-state-metrics

To access cluster metrics from outside (via the Compute Engine), kube-state-metrics must be installed.

1. Add the Prometheus Helm repository and update it:
   ```bash
   helm repo add prometheus-community https://prometheus-community.github.io/helm-charts
   helm repo update
   ```

2. Regenerate the cluster configuration if necessary:
   ```bash
   gcloud container clusters get-credentials autopilot-cluster-1 --location northamerica-northeast1
   ```

3. Install kube-state-metrics using Helm:
   ```bash
   helm install kube-state-metrics prometheus-community/kube-state-metrics --namespace default -f ksm-values.yaml
   ```

4. Update the `/etc/hosts` file on the Monitoring Compute Engine to reference the LoadBalancer's IP:
   ```bash
   IP=$(kubectl get service kube-state-metrics -n default -o=jsonpath='{.status.loadBalancer.ingress[0].ip}') && sudo grep -q 'gke-cluster-ksm' /etc/hosts && sudo sed -i "s/.* gke-cluster-ksm/$IP gke-cluster-ksm/" /etc/hosts || echo "$IP gke-cluster-ksm" | sudo tee -a /etc/hosts > /dev/null
   ```

Once the `/etc/hosts` file is updated, running `run-prometheus.sh` should work as expected.

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

## Experiments

Before running an experiment, make sure to have installed all the required Python dependencies in the appropriate virtual environment. Navigate to the `experiments` folder and then run:

```bash
python3 -m venv venv
source venv/bin/activate
pip3 install -r requirements.txt
```


## Authors

* [Roberto Pizziol](https://github.com/rpizziol)


