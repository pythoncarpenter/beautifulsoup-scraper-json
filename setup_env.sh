#!/bin/zsh

# --- Configuration ---
# REPLACE with the actual path to your project directory.
project_dir="$HOME/z9b-projects/business_proj/openai-short"  
# REPLACE with the major.minor Python version you expect (e.g., 3.12).
python_interpreter="3.12"  

# --- Function to Check for Errors and Exit ---
check_error() {
  if [[ "$?" -ne 0 ]]; then
    echo "Error: $1"
    exit 1
  fi
}

# --- 1. Check if the Project Directory Exists ---
echo "Checking project directory..."
if [[ ! -d "$project_dir" ]]; then
  echo "Error: Project directory not found: $project_dir"
  exit 1
fi
cd "$project_dir"
check_error "Could not change to project directory: $project_dir"

# --- 2. Check if pyenv is Installed and Working ---
echo "Checking pyenv installation..."
if ! command -v pyenv 1>/dev/null 2>&1; then
  echo "Error: pyenv is not installed."
  exit 1
fi

pyenv_version=$(pyenv --version)
check_error "Could not get pyenv version"
echo "pyenv version: $pyenv_version"

# --- 3. Check if the Correct Python Version is Installed ---
echo "Checking Python version installation..."
if ! pyenv versions | grep -q "$python_interpreter"; then
  echo "Error: Python $python_interpreter is not installed with pyenv."
  exit 1
fi

# --- 4. Check if pipenv is Installed ---
echo "Checking pipenv installation..."
if ! command -v pipenv 1>/dev/null 2>&1; then
  echo "Error: pipenv is not installed."
  exit 1
fi

pipenv_version=$(pipenv --version)
check_error "Could not get pipenv version"
echo "pipenv version: $pipenv_version"

# --- 5. Check if Pipfile Exists ---
echo "Checking for Pipfile..."
if [[ ! -f "Pipfile" ]]; then
  echo "Error: Pipfile not found in the project directory."
  exit 1
fi
echo "Pipfile found."

# --- 6. Check if Virtual Environment Exists ---
echo "Checking for virtual environment..."
venv_path=$(pipenv --venv)
if [[ ! -d "$venv_path" ]]; then
  echo "Error: Virtual environment not found."
  exit 1
fi
echo "Virtual environment found: $venv_path"

# --- 7. Check Python Version Inside Virtual Environment ---
echo "Checking Python version inside virtual environment..."
venv_python_version=$(pipenv run python -c "import sys; print('.'.join(map(str, sys.version_info[:2])))")
check_error "Could not get Python version from virtual environment"

if [[ "$venv_python_version" != "$python_interpreter" ]]; then
  echo "Error: Python version in virtual environment ($venv_python_version) does not match expected version ($python_interpreter)."
  exit 1
fi

echo "Python version in virtual environment matches expected version: $python_interpreter"

# --- 8. Check if Required Dependencies Are Installed ---
echo "Checking installed dependencies..."
pipenv run pip list > installed_packages.txt
check_error "Could not get list of installed packages"

# List the required packages (update this array as needed)
packages=("pandas" "numpy" "statsmodels" "matplotlib" "openai")
for package in "${packages[@]}"; do
  if ! grep -q "$package" installed_packages.txt; then
    echo "Error: Package '$package' is not installed in the virtual environment."
    exit 1
  fi
done
rm installed_packages.txt  # Clean up temporary file
echo "All required packages are installed."

# --- Final Instructions ---
echo ""
echo "Environment setup was successful!"
echo "You can now activate the virtual environment with: pipenv shell"
exit 0