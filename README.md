# GitHub Issues Scraper

A GitHub issues scraper with a Tkinter GUI that fetches issues from a GitHub repository and filters them based on keywords extracted from a prompt using TF-IDF analysis. Matching issues are saved in a JSON file in chunks for efficiency.

## Features

- **Graphical User Interface (GUI)**
  - Input field for the GitHub Issues/Pull URL.
  - Large text area (prompt) for entering instructions or context.
  - Output file path entry.
  - Displays extracted keywords.
  - Submit button disables during processing (showing a "Loading…" state) and re-enables when finished.

- **Keyword Extraction**
  - Uses TF-IDF analysis (via scikit-learn) on the provided prompt to extract the top keywords.
  - The extracted keywords are displayed in the GUI and used to filter issues.

- **Efficient Issue Scraping**
  - Retrieves issues via the GitHub API.
  - Skips entire pages that do not contain any of the extracted keywords to speed up processing.
  - Uses a persistent `requests.Session()` and a timeout for API calls.
  - Filters and stores only the necessary fields (issue number, title, body, URL).
  - Uses a chunked writing approach to reduce memory usage and minimize file I/O overhead.

## Requirements

- **Python 3.12+** (or a compatible version)
- **Pipenv** for managing the virtual environment and dependencies
- Python packages:
  - `requests`
  - `python-dotenv`
  - `scikit-learn`
  - `tkinter` (usually bundled with Python)
  - *(Optional)* `tiktoken` for more accurate token counting

## Setup

1. **Clone the Repository**

   ```bash
   git clone <repository_url>
   cd <repository_directory>