#!/usr/bin/env python3
import requests
from bs4 import BeautifulSoup
import json
import tkinter as tk
import os

def scrape_github_issues(url):
    # Use a custom User-Agent header to mimic a real browser.
    headers = {
        'User-Agent': (
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) '
            'AppleWebKit/537.36 (KHTML, like Gecko) '
            'Chrome/89.0.4389.90 Safari/537.36'
        )
    }
    response = requests.get(url, headers=headers)
    if response.status_code != 200:
        return json.dumps({
            "error": "Failed to fetch page",
            "status_code": response.status_code
        })
    
    soup = BeautifulSoup(response.text, 'html.parser')
    issues = []
    
    # Look for each issue row. GitHub's React-based page wraps issues in <li> elements.
    issue_rows = soup.find_all("li", class_=lambda x: x and "ListItem-module__listItem" in x)
    
    for row in issue_rows:
        # Extract the title and URL from the <a> element.
        title_elem = row.find("a", class_=lambda x: x and "TitleHeader-module__inline" in x)
        if title_elem:
            title = title_elem.get_text(strip=True)
            href = title_elem.get("href", "")
            full_url = "https://github.com" + href if href.startswith("/") else href
        else:
            continue  # If no title is found, skip this issue.
        
        # Extract the issue number from a span element that contains it.
        num_elem = row.find("span", class_=lambda x: x and "issue-item-module__defaultNumberDescription" in x)
        number = ""
        if num_elem:
            # The first token is usually the number, e.g., "#445"
            raw_number = num_elem.get_text(strip=True).split()[0]
            if raw_number.startswith("#"):
                number = raw_number[1:]
            else:
                number = raw_number
        
        # Extract created date (if available) from the <relative-time> tag.
        rel_time_elem = row.find("relative-time")
        created_at = rel_time_elem.get("datetime", "") if rel_time_elem else ""
        
        # Extract the author from the link that has an author class.
        author_elem = row.find("a", class_=lambda x: x and "issue-item-module__authorCreatedLink" in x)
        author = author_elem.get_text(strip=True) if author_elem else ""
        
        # Append the issue to the list if we have a title and a number.
        if title and number:
            issues.append({
                "number": number,
                "title": title,
                "url": full_url,
                "created_at": created_at,
                "author": author
            })
    
    # Return the issues as a JSON-formatted string.
    return json.dumps(issues, indent=2)

def on_submit():
    # Get the URL from the text box (defaulting if empty).
    url = url_text.get("1.0", tk.END).strip()
    if not url:
        url = "https://github.com/vercel/nft/issues"
    
    # Get the output file path input (e.g., "~/Desktop/filename"); default if empty.
    output_path_input = output_entry.get().strip()
    if not output_path_input:
        output_path_input = "~/Desktop/issues"  # Default path if left blank.
    
    # Expand '~' to the full home directory and ensure the filename ends with ".json"
    output_path = os.path.expanduser(output_path_input)
    if not output_path.endswith(".json"):
        output_path += ".json"
    
    # Close the GUI window.
    root.destroy()
    
    # Run the scraper and capture its output.
    output = scrape_github_issues(url)
    
    # Write the JSON output to the specified file (this overwrites any existing file).
    try:
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        with open(output_path, "w") as f:
            f.write(output)
    except Exception:
        # In production, you might log errors instead of printing.
        pass

# --------------------- GUI Setup ---------------------
root = tk.Tk()
root.title("GitHub Issues Scraper")

# URL input label and text box with word wrapping.
url_label = tk.Label(root, text="Input issues URL from GitHub:")
url_label.pack(pady=(10, 0))
url_text = tk.Text(root, wrap=tk.WORD, width=50, height=4)
url_text.insert(tk.END, "https://github.com/vercel/nft/issues")
url_text.pack(padx=10, pady=10)

# Output file path label and single-line input.
output_label = tk.Label(root, text="Specify output file path (e.g., ~/Desktop/filename):")
output_label.pack(pady=(10, 0))
output_entry = tk.Entry(root, width=50)
output_entry.insert(tk.END, "~/Desktop/issues")
output_entry.pack(padx=10, pady=10)

# Submit button to run the scraper and save results.
submit_button = tk.Button(root, text="Submit", command=on_submit)
submit_button.pack(pady=(0, 10))

root.mainloop()