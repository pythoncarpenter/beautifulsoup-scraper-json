#!/usr/bin/env python3
import os
import re
import sys
import json
import logging
import requests
import tkinter as tk
from tkinter import messagebox
from tkinter import ttk
from dotenv import load_dotenv
from sklearn.feature_extraction.text import TfidfVectorizer
import datetime
import threading
import queue

# Global flag to indicate whether submission was made
submitted = False
logger = None  # Initialize logger to None

def setup_logging():
    """Configures the logging for the application."""
    global logger  # Declare logger as global so it can be used everywhere
    if getattr(sys, 'frozen', False):
        # Running in a bundle
        application_path = sys._MEIPASS
    else:
        # Running as a script
        application_path = os.path.dirname(os.path.abspath(__file__))
    log_file = os.path.join(application_path, "scrape.log")
    logging.basicConfig(
        filename=log_file,
        level=logging.DEBUG,
        format="%(asctime)s %(levelname)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    logger = logging.getLogger()
    logger.debug("Logging initialized. Project root: %s", application_path)


def load_environment_variables():
    """Loads environment variables, specifically the GITHUB_TOKEN."""
    if getattr(sys, 'frozen', False):
        # Running in a bundle
        application_path = sys._MEIPASS
    else:
        # Running as a script
        application_path = os.path.dirname(os.path.abspath(__file__))

    dotenv_path = os.path.join(application_path, '.env')
    load_dotenv(dotenv_path)
    # Do NOT print the token:  print("GITHUB_TOKEN:", token)

def parse_repo_url(url):
    """
    Given a GitHub URL like 'https://github.com/owner/repo/issues',
    return (owner, repo). Raise ValueError if the URL is not valid.
    """
    logger.debug("Parsing repository URL: %s", url)
    parts = url.strip().strip("/").split("/")
    if len(parts) < 5 or parts[-1] not in ("issues", "pulls", "pull"):
        error_msg = f"Not a valid GitHub issues/pulls URL: {url}"
        logger.error(error_msg)
        raise ValueError(error_msg)
    owner = parts[-3]
    repo = parts[-2]
    logger.debug("Parsed owner: %s, repo: %s", owner, repo)
    return owner, repo

def extract_keywords(prompt_text, top_n=10):
    """
    Use TF-IDF analysis on the prompt text to extract top keywords.
    Handles edge cases and provides better keyword selection.
    """
    logger.debug("Extracting keywords from prompt text.")
    docs = [line.strip() for line in prompt_text.splitlines() if line.strip()]
    if not docs:
        return []  # Return an empty list if there's no meaningful input

    try:
        vectorizer = TfidfVectorizer(stop_words="english", min_df=1, ngram_range=(1, 2))  # Consider 1 and 2-word phrases
        tfidf_matrix = vectorizer.fit_transform(docs)
        scores = tfidf_matrix.sum(axis=0).A1
        terms = vectorizer.get_feature_names_out()
        term_scores = list(zip(terms, scores))
        term_scores.sort(key=lambda x: x[1], reverse=True)

        # Filter out terms that are substrings of other terms (prefer longer terms)
        filtered_terms = []
        for term, score in term_scores:
            if not any(other_term != term and term in other_term for other_term, _ in filtered_terms):
                filtered_terms.append((term, score))

        keywords = [term for term, score in filtered_terms[:top_n]]
        logger.debug("Extracted keywords: %s", keywords)
        return keywords
    except Exception as e:
        logger.error("TF-IDF extraction failed: %s", e)
        return []

def get_filtered_keywords(prompt_text, github_url, desired_count=5, extract_count=10):
    """
    Extracts and filters keywords, handling potential errors gracefully.
    """
    logger.debug("Getting filtered keywords for URL: %s", github_url)
    extracted = extract_keywords(prompt_text, top_n=extract_count)
    if not extracted:  # Handle the case where no keywords are extracted
        return []

    try:
        _, repo_name = parse_repo_url(github_url)
    except ValueError:
        repo_name = ""  # Use an empty string if parsing fails

    blocked_list = {"bug", "report", "issue", "fix", "error", "problem", "test", "todo"}
    filtered = [
        kw for kw in extracted
        if kw.lower() != repo_name.lower() and kw.lower() not in blocked_list
    ]
    logger.debug("Filtered keywords: %s", filtered)
    return filtered[:desired_count]

def issue_matches(issue, keywords):
    """
    Check if any of the keywords (case-insensitive) appear in the issue's title or body.
    """
    title = (issue.get("title") or "").lower()
    body = (issue.get("body") or "").lower()
    for kw in keywords:
        if kw.lower() in title or kw.lower() in body:
            logger.debug("Issue #%s matches keyword: %s", issue.get("number"), kw)
            return True
    return False

def write_chunk_to_file(file_handle, chunk, first_item_flag):
    """
    Write a list of issue dicts (chunk) to an already-open file.
    The file is assumed to be a JSON array that has been started.
    first_item_flag is a mutable list containing one boolean element so that it
    can be updated across calls (to handle commas correctly).
    """
    logger.debug("Writing chunk of %d issues to file.", len(chunk))
    for item in chunk:
        if not first_item_flag[0]:
            file_handle.write(",\n")
        else:
            first_item_flag[0] = False
        json.dump(item, file_handle)
    file_handle.flush()

def scrape_github_issues_with_filter(url, output_path, keywords, chunk_size=50, per_page=100, max_pages=200):
    """
    Scrapes issues, handles errors, and writes output.  Returns the output path on success,
    or an error string on failure.
    """
    logger.info("Starting filtered scrape for URL: %s", url)
    try:
        owner, repo = parse_repo_url(url)
    except ValueError as e:
        logger.error("Error in URL parsing: %s", e)
        return f"Error: Invalid GitHub issues URL: {e}" # Return error string

    token = os.getenv("GITHUB_TOKEN", "")
    if not token:
        logger.error("GITHUB_TOKEN missing in environment.")
        return "Error: Missing GITHUB_TOKEN"

    headers = {
        "Accept": "application/vnd.github+json",
        "Authorization": f"Bearer {token}"
    }
    session = requests.Session()
    page = 1
    chunk = []
    first_item_flag = [True]  # Used for proper JSON formatting

    three_months_ago = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=90)
    logger.debug("Only processing issues from after: %s", three_months_ago.isoformat())

    with open(output_path, "w", encoding="utf-8") as f_out:
        # Write header with timestamp and keywords.
        timestamp = datetime.datetime.now().isoformat()
        f_out.write("// Timestamp: " + timestamp + "\n")
        f_out.write("// Keywords: " + ", ".join(keywords) + "\n")
        f_out.write("[\n")  # Start JSON array
        logger.debug("Output file %s initialized with header.", output_path)

        while page <= max_pages:
            logger.info("Fetching page %d", page)
            try:
                resp = session.get(
                    f"https://api.github.com/repos/{owner}/{repo}/issues",
                    headers=headers,
                    params={"state": "all", "page": page, "per_page": per_page},
                    timeout=10
                )
                resp.raise_for_status()  # Raise HTTPError for bad responses (4xx or 5xx)
                batch = resp.json()

                # Add checks for unexpected API responses
                if not isinstance(batch, list):
                    logger.error("Unexpected response from GitHub API: %s", resp.text)
                    return "Error: Unexpected response from GitHub API"
            except requests.exceptions.RequestException as e:
                logger.error("Request failed on page %d: %s", page, e)
                return f"Error: Network request failed: {e}"
            except json.JSONDecodeError as e:
                logger.error("Failed to decode JSON response on page %d: %s", page, e)
                return f"Error: Failed to decode JSON: {e}"
            except Exception as e:
                return f"Error: {e}"

            if not batch:
                logger.info("No more issues found on page %d.", page)
                break

            last_issue_date = None
            if batch:
                last_issue = batch[-1]
                created_at_str = last_issue.get("created_at")
                if created_at_str:
                    try:
                        last_issue_date = datetime.datetime.fromisoformat(created_at_str.replace("Z", "+00:00"))
                    except Exception as e:
                        logger.error("Error parsing created_at on page %d: %s", page, e)

            is_final_page = last_issue_date and (last_issue_date < three_months_ago)
            logger.debug("Is final page? %s", is_final_page)

            page_text = " ".join(
                ((issue.get("title") or "") + " " + (issue.get("body") or ""))
                for issue in batch if "pull_request" not in issue
            ).lower()

            if not any(kw.lower() in page_text for kw in keywords):
                logger.info("No keywords found in page %d; skipping.", page)
                if len(batch) < per_page:
                    break
                page += 1
                continue

            for item in batch:
                if "pull_request" in item:
                    continue
                created_at_str = item.get("created_at")
                if created_at_str:
                    try:
                        issue_date = datetime.datetime.fromisoformat(created_at_str.replace("Z", "+00:00"))
                    except Exception as e:
                        logger.error("Error parsing created_at for an issue: %s", e)
                        continue
                    if issue_date < three_months_ago:
                        continue
                else:
                    continue

                if issue_matches(item, keywords):
                    minimal_item = {
                        "number": item.get("number"),
                        "title": item.get("title"),
                        "body": item.get("body"),
                        "url": item.get("html_url")
                    }
                    chunk.append(minimal_item)
                    logger.debug("Added issue #%s to chunk.", item.get("number"))
                    if len(chunk) >= chunk_size:
                        write_chunk_to_file(f_out, chunk, first_item_flag)
                        logger.debug("Chunk written to file. Resetting chunk.")
                        chunk = []

            if is_final_page:
                logger.info("Reached issues older than cutoff on page %d; stopping.", page)
                break

            page += 1

        if chunk:
            write_chunk_to_file(f_out, chunk, first_item_flag)
            logger.debug("Final chunk written to file.")
        f_out.write("\n]")  # End JSON array
        logger.info("Finished writing output to %s", output_path)

    return output_path

