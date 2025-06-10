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
        # Increased timeout for kubectl commands to 12 minutes to handle slow rollouts or network issues
        result = subprocess.run(full_command, check=True, capture_output=True, text=True, timeout=720) 
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
        response = requests.get(api_url, params=params, timeout=60) # Timeout increased to 60 seconds
        response.raise_for_status()
        data = response.json()
        if data["status"] == "success":
            if "result" in data["data"] and len(data["data"]["result"]) > 0:
                return data["data"]["result"] # Returns a list of metric objects
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
    parser.add_argument("--experiment_name", help="Name of the experiment. Used to generate times and metrics file names. Defaults to 'YYYYMMDD_HHmm_{application_name}'.")
    parser.add_argument("--namespace", default="default", help="Kubernetes namespace to operate in (default: default).")
    parser.add_argument("--wait_minutes", type=float, default=1.0, help="Minutes to wait between scaling steps (default: 1.0, can be a float).")
    parser.add_argument("--prometheus_url", default="http://localhost:9090", help="URL of the Prometheus server (default: http://localhost:9090).")
    parser.add_argument("--sampling_interval", default="15s", help="Sampling interval for Prometheus queries (default: 15s).")
    parser.add_argument("--max_replicas", type=int, default=4, help="Maximum number of replicas to scale up to (default: 4).")
    parser.add_argument("--step_size", type=int, default=1, help="Step size for scaling replicas (default: 1).")

    args = parser.parse_args()

    # Generate default experiment_name if not provided
    if not args.experiment_name:
        current_time = datetime.datetime.now().strftime("%Y%m%d_%H%M")
        args.experiment_name = f"{current_time}_{args.application_name}"

    # Ensure the "data" folder exists
    data_folder = "data"
    os.makedirs(data_folder, exist_ok=True)

    # Derive file names from experiment_name and save them in the "data" folder
    times_file = os.path.join(data_folder, f"{args.experiment_name}_times.txt")
    metrics_csv_file = os.path.join(data_folder, f"{args.experiment_name}_export.csv")

    deployment_yaml_file = os.path.join(".", "..", "webapps", f"{args.application_name}-deployment.yaml")
    deployment_yaml_file = os.path.normpath(deployment_yaml_file)

    deployment_k8s_name = f"{args.application_name}-deployment"
    rollout_timeout = "10m"

    # 1. Start time recording
    start_time_dt = datetime.datetime.now(datetime.timezone.utc)
    start_time_unix = start_time_dt.timestamp()
    start_time_iso = start_time_dt.isoformat()

    print(f"Experiment start: {start_time_iso}")
    with open(times_file, "w") as f:
        f.write(f"START_TIME_ISO={start_time_iso}\n")
        f.write(f"START_TIME_UNIX={start_time_unix}\n")

    try:
        wait_seconds = args.wait_minutes * 60

        # 2. Deploy the application and wait for it to be ready
        print(f"\n--- Deploying application: {args.application_name} in namespace {args.namespace} from {deployment_yaml_file} ---")
        if not os.path.exists(deployment_yaml_file):
            print(f"ERROR: Deployment file '{deployment_yaml_file}' not found.")
            return 1
        run_kubectl_command(["apply", "-f", deployment_yaml_file, "-n", args.namespace])
        print(f"Deployment '{deployment_k8s_name}' applied.")

        print(f"\n--- Waiting for deployment '{deployment_k8s_name}' to be ready... ---")
        run_kubectl_command(["rollout", "status", f"deployment/{deployment_k8s_name}", "-n", args.namespace, f"--timeout={rollout_timeout}"])
        print(f"Deployment '{deployment_k8s_name}' is ready.")

        # 3. Perform scaling steps
        print(f"\n--- Scaling {deployment_k8s_name} from 2 up to {args.max_replicas} replicas and then down ---")
        
        # Scale up
        for replicas in range(2, args.max_replicas + 1, args.step_size):
            print(f"\n--- Scaling {deployment_k8s_name} to {replicas} replicas ---")
            run_kubectl_command(["scale", "deployment", deployment_k8s_name, f"--replicas={replicas}", "-n", args.namespace])
            print(f"--- Waiting for rollout to complete for {replicas} replicas... ---")
            run_kubectl_command(["rollout", "status", f"deployment/{deployment_k8s_name}", "-n", args.namespace, f"--timeout={rollout_timeout}"])
            print(f"Deployment is stable with {replicas} replicas.")
            print(f"--- Waiting for {args.wait_minutes} minutes to collect metrics ---")
            time.sleep(wait_seconds)

        # Scale down
        for replicas in range(args.max_replicas - args.step_size, 1, -args.step_size):
            print(f"\n--- Scaling {deployment_k8s_name} to {replicas} replicas ---")
            run_kubectl_command(["scale", "deployment", deployment_k8s_name, f"--replicas={replicas}", "-n", args.namespace])
            print(f"--- Waiting for rollout to complete for {replicas} replicas... ---")
            run_kubectl_command(["rollout", "status", f"deployment/{deployment_k8s_name}", "-n", args.namespace, f"--timeout={rollout_timeout}"])
            print(f"Deployment is stable with {replicas} replicas.")
            print(f"--- Waiting for {args.wait_minutes} minutes to collect metrics ---")
            time.sleep(wait_seconds)
            
        print("Scaling completed.")

    except Exception as e:
        print(f"An error interrupted the experiment during kubectl operations: {e}")
    finally:
        # 4. End time recording
        end_time_dt = datetime.datetime.now(datetime.timezone.utc)
        end_time_unix = end_time_dt.timestamp()
        end_time_iso = end_time_dt.isoformat()

        print(f"\nExperiment end (or attempt): {end_time_iso}")
        with open(times_file, "a") as f:
            f.write(f"END_TIME_ISO={end_time_iso}\n")
            f.write(f"END_TIME_UNIX={end_time_unix}\n")

    # 5. Generate CSV from Prometheus metrics
    print(f"\n--- Generating CSV of metrics from {args.prometheus_url} ---")

    final_start_time_unix_for_query = start_time_unix
    final_end_time_unix_for_query = end_time_unix
    try:
        times_data = {}
        with open(times_file, "r") as f:
            for line in f:
                if "=" in line:
                    key, value = line.strip().split("=", 1)
                    times_data[key] = value
        final_start_time_unix_for_query = float(times_data.get("START_TIME_UNIX", start_time_unix))
        final_end_time_unix_for_query = float(times_data.get("END_TIME_UNIX", end_time_unix))
        start_dt_str = datetime.datetime.fromtimestamp(final_start_time_unix_for_query, datetime.timezone.utc).isoformat()
        end_dt_str = datetime.datetime.fromtimestamp(final_end_time_unix_for_query, datetime.timezone.utc).isoformat()
        print(f"Interval for Prometheus query: from {start_dt_str} to {end_dt_str}")
    except Exception as e:
        print(f"Warning: unable to read precise times from file '{times_file}'. Using script start/end times. Error: {e}")

    # --- INIZIO DELLA LOGICA DI ELABORAZIONE METRICHE CORRETTA ---
    
    metric_replicas_query = f'kube_deployment_spec_replicas{{deployment="{deployment_k8s_name}", namespace="{args.namespace}"}}'
    # Uso l'etichetta che hai verificato funzionare dal tuo screenshot
    node_type_label_name = 'label_node_kubernetes_io_instance_type' 
    metric_nodes_query = f"count by ({node_type_label_name}) (kube_node_labels)"

    print(f"Metric Query for Replicas: {metric_replicas_query}")
    print(f"Metric Query for Nodes: {metric_nodes_query}")

    replicas_data_raw = query_prometheus_range(args.prometheus_url, metric_replicas_query, final_start_time_unix_for_query, final_end_time_unix_for_query, args.sampling_interval)
    nodes_data_raw = query_prometheus_range(args.prometheus_url, metric_nodes_query, final_start_time_unix_for_query, final_end_time_unix_for_query, args.sampling_interval)

    metrics_by_ts = {}
    
    # Processa i dati delle repliche (che è una singola serie)
    if replicas_data_raw:
        for ts_float, val_str in replicas_data_raw[0].get("values", []):
            ts_int = int(float(ts_float))
            if ts_int not in metrics_by_ts:
                metrics_by_ts[ts_int] = {}
            metrics_by_ts[ts_int]["deployment_spec_replicas"] = val_str

    # Processa i dati dei nodi (che sono molte serie, una per tipo di nodo)
    node_types = set()
    for series in nodes_data_raw:
        node_type = series.get("metric", {}).get(node_type_label_name)
        if not node_type:
            continue # Salta la serie se per qualche motivo non ha l'etichetta che cerchiamo
        node_types.add(node_type)
        for ts_float, val_str in series.get("values", []):
            ts_int = int(float(ts_float))
            if ts_int not in metrics_by_ts:
                metrics_by_ts[ts_int] = {}
            metrics_by_ts[ts_int][node_type] = val_str

    if not metrics_by_ts:
        print("No metric data retrieved from Prometheus. The CSV file will not be generated or will be empty.")
    else:
        # Determina l'intervallo per la generazione del CSV
        step_seconds = 15 
        try:
            if args.sampling_interval.endswith('s'): step_seconds = int(args.sampling_interval[:-1])
            elif args.sampling_interval.endswith('m'): step_seconds = int(args.sampling_interval[:-1]) * 60
        except (ValueError, IndexError):
            print(f"Could not parse sampling interval '{args.sampling_interval}'. Using {step_seconds}s for CSV.")
        
        # Genera dinamicamente le colonne del CSV
        sorted_node_types = sorted(list(node_types))
        fieldnames = ["timestamp_iso", "timestamp_unix", "deployment_spec_replicas"] + sorted_node_types
        
        print(f"CSV Headers will be: {fieldnames}")

        with open(metrics_csv_file, "w", newline="") as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames, restval=None) # restval=None scrive celle vuote se manca un dato
            writer.writeheader()

            query_start_sec = int(final_start_time_unix_for_query)
            query_end_sec = int(final_end_time_unix_for_query)
            
            if step_seconds > 0:
                available_timestamps = sorted(metrics_by_ts.keys())
                # Itera su un range temporale completo per avere un CSV consistente
                for current_ts_unix in range(query_start_sec, query_end_sec + 1, step_seconds):
                    # Trova il punto dati reale più vicino nel tempo
                    closest_ts = min(available_timestamps, key=lambda ts: abs(ts - current_ts_unix), default=None)
                    
                    data_for_row = {}
                    # Usa il dato solo se è ragionevolmente vicino al nostro timestamp ideale
                    if closest_ts is not None and abs(closest_ts - current_ts_unix) < step_seconds:
                        data_for_row = metrics_by_ts.get(closest_ts, {})

                    # Prepara la riga da scrivere, usando .get() per gestire dati mancanti
                    row_to_write = {
                        "timestamp_iso": datetime.datetime.fromtimestamp(current_ts_unix, datetime.timezone.utc).isoformat(),
                        "timestamp_unix": current_ts_unix,
                        "deployment_spec_replicas": data_for_row.get("deployment_spec_replicas")
                    }
                    for node_type in sorted_node_types:
                        row_to_write[node_type] = data_for_row.get(node_type, '0')  # Default to '0' if no data
                    
                    writer.writerow(row_to_write)

        print(f"Metrics successfully exported to '{metrics_csv_file}'")

if __name__ == "__main__":
    main()