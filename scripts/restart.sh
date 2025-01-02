#!/bin/bash

# Get the directory where the script is located
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"

# Run stop script
echo "Stopping services..."
"$SCRIPT_DIR/stop.sh"

# Wait a moment for processes to fully stop
sleep 2

# Run start script
echo "Starting services..."
"$SCRIPT_DIR/start.sh"