def create_gui():
    """Creates and configures the Tkinter GUI."""
    root = tk.Tk()
    root.title("GitHub Issues/Fix Pages Scraper (REST API)")
    logger.debug("Tkinter GUI initialized.")

    # Create blank input fields.
    url_label = tk.Label(root, text="GitHub Issues/Pull URL:")
    url_label.grid(row=0, column=0, padx=10, pady=(10, 0), sticky="w")
    url_text = tk.Text(root, wrap=tk.WORD, width=50, height=2)
    url_text.insert(tk.END, "")
    url_text.grid(row=1, column=0, padx=10, pady=(0, 10))

    prompt_label = tk.Label(root, text="Enter Prompt (for keyword extraction):")
    prompt_label.grid(row=2, column=0, padx=10, pady=(10, 0), sticky="w")
    prompt_text = tk.Text(root, wrap=tk.WORD, width=50, height=8)
    prompt_text.insert(tk.END, "")
    prompt_text.grid(row=3, column=0, padx=10, pady=(0, 10))

    output_label = tk.Label(root, text="Output File Path (e.g., ~/Desktop/issues):")
    output_label.grid(row=4, column=0, padx=10, pady=(10, 0), sticky="w")
    output_entry = tk.Entry(root, width=50)
    output_entry.insert(tk.END, "")
    output_entry.grid(row=5, column=0, padx=10, pady=(0, 10))

    keywords_label = tk.Label(root, text="Extracted Keywords: (none yet)")
    keywords_label.grid(row=6, column=0, padx=10, pady=(10, 0), sticky="w")

    submit_button = tk.Button(root, text="Submit", width=20, command=lambda: on_submit(
        root, url_text, prompt_text, output_entry, keywords_label, submit_button
    ))
    submit_button.grid(row=7, column=0, padx=10, pady=(10, 20))

    root.protocol("WM_DELETE_WINDOW", lambda: on_closing(root))
    return root

