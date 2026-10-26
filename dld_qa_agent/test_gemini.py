"""Quick Gemini connection test. Run:  python3 test_gemini.py
Checks: key found? internet/proxy? model available? how fast is one answer?"""
import getpass
import json
import os
import time
import urllib.error
import urllib.request
from pathlib import Path

MODEL = "gemini-flash-latest"
HERE = Path(__file__).resolve().parent

key = os.environ.get("GEMINI_API_KEY", "").strip()
if not key and (HERE / "gemini_key.txt").exists():
    key = (HERE / "gemini_key.txt").read_text().strip()
if not key:
    key = getpass.getpass("Gemini API key (hidden): ").strip()
print(f"1. Key found: {'yes' if key else 'NO'} ({len(key)} characters)")
proxies = {k: v for k, v in os.environ.items() if k.lower() in ("http_proxy", "https_proxy", "no_proxy")}
print(f"2. Proxy settings: {proxies or 'none'}")


def call(url, body=None, headers=None, timeout=60):
    req = urllib.request.Request(url, data=json.dumps(body).encode() if body else None,
                                 headers={"Content-Type": "application/json", **(headers or {})})
    t = time.time()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return "OK", time.time() - t, json.loads(r.read())
    except urllib.error.HTTPError as e:
        return f"HTTP {e.code}", time.time() - t, e.read().decode(errors="replace")[:400]
    except Exception as e:
        return f"{type(e).__name__}", time.time() - t, str(e)


status, sec, data = call(f"https://generativelanguage.googleapis.com/v1beta/models?key={key}", timeout=30)
print(f"3. Reach Google + key valid: {status} ({sec:.1f} s)")
if status == "OK":
    names = [m["name"].split("/")[-1] for m in data.get("models", []) if "flash" in m["name"]]
    print(f"   Flash models on your key: {', '.join(names[:12])}")
else:
    print(f"   Detail: {data}")

status, sec, data = call("https://generativelanguage.googleapis.com/v1beta/openai/chat/completions",
                         {"model": MODEL, "messages": [{"role": "user", "content": "Reply with the word OK"}]},
                         {"Authorization": f"Bearer {key}"}, timeout=90)
answer = data["choices"][0]["message"]["content"] if status == "OK" else data
print(f"4. Model '{MODEL}' answer: {status} in {sec:.1f} s -> {str(answer)[:200]}")
print("\nAll OK -> run the agent again." if status == "OK" else
      "\nSend this output (no key is shown) to get help.")
