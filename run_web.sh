#!/bin/bash
# TVDR Smart-City Command Center - Web UI Launcher
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
cd "$SCRIPT_DIR"

if [ -f "./venv/bin/python" ]; then
    PYTHON_EXEC="./venv/bin/python"
elif [ -f "./venv/bin/python3" ]; then
    PYTHON_EXEC="./venv/bin/python3"
else
    PYTHON_EXEC="python3"
fi

echo "=========================================================="
echo "🚦 Launching TVDR Smart-City Command Center Web App..."
echo "🌐 Browser URL: http://lo/calhost:5001"
echo "=========================================================="

exec "$PYTHON_EXEC" web_app.py "$@"

