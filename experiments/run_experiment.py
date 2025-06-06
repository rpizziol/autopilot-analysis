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
        result = subprocess.run(full_command, check=True, capture_output=True, text=True)
        if result.stdout:
            print(f"kubectl stdout: {result.stdout.strip()}")
        if result.stderr:
            print(f"kubectl stderr: {result.stderr.strip()}") # Useful for warnings or additional info
        return result
    except subprocess.CalledProcessError as e:
        print(f"{error_message_prefix}: {e}")
        print(f"Stdout: {e.stdout}")
        print(f"Stderr: {e.stderr}")
        raise # Re-raise the exception to stop the script if a kubectl command fails

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
        response = requests.get(api_url, params=params, timeout=60) # Timeout increased to 60 seconds
        response.raise_for_status()
        data = response.json()
        if data["status"] == "success":
            if len(data["data"]["result"]) > 0:
                # Usually for these queries, we expect a single element in the "result" array
                # if the query does not produce a vector of multiple time series.
                return data["data"]["result"][0]["values"] # List of [timestamp, value]
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
    parser = argparse.ArgumentParser(description="Script for deployment, scaling, and collecting metrics from Prometheus.")
    parser.add_argument("application_name", help="Base name of the application (e.g., my-app). Used by convention for YAML files (expected in ./../webapps/) and deployment names.")
    parser.add_argument("--namespace", default="default", help="Kubernetes namespace to operate in (default: default).")
    parser.add_argument("--wait_minutes", type=float, default=1.0, help="Minutes to wait between scaling steps (default: 1.0, can be a float).")
    parser.add_argument("--prometheus_url", default="http://localhost:9090", help="URL of the Prometheus server (default: http://localhost:9090).")
    parser.add_argument("--times_file", default="experiment_times.txt", help="File to save start and end times (default: experiment_times.txt).")
    parser.add_argument("--metrics_csv_file", default="metrics_export.csv", help="CSV file to save metrics (default: metrics_export.csv).")
    parser.add_argument("--sampling_interval", default="15s", help="Sampling interval for Prometheus queries (default: 15s).")


    args = parser.parse_args()

    # --- MODIFIED ---
    # Deployment YAML file is expected in ./../webapps/ directory
    deployment_yaml_file = os.path.join(".", "..", "webapps", f"{args.application_name}-deployment.yaml")
    # Normalize the path for cleaner print outputs and consistent behavior
    deployment_yaml_file = os.path.normpath(deployment_yaml_file)
    # --- END MODIFIED ---

    # Convention: the Kubernetes deployment name is app_name-deployment
    deployment_k8s_name = f"{args.application_name}-deployment"

    # 1. Check the initial time and save it to a file
    start_time_dt = datetime.datetime.now(datetime.timezone.utc)
    start_time_unix = start_time_dt.timestamp()
    start_time_iso = start_time_dt.isoformat()

    print(f"Experiment start: {start_time_iso}")
    with open(args.times_file, "w") as f:
        f.write(f"START_TIME_ISO={start_time_iso}\n")
        f.write(f"START_TIME_UNIX={start_time_unix}\n")

    try:

        wait_seconds = args.wait_minutes * 60
        
        # 2. Deploy the application
        print(f"\n--- Deploying application: {args.application_name} in namespace {args.namespace} from {deployment_yaml_file} ---")
        if not os.path.exists(deployment_yaml_file):
            # --- MODIFIED ERROR MESSAGE ---
            print(f"ERROR: Deployment file '{deployment_yaml_file}' not found. Ensure it exists in the './../webapps/' directory relative to the script's execution path.")
            # --- END MODIFIED ERROR MESSAGE ---
            return 1 # Exit with error code
        run_kubectl_command(["apply", "-f", deployment_yaml_file, "-n", args.namespace],
                            f"Deployment of {deployment_yaml_file} failed")
        print(f"Deployment '{deployment_k8s_name}' applied.")
        print(f"\n--- Waiting for {args.wait_minutes} minutes ---")
        time.sleep(wait_seconds * 2) # Wait for initial deployment to stabilize

        # 3. Perform initial scaling to 2 replicas
        print(f"\n--- Scaling {deployment_k8s_name} to 2 replicas ---")
        run_kubectl_command(["scale", "deployment", deployment_k8s_name, "--replicas=2", "-n", args.namespace],
                            f"Scaling {deployment_k8s_name} to 2 replicas failed")
        print(f"Deployment '{deployment_k8s_name}' scaled to 2 replicas.")

        # 4. Wait X minutes, scale to 3, wait X minutes, scale to 4

        print(f"\n--- Waiting for {args.wait_minutes} minutes ---")
        time.sleep(wait_seconds)
        print(f"\n--- Scaling {deployment_k8s_name} to 3 replicas ---")
        run_kubectl_command(["scale", "deployment", deployment_k8s_name, "--replicas=3", "-n", args.namespace],
                            f"Scaling {deployment_k8s_name} to 3 replicas failed")
        print(f"Deployment '{deployment_k8s_name}' scaled to 3 replicas.")

        print(f"\n--- Waiting for {args.wait_minutes} minutes ---")
        time.sleep(wait_seconds)
        print(f"\n--- Scaling {deployment_k8s_name} to 4 replicas ---")
        run_kubectl_command(["scale", "deployment", deployment_k8s_name, "--replicas=4", "-n", args.namespace],
                            f"Scaling {deployment_k8s_name} to 4 replicas failed")
        print(f"Deployment '{deployment_k8s_name}' scaled to 4 replicas.")
        print("Scaling completed.")

    except Exception as e:
        print(f"An error interrupted the experiment during kubectl operations: {e}")
        # Despite the error, we still record the end time
    finally:
        # 5. Check the final time and append it
        end_time_dt = datetime.datetime.now(datetime.timezone.utc)
        end_time_unix = end_time_dt.timestamp()
        end_time_iso = end_time_dt.isoformat()

        print(f"\nExperiment end (or attempt): {end_time_iso}")
        with open(args.times_file, "a") as f:
            f.write(f"END_TIME_ISO={end_time_iso}\n")
            f.write(f"END_TIME_UNIX={end_time_unix}\n")

    # 6. Generate CSV from Prometheus metrics
    print(f"\n--- Generating CSV of metrics from {args.prometheus_url} ---")

    final_start_time_unix_for_query = start_time_unix
    final_end_time_unix_for_query = end_time_unix
    try:
        times_data = {}
        with open(args.times_file, "r") as f:
            for line in f:
                if "=" in line:
                    key, value = line.strip().split("=", 1)
                    times_data[key] = value
        final_start_time_unix_for_query = float(times_data.get("START_TIME_UNIX", start_time_unix))
        # Use the most recently recorded end time
        final_end_time_unix_for_query = float(times_data.get("END_TIME_UNIX", end_time_unix))
        
        start_dt_str = datetime.datetime.fromtimestamp(final_start_time_unix_for_query, datetime.timezone.utc).isoformat()
        end_dt_str = datetime.datetime.fromtimestamp(final_end_time_unix_for_query, datetime.timezone.utc).isoformat()
        print(f"Interval for Prometheus query: from {start_dt_str} to {end_dt_str}")

    except Exception as e:
        print(f"Warning: unable to read precise times from file '{args.times_file}'. Using script start/end times. Error: {e}")
        # In case of an error reading the file, final_start_time_unix_for_query and final_end_time_unix_for_query
        # retain the start_time_unix and end_time_unix values initialized at the script's start and end.


    metric1_query = "count(stackdriver_k_8_s_node_kubernetes_io_node_cpu_allocatable_cores)"
    # WARNING: Verify the exact label names (e.g., 'deployment', 'namespace') in your Prometheus.
    # They might be prefixed like 'exported_deployment', 'label_deployment_name', etc.
    metric2_query = f'stackdriver_prometheus_target_prometheus_googleapis_com_kube_deployment_spec_replicas_gauge{{deployment="{deployment_k8s_name}", namespace="{args.namespace}"}}'
    
    print(f"Metric Query 1: {metric1_query}")
    print(f"Metric Query 2: {metric2_query}")

    metric1_data_raw = query_prometheus_range(args.prometheus_url, metric1_query, final_start_time_unix_for_query, final_end_time_unix_for_query, args.sampling_interval)
    metric2_data_raw = query_prometheus_range(args.prometheus_url, metric2_query, final_start_time_unix_for_query, final_end_time_unix_for_query, args.sampling_interval)

    # Organize data by timestamp for easier merging
    # Each value in metricX_data_raw is [timestamp, string_value]
    metrics_by_ts = {}

    for ts_float, val_str in metric1_data_raw:
        ts_int = int(float(ts_float))
        if ts_int not in metrics_by_ts:
            metrics_by_ts[ts_int] = {}
        metrics_by_ts[ts_int]["node_count"] = val_str

    for ts_float, val_str in metric2_data_raw:
        ts_int = int(float(ts_float))
        if ts_int not in metrics_by_ts:
            metrics_by_ts[ts_int] = {}
        metrics_by_ts[ts_int]["spec_replicas"] = val_str
    
    if not metrics_by_ts:
        print("No metric data retrieved from Prometheus. The CSV file will not be generated or will be empty.")
    else:
        # Create a full timestamp range for the CSV based on the actual sampling interval
        # Round start_time and end_time to seconds to avoid issues with floats
        query_start_sec = int(final_start_time_unix_for_query)
        query_end_sec = int(final_end_time_unix_for_query)
        step_seconds = 0
        if args.sampling_interval.endswith('s'):
            step_seconds = int(args.sampling_interval[:-1])
        elif args.sampling_interval.endswith('m'):
            step_seconds = int(args.sampling_interval[:-1]) * 60
        else:
            print(f"Sampling interval format ('{args.sampling_interval}') not supported for CSV generation. Using 15s.")
            step_seconds = 15


        # Write to the CSV file
        with open(args.metrics_csv_file, "w", newline="") as csvfile:
            fieldnames = ["timestamp_iso", "timestamp_unix", "node_count", "deployment_spec_replicas"]
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()

            if step_seconds > 0:
                current_ts_unix = query_start_sec
                while current_ts_unix <= query_end_sec:
                    ts_iso = datetime.datetime.fromtimestamp(current_ts_unix, datetime.timezone.utc).isoformat()
                    data_row = metrics_by_ts.get(current_ts_unix, {}) # Get data if it exists for this timestamp
                    writer.writerow({
                        "timestamp_iso": ts_iso,
                        "timestamp_unix": current_ts_unix,
                        "node_count": data_row.get("node_count"), # Returns None if the key does not exist
                        "deployment_spec_replicas": data_row.get("spec_replicas")
                    })
                    current_ts_unix += step_seconds
            else: # Fallback if step_seconds is not calculable, use found timestamps
                 sorted_timestamps = sorted(metrics_by_ts.keys())
                 for ts_unix in sorted_timestamps:
                    ts_iso = datetime.datetime.fromtimestamp(ts_unix, datetime.timezone.utc).isoformat()
                    writer.writerow({
                        "timestamp_iso": ts_iso,
                        "timestamp_unix": ts_unix,
                        "node_count": metrics_by_ts[ts_unix].get("node_count"),
                        "deployment_spec_replicas": metrics_by_ts[ts_unix].get("spec_replicas")
                    })

        print(f"Metrics exported to '{args.metrics_csv_file}'")

if __name__ == "__main__":
    # main() # For testing, you might want to comment this out to prevent execution on import
    # Example of command-line execution:
    # python script_name.py your_app_name --namespace your_namespace --wait_minutes 0.5 --prometheus_url http://your.prometheus.url:9090
    
    # Example of how you might call it if this file were imported:
    # import sys
    # # Simulate command-line arguments
    # sys.argv = ['run_experiment.py', 'my-test-app', '--namespace', 'default', '--wait_minutes', '0.1']
    main()