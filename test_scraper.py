import os
import json
import subprocess
import pytest

@pytest.fixture(scope="session")
def run_scraper():
    """
    Runs the run.sh script one time before tests in this file.
    Assumes run.sh writes a JSON file to ~/Desktop/issues.json 
    (or your chosen path).
    """
    # Optionally, set environment variables if needed:
    # os.environ["SCRAPER_URL"] = "https://github.com/neovim/neovim/issues"

    # Run the script. This should create or update ~/Desktop/issues.json.
    subprocess.run(["./run.sh"], check=True)

    # Return the path to the JSON output.
    return os.path.expanduser("~/Desktop/issues.json")

def _load_json_without_comments(output_path):
    """
    Loads JSON content from a file that may have comment lines (starting with //) at the top.
    """
    with open(output_path, "r", encoding="utf-8") as f:
        lines = f.readlines()
    # Filter out lines starting with //
    json_str = "".join(line for line in lines if not line.lstrip().startswith("//"))
    return json.loads(json_str)

def _get_keywords_from_output(output_path):
    """
    Reads the keywords comment line from the output file.
    Assumes a comment line starting with "// Keywords:" exists.
    Returns a list of keywords.
    """
    with open(output_path, "r", encoding="utf-8") as f:
        for line in f:
            if line.lstrip().startswith("// Keywords:"):
                parts = line.split(":", 1)
                if len(parts) < 2:
                    return []
                keywords_str = parts[1].strip()
                return [kw.strip() for kw in keywords_str.split(",") if kw.strip()]
    return []

def test_scraper_output_exists(run_scraper):
    """
    Test that the JSON output file was actually created.
    """
    output_path = run_scraper
    assert os.path.isfile(output_path), f"Output file not found at {output_path}"

def test_multi_page_capture(run_scraper):
    """
    Test that the scraper captured multiple pages of issues.
    """
    output_path = run_scraper
    data = _load_json_without_comments(output_path)
    # Expecting a list of issues.
    assert isinstance(data, list), "Expected a list of issues in the JSON output."
    issue_count = len(data)
    print(f"Found {issue_count} issues.")
    # Assume a typical GitHub issues page shows 25 issues; check for more than one page.
    assert issue_count > 25, "It appears we did not capture multiple pages."

def test_keyword_filtering(run_scraper):
    """
    Test that the keywords used in the scraping process do not include:
      - The repository name (for https://github.com/neovim/neovim/issues, 'neovim')
      - Any blocked keywords (e.g. 'bug', 'report', etc.)
    """
    output_path = run_scraper
    keywords = _get_keywords_from_output(output_path)
    repo_name = "neovim"
    blocked_list = {"bug", "report", "issue", "fix", "error", "problem", "test", "todo"}
    for kw in keywords:
        assert kw.lower() != repo_name.lower(), f"Keyword '{kw}' should not match repository name '{repo_name}'."
        assert kw.lower() not in blocked_list, f"Keyword '{kw}' is in the blocked list."