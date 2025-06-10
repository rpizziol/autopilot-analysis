#!/usr/bin/env python3
import argparse
import subprocess
import time
import datetime
import requests
import csv
import os
import sys

# --- Helper Functions

def run_kubectl_command(command_args, error_message_prefix="Error during kubectl execution", can_fail=False):
    """Executes a kubectl command and handles errors."""
    try:
        full_command = ["kubectl"] + command_args
        print(f"Executing: {' '.join(full_command)}")
        # Timeout increased to handle slow rollouts or termination
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
        if not can_fail:
            raise
    except subprocess.TimeoutExpired as e:
        print(f"kubectl command timed out: {' '.join(e.cmd)}")
        print(f"Timeout was: {e.timeout} seconds")
        print(f"Stdout: {e.stdout}")
        print(f"Stderr: {e.stderr}")
        if not can_fail:
            raise
    return None

def query_prometheus_range(prometheus_url, query, start_time_unix, end_time_unix, step="15s"):
    """Queries the Prometheus query_range API."""
    api_url = f"{prometheus_url.rstrip('/')}/api/v1/query_range"
    params = {"query": query, "start": start_time_unix, "end": end_time_unix, "step": step}
    try:
        print(f"Querying Prometheus: {query} (from {start_time_unix} to {end_time_unix}, step {step})")
        response = requests.get(api_url, params=params, timeout=60)
        response.raise_for_status()
        data = response.json()
        if data["status"] == "success":
            return data["data"].get("result", [])
        else:
            print(f"Error in Prometheus query '{query}': {data.get('errorType', '')} {data.get('error', 'Unknown error')}")
            return []
    except requests.exceptions.RequestException as e:
        print(f"Error connecting to Prometheus ({api_url}) for query '{query}': {e}")
        return []
    except Exception as e:
        print(f"Unexpected error while querying Prometheus for '{query}': {e}")
        return []

# --- Main Script ---