def on_closing(root):
    global submitted
    if not submitted:
        logger.error("Window closed without user submission. No task was performed.")
        root.destroy()  # Use destroy directly, no need for quit
    else:
        logger.debug("Window close requested after submission; GUI will close after task completion.")

def on_submit(root, url_text, prompt_text, output_entry, keywords_label, submit_button):
    global submitted
    submitted = True  # Set the global flag
    logger.debug("Submit button clicked.")

    # --- 1. Disable GUI Elements ---
    url_text.config(state="disabled")
    prompt_text.config(state="disabled")
    output_entry.config(state="disabled")
    submit_button.config(state="disabled", text="Loading...")

    # --- 2. Get Input Values ---
    url_value = url_text.get("1.0", tk.END).strip()
    prompt_value = prompt_text.get("1.0", tk.END).strip()
    output_path_input = output_entry.get().strip()

    # --- 3. Input Validation (Basic) ---
    if not url_value or not prompt_value:
        messagebox.showerror("Error", "Please enter both a URL and a prompt.")
        reset_gui(url_text, prompt_text, output_entry, submit_button, keywords_label)
        return

    if not output_path_input:
        output_path_input = "~/Desktop/issues"
    output_path = os.path.expanduser(output_path_input)
    if not output_path.endswith(".json"):
        output_path += ".json"
    logger.debug("Output path resolved to: %s", output_path)

    # --- 4. Keyword Extraction ---
    try:
        keywords = get_filtered_keywords(prompt_value, url_value)
        keywords_label.config(text="Extracted Keywords: " + ", ".join(keywords))
    except Exception as e:
        messagebox.showerror("