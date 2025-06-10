#!/usr/bin/env python3
import argparse
import subprocess
import time
import datetime
import requests
import csv
import os

# --- Helper Functions ---

def run_kubectl_command(command_args, error_message_prefix="Error during kubectl execution"):
    """Executes a kubectl command and handles errors."""
    try:
        full_command = ["kubectl"] + command_args
        print(f"Executing: {' '.join(full_command)}")
        # Increased timeout to handle slow rollouts or termination
        result = subprocess.run(full_command, check=True, capture_output=True, text=True, timeout=1800) # 30 minutes
        if result.stdout:
            print(f"kubectl stdout: {result.stdout.strip()}")
        if result.stderr:
            print(f"kubectl stderr: {result.stderr.strip()}")
        return result
    except subprocess.CalledProcessError as e:
        print(f"{error_message_prefix}: {e}")
        print(f"Stdout: {e.stdout}")
        print(f"Stderr: {e.stderr}")
        raise
    except subprocess.TimeoutExpired as e:
        print(f"kubectl command timed out: {' '.join(e.cmd)}")
        print(f"Timeout was: {e.timeout} seconds")
        print(f"Stdout: {e.stdout}")
        print(f"Stderr: {e.stderr}")
        raise

def query_prometheus_range(prometheus_url, query, start_time_unix, end_time_unix, step="15s"):
    """Queries the Prometheus query_range API."""
    api_url = f"{prometheus_url.rstrip('/')}/api/v1/query_range"
    params = {
        "query": query,
        "start": start_time_unix,
        "end": end_time_unix,
        "step": step
    }
    try:
        print(f"Querying Prometheus: {query} (from {start_time_unix} to {end_time_unix}, step {step})")
        response = requests.get(api_url, params=params, timeout=60)
        response.raise_for_status()
        data = response.json()
        if data["status"] == "success":
            if "result" in data["data"] and len(data["data"]["result"]) > 0:
                return data["data"]["result"]
            else:
                print(f"Warning: No data returned from Prometheus for query: {query}")
                return []
        else:
            print(f"Error in Prometheus query '{query}': {data.get('errorType', '')} {data.get('error', 'Unknown error')}")
            return []
    except requests.exceptions.RequestException as e:
        print(f"Error connecting to Prometheus ({api_url}) for query '{query}': {e}")
        return []
    except KeyError:
        print(f"Unexpected response from Prometheus for query: {query}. Response: {data}")
        return []
    except Exception as e:
        print(f"Unexpected error while querying Prometheus for '{query}': {e}")
        return []

# --- Main Script ---

def main():
    parser = argparse.ArgumentParser(description="Script for deployment, scaling, cleanup, and collecting metrics.")
    parser.add_argument("application_name", help="Base name of the application.")
    parser.add_argument("--experiment_name", help="Name of the experiment. Defaults to 'YYYYMMDD_HHmm_{application_name}'.")
    parser.add_argument("--namespace", default="default", help="Kubernetes namespace.")
    parser.add_argument("--wait_minutes", type=float, default=1.0, help="Minutes to wait between scaling steps.")
    parser.add_argument("--prometheus_url", default="http://localhost:9090", help="URL of the Prometheus server.")
    parser.add_argument("--sampling_interval", default="15s", help="Sampling interval for Prometheus queries.")
    parser.add_argument("--max_replicas", type=int, default=4, help="Maximum number of replicas to scale up to.")
    parser.add_argument("--step_size", type=int, default=1, help="Step size for scaling replicas.")

    args = parser.parse_args()

    # --- Setup ---
    if not args.experiment_name:
        current_time = datetime.datetime.now().strftime("%Y%m%d_%H%M")
        args.experiment_name = f"{current_time}_{args.application_name}"

    data_folder = "data"
    os.makedirs(data_folder, exist_ok=True)
    times_file = os.path.join(data_folder, f"{args.experiment_name}_times.txt")
    metrics_csv_file = os.path.join(data_folder, f"{args.experiment_name}_export.csv")
    deployment_yaml_file = os.path.join(".", "..", "webapps", f"{args.application_name}-deployment.yaml")
    deployment_yaml_file = os.path.normpath(deployment_yaml_file)
    deployment_k8s_name = f"{args.application_name}-deployment"
    rollout_timeout = "30m"
    
    end_time_unix = None # Initialize end_time to None

    # --- Start Time Recording ---
    start_time_dt = datetime.datetime.now(datetime.timezone.utc)
    start_time_unix = start_time_dt.timestamp()
    start_time_iso = start_time_dt.isoformat()
    print(f"Experiment start: {start_time_iso}")
    with open(times_file, "w") as f:
        f.write(f"START_TIME_ISO={start_time_iso}\n")
        f.write(f"START_TIME_UNIX={start_time_unix}\n")

    try:
        wait_seconds = args.wait_minutes * 60

        # --- 1. Deploy Application ---
        print(f"\n--- Deploying application: {args.application_name} ---")
        if not os.path.exists(deployment_yaml_file):
            print(f"ERROR: Deployment file '{deployment_yaml_file}' not found.")
            return 1
        run_kubectl_command(["apply", "-f", deployment_yaml_file, "-n", args.namespace])
        print(f"\n--- Waiting for initial rollout of '{deployment_k8s_name}'... ---")
        run_kubectl_command(["rollout", "status", f"deployment/{deployment_k8s_name}", "-n", args.namespace, f"--timeout={rollout_timeout}"])
        print(f"Deployment '{deployment_k8s_name}' is ready.")

        # --- 2. Perform Scaling Steps ---
        print(f"\n--- Scaling {deployment_k8s_name} from 2 up to {args.max_replicas} and down ---")
        
        # Scale up
        for replicas in range(2, args.max_replicas + 1, args.step_size):
            print(f"\n--- Scaling {deployment_k8s_name} to {replicas} replicas ---")
            run_kubectl_command(["scale", "deployment", deployment_k8s_name, f"--replicas={replicas}", "-n", args.namespace])
            print(f"--- Waiting for rollout to complete for {replicas} replicas... ---")
            run_kubectl_command(["rollout", "status", f"deployment/{deployment_k8s_name}", "-n", args.namespace, f"--timeout={rollout_timeout}"])
            print(f"--- Waiting for {args.wait_minutes} minutes to collect metrics ---")
            time.sleep(wait_seconds)

        # Scale down
        for replicas in range(args.max_replicas - args.step_size, 1, -args.step_size):
            print(f"\n--- Scaling {deployment_k8s_name} to {replicas} replicas ---")
            run_kubectl_command(["scale", "deployment", deployment_k8s_name, f"--replicas={replicas}", "-n", args.namespace])
            print(f"--- Waiting for rollout to complete for {replicas} replicas... ---")
            run_kubectl_command(["rollout", "status", f"deployment/{deployment_k8s_name}", "-n", args.namespace, f"--timeout={rollout_timeout}"])
            print(f"--- Waiting for {args.wait_minutes} minutes to collect metrics ---")
            time.sleep(wait_seconds)
            
        print("Scaling steps completed.")

        # --- 3. Cleanup Phase ---
        print(f"\n--- Deleting application '{deployment_k8s_name}' and waiting for termination ---")
        # The --wait flag ensures the command blocks until the resource and its dependents are gone.
        run_kubectl_command(["delete", "deployment", deployment_k8s_name, "-n", args.namespace, "--wait=true"])
        print(f"Deployment '{deployment_k8s_name}' and its pods have been deleted.")
        
        # Record end time ONLY on successful completion of all steps
        end_time_dt = datetime.datetime.now(datetime.timezone.utc)
        end_time_unix = end_time_dt.timestamp()
        end_time_iso = end_time_dt.isoformat()
        print(f"\nExperiment completed successfully at: {end_time_iso}")
        with open(times_file, "a") as f:
            f.write(f"END_TIME_ISO={end_time_iso}\n")
            f.write(f"END_TIME_UNIX={end_time_unix}\n")

    except Exception as e:
        print(f"\nAn error interrupted the experiment: {e}")
    finally:
        # If an error occurred, end_time_unix will still be None.
        # Record the time of the error as the end time.
        if end_time_unix is None:
            print("Recording end time after an error or interruption.")
            end_time_dt = datetime.datetime.now(datetime.timezone.utc)
            end_time_unix = end_time_dt.timestamp()
            end_time_iso = end_time_dt.isoformat()
            with open(times_file, "a") as f:
                f.write(f"END_TIME_ISO={end_time_iso}\n")
                f.write(f"END_TIME_UNIX={end_time_unix}\n")

    # --- 4. Generate CSV from Prometheus Metrics ---
    print(f"\n--- Generating CSV of metrics from {args.prometheus_url} ---")
    
    # ... (The rest of the metrics processing and CSV writing logic remains the same) ...
    final_start_time_unix_for_query = start_time_unix
    final_end_time_unix_for_query = end_time_unix
    # This block now uses the final, correct end_time_unix
    try:
        times_data = {}
        with open(times_file, "r") as f:
            for line in f:
                if "=" in line:
                    key, value = line.strip().split("=", 1)
                    times_data[key] = value
        final_start_time_unix_for_query = float(times_data.get("START_TIME_UNIX", start_time_unix))
        final_end_time_unix_for_query = float(times_data.get("END_TIME_UNIX", end_time_unix))
    except Exception as e:
        print(f"Warning: unable to read times from file '{times_file}'. Using script start/end times. Error: {e}")

    metric_spec_replicas_query = f'kube_deployment_spec_replicas{{deployment="{deployment_k8s_name}", namespace="{args.namespace}"}}'
    metric_ready_replicas_query = f'kube_deployment_status_replicas_available{{deployment="{deployment_k8s_name}", namespace="{args.namespace}"}}'
    node_type_label_name = 'label_node_kubernetes_io_instance_type'
    metric_nodes_query = f"count by ({node_type_label_name}) (kube_node_labels)"

    print(f"Metric Query for Desired Replicas: {metric_spec_replicas_query}")
    print(f"Metric Query for Ready Replicas: {metric_ready_replicas_query}")
    print(f"Metric Query for Nodes: {metric_nodes_query}")

    spec_replicas_data = query_prometheus_range(args.prometheus_url, metric_spec_replicas_query, final_start_time_unix_for_query, final_end_time_unix_for_query, args.sampling_interval)
    ready_replicas_data = query_prometheus_range(args.prometheus_url, metric_ready_replicas_query, final_start_time_unix_for_query, final_end_time_unix_for_query, args.sampling_interval)
    nodes_data = query_prometheus_range(args.prometheus_url, metric_nodes_query, final_start_time_unix_for_query, final_end_time_unix_for_query, args.sampling_interval)

    metrics_by_ts = {}
    
    if spec_replicas_data:
        for ts_float, val_str in spec_replicas_data[0].get("values", []):
            ts_int = int(float(ts_float))
            if ts_int not in metrics_by_ts: metrics_by_ts[ts_int] = {}
            metrics_by_ts[ts_int]["deployment_spec_replicas"] = val_str

    if ready_replicas_data:
        for ts_float, val_str in ready_replicas_data[0].get("values", []):
            ts_int = int(float(ts_float))
            if ts_int not in metrics_by_ts: metrics_by_ts[ts_int] = {}
            metrics_by_ts[ts_int]["deployment_ready_replicas"] = val_str

    node_types = set()
    for series in nodes_data:
        node_type = series.get("metric", {}).get(node_type_label_name)
        if not node_type: continue
        node_types.add(node_type)
        for ts_float, val_str in series.get("values", []):
            ts_int = int(float(ts_float))
            if ts_int not in metrics_by_ts: metrics_by_ts[ts_int] = {}
            metrics_by_ts[ts_int][node_type] = val_str

    if not metrics_by_ts:
        print("No metric data retrieved from Prometheus. The CSV file will not be generated or will be empty.")
    else:
        step_seconds = 15
        try:
            if args.sampling_interval.endswith('s'): step_seconds = int(args.sampling_interval[:-1])
            elif args.sampling_interval.endswith('m'): step_seconds = int(args.sampling_interval[:-1]) * 60
        except (ValueError, IndexError):
            print(f"Could not parse sampling interval '{args.sampling_interval}'. Using {step_seconds}s for CSV.")
        
        sorted_node_types = sorted(list(node_types))
        fieldnames = ["timestamp_iso", "timestamp_unix", "deployment_spec_replicas", "deployment_ready_replicas"] + sorted_node_types
        
        print(f"CSV Headers will be: {fieldnames}")

        with open(metrics_csv_file, "w", newline="") as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()

            query_start_sec = int(final_start_time_unix_for_query)
            query_end_sec = int(final_end_time_unix_for_query)
            
            if step_seconds > 0:
                available_timestamps = sorted(metrics_by_ts.keys())
                for current_ts_unix in range(query_start_sec, query_end_sec + 1, step_seconds):
                    closest_ts = min(available_timestamps, key=lambda ts: abs(ts - current_ts_unix), default=None)
                    
                    data_for_row = {}
                    if closest_ts is not None and abs(closest_ts - current_ts_unix) < step_seconds:
                        data_for_row = metrics_by_ts.get(closest_ts, {})

                    row_to_write = {
                        "timestamp_iso": datetime.datetime.fromtimestamp(current_ts_unix, datetime.timezone.utc).isoformat(),
                        "timestamp_unix": current_ts_unix,
                        "deployment_spec_replicas": data_for_row.get("deployment_spec_replicas", '0'),
                        "deployment_ready_replicas": data_for_row.get("deployment_ready_replicas", '0')
                    }
                    for node_type in sorted_node_types:
                        row_to_write[node_type] = data_for_row.get(node_type, '0')
                    
                    writer.writerow(row_to_write)

        print(f"Metrics successfully exported to '{metrics_csv_file}'")

if __name__ == "__main__":
    main()
