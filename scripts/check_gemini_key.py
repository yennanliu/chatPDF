#!/usr/bin/env python3
"""Quick check: does the GEMINI_API_KEY in .env work?"""
import os, sys
from pathlib import Path

# Load .env manually
env_path = Path(__file__).parent.parent / "backend" / ".env"
for line in env_path.read_text().splitlines():
    if "=" in line and not line.startswith("#"):
        k, _, v = line.partition("=")
        os.environ.setdefault(k.strip(), v.strip())

key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
if not key:
    print("FAIL  No GEMINI_API_KEY or GOOGLE_API_KEY found in .env")
    sys.exit(1)

print(f"Key found: {key[:8]}...{key[-4:]}")

import urllib.request, json

# 1. List models
url = f"https://generativelanguage.googleapis.com/v1beta/models?key={key}"
try:
    r = urllib.request.urlopen(url, timeout=10)
    models = [m["name"] for m in json.loads(r.read()).get("models", [])
              if "generateContent" in m.get("supportedGenerationMethods", [])]
    print(f"PASS  Key valid — {len(models)} generative models available")
except Exception as e:
    print(f"FAIL  Key rejected by API: {e}")
    sys.exit(1)

# 2. Send a real generate request
payload = json.dumps({
    "contents": [{"parts": [{"text": "Reply with exactly: OK"}]}]
}).encode()
url2 = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash-lite:generateContent?key={key}"
req = urllib.request.Request(url2, data=payload, headers={"Content-Type": "application/json"})
try:
    r2 = urllib.request.urlopen(req, timeout=15)
    data = json.loads(r2.read())
    text = data["candidates"][0]["content"]["parts"][0]["text"]
    print(f"PASS  generateContent works — model replied: {text.strip()!r}")
except urllib.error.HTTPError as e:
    body = e.read().decode()
    print(f"FAIL  generateContent HTTP {e.code}: {body[:300]}")
    sys.exit(1)
except Exception as e:
    print(f"FAIL  generateContent error: {e}")
    sys.exit(1)
