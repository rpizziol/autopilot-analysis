#!/bin/bash

# Script to install Docker Engine and Docker Compose on Ubuntu using the official Docker repository.
# Must be run with sudo privileges.

# Exit immediately if a command exits with a non-zero status.
set -e
# Treat unset variables as an error when substituting.
set -u
# Pipeline return status is the status of the last command to exit with a non-zero status.
set -o pipefail

# --- Configuration ---
# Get the username of the user who invoked sudo
# Fallback to logname if SUDO_USER is not set (e.g., if run directly as root)
ORIGINAL_USER=${SUDO_USER:-$(logname)}

# --- Check for root privileges ---
if [ "$(id -u)" -ne 0 ]; then
   echo "This script must be run as root. Please use sudo." >&2
   exit 1
fi

echo "--- Docker Installation Script ---"
echo "Running as root. Will add user '$ORIGINAL_USER' to the docker group."
echo ""
sleep 2

# --- Step 1: Update package list and install prerequisites ---
echo ">>> [1/6] Updating package list and installing prerequisites..."
apt-get update
apt-get install -y ca-certificates curl gnupg
echo "Prerequisites installed."
echo ""

# --- Step 2: Add Docker's official GPG key ---
echo ">>> [2/6] Adding Docker's official GPG key..."
install -m 0755 -d /etc/apt/keyrings
# Remove existing key file if it exists to avoid potential issues
rm -f /etc/apt/keyrings/docker.asc
curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
chmod a+r /etc/apt/keyrings/docker.asc
echo "Docker GPG key added."
echo ""

# --- Step 3: Set up the Docker repository ---
echo ">>> [3/6] Setting up the Docker repository..."
# Get OS version codename
OS_CODENAME=$(. /etc/os-release && echo "$VERSION_CODENAME")
echo \
  "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu \
  ${OS_CODENAME} stable" > /etc/apt/sources.list.d/docker.list
echo "Docker repository added for Ubuntu ${OS_CODENAME}."
echo ""

# --- Step 4: Install Docker Engine, CLI, Containerd, and plugins ---
echo ">>> [4/6] Updating package list again and installing Docker packages..."
apt-get update
apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
echo "Docker packages installed."
echo ""

# --- Step 5: Verify Docker installation (Optional but recommended) ---
echo ">>> [5/6] Verifying Docker installation by running hello-world..."
if docker run hello-world; then
    echo "Docker hello-world container ran successfully."
else
    echo "WARNING: Docker hello-world container failed to run. Please check the installation." >&2
    # Decide if you want to exit here or continue
    # exit 1
fi
echo ""

# --- Step 6: Add the original user to the docker group ---
echo ">>> [6/6] Adding user '$ORIGINAL_USER' to the 'docker' group..."
# Check if group exists, create if not (should normally exist after install)
if ! getent group docker > /dev/null; then
    echo "    'docker' group not found, creating it..."
    groupadd docker
fi
# Add user to the group
usermod -aG docker "$ORIGINAL_USER"
echo "User '$ORIGINAL_USER' added to the 'docker' group."
echo ""

# --- Final Instructions ---
echo "--- Docker Installation Complete ---"
echo ""
echo "Successfully installed Docker Engine and Docker Compose."
echo ""
echo "IMPORTANT:"
echo "  User '$ORIGINAL_USER' has been added to the 'docker' group."
echo "  You MUST log out and log back in for this group change to take effect."
echo "  Alternatively, you can run 'newgrp docker' in your current shell,"
echo "  but logging out/in is recommended for a full effect across all sessions."
echo ""
echo "After logging back in, you should be able to run 'docker' commands without sudo."
echo "--- End of Script ---"

exit 0