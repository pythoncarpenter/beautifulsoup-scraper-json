#!/usr/bin/env python3
import os
import requests
from bs4 import BeautifulSoup
import json
import tkinter as tk
import logging
import uuid

# Setup logging to a file in the project root.
project_root = os.path.dirname(os.path.abspath(__file__))
log_file = os.path.join(project_root, "scrape.log")
logging.basicConfig(
    filename=log_file,
    level=logging.DEBUG,
    format="%(asctime)s %(levelname)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logger = logging.getLogger()

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

def scrape_github_issues(url):
    """
    Scrapes a GitHub issues page and extracts details for each issue.
    Returns a JSON-formatted string.
    """
    logger.info("Starting scrape_github_issues for URL: %s", url)
    headers = {
        'User-Agent': (
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) '
            'AppleWebKit/537.36 (KHTML, like Gecko) '
            'Chrome/89.0.4389.90 Safari/537.36'
        )
    }
    try:
        response = requests.get(url, headers=headers)
        logger.info("Received response with status code: %d", response.status_code)
    except Exception as e:
        logger.error("Exception during request: %s", e)
        return json.dumps({"error": "Exception during request"}, indent=2)

    if response.status_code != 200:
        logger.error("Failed to fetch page, status code: %d", response.status_code)
        return json.dumps({
            "error": "Failed to fetch page",
            "status_code": response.status_code
        }, indent=2)
    
    soup = BeautifulSoup(response.text, 'html.parser')
    issues = []
    
    # Find all <li> elements representing issue rows.
    issue_rows = soup.find_all("li", class_=lambda x: x and "ListItem-module__listItem" in x)
    logger.info("Found %d issue rows", len(issue_rows))
    
    for row in issue_rows:
        title_elem = row.find("a", class_=lambda x: x and "TitleHeader-module__inline" in x)
        if not title_elem:
            continue
        title = title_elem.get_text(strip=True)
        href = title_elem.get("href", "")
        full_url = "https://github.com" + href if href.startswith("/") else href

        num_elem = row.find("span", class_=lambda x: x and "issue-item-module__defaultNumberDescription" in x)
        number = ""
        if num_elem:
            raw_number = num_elem.get_text(strip=True)
            number = ''.join(filter(str.isdigit, raw_number))
        else:
            logger.debug("No number element found for issue with title: %s", title)

        rel_time_elem = row.find("relative-time")
        created_at = rel_time_elem.get("datetime", "") if rel_time_elem else ""
        
        author_elem = row.find("a", class_=lambda x: x and "issue-item-module__authorCreatedLink" in x)
        author = author_elem.get_text(strip=True) if author_elem else ""
        
        if title and number:
            issues.append({
                "number": number,
                "title": title,
                "url": full_url,
                "created_at": created_at,
                "author": author
            })
        else:
            logger.warning("Skipping issue due to missing title or number: title='%s', number='%s'", title, number)
    
    # Deduplicate based on (number, title)
    issues = deduplicate_items(issues, key_func=lambda item: (item.get("number", ""), item.get("title", "")))
    
    logger.info("Finished scraping issues. Total unique issues: %d", len(issues))
    return json.dumps(issues, indent=2)

def scrape_fix_pages(url):
    """
    Scrapes a GitHub fix page (typically a pull request page) and extracts conversation responses.
    Each response object has: id, type, author, timestamp, and content.
    Returns a JSON-formatted string.
    """
    logger.info("Starting scrape_fix_pages for URL: %s", url)
    headers = {
        'User-Agent': (
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) '
            'AppleWebKit/537.36 (KHTML, like Gecko) '
            'Chrome/89.0.4389.90 Safari/537.36'
        )
    }
    try:
        response = requests.get(url, headers=headers)
        logger.info("Received response with status code: %d", response.status_code)
    except Exception as e:
        logger.error("Exception during request in scrape_fix_pages: %s", e)
        return json.dumps({"error": "Exception during request"}, indent=2)

    if response.status_code != 200:
        logger.error("Failed to fetch fix page, status code: %d", response.status_code)
        return json.dumps({
            "error": "Failed to fetch page",
            "status_code": response.status_code
        }, indent=2)
    
    soup = BeautifulSoup(response.text, 'html.parser')
    responses = []
    
    # Look for conversation items in the pull request/fix page.
    conversation_items = soup.find_all("div", class_=lambda x: x and ("timeline-comment" in x or "js-comment-container" in x))
    logger.info("Found %d conversation items", len(conversation_items))
    
    for item in conversation_items:
        author_elem = item.find("a", class_=lambda x: x and "author" in x)
        author = author_elem.get_text(strip=True) if author_elem else "Unknown"
        
        time_elem = item.find("relative-time")
        timestamp = time_elem.get("datetime", "") if time_elem else ""
        
        content_elem = item.find("td", class_=lambda x: x and "comment-body" in x)
        if not content_elem:
            content_elem = item.find("div", class_=lambda x: x and "edit-comment-hide" in x)
        content = content_elem.get_text(strip=True) if content_elem else ""
        
        response_type = "comment"  # Default type for now.
        response_id = str(uuid.uuid4())
        
        if content:
            responses.append({
                "id": response_id,
                "type": response_type,
                "author": author,
                "timestamp": timestamp,
                "content": content
            })
        else:
            logger.debug("Skipping a fix item due to missing content.")
    
    # Deduplicate responses based on (author, content, timestamp) or (author, content) if timestamp is empty.
    responses = deduplicate_items(
        responses,
        key_func=lambda item: (
            item.get("author", ""), 
            item.get("content", ""), 
            item.get("timestamp", "")
        ) if item.get("timestamp") else (
            item.get("author", ""), 
            item.get("content", "")
        )
    )
    
    logger.info("Finished scraping fixes. Total unique responses: %d", len(responses))
    return json.dumps({"responses": responses}, indent=2)

def on_submit():
    logger.info("Submit button pressed.")
    url = url_text.get("1.0", tk.END).strip()
    if not url:
        logger.info("No URL provided; defaulting to issues page.")
        url = "https://github.com/vercel/nft/issues"
    
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
        output = scrape_github_issues(url)
    elif mode == "fixes":
        output = scrape_fix_pages(url)
    else:
        output = json.dumps({"error": "Unknown mode"}, indent=2)
    
    try:
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        with open(output_path, "w") as f:
            f.write(output)
        logger.info("Results successfully written to %s", output_path)
    except Exception as e:
        logger.error("Error writing file: %s", e)

# --------------------- GUI Setup ---------------------
root = tk.Tk()
root.title("GitHub Issues/Fix Pages Scraper")

url_label = tk.Label(root, text="Input page URL from GitHub:")
url_label.pack(pady=(10, 0))

url_text = tk.Text(root, wrap=tk.WORD, width=50, height=4)
url_text.insert(tk.END, "https://github.com/vercel/nft/issues")
url_text.pack(padx=10, pady=10)

output_label = tk.Label(root, text="Specify output file path (e.g., ~/Desktop/filename):")
output_label.pack(pady=(10, 0))

output_entry = tk.Entry(root, width=50)
# Set the default based on the default mode ("issues").
output_entry.insert(tk.END, "~/Desktop/issues")
output_entry.pack(padx=10, pady=10)

mode_var = tk.StringVar(value="issues")
mode_frame = tk.Frame(root)
mode_frame.pack(pady=(10, 0))

radio_issues = tk.Radiobutton(mode_frame, text="Issue Pages", variable=mode_var, value="issues")
radio_issues.pack(side=tk.LEFT, padx=10)

radio_fixes = tk.Radiobutton(mode_frame, text="Fix Pages", variable=mode_var, value="fixes")
radio_fixes.pack(side=tk.LEFT, padx=10)

# Update output file path based on radio button selection.
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