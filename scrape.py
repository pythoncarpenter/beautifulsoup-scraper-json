#!/usr/bin/env python3
import requests
from bs4 import BeautifulSoup
import json
import tkinter as tk
import os

def scrape_github_issues(url):
    # Use a custom User-Agent header to mimic a real browser
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
    
    # DEBUG: Print out the response text so you can inspect the HTML structure.
    # (You may want to comment this out once you know the correct structure.)
    print("DEBUG: HTML Response:")
    print(response.text)
    
    soup = BeautifulSoup(response.text, 'html.parser')
    issues = []
    
    # Look for elements with the class "js-issue-row"
    # If you see that GitHub has changed its markup, update this selector.
    for issue in soup.find_all("div", class_="js-issue-row"):
        title_elem = issue.find("a", class_="Link--primary")
        if title_elem:
            title = title_elem.text.strip()
            href = title_elem.get("href", "")
            full_url = "https://github.com" + href
            issues.append({"title": title, "url": full_url})
    
    # Return the scraped issues as a formatted JSON string.
    return json.dumps(issues, indent=2)

def on_submit():
    # Get the URL from the text box (with wrapping enabled)
    url = url_text.get("1.0", tk.END).strip()
    if not url:
        url = "https://github.com/vercel/nft/issues"
    
    # Get the output file path input (e.g., "~/Desktop/filename")
    output_path_input = output_entry.get().strip()
    if not output_path_input:
        output_path_input = "~/Desktop/issues"  # default path if left blank
    
    # Expand ~ to the full home directory and append ".json" if not present
    output_path = os.path.expanduser(output_path_input)
    if not output_path.endswith(".json"):
        output_path += ".json"
    
    # Close the GUI window
    root.destroy()
    
    # Run the scraper with the provided URL
    output = scrape_github_issues(url)
    
    # Write the JSON output to the specified file, ensuring the directory exists
    try:
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        with open(output_path, "w") as f:
            f.write(output)
        print(f"Results saved to: {output_path}")
    except Exception as e:
        print(f"Error saving file: {e}")
    
    # Also print the JSON output to the console
    print("Scraped issues:")
    print(output)

# --------------------- GUI Setup ---------------------
root = tk.Tk()
root.title("GitHub Issues Scraper")

# URL input label and text box with word wrapping
url_label = tk.Label(root, text="Input issues URL from GitHub:")
url_label.pack(pady=(10, 0))

url_text = tk.Text(root, wrap=tk.WORD, width=50, height=4)
url_text.insert(tk.END, "https://github.com/vercel/nft/issues")
url_text.pack(padx=10, pady=10)

# Output file path label and single-line input
output_label = tk.Label(root, text="Specify output file path (e.g., ~/Desktop/filename):")
output_label.pack(pady=(10, 0))

output_entry = tk.Entry(root, width=50)
output_entry.insert(tk.END, "~/Desktop/issues")
output_entry.pack(padx=10, pady=10)

# Submit button to run the scraper and save results
submit_button = tk.Button(root, text="Submit", command=on_submit)
submit_button.pack(pady=(0, 10))

root.mainloop()