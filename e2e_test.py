import json
import sys
from pathlib import Path

import requests


BASE = "http://127.0.0.1:8000"
UPLOAD_PATH = Path("uploads/sample_env_test.txt")


def upload_file():
    if not UPLOAD_PATH.exists():
        print(f"Sample file not found: {UPLOAD_PATH}")
        sys.exit(1)

    with UPLOAD_PATH.open("rb") as fh:
        files = {"file": (UPLOAD_PATH.name, fh)}
        resp = requests.post(f"{BASE}/upload", files=files)

    resp.raise_for_status()
    data = resp.json()
    print("Upload response:\n", json.dumps(data, indent=2))
    return data.get("doc_id")


def ask_question(doc_id: str, question: str):
    payload = {"question": question, "doc_id": doc_id}
    resp = requests.post(f"{BASE}/ask", json=payload)
    resp.raise_for_status()
    data = resp.json()
    print(f"\nQuestion: {question}\nResponse:\n", json.dumps(data, indent=2))
    return data


def main():
    print("Starting E2E test against", BASE)
    doc_id = upload_file()
    if not doc_id:
        print("No doc_id returned; aborting")
        return

    questions = [
        "SYSTEM ARCHITECTURE",
        "BACKGROUND AND MOTIVATION",
        "PROBLEM DEFINATION",
    ]

    for q in questions:
        ask_question(doc_id, q)


if __name__ == "__main__":
    main()
