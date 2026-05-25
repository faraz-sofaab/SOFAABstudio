# SOFAAB Studio

Fabric textures digitisation pipeline for SOFAAB (premium Indian furniture brand). Converts raw fabric scans into PBR maps usable in `<model-viewer>` / Three.js previews. Also contains a standalone Gemini-powered AI Interior Design Advisor.

## Components

- `sofaab-advisor.jsx` — Single-file React component. Chat UI calling Google Gemini directly from the browser. Demo/prototype, not bundled or built yet.
- `fabric textures/generate_pbr_maps.py` — Standalone CLI. Generates Albedo / Normal / Roughness / Specular / AO from one or more base textures.
- `fabric textures/generate_model_viewer_pbr.py` — Standalone CLI. Adds seamless tiling + ORM packing for glTF / `<model-viewer>`.
- `fabric textures/dashboard/` — Flask web app. SQLite-backed library + browser UI for uploading scans, tuning PBR parameters, and previewing on a GLB model with Three.js.

## Stack

- Python 3.12+ (Flask, OpenCV `cv2`, numpy, Werkzeug, sqlite3) — no dependency manifest yet; install ad-hoc with `pip` for now.
- Frontend: vanilla JS + Three.js via ESM importmap (no bundler). HTML in `fabric textures/dashboard/templates/`, JS/CSS/assets in `fabric textures/dashboard/static/`.
- Storage: local filesystem (`uploads/`, `generated/`) + SQLite (`database.db`) — all under `fabric textures/dashboard/`.

## Run

- Dashboard: `cd "fabric textures/dashboard"; python app.py` → http://127.0.0.1:8081 (Flask debug mode).
- Standalone PBR gen: `python "fabric textures/generate_model_viewer_pbr.py" --input_dir <dir> --output_dir <dir> --resolution 2048`.
- Advisor JSX: no build pipeline yet — paste into a React playground or wire into a Vite/Next host.

## Conventions

- OpenCV channel order is BGR; when stacking maps (`np.stack([B, G, R], axis=-1)`) the leftmost is Blue. Normal maps follow OpenGL/Three.js convention with Y inverted (`normal_y = -grad_y`).
- ORM packing for glTF: R = AO (occlusion), G = roughness, B = metallic. Fabric → metallic channel is zero-filled.
- Texture path on disk: `generated/<base_name>/<base_name>_{diffuse,normal,roughness,occlusion,orm,metallic_roughness}.jpg`.
- Filenames are sanitised with `secure_filename`; the texture `id` is the filename without extension.

## Gotchas

- `sofaab-advisor.jsx:11` ships a hardcoded Gemini API key as the input's default value. Treat the key in this repo as already-compromised — rotate before sharing this code. See `@.claude/rules/security.md`.
- Flask `app.py` runs with `debug=True` on `0.0.0.0`-equivalent. Don't expose the dashboard publicly without disabling debug.
- `make_seamless()` uses 50% offset + sigmoid blend; mirror tiling halves effective resolution because the 2×2 mirrored grid is resized back down.
- Settings are written to SQLite before `generate_pbr` runs. If generation fails, the DB row is already updated — re-running may use stale settings.
- `app.py:389` calls `json.dumps(...)` but `json` is never imported. The `manage_models` config save path will raise `NameError` on first hit.

## See also

- @.claude/rules/architecture.md — module map and data flow
- @.claude/rules/python.md — Python / OpenCV conventions
- @.claude/rules/security.md — secrets handling and known issues
- @.claude/rules/workflows.md — common dev tasks
- @docs/architecture-guide.md — detailed system diagrams
- @docs/api-reference.md — Flask endpoint reference
- @docs/workflow-diagrams.md — pipeline and dev flow diagrams
