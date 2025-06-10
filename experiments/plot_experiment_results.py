#!/usr/bin/env python3
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import argparse
import os

def create_combined_plot(csv_filepath, experiment_name):
    """
    Reads experiment data from a CSV file and generates a single plot
    that combines replica counts and node type counts over time.
    """
    # --- 1. Data Loading and Preparation ---
    
    # Check if the file exists
    if not os.path.exists(csv_filepath):
        print(f"Error: The file '{csv_filepath}' was not found.")
        return

    print(f"Reading data from '{csv_filepath}'...")
    # Read the CSV file into a pandas DataFrame
    df = pd.read_csv(csv_filepath)

    # Convert the timestamp column to datetime objects, which is better for plotting
    df['timestamp_iso'] = pd.to_datetime(df['timestamp_iso'], errors='coerce')
    df.dropna(subset=['timestamp_iso'], inplace=True)

    # Identify all node columns dynamically
    standard_columns = ['timestamp_iso', 'timestamp_unix', 'deployment_spec_replicas', 'deployment_ready_replicas']
    node_columns = [col for col in df.columns if col not in standard_columns]

    # Convert all relevant columns to numeric types, filling any errors/missing values with 0
    for col in standard_columns[2:] + node_columns:
        df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)

    print("Data loaded successfully. Generating combined plot...")

    # --- 2. Create the Combined Plot ---

    fig, ax = plt.subplots(figsize=(18, 9)) # Create a single figure and axes object

    # Plot replica counts with a distinct, prominent style
    ax.plot(df['timestamp_iso'], df['deployment_spec_replicas'], label='Desired Replicas', 
            linestyle='-', marker='o', markersize=5, linewidth=2.5, color='royalblue')
    ax.plot(df['timestamp_iso'], df['deployment_ready_replicas'], label='Ready Replicas', 
            linestyle='-', marker='x', markersize=5, linewidth=2.5, color='darkorange')

    # Plot each node type count with a lighter, dashed style
    # Using a predefined list of colors to cycle through for the nodes
    node_colors = ['green', 'red', 'purple', 'brown', 'pink', 'gray']
    for i, node_type in enumerate(node_columns):
        ax.plot(df['timestamp_iso'], df[node_type], label=f'Nodes: {node_type}', 
                linestyle='--', linewidth=1.5, color=node_colors[i % len(node_colors)])

    # Formatting the plot
    ax.set_title(f'Full Experiment Summary: Pod Replicas and Node Provisioning\n({experiment_name})', fontsize=18)
    ax.set_xlabel('Time', fontsize=12)
    ax.set_ylabel('Count (Replicas or Nodes)', fontsize=12)
    ax.legend(fontsize=10)
    ax.grid(True, which='both', linestyle='--', linewidth=0.5)
    
    # Set major ticks to appear every minute
    ax.xaxis.set_major_locator(mdates.MinuteLocator(interval=1))
    # Format the major tick labels to show Hour:Minute:Second
    ax.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M:%S'))
    # Optional: Add minor ticks for every 15 seconds for more detail
    ax.xaxis.set_minor_locator(mdates.SecondLocator(interval=15))
    
    fig.autofmt_xdate() # Rotate and align the tick labels nicely

    plt.tight_layout() # Adjust layout to make room for labels

    # Save the plot to a file inside the experiment folder
    experiment_folder = os.path.join("data", experiment_name)
    os.makedirs(experiment_folder, exist_ok=True)  # Ensure the folder exists
    plot_filename = os.path.join(experiment_folder, f'{experiment_name}_full_summary.png')
    fig.savefig(plot_filename, dpi=300)
    print(f"Combined plot saved to '{plot_filename}'")
    
    plt.close(fig) # Close the plot figure to free up memory

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate a combined plot from experiment CSV data.")
    parser.add_argument("experiment_name", help="The base name of the experiment (e.g., '20250610_1155_single-tier').")
    
    args = parser.parse_args()
    
    # Construct the full file path from the experiment name
    csv_filepath = os.path.join("data", args.experiment_name, f"{args.experiment_name}_export.csv")

    create_combined_plot(csv_filepath, args.experiment_name)
