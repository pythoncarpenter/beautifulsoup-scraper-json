# Specifications for GitHub Issues/Fix Pages Scraper Widget

## 1. Overview

- **Purpose:**  
  Scrapes GitHub issues (and optionally pull requests) from a user-specified repository URL. Filters issues based on keywords extracted via TF‑IDF from a provided prompt, then exports the filtered results to a JSON file.

- **User Interaction:**  
  Provides a graphical interface (Tkinter GUI) where users can input:
  - A GitHub Issues/Pull URL.
  - A text prompt (used for keyword extraction).
  - An output file path (where the JSON result will be stored).

- **Concurrency:**  
  Runs the scraping task in a background thread to keep the GUI responsive.

- **Logging:**  
  Detailed logging (DEBUG level) is implemented, with output written to a `scrape.log` file for traceability and debugging.

---

## 2. Environment and Dependencies

- **Python Version:**  
  Python 3.x (tested with Python 3.12.1).

- **Required Libraries/Modules:**
  - **Standard Libraries:**  
    `os`, `re`, `sys`, `json`, `uuid`, `logging`, `datetime`, `threading`
  - **Third-Party Libraries:**  
    `requests` (HTTP requests), `python-dotenv` (environment variable loading), `scikit-learn` (TF‑IDF via `TfidfVectorizer`), `tkinter` (GUI toolkit)

- **Environment Variables:**
  - **GITHUB_TOKEN:**  
    Must be set (ideally in a `.env` file located next to the script) for authenticated GitHub API access.

---

## 3. Logging & Debugging

- **Log File:**  
  `scrape.log` located in the project root.

- **Log Configuration:**  
  - **Level:** DEBUG (detailed logs for all steps, including errors)
  - **Format:** Timestamp, log level, and message (formatted as `"YYYY-MM-DD HH:MM:SS LEVEL: message"`).

- **Usage:**  
  Logs key events such as:
  - Initialization of environment and GUI.
  - Parsing and validation of input URL.
  - Results of keyword extraction.
  - HTTP request outcomes for each API call.
  - Any errors (e.g., network issues, token problems, JSON formatting errors).

---

## 4. User Interface (GUI) Specifications

- **Toolkit:** Tkinter  
- **Window Title:** `"GitHub Issues/Fix Pages Scraper (REST API)"`

- **Input Fields:**
  - **GitHub Issues/Pull URL:**  
    Multi-line `Text` widget for entering the URL.
  - **Prompt Text:**  
    Multi-line `Text` widget for entering descriptive prompt text that will be analyzed for keywords.
  - **Output File Path:**  
    Single-line `Entry` widget; if left blank, defaults to `~/Desktop/issues.json`.

- **Display Elements:**
  - **Keywords Label:**  
    Shows the extracted keywords after processing the prompt text.
  - **Submit Button:**  
    Initiates processing. Changes state to “Loading...” and disables inputs during processing.

- **Window Behavior:**
  - Prevents premature closure (logs an error if the window is closed before a submission is made).
  - Uses a protocol handler (`WM_DELETE_WINDOW`) to manage GUI termination safely.
  - Shows a message box on successful completion, then gracefully closes the GUI.

---

## 5. Functional Components & Workflow

### 5.1. Environment Setup
- **Load Environment Variables:**  
  Uses `dotenv` to load a `.env` file located in the same directory as the script.  
- **Retrieve Token:**  
  Fetches `GITHUB_TOKEN` for authenticating API requests.

### 5.2. Keyword Extraction & Filtering
- **Extract Keywords:**  
  Uses `TfidfVectorizer` from scikit-learn on the provided prompt text.  
  - Splits the prompt into non-empty lines (documents) and computes TF‑IDF scores.
  - Extracts a specified number (default 10) of top keywords.

- **Filter Keywords:**  
  The list is further filtered to:
  - Remove any keyword matching the GitHub repository name.
  - Exclude keywords from a blocked list (`{"bug", "report", "issue", "fix", "error", "problem", "test", "todo"}`).
  - Finally, only up to a desired count (default 5) are retained.

### 5.3. GitHub URL Parsing
- **Function:** `parse_repo_url(url)`  
  - Validates that the URL is structured for GitHub issues or pull requests.
  - Extracts and returns the repository owner and name.
  - Raises an error if the URL is not valid.

### 5.4. Scraping Process
- **Function:** `scrape_github_issues_with_filter(...)`
  - **Input Parameters:**  
    - GitHub URL  
    - Output file path  
    - Filter keywords  
    - Optional parameters: chunk size, per_page count, and max_pages.
    
  - **API Interaction:**
    - Uses the GitHub REST API with authentication headers.
    - Paginates through issues (using `per_page` and `page` parameters).
    - Stops processing if no issues are returned or if issues are older than 90 days.
  
  - **Filtering Criteria:**
    - Issues must be created within the last three months.
    - The issue’s title or body must contain one or more of the filtered keywords.
  
  - **Data Collection:**
    - For each matching issue, a minimal representation is saved:
      - `number`, `title`, `body`, and `url`.
  
  - **Output File Writing:**
    - Writes a header with a timestamp and the extracted keywords as comments.
    - Outputs a well-formatted JSON array, written in chunks to manage memory usage.
    - Ensures correct JSON formatting (handling commas between objects).

### 5.5. Threading and Asynchronous Execution
- **Background Thread:**  
  - The scraping task is executed in a separate daemon thread.
  - This prevents the GUI from freezing during network operations.
  - Upon completion, the main thread is updated to show a success message and close the GUI.

---

## 6. Error Handling & Security

- **Error Conditions:**
  - **Invalid URL:**  
    Caught and logged if the provided GitHub URL does not match expected patterns.
  - **Missing GITHUB_TOKEN:**  
    Logs an error and returns a JSON error response if the token is absent.
  - **Network Issues:**  
    Handled using try/except blocks around API calls.
  - **Parsing/Processing Errors:**  
    Errors in TF‑IDF processing or date parsing are caught, logged, and do not crash the application.

- **Security Considerations:**
  - **Token Handling:**  
    The token is loaded from a local `.env` file. (Note: the token is printed to the console for debugging purposes; consider removing or securing this in production.)
  - **Data Sanitization:**  
    User inputs are stripped of leading/trailing whitespace and validated.

---

## 7. Output Specifications

- **Output Format:**  
  A JSON file containing an array of issue objects.
  
- **Metadata Header:**  
  The file starts with comments (non-JSON lines) that include:
  - A timestamp (when scraping began).
  - The list of keywords used for filtering.

- **Issue Data Fields:**
  - `number`: The issue number.
  - `title`: The issue title.
  - `body`: The issue body/content.
  - `url`: The HTML URL to the issue on GitHub.

- **File Naming:**  
  If the output path does not include a `.json` extension, it is automatically appended.

---

## 8. Deployment and Execution

- **Execution:**  
  The script is executable as a standalone program (shebang `#!/usr/bin/env python3`).
  
- **User Scenario Example:**  
  1. The user enters a valid GitHub issues URL (e.g., `https://github.com/owner/repo/issues`).
  2. The user provides a descriptive prompt for keyword extraction.
  3. The user specifies or accepts the default output file location.
  4. On clicking “Submit,” the widget:
     - Disables further input,
     - Extracts and displays keywords,
     - Begins scraping in the background,
     - Writes filtered issues to the JSON file,
     - And finally shows a completion message before closing the GUI.

---

## 9. Potential Enhancements

- **Security:**  
  Remove or mask the printing of the `GITHUB_TOKEN` in production.

- **User Feedback:**  
  Provide more detailed GUI notifications for errors (in addition to logging).

- **Customization:**  
  Offer additional parameters via the GUI (e.g., adjustable date range, chunk size, or API request settings).

- **Robustness:**  
  Enhance error handling to better manage intermittent network failures or API rate limits.