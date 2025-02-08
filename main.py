#!/usr/bin/env python3
import os
import re
import requests
import json
import tkinter as tk
import logging
import uuid
from dotenv import load_dotenv

# Load environment variables globally from the .env file
load_dotenv()

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

# --------------------- Utility: Dedup ---------------------
def deduplicate_items(items, key_func):
    """
    Deduplicates a list of dictionary items using a key function.
    """
    unique = {}
    for item in items:
        key = key_func(item)
        if key not in unique:
            unique[key] = item
        else:
            logger.info("Duplicate item skipped: %s", item)
    return list(unique.values())

# --------------------- Utility: Parse URL ---------------------
def parse_repo_url(url):
    """
    Parse a GitHub URL like 'https://github.com/owner/repo/issues'
    and return (owner, repo).
    """
    # Remove trailing slash, split on "/"
    parts = url.strip().strip("/").split("/")
    # Typically: [ 'https:', '', 'github.com', 'owner', 'repo', 'issues' ]
    if len(parts) < 5 or parts[-1] not in ("issues", "pulls", "pull"):
        raise ValueError(f"Not a valid GitHub issues/pulls URL: {url}")
    owner = parts[-3]  # e.g. "owner"
    repo = parts[-2]   # e.g. "repo"
    return (owner, repo)

def parse_pull_number(url):
    """
    If the user selected 'Fix Pages', we parse the PR number from
    something like 'https://github.com/owner/repo/pull/123'.
    Returns an integer or None if not found.
    """
    match = re.search(r"/pull/(\d+)", url)
    if match:
        return int(match.group(1))
    # Alternatively, some older GitHub URLs might have /pulls/ but you can adjust as needed.
    return None

# --------------------- Issues via GitHub REST API ---------------------
def scrape_github_issues(url):
    """
    Fetch all issues for the given repository using the REST API.
    Return a JSON string (list of issue dicts).
    """
    logger.info("Starting scrape_github_issues (REST API) for URL: %s", url)

    # 1) Parse the (owner, repo) from the URL.
    try:
        owner, repo = parse_repo_url(url)
    except ValueError as e:
        logger.error(str(e))
        return json.dumps({"error": "Invalid GitHub issues URL"}, indent=2)

    # 2) Get GitHub token from the environment (loaded globally)
    token = os.getenv("GITHUB_TOKEN", "")
    if not token:
        logger.error("GITHUB_TOKEN missing in environment.")
        return json.dumps({"error": "Missing GITHUB_TOKEN"}, indent=2)

    # 3) Paginate through issues
    issues = []
    per_page = 100
    page = 1
    headers = {
        "Accept": "application/vnd.github+json",
        "Authorization": f"Bearer {token}"
    }
    while True:
        logger.info("Requesting page=%d of issues for %s/%s", page, owner, repo)
        resp = requests.get(
            f"https://api.github.com/repos/{owner}/{repo}/issues",
            headers=headers,
            params={
                "state": "all",   # or "open", "closed"
                "page": page,
                "per_page": per_page
            }
        )
        if resp.status_code != 200:
            logger.error("Failed to fetch issues: %d %s", resp.status_code, resp.text)
            break

        batch = resp.json()
        if not isinstance(batch, list) or len(batch) == 0:
            logger.info("No more issues found.")
            break

        # Convert to the same structure the old script returned:
        # "number", "title", "url", "created_at", "author"
        for item in batch:
            # If it's a PR, "pull_request" field will exist.
            # Comment out the following line if you want to include PRs.
            if "pull_request" in item:
                # continue
                pass
            number = str(item.get("number", ""))
            title = item.get("title", "")
            html_url = item.get("html_url", "")
            created_at = item.get("created_at", "")
            author_info = item.get("user", {}) or {}
            author = author_info.get("login", "")

            if title and number:
                issues.append({
                    "number": number,
                    "title": title,
                    "url": html_url,
                    "created_at": created_at,
                    "author": author
                })

        if len(batch) < per_page:
            logger.info("Last page reached.")
            break

        page += 1

    # 4) Deduplicate (by (number, title))
    issues = deduplicate_items(issues, key_func=lambda i: (i.get("number", ""), i.get("title", "")))

    logger.info("Finished scraping issues. Total unique issues: %d", len(issues))
    return json.dumps(issues, indent=2)

# --------------------- Fix Pages (Pull Requests) via GitHub REST API ---------------------
def scrape_fix_pages(url):
    """
    Fetch conversation comments for a Pull Request using the REST API.
    Return a JSON string with "responses": [...comments...].
    """
    logger.info("Starting scrape_fix_pages (REST API) for URL: %s", url)

    # 1) Parse (owner, repo) and PR number
    try:
        owner, repo = parse_repo_url(url)
        pr_number = parse_pull_number(url)
        if not pr_number:
            raise ValueError("Could not extract PR number from URL.")
    except ValueError as e:
        logger.error(str(e))
        return json.dumps({"error": "Invalid GitHub PR URL"}, indent=2)

    # 2) Get GitHub token from the environment (loaded globally)
    token = os.getenv("GITHUB_TOKEN", "")
    if not token:
        logger.error("GITHUB_TOKEN missing in environment.")
        return json.dumps({"error": "Missing GITHUB_TOKEN"}, indent=2)

    # 3) Retrieve comments from /repos/{owner}/{repo}/issues/{pr_number}/comments
    #    If you also need code-review comments, do /pulls/{pr_number}/comments
    responses = []
    page = 1
    per_page = 100
    headers = {
        "Accept": "application/vnd.github+json",
        "Authorization": f"Bearer {token}"
    }
    while True:
        logger.info("Requesting page=%d of PR comments for %s/%s PR#%d", page, owner, repo, pr_number)
        resp = requests.get(
            f"https://api.github.com/repos/{owner}/{repo}/issues/{pr_number}/comments",
            headers=headers,
            params={
                "page": page,
                "per_page": per_page
            }
        )
        if resp.status_code != 200:
            logger.error("Failed to fetch PR comments: %d %s", resp.status_code, resp.text)
            break

        batch = resp.json()
        if not isinstance(batch, list) or len(batch) == 0:
            break

        for item in batch:
            author_info = item.get("user", {}) or {}
            author = author_info.get("login", "Unknown")

            timestamp = item.get("created_at", "")
            content = item.get("body", "")
            response_id = str(uuid.uuid4())
            response_type = "comment"  # for now

            if content:
                responses.append({
                    "id": response_id,
                    "type": response_type,
                    "author": author,
                    "timestamp": timestamp,
                    "content": content
                })

        if len(batch) < per_page:
            break
        page += 1

    # 4) Deduplicate based on (author, content, timestamp)
    responses = deduplicate_items(
        responses,
        key_func=lambda r: (
            r.get("author", ""), r.get("content", ""), r.get("timestamp", "")
        )
    )

    logger.info("Finished scraping fixes. Total unique responses: %d", len(responses))
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
        # Default paths
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
        output = scrape_github_issues(url)
    elif mode == "fixes":
        output = scrape_fix_pages(url)
    else:
        output = json.dumps({"error": "Unknown mode"}, indent=2)
    
    try:
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(output)
        logger.info("Results successfully written to %s", output_path)
    except Exception as e:
        logger.error("Error writing file: %s", e)

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