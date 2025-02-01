#!/bin/bash
# run_product.sh
#
# This script launches the main executable of the project,
# which starts the Tkinter GUI and triggers the scraping process.
#
# It automatically ensures:
#   - XQuartz is running (if not, it launches it),
#   - The DISPLAY environment variable is set,
#   - The project is run inside the pipenv virtual environment.
#
# Usage:
#   ./run_product.sh

# 1. Check if XQuartz is running (for X11-based GUIs)
if ! pgrep -x "XQuartz" > /dev/null; then
    echo "XQuartz does not appear to be running. Launching XQuartz..."
    open -a XQuartz
    sleep 2
fi

# 2. Check and set the DISPLAY variable if not already set.
if [ -z "$DISPLAY" ]; then
    echo "DISPLAY variable is not set. Setting it to default :0.0 for local GUI tests."
    export DISPLAY=:0.0
fi

# 3. Check if we're in a pipenv virtual environment.
if [ -z "$VIRTUAL_ENV" ]; then
    echo "Not inside a pipenv shell. Running using 'pipenv run'..."
    # This runs the application within the virtual environment without manual intervention.
    pipenv run python scrape.py
else
    echo "Inside pipenv environment. Running the application..."
    python scrape.py
fi

# End of run_product.sh