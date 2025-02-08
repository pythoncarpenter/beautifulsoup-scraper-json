#!/usr/bin/env python3
import os
import re
import sys
import json
import uuid
import logging
import requests
import tkinter as tk
from tkinter import ttk
from dotenv import load_dotenv
from sklearn.feature_extraction.text import TfidfVectorizer  # requires scikit-learn

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

# --------------------- Utility Functions ---------------------
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

def extract_keywords(prompt_text, top_n=5):
    """
    Use TF-IDF analysis on the prompt text to extract top keywords.
    We split the prompt into documents (using non-empty lines); if there’s only one line,
    the entire text is used as one document.
    Returns a list of keywords.
    """
    docs = [line.strip() for line in prompt_text.splitlines() if line.strip()]
    if not docs:
        docs = [prompt_text.strip()]
    try:
        vectorizer = TfidfVectorizer(stop_words="english", min_df=1)
        tfidf_matrix = vectorizer.fit_transform(docs)
        scores = tfidf_matrix.sum(axis=0).A1  # sum scores across documents
        terms = vectorizer.get_feature_names_out()
        term_scores = list(zip(terms, scores))
        term_scores.sort(key=lambda x: x[1], reverse=True)
        keywords = [term for term, score in term_scores[:top_n]]
        return keywords
    except Exception as e:
        logger.error("TF-IDF extraction failed: %s", e)
        return []

def issue_matches(issue, keywords):
    """
    Check if any of the keywords (case-insensitive) appear in the issue's title or body.
    """
    title = issue.get("title", "").lower()
    body = issue.get("body", "").lower()
    for kw in keywords:
        if kw.lower() in title or kw.lower() in body:
            return True
    return False

def write_chunk_to_file(file_handle, chunk, first_item_flag):
    """
    Write a list of issue dicts (chunk) to an already-open file.
    The file is assumed to be a JSON array that has been started.
    first_item_flag is a mutable list containing one boolean element so that it
    can be updated across calls (to handle commas correctly).
    """
    for item in chunk:
        if not first_item_flag[0]:
            file_handle.write(",\n")
        else:
            first_item_flag[0] = False
        json.dump(item, file_handle)
    file_handle.flush()

def scrape_github_issues_with_filter(url, output_path, keywords, chunk_size=50, per_page=100):
    """
    Scrape issues from the given GitHub repository URL.
    First, for each page of issues, quickly check if any of the extracted keywords appear
    anywhere in the combined text of that page. If none appear, skip processing that page.
    Otherwise, process each issue and, if it matches one of the keywords, add it (with minimal
    fields) to a chunk. When the chunk size reaches chunk_size, write it to the output file.
    """
    logger.info("Starting filtered scrape for URL: %s", url)
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
    session = requests.Session()
    page = 1
    chunk = []
    first_item_flag = [True]  # Used for proper JSON formatting

    with open(output_path, "w", encoding="utf-8") as f_out:
        f_out.write("[\n")  # Start JSON array
        while True:
            logger.info("Fetching page %d", page)
            try:
                resp = session.get(
                    f"https://api.github.com/repos/{owner}/{repo}/issues",
                    headers=headers,
                    params={"state": "all", "page": page, "per_page": per_page},
                    timeout=10
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

            # Quickly combine text from all non-PR issues in the batch for keyword checking
            page_text = " ".join(
                (issue.get("title", "") + " " + issue.get("body", ""))
                for issue in batch if "pull_request" not in issue
            ).lower()

            # If none of the keywords appear in the page, skip processing the whole page
            if not any(kw.lower() in page_text for kw in keywords):
                logger.info("No keywords found in page %d; skipping", page)
                if len(batch) < per_page:
                    break
                page += 1
                continue

            # Otherwise, process each issue individually
            for item in batch:
                if "pull_request" in item:
                    continue
                if issue_matches(item, keywords):
                    minimal_item = {
                        "number": item.get("number"),
                        "title": item.get("title"),
                        "body": item.get("body"),
                        "url": item.get("html_url")
                    }
                    chunk.append(minimal_item)
                    if len(chunk) >= chunk_size:
                        write_chunk_to_file(f_out, chunk, first_item_flag)
                        chunk = []  # Clear the chunk after writing

            if len(batch) < per_page:
                break
            page += 1

        if chunk:
            write_chunk_to_file(f_out, chunk, first_item_flag)
        f_out.write("\n]")  # End JSON array

    logger.info("Finished scraping. Results written to %s", output_path)
    return output_path

# --------------------- GUI Setup ---------------------
root = tk.Tk()
root.title("GitHub Issues/Fix Pages Scraper (REST API)")

# URL Field
url_label = tk.Label(root, text="GitHub Issues/Pull URL:")
url_label.grid(row=0, column=0, padx=10, pady=(10, 0), sticky="w")
url_text = tk.Text(root, wrap=tk.WORD, width=50, height=2)
url_text.insert(tk.END, "https://github.com/neovim/neovim/issues")
url_text.grid(row=1, column=0, padx=10, pady=(0, 10))

# Prompt Field (Large Text Field)
prompt_label = tk.Label(root, text="Enter Prompt (for keyword extraction):")
prompt_label.grid(row=2, column=0, padx=10, pady=(10, 0), sticky="w")
prompt_text = tk.Text(root, wrap=tk.WORD, width=50, height=8)
prompt_text.insert(tk.END, "Type your prompt here...")
prompt_text.grid(row=3, column=0, padx=10, pady=(0, 10))

# Output File Field
output_label = tk.Label(root, text="Output File Path (e.g., ~/Desktop/issues):")
output_label.grid(row=4, column=0, padx=10, pady=(10, 0), sticky="w")
output_entry = tk.Entry(root, width=50)
output_entry.insert(tk.END, "~/Desktop/issues")
output_entry.grid(row=5, column=0, padx=10, pady=(0, 10))

# Keywords Display Label
keywords_label = tk.Label(root, text="Extracted Keywords: (none yet)")
keywords_label.grid(row=6, column=0, padx=10, pady=(10, 0), sticky="w")

# Submit Button
submit_button = tk.Button(root, text="Submit", width=20)
submit_button.grid(row=7, column=0, padx=10, pady=(10, 20))

# --------------------- on_submit Handler ---------------------
def on_submit():
    # Disable the submit button and change its text to indicate loading
    submit_button.config(state="disabled", text="Loading...")
    root.update_idletasks()

    # Retrieve field values
    url_value = url_text.get("1.0", tk.END).strip()
    prompt_value = prompt_text.get("1.0", tk.END).strip()
    output_path_input = output_entry.get().strip()
    if not output_path_input:
        output_path_input = "~/Desktop/issues"
    output_path = os.path.expanduser(output_path_input)
    if not output_path.endswith(".json"):
        output_path += ".json"

    # First, extract keywords from the prompt using TF-IDF analysis
    keywords = extract_keywords(prompt_value, top_n=5)
    keywords_label.config(text="Extracted Keywords: " + ", ".join(keywords))
    root.update_idletasks()

    # Now, start scraping using the extracted keywords.
    scrape_github_issues_with_filter(url_value, output_path, keywords,
                                       chunk_size=50, per_page=100)

    # Once complete, re-enable the submit button and update the status
    submit_button.config(state="normal", text="Submit")
    keywords_label.config(text="Scraping complete. Extracted Keywords: " + ", ".join(keywords))
    logger.info("Scraping completed; results written to %s", output_path)

# Bind the on_submit function to the submit button
submit_button.config(command=on_submit)

root.mainloop()