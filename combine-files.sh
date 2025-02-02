#!/bin/bash

# Set the name of the output file
output_file="combined_files.txt"

# Get the current directory automatically
repo_root="$PWD"

# Check for the -l option
if [ "$1" == "-l" ]; then
  # List all files in the output file
  if [ -f "$output_file" ]; then
    head -n 1 "$output_file" | sed 's/Files used in this run: //'  # Extract file list from the first line
  else
    echo "The output file ($output_file) does not exist."
  fi
  exit 0  # Exit after listing files
fi

# If no arguments are provided, use the last used arguments
if [ $# -eq 0 ]; then
  if [ -f "$output_file" ]; then
    echo "Updating with files from the last run."
    # Extract the last used arguments from the output file
    last_args=$(head -n 1 "$output_file" | sed 's/Files used in this run: //')
    set -- $last_args  # Set the positional parameters to the last used arguments
  else
    echo "Error: No file names provided and no previous run found."
    echo "Usage: $0 file1.txt file2.txt file3.txt ..."
    exit 1
  fi
fi

# Read the first line of the existing file to get the old file list
old_files=""
if [ -f "$output_file" ]; then
  old_files=$(head -n 1 "$output_file")
fi

# Create a temporary file
temp_file=$(mktemp)

# Add the list of file patterns to the top of the temporary file
echo "Files used in this run: $@" >> "$temp_file"
echo "" >> "$temp_file" 

# Process each file name provided as a command-line argument
for file_pattern in "$@"; do
  # Find files matching the pattern (including [id].ts)
  find "$repo_root" -name "$file_pattern" -type f -print0 | while IFS= read -r -d $'\0' file; do
    # Check if the file is text-based
    if file "$file" | grep -q "text"; then
      cat "$file" >> "$temp_file"
      echo "" >> "$temp_file" 
    else
      echo "Skipping non-text file: $file"
    fi
  done
done

# Overwrite the output file with the contents of the temporary file
mv "$temp_file" "$output_file"

# Extract the actual file names from the old_files string
old_files_array=(${old_files//Files used in this run: /})

# Print the changes to the console with colors using printf
printf "\e[32mFiles added:\e[0m\n"  # Green
for file_pattern in "$@"; do
  if [[ ! " ${old_files_array[@]} " =~ " ${file_pattern} " ]]; then
    printf "\e[32m%s\e[0m\n" "$file_pattern"  # Green
  fi
done

printf "\e[31mFiles removed:\e[0m\n"  # Red
for old_file in "${old_files_array[@]}"; do
  if [[ ! " $@ " =~ " ${old_file} " ]]; then
    printf "\e[31m%s\e[0m\n" "$old_file"  # Red
  fi
done