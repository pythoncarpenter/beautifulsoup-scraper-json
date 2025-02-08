#!/usr/bin/env python3
import os
import re
import requests
import json
import tkinter as tk
import logging
import uuid
from dotenv import load_dotenv

# Load environment variables from the .env file located next to this script
dotenv_path = os.path.join(os.path.dirname(__file__), '.env')
load_dotenv(dotenv_path)
token = os.getenv("GITHUB_TOKEN", "")
print("GITHUB_TOKEN:", token)  # For debugging; remove or secure in production

# --------------------- Logging Setup ---------------------
project_root = os.path.dirname(os.path.abspath(__file__))
log_file = os.path.join(project_root, "scrape.log")
logging.basicConfig(
    filename=log_file,
    level=logging.DEBUG,
    format="%(asctime)s %(levelname)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logger = logging.getLogger()

# --------------------- Utility: Parse GitHub Repo URL ---------------------
def parse_repo_url(url):
    """
    Given a GitHub URL like 'https://github.com/owner/repo/issues',
    return (owner, repo). Raise ValueError if the URL is not valid.
    """
    parts = url.strip().strip("/").split("/")
    if len(parts) < 5 or parts[-1] not in ("issues", "pulls", "pull"):
        raise ValueError(f"Not a valid GitHub issues/pulls URL: {url}")
    owner = parts[-3]
    repo = parts[-2]
    return owner, repo

# --------------------- Chunked GitHub Issues Scraper ---------------------
def scrape_github_issues_chunked(url, output_path, per_page=100):
    """
    Fetch issues from the given GitHub repository URL in chunks.
    Captures only minimal fields:
      - number
      - title
      - body (the context of the issue)
      - url

    Each page of issues is immediately written to output_path (a JSON file)
    to keep memory usage low and speed up processing.
    """
    logger.info("Starting chunked scrape_github_issues for URL: %s", url)
    try:
        owner, repo = parse_repo_url(url)
    except ValueError as e:
        logger.error(str(e))
        return json.dumps({"error": "Invalid GitHub issues URL"}, indent=2)

    token = os.getenv("GITHUB_TOKEN", "")
    if not token:
        logger.error("GITHUB_TOKEN missing in environment.")
        return json.dumps({"error": "Missing GITHUB_TOKEN"}, indent=2)

    headers = {
        "Accept": "application/vnd.github+json",
        "Authorization": f"Bearer {token}"
    }
    session = requests.Session()  # Reuse connections for speed
    page = 1
    first_item = True

    # Open the file for incremental writing
    with open(output_path, "w", encoding="utf-8") as f_out:
        f_out.write("[\n")  # Begin JSON array
        while True:
            logger.info("Fetching page %d", page)
            try:
                resp = session.get(
                    f"https://api.github.com/repos/{owner}/{repo}/issues",
                    headers=headers,
                    params={"state": "all", "page": page, "per_page": per_page},
                    timeout=10  # seconds
                )
            except requests.exceptions.RequestException as e:
                logger.error("Request failed: %s", e)
                break

            if resp.status_code != 200:
                logger.error("Failed to fetch issues: %d %s", resp.status_code, resp.text)
                break

            batch = resp.json()
            if not isinstance(batch, list) or len(batch) == 0:
                logger.info("No more issues found.")
                break

            # Process each issue in the batch
            for item in batch:
                # Skip pull requests if present (remove this check if you need them)
                if "pull_request" in item:
                    continue

                minimal_item = {
                    "number": item.get("number"),
                    "title": item.get("title"),
                    "body": item.get("body"),       # Context of the issue
                    "url": item.get("html_url")
                }
                if not first_item:
                    f_out.write(",\n")
                else:
                    first_item = False

                json.dump(minimal_item, f_out)

            # Flush data to disk after each chunk
            f_out.flush()

            # If the batch size is smaller than per_page, we've reached the last page
            if len(batch) < per_page:
                logger.info("Last page reached.")
                break

            page += 1
        f_out.write("\n]")  # End JSON array

    logger.info("Finished scraping issues. Results written to %s", output_path)
    return output_path

# --------------------- Fix Pages Scraper (for PR Comments) ---------------------
def scrape_fix_pages(url):
    """
    Fetch pull request comments.
    Captures minimal information.
    """
    logger.info("Starting scrape_fix_pages for URL: %s", url)
    try:
        owner, repo = parse_repo_url(url)
        pr_number = None
        match = re.search(r"/pull/(\d+)", url)
        if match:
            pr_number = int(match.group(1))
        if not pr_number:
            raise ValueError("Could not extract PR number from URL.")
    except ValueError as e:
        logger.error(str(e))
        return json.dumps({"error": "Invalid GitHub PR URL"}, indent=2)

    token = os.getenv("GITHUB_TOKEN", "")
    if not token:
        logger.error("GITHUB_TOKEN missing in environment.")
        return json.dumps({"error": "Missing GITHUB_TOKEN"}, indent=2)

    headers = {
        "Accept": "application/vnd.github+json",
        "Authorization": f"Bearer {token}"
    }
    session = requests.Session()
    page = 1
    responses = []
    per_page = 100

    while True:
        logger.info("Fetching PR comments page %d", page)
        try:
            resp = session.get(
                f"https://api.github.com/repos/{owner}/{repo}/issues/{pr_number}/comments",
                headers=headers,
                params={"page": page, "per_page": per_page},
                timeout=10
            )
        except requests.exceptions.RequestException as e:
            logger.error("Request failed: %s", e)
            break

        if resp.status_code != 200:
            logger.error("Failed to fetch PR comments: %d %s", resp.status_code, resp.text)
            break

        batch = resp.json()
        if not isinstance(batch, list) or len(batch) == 0:
            break

        for item in batch:
            minimal_item = {
                "id": str(uuid.uuid4()),
                "body": item.get("body"),
                "url": item.get("html_url")
            }
            responses.append(minimal_item)

        if len(batch) < per_page:
            break
        page += 1

    logger.info("Finished scraping fixes. Total responses: %d", len(responses))
    return json.dumps({"responses": responses}, indent=2)

# --------------------- on_submit (GUI Handler) ---------------------
def on_submit():
    logger.info("Submit button pressed.")
    url = url_text.get("1.0", tk.END).strip()
    if not url:
        logger.info("No URL provided; defaulting to issues page.")
        url = "https://github.com/neovim/neovim/issues"
    mode = mode_var.get()
    logger.info("Mode selected: %s", mode)
    output_path_input = output_entry.get().strip()
    if not output_path_input:
        if mode == "issues":
            output_path_input = "~/Desktop/issues"
        elif mode == "fixes":
            output_path_input = "~/Desktop/fixes"
        else:
            output_path_input = "~/Desktop/output"
        logger.info("No output path provided; defaulting to: %s", output_path_input)
    output_path = os.path.expanduser(output_path_input)
    if not output_path.endswith(".json"):
        output_path += ".json"
    root.destroy()
    if mode == "issues":
        result = scrape_github_issues_chunked(url, output_path, per_page=100)
    elif mode == "fixes":
        output = scrape_fix_pages(url)
        try:
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            with open(output_path, "w", encoding="utf-8") as f:
                f.write(output)
        except Exception as e:
            logger.error("Error writing file: %s", e)
        result = output_path
    else:
        result = json.dumps({"error": "Unknown mode"}, indent=2)
    logger.info("Results written to %s", result)

# --------------------- GUI Setup ---------------------
root = tk.Tk()
root.title("GitHub Issues/Fix Pages Scraper (REST API)")

url_label = tk.Label(root, text="Input GitHub Issues/Pull URL:")
url_label.pack(pady=(10, 0))

url_text = tk.Text(root, wrap=tk.WORD, width=50, height=4)
url_text.insert(tk.END, "https://github.com/neovim/neovim/issues")
url_text.pack(padx=10, pady=10)

output_label = tk.Label(root, text="Specify output file path (e.g., ~/Desktop/filename):")
output_label.pack(pady=(10, 0))

output_entry = tk.Entry(root, width=50)
output_entry.insert(tk.END, "~/Desktop/issues")
output_entry.pack(padx=10, pady=10)

mode_var = tk.StringVar(value="issues")
mode_frame = tk.Frame(root)
mode_frame.pack(pady=(10, 0))

radio_issues = tk.Radiobutton(mode_frame, text="Issue Pages", variable=mode_var, value="issues")
radio_issues.pack(side=tk.LEFT, padx=10)
radio_fixes = tk.Radiobutton(mode_frame, text="Fix Pages", variable=mode_var, value="fixes")
radio_fixes.pack(side=tk.LEFT, padx=10)

def update_output_default(*args):
    mode = mode_var.get()
    if mode == "issues":
        default_path = "~/Desktop/issues"
    elif mode == "fixes":
        default_path = "~/Desktop/fixes"
    else:
        default_path = "~/Desktop/output"
    output_entry.delete(0, tk.END)
    output_entry.insert(tk.END, default_path)

mode_var.trace_add("write", update_output_default)

submit_button = tk.Button(root, text="Submit", command=on_submit)
submit_button.pack(pady=(10, 10))

root.mainloop()