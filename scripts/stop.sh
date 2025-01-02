#!/bin/bash

# Get the directory where the script is located
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# Stop Flask application
if [ -f "$PROJECT_ROOT/.flask.pid" ]; then
    echo "Stopping Flask application..."
    PID=$(cat "$PROJECT_ROOT/.flask.pid")
    if ps -p $PID > /dev/null; then
        kill $PID
    fi
    rm "$PROJECT_ROOT/.flask.pid"
else
    # Try to find and kill Flask process
    echo "Stopping any running Flask processes..."
    pkill -f "python.*app.py"
fi

echo "All services stopped successfully!"
