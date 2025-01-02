#!/bin/bash

# Get the directory where the script is located
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# Activate virtual environment
source "$PROJECT_ROOT/venv/bin/activate"

# Start the Flask application
echo "Starting Flask application..."
cd "$PROJECT_ROOT/website"
python app.py &
echo $! > "$PROJECT_ROOT/.flask.pid"

echo "Services started successfully!"
echo "Access the application at http://localhost:5000"
