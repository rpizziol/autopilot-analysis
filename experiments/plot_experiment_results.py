#!/usr/bin/env python3
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import argparse
import os

def create_plots(csv_filepath, experiment_name):
    """
    Reads experiment data from a CSV file and generates two plots.
    1. A comparison of desired vs. ready replicas.
    2. A comparison of ready replicas vs. the count of each node type.
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
    # The 'coerce' option will turn any parsing errors into NaT (Not a Time)
    df['timestamp_iso'] = pd.to_datetime(df['timestamp_iso'], errors='coerce')

    # Drop any rows where the timestamp could not be parsed
    df.dropna(subset=['timestamp_iso'], inplace=True)

    # Identify all node columns dynamically by finding columns that are not the standard ones
    standard_columns = ['timestamp_iso', 'timestamp_unix', 'deployment_spec_replicas', 'deployment_ready_replicas']
    node_columns = [col for col in df.columns if col not in standard_columns]

    # Convert all relevant columns to numeric types, filling any errors/missing values with 0
    for col in standard_columns[2:] + node_columns:
        df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)

    print("Data loaded successfully. Generating plots...")

    # --- 2. Plot 1: Desired vs. Ready Replicas ---

    fig1, ax1 = plt.subplots(figsize=(15, 7)) # Create a figure and an axes object

    ax1.plot(df['timestamp_iso'], df['deployment_spec_replicas'], label='Desired Replicas', linestyle='--', marker='o', markersize=4)
    ax1.plot(df['timestamp_iso'], df['deployment_ready_replicas'], label='Ready Replicas', linestyle='-', marker='x', markersize=4)

    # Formatting the plot
    ax1.set_title('Desired vs. Ready Pod Replicas Over Time', fontsize=16)
    ax1.set_xlabel('Time', fontsize=12)
    ax1.set_ylabel('Number of Replicas', fontsize=12)
    ax1.legend()
    ax1.grid(True, which='both', linestyle='--', linewidth=0.5)
    
    # Improve date formatting on the x-axis
    ax1.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M:%S'))
    fig1.autofmt_xdate() # Rotate and align the tick labels nicely

    # Save the first plot to a file, using the experiment name
    plot1_filename = os.path.join("data", f'{experiment_name}_replicas_comparison.png')
    fig1.savefig(plot1_filename, dpi=300)
    print(f"Plot 1 saved to '{plot1_filename}'")


    # --- 3. Plot 2: Ready Replicas vs. Node Types ---

    fig2, ax2 = plt.subplots(figsize=(15, 7))

    # Plot the number of ready replicas with a distinct style
    ax2.plot(df['timestamp_iso'], df['deployment_ready_replicas'], label='Ready Replicas', color='black', linewidth=2.5, linestyle=':', zorder=10)

    # Plot each node type count
    for node_type in node_columns:
        ax2.plot(df['timestamp_iso'], df[node_type], label=f'Nodes: {node_type}', marker='.', linestyle='-')

    # Formatting the plot
    ax2.set_title('Ready Replicas vs. Node Provisioning Over Time', fontsize=16)
    ax2.set_xlabel('Time', fontsize=12)
    ax2.set_ylabel('Count (Replicas or Nodes)', fontsize=12)
    ax2.legend()
    ax2.grid(True, which='both', linestyle='--', linewidth=0.5)

    # Improve date formatting on the x-axis
    ax2.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M:%S'))
    fig2.autofmt_xdate()

    # Save the second plot to a file, using the experiment name
    plot2_filename = os.path.join("data", f'{experiment_name}_replicas_vs_nodes.png')
    fig2.savefig(plot2_filename, dpi=300)
    print(f"Plot 2 saved to '{plot2_filename}'")
    
    plt.close('all') # Close all plot figures to free up memory

if __name__ == "__main__":
    # Setup command-line argument parsing
    parser = argparse.ArgumentParser(description="Generate plots from experiment CSV data.")
    parser.add_argument("experiment_name", help="The base name of the experiment (e.g., '20250610_1155_single-tier').")
    
    args = parser.parse_args()
    
    # Construct the full file path from the experiment name
    # Assumes the CSV is in a 'data' subfolder and follows the naming convention
    csv_filepath = os.path.join("data", f"{args.experiment_name}_export.csv")

    create_plots(csv_filepath, args.experiment_name)