def main():
    parser = argparse.ArgumentParser(description="Script for HPA experiments with Locust load testing.")
    # Application arguments
    parser.add_argument("application_name", help="Base name of the application.")
    parser.add_argument("--namespace", default="default", help="Kubernetes namespace.")
    # Experiment arguments
    parser.add_argument("--experiment_name", help="Name for the experiment. Defaults to 'YYYYMMDD_HHmm_{application_name}'.")
    parser.add_argument("--prometheus_url", default="http://localhost:9090", help="URL of the Prometheus server.")
    parser.add_argument("--sampling_interval", default="15s", help="Sampling interval for Prometheus queries.")
    # Locust arguments
    parser.add_argument("--locust_users", type=int, default=10, help="Number of concurrent Locust users.")
    parser.add_argument("--locust_spawn_rate", type=int, default=1, help="Number of users to spawn per second.")
    parser.add_argument("--locust_run_time", default="5m", help="Duration for the Locust test (e.g., 10m, 1h30m).")
    
    args = parser.parse_args()

    # --- Setup ---
    if not args.experiment_name:
        current_time = datetime.datetime.now().strftime("%Y%m%d_%H%M")
        args.experiment_name = f"{current_time}_{args.application_name}"

    data_folder = "data"
    os.makedirs(data_folder, exist_ok=True)
    times_file = os.path.join(data_folder, f"{args.experiment_name}_times.txt")
    metrics_csv_file = os.path.join(data_folder, f"{args.experiment_name}_export.csv")

    deployment_yaml = os.path.normpath(os.path.join("..", "webapps", f"{args.application_name}-deployment.yaml"))
    service_yaml = os.path.normpath(os.path.join("..", "webapps", f"{args.application_name}-service.yaml"))
    hpa_yaml = os.path.normpath(os.path.join("..", "webapps", f"{args.application_name}-hpa.yaml"))
    
    deployment_k8s_name = f"{args.application_name}-deployment"
    service_k8s_name = f"{args.application_name}-service"
    hpa_k8s_name = f"{args.application_name}-hpa"
    
    # --- Experiment Execution ---
    start_time_dt = datetime.datetime.now(datetime.timezone.utc)
    start_time_unix = start_time_dt.timestamp()
    
    # Use a broad try/finally block to ensure cleanup and data collection always run
    try:
        # 1. Deploy all resources
        print("\n--- Phase 1: Deploying Kubernetes Resources ---")
        for f in [deployment_yaml, service_yaml, hpa_yaml]:
            if not os.path.exists(f):
                print(f"ERROR: Required file '{f}' not found. Aborting.")
                sys.exit(1)
            run_kubectl_command(["apply", "-f", f, "-n", args.namespace])
        
        # 2. Get External IP for the service
        print("\n--- Phase 2: Waiting for Service External IP ---")
        target_ip = ""
        for _ in range(30): # Wait up to 5 minutes (30 * 10s)
            ip_process = subprocess.run(["kubectl", "get", "service", service_k8s_name, "-n", args.namespace, "-o=jsonpath='{.status.loadBalancer.ingress[0].ip}'"], capture_output=True, text=True)
            ip = ip_process.stdout.strip().replace("'", "")
            if ip:
                target_ip = ip
                print(f"Service is ready at external IP: {target_ip}")
                break
            print("Waiting for LoadBalancer IP...")
            time.sleep(10)
        
        if not target_ip:
            print("ERROR: Timed out waiting for the service's external IP. Aborting.")
            raise Exception("Service IP not found")

        # 3. Start Locust Load Test
        print("\n--- Phase 3: Starting Locust Load Test ---")
        locust_command = [
            "locust", "--headless",
            "-u", str(args.locust_users),
            "-r", str(args.locust_spawn_rate),
            "-t", args.locust_run_time,
            "--host", f"http://{target_ip}"
        ]
        
        if not os.path.exists("locustfile.py"):
            print("ERROR: locustfile.py not found in the current directory. Aborting.")
            sys.exit(1)

        print(f"Executing: {' '.join(locust_command)}")
        # Run Locust as a background process
        locust_process = subprocess.Popen(locust_command)

        # Wait for the specified duration. The Popen process runs in parallel.
        print(f"Load test running for {args.locust_run_time}. The script will now wait...")
        # A simple way to wait for the headless run to finish is to just wait for the process itself.
        locust_process.wait() 
        print("Locust test finished.")
    
    except Exception as e:
        print(f"\nAn error interrupted the experiment: {e}")
    
    finally:
        # --- Cleanup and Data Collection ---
        end_time_dt = datetime.datetime.now(datetime.timezone.utc)
        end_time_unix = end_time_dt.timestamp()
        
        print(f"\nExperiment ended at: {end_time_dt.isoformat()}")
        with open(times_file, "w") as f:
            f.write(f"START_TIME_UNIX={start_time_unix}\n")
            f.write(f"END_TIME_UNIX={end_time_unix}\n")

        # Cleanup Kubernetes resources
        print("\n--- Final Phase: Cleaning up Kubernetes resources ---")
        run_kubectl_command(["delete", "hpa", hpa_k8s_name, "-n", args.namespace, "--wait=false"], can_fail=True)
        run_kubectl_command(["delete", "service", service_k8s_name, "-n", args.namespace, "--wait=false"], can_fail=True)
        run_kubectl_command(["delete", "deployment", deployment_k8s_name, "-n", args.namespace, "--wait=true"], can_fail=True)
        print("Cleanup complete.")

        # --- Metrics Processing ---
        print(f"\n--- Generating CSV of metrics from {args.prometheus_url} ---")
        # The logic for querying Prometheus and writing the CSV is identical to the previous script.
        # It is self-contained and will use the start/end times recorded above.

        # Define metric queries
        metric_spec_replicas_query = f'kube_deployment_spec_replicas{{deployment="{deployment_k8s_name}", namespace="{args.namespace}"}}'
        metric_ready_replicas_query = f'kube_deployment_status_replicas_available{{deployment="{deployment_k8s_name}", namespace="{args.namespace}"}}'
        node_type_label_name = 'label_node_kubernetes_io_instance_type' 
        metric_nodes_query = f"count by ({node_type_label_name}) (kube_node_labels)"
        metric_hpa_replicas_query = f'kube_hpa_status_current_replicas{{hpa="{hpa_k8s_name}", namespace="{args.namespace}"}}'

        # Query Prometheus
        spec_replicas_data = query_prometheus_range(args.prometheus_url, metric_spec_replicas_query, start_time_unix, end_time_unix, args.sampling_interval)
        ready_replicas_data = query_prometheus_range(args.prometheus_url, metric_ready_replicas_query, start_time_unix, end_time_unix, args.sampling_interval)
        nodes_data = query_prometheus_range(args.prometheus_url, metric_nodes_query, start_time_unix, end_time_unix, args.sampling_interval)
        hpa_replicas_data = query_prometheus_range(args.prometheus_url, metric_hpa_replicas_query, start_time_unix, end_time_unix, args.sampling_interval)
        
        # Process data into a timestamp-keyed dictionary
        metrics_by_ts = {}
        def process_series(data, metric_name):
            if data:
                for ts_float, val_str in data[0].get("values", []):
                    ts_int = int(float(ts_float))
                    if ts_int not in metrics_by_ts: metrics_by_ts[ts_int] = {}
                    metrics_by_ts[ts_int][metric_name] = val_str
        
        process_series(spec_replicas_data, "deployment_spec_replicas")
        process_series(ready_replicas_data, "deployment_ready_replicas")
        process_series(hpa_replicas_data, "hpa_current_replicas")

        node_types = set()
        for series in nodes_data:
            node_type = series.get("metric", {}).get(node_type_label_name, "unknown_node")
            node_types.add(node_type)
            for ts_float, val_str in series.get("values", []):
                ts_int = int(float(ts_float))
                if ts_int not in metrics_by_ts: metrics_by_ts[ts_int] = {}
                metrics_by_ts[ts_int][node_type] = val_str

        # Write to CSV
        if metrics_by_ts:
            sorted_node_types = sorted(list(node_types))
            fieldnames = ["timestamp_iso", "timestamp_unix", "deployment_spec_replicas", "deployment_ready_replicas", "hpa_current_replicas"] + sorted_node_types
            
            with open(metrics_csv_file, "w", newline="") as csvfile:
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                writer.writeheader()

                step_seconds = 15
                try: step_seconds = int(args.sampling_interval.rstrip('sm')) * (60 if args.sampling_interval.endswith('m') else 1)
                except: pass
                
                available_timestamps = sorted(metrics_by_ts.keys())
                for ts_unix in range(int(start_time_unix), int(end_time_unix) + 1, step_seconds):
                    closest_ts = min(available_timestamps, key=lambda t: abs(t - ts_unix), default=None)
                    data_row = metrics_by_ts.get(closest_ts, {}) if closest_ts and abs(closest_ts - ts_unix) < step_seconds else {}
                    
                    row_to_write = {"timestamp_iso": datetime.datetime.fromtimestamp(ts_unix, datetime.timezone.utc).isoformat(), "timestamp_unix": ts_unix}
                    for field in fieldnames[2:]:
                        row_to_write[field] = data_row.get(field, '0')
                    writer.writerow(row_to_write)
            print(f"Metrics successfully exported to '{metrics_csv_file}'")
        else:
            print("No metric data retrieved from Prometheus. CSV file will be empty.")


if __name__ == "__main__":
    main()
