#!/usr/bin/env python3
import sys

def count_tokens_tiktoken(text, model="gpt-3.5-turbo"):
    """
    Uses tiktoken (if installed) to count tokens for the specified model.
    Returns the token count or None if tiktoken is not available.
    """
    try:
        import tiktoken
    except ImportError:
        return None

    encoding = tiktoken.encoding_for_model(model)
    tokens = encoding.encode(text)
    return len(tokens)

def approximate_token_count(text):
    """
    Approximates token count by assuming roughly 4 characters per token.
    """
    return int(len(text) / 4)

def main():
    if len(sys.argv) < 2:
        print(f"Usage: {sys.argv[0]} <file>")
        sys.exit(1)

    file_path = sys.argv[1]
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()
    except Exception as e:
        print(f"Error reading file '{file_path}': {e}")
        sys.exit(1)

    # Try to count tokens using tiktoken; fall back to approximation if unavailable.
    token_count = count_tokens_tiktoken(content)
    if token_count is None:
        token_count = approximate_token_count(content)
        print("tiktoken not installed; using approximate token count.")
    else:
        print("Using tiktoken for accurate token count.")

    # Set the threshold for the context window (e.g., 4096 tokens)
    THRESHOLD_TOKENS = 4096

    if token_count > THRESHOLD_TOKENS:
        print(f"File exceeds context window: {token_count} tokens (threshold: {THRESHOLD_TOKENS} tokens)")
    else:
        print(f"File is within context window: {token_count} tokens (threshold: {THRESHOLD_TOKENS} tokens)")

if __name__ == "__main__":
    main()