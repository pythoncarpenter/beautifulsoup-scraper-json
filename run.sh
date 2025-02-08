#!/bin/bash
# run.sh - Comprehensive one-click setup with recursive retry, network timeout handling,
# and graceful error handling for first-time execution.

# --- Enable Strict Error Handling ---
set -euo pipefail
trap 'echo "Error occurred at line ${LINENO}. Exiting." && exit 1' ERR

# --- Function: Retry pipenv install with network timeout handling ---
retry_pipenv_install() {
    local retries=3
    local count=1
    while [ $count -le $retries ]; do
        echo "Attempt $count of $retries: Running 'pipenv install'..."
        if pipenv install; then
            echo "pipenv install succeeded."
            return 0
        else
            echo "Attempt $count failed. Possible network issue. Retrying in 5 seconds..."
            sleep 5
        fi
        count=$((count + 1))
    done
    echo "pipenv install failed after $retries attempts."
    return 1
}

# --- Function: Check and wait for XQuartz on macOS (recursive) ---
check_xquartz_recursive() {
    if pgrep -x "XQuartz" > /dev/null; then
        echo "XQuartz is running."
    else
        echo "XQuartz not running. Retrying in 2 seconds..."
        sleep 2
        check_xquartz_recursive  # Recursive call until XQuartz is detected.
    fi
}

# --- Function: Setup environment and run scraper (recursive retry) ---
setup_and_run() {
    local attempt="${1:-1}"
    local max_attempts=5

    echo "Setup attempt $attempt of $max_attempts..."

    # Step 0: Ensure key files have execute permissions.
    chmod +x run.sh main.py setup_env.sh || echo "Warning: Could not update permissions for some files."

    # Step 1: Check for pipenv.
    if ! command -v pipenv >/dev/null 2>&1; then
        echo "Error: pipenv is not installed. Please install pipenv and try again." >&2
        exit 1
    fi

    # Step 2: Verify that Pipfile exists.
    if [ ! -f "Pipfile" ]; then
        echo "Error: Pipfile not found in the repository. Aborting." >&2
        exit 1
    fi

    # Step 3: Ensure the virtual environment exists; if not, create it.
    venv_path=$(pipenv --venv 2>/dev/null || true)
    if [ -z "$venv_path" ] || [ ! -d "$venv_path" ]; then
        echo "Virtual environment not found. Running 'pipenv install'..."
        if ! retry_pipenv_install; then
            echo "Error: 'pipenv install' failed. Aborting."
            exit 1
        fi
        # After installing, recursively call setup_and_run to re-check the environment.
        if [ "$attempt" -lt "$max_attempts" ]; then
            sleep 2
            setup_and_run $((attempt + 1))
            return
        else
            echo "Max attempts reached while creating virtual environment. Aborting."
            exit 1
        fi
    fi

    # Step 4: Check that the Python version is correct (3.12 expected).
    expected_python="3.12"
    venv_python_version=$(pipenv run python -c "import sys; print('.'.join(map(str, sys.version_info[:2])))" 2>/dev/null)
    if [ "$venv_python_version" != "$expected_python" ]; then
        echo "Error: Python version in virtual environment ($venv_python_version) does not match expected ($expected_python)." >&2
        exit 1
    fi

    # Step 5: (Optional) Verify packages are installed.
    #         Removed strict checks for pandas, numpy, statsmodels, matplotlib, and openai.
    #         If you have specific packages you DO want to enforce, add them here.

    echo "Environment checks passed."

    # Step 6: Setup system-specific GUI engine.
    os_type=$(uname)
    if [[ "$os_type" == "Darwin" ]]; then
        # On macOS, ensure XQuartz is running if your application needs X11.
        # Remove or comment out these lines if you don't need XQuartz at all:
        if ! pgrep -x "XQuartz" > /dev/null; then
            echo "XQuartz is not running. Launching XQuartz..."
            open -a XQuartz || { echo "Error: Failed to launch XQuartz. Aborting."; exit 1; }
        fi
        # Use recursive function to wait for XQuartz.
        check_xquartz_recursive
        # Set DISPLAY if not already set.
        if [ -z "${DISPLAY:-}" ]; then
            echo "DISPLAY variable not set. Setting to :0.0 for GUI support."
            export DISPLAY=:0.0
        fi
    elif [[ "$os_type" == "Linux" ]]; then
        if [ -z "${DISPLAY:-}" ]; then
            echo "Warning: DISPLAY is not set. Ensure an X server is running for GUI support." >&2
        fi
    elif [[ "$os_type" == MINGW* || "$os_type" == CYGWIN* ]]; then
        echo "Windows detected. Please ensure you have a compatible GUI engine available." >&2
    fi

    # Step 7: Run the scraper application.
    echo "Starting the scraper application..."
    if [ -z "${VIRTUAL_ENV:-}" ]; then
        pipenv run python main.py || { echo "Error: Running main.py failed."; exit 1; }
    else
        python main.py || { echo "Error: Running main.py failed."; exit 1; }
    fi

    echo "Scraper application completed successfully."
    echo "Check scrape.log and the output JSON file for results."
}

# --- Kick Off the Setup Process ---
setup_and_run 1