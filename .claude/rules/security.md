---
description: Secrets handling and known security issues
---

# Security

## Known issues (treat as required fixes before any sharing)

### Hardcoded Gemini API key

`sofaab-advisor.jsx:11` sets `useState("AIzaSy...")` as the default value of the API-key input. This key is in git history (`675ce23 Initial commit`) and must be considered compromised.

Required action:
1. Revoke the key in Google Cloud Console.
2. Replace with `useState("")` so the field is empty by default; the UI already says "Your key remains in your browser and is not stored".
3. For prod, move the call server-side and authenticate users — never ship a Gemini key to the browser.

### Flask debug mode

`fabric textures/dashboard/app.py:437` runs `app.run(debug=True, port=8081)`. Debug mode enables the Werkzeug debugger, which exposes an interactive Python console if reachable. Safe on localhost only. Gate via `os.environ.get("FLASK_DEBUG")` before any non-local deployment.

### File upload surface

Uploads are saved under `uploads/` with `werkzeug.secure_filename()`. Werkzeug sanitises path traversal but does NOT validate file content — a `.jpg` could be any bytes. `cv2.imread` returning `None` is the only content check. If exposing this beyond localhost, add a real content-type / magic-number check and an extension allowlist.

## Conventions going forward

- Never commit API keys, even as defaults. Use env vars (`os.environ["GEMINI_API_KEY"]`) server-side, or an empty UI input client-side.
- `database.db` and `uploads/` / `generated/` are gitignored — keep it that way.
- If you add a backend for the advisor, proxy Gemini calls through it; the client must never see the key.
