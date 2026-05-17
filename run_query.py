import sys
from pathlib import Path
import requests

BASE = "http://127.0.0.1:8000"

def run(file_path, question):
    p = Path(file_path)
    if not p.exists():
        print("File not found", file_path); return

    with p.open('rb') as fh:
        files = {'file': (p.name, fh)}
        r = requests.post(f"{BASE}/upload", files=files)
    r.raise_for_status()
    di = r.json().get('doc_id')
    print('uploaded', p.name, 'doc_id', di)

    payload = {'question': question, 'doc_id': di}
    r2 = requests.post(f"{BASE}/ask", json=payload)
    r2.raise_for_status()
    print(r2.json())


if __name__ == '__main__':
    if len(sys.argv) < 3:
        print('usage: run_query.py <file> <question>')
        sys.exit(1)
    run(sys.argv[1], sys.argv[2])
