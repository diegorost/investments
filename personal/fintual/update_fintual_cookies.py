#!/usr/bin/env python3
"""
Update Fintual cookies from a browser curl command.

How to use when cookies expire:
  1. Open https://fintual.cl/api/goals?user_token=PU_JsaodzqYy82Esj_Cz&user_email=diegorostn@gmail.com in Chrome
  2. F12 → Network → click the goals request → Right click → Copy → Copy as cURL (cmd)
  3. Paste the curl command into a file called curl.txt in this folder
  4. Run:  python update_fintual_cookies.py curl.txt
"""

import re, json, sys
from pathlib import Path

CONFIG_FILE = Path(__file__).parent / "fintual_cookies.json"

def parse_curl(text):
    # Extract -b "..." cookie string (handles both ^ escaped Windows and normal)
    text = text.replace("^\n", " ").replace("^\r\n", " ").replace("\\\n", " ")
    match = re.search(r'-b\s+"([^"]+)"', text)
    if not match:
        match = re.search(r"--cookie\s+'([^']+)'", text)
    if not match:
        print("ERROR: Could not find cookies in the curl command.")
        sys.exit(1)

    cookie_str = match.group(1)
    cookies = {}
    for part in cookie_str.split("; "):
        if "=" in part:
            k, v = part.split("=", 1)
            cookies[k.strip()] = v.strip()
    return cookies

def main():
    if len(sys.argv) < 2:
        print("Usage: python update_fintual_cookies.py curl.txt")
        print("  (paste the curl command copied from Chrome DevTools into curl.txt)")
        sys.exit(1)

    curl_text = Path(sys.argv[1]).read_text(encoding="utf-8")
    cookies = parse_curl(curl_text)

    # Keep only the relevant ones
    relevant = ["_fintual_session_cookie", "cf_clearance", "uid"]
    filtered = {k: v for k, v in cookies.items() if k in relevant}

    if not filtered:
        print("ERROR: No known Fintual cookies found. Make sure you copied the right request.")
        sys.exit(1)

    config = json.loads(CONFIG_FILE.read_text()) if CONFIG_FILE.exists() else {}
    config["cookies"] = {**config.get("cookies", {}), **filtered}
    CONFIG_FILE.write_text(json.dumps(config, indent=2))

    print(f"Updated {len(filtered)} cookies: {', '.join(filtered.keys())}")
    print("Done — restart the dashboard server.")

if __name__ == "__main__":
    main()
