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
    # 1. Set up the environment or arguments as needed:
    #    For example, you might set an environment variable if your run.sh uses it:
    #    os.environ["SCRAPER_URL"] = "https://github.com/vercel/nft/issues"

    # 2. Run the script. This should create or update ~/Desktop/issues.json.
    #    If your script depends on being in a certain directory, cd into it first.
    #    Use shell=True only if strictly necessary:
    subprocess.run(["./run.sh"], check=True)

    # 3. Return the path to the JSON output so we can read it in subsequent tests.
    #    Adjust to match your script's actual output path (e.g., ~/Desktop/issues.json).
    return os.path.expanduser("~/Desktop/issues.json")

def test_scraper_output_exists(run_scraper):
    """
    Test that the JSON output file was actually created.
    """
    output_path = run_scraper
    assert os.path.isfile(output_path), f"Output file not found at {output_path}"

def test_multi_page_capture(run_scraper):
    """
    Test that the scraper captured multiple pages of issues if there's a 'Next' link.
    We check if the total number of issues is above a typical single-page count (e.g. 25).
    """
    output_path = run_scraper

    with open(output_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    # 'data' should be a list of issues if run.sh is in 'issues' mode.
    # If it's a dict with {"responses": ...}, adapt accordingly.
    assert isinstance(data, list), "Expected a list of issues in the JSON output."

    issue_count = len(data)
    print(f"Found {issue_count} issues.")

    # A typical GitHub issues page might show 25 issues by default.
    # If your repo definitely has more than 25, we expect the scraper 
    # to follow the 'Next' link and collect more.
    assert issue_count > 25, "It appears we did not capture multiple pages."

    # Optionally, you could check for a specific known item or number:
    # assert any(issue["number"] == "999" for issue in data), "Item from page 2 missing."