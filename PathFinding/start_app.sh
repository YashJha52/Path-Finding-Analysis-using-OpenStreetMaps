#!/bin/bash

# --- Pathfinding App Launcher ---

# Get the directory where this script is located
# This makes the script work no matter where you run it from
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"

echo "📍 Project Directory: $SCRIPT_DIR"

# 1. Activate the virtual environment
echo "🔌 Activating 'isp1' environment..."
source "$SCRIPT_DIR/isp1/bin/activate"

# 2. Run the Streamlit app using your specified command
echo "🚀 Starting the Pathfinding App..."
python3 -m streamlit run "$SCRIPT_DIR/IS_Project.py"

# This line will only run after you stop the app with Ctrl+C
echo "✅ App stopped. Deactivating environment."
deactivate
