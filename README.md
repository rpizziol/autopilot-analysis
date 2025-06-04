# Autopilot Analysis
An infrastructure for experimenting with GKE Autopilot.

## Monitor Compute Engine

The Compute Engine instance is used to retrieve metrics data for running applications in the cluster.

To create it, run the `create-monitor-compute-engine.sh` script located in the `monitor-compute-engine` folder. Then, connect to it using the following command:

```bash
gcloud compute ssh --zone "northamerica-northeast1-a" "instance-1" --project "syda-autopilot"
```

Once connected, install Git by running:

```bash
sudo apt update
sudo apt install git -y
```

## Prometheus

Run install-docker.sh.
Run run-prometheus.sh.

Then create a 

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
