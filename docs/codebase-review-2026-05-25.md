# SOFAAB Studio — Codebase Review

**Date:** 2026-05-25
**Scope:** Internal tool, staying local-only. Production hardening de-emphasised.
**Format:** Discussion-ready summary for a team meeting.
**Files reviewed:** 7 source files (~1,720 LOC) — Flask + OpenCV pipeline (`fabric textures/`), vanilla JS + Three.js dashboard (`fabric textures/dashboard/`), single-file React advisor (`sofaab-advisor.jsx`).

---

## Executive summary

**Overall grade: C+ (5.8 / 10)** — solid prototype, several immediate bugs, classic "second-system" code duplication, and a UX gap in the 3D step that's blocking the value prop.

The good news: this is small (~1.7k LOC) and well-documented (`CLAUDE.md`, `.claude/rules/`, `docs/` are above average for a one-commit project). A focused 1–2 day refactor pass would move it to **B (7+/10)** with minimal risk because there's no production traffic, no test suite to update, and no other consumers.

**The three things to discuss first:**
1. **Five concrete bugs ship today** — silent edge_crop scaling, missing default GLB, `json` not imported, no orbit controls so the 3D preview is unusable, stale settings persist after failed generation.
2. **One PBR algorithm is forked three ways** — `app.py:generate_pbr`, `generate_pbr_maps.py`, `generate_model_viewer_pbr.py`. Pick one, delete the others, expose a thin CLI wrapper.
3. **UI feature drift** — server accepts hue / mirror tiling / normal strength / resolution / tint, the sliders for those don't exist in the HTML. Either expose them or trim the server contract.

### Issue summary by severity

| Severity | Count | Notes |
|---|---|---|
| Critical | 0 | (No exploitable issues for a local-only tool.) |
| High | 5 | Five user-visible bugs, all in this report's §2. |
| Medium | 9 | Mostly architecture and maintainability. |
| Low | 11 | Polish, conventions, dead code. |
| Info | 4 | Future-looking. |

### Per-area scorecard

| Area | Score | Why |
|---|---|---|
| Architecture | 6 / 10 | Sensible for size; `app.py` doing too much; PBR forked 3×. |
| Security (local-only context) | 7 / 10 | Hardcoded Gemini key is the only real issue. |
| Performance | 8 / 10 | Sync PBR generation is fine for local; texture load is sequential. |
| Reliability | 6 / 10 | DB writes before generation; no logging; no error surfaces. |
| Maintainability | 6 / 10 | Strong context docs offset missing CI/lint/tests. |
| Quality | 6 / 10 | Magic numbers, no type hints, dead code. |
| Testing | 3 / 10 | No tests. |
| Documentation | 7 / 10 | `CLAUDE.md` + rules + `docs/` are great; no `README.md` at root. |
| Dependencies | 4 / 10 | No `requirements.txt`; Three.js 24 minor versions behind. |
| DevOps | 3 / 10 | No CI, no env config, `debug=True` always — acceptable for local. |
| Accessibility | 5 / 10 | Native inputs OK, no labels-for, no alt text. |
| Concurrency | 7 / 10 | SQLite serialises; one Three.js init race. |

---

## 1. Quick wins to discuss first

These are <30-min each and high impact. Worth picking 4–5 before the meeting ends.

| # | Change | File | Why it's worth it |
|---|---|---|---|
| QW-1 | Add `import json` | `app.py:1-9` | Kills `NameError` in `/api/models` POST and GET (`app.py:389, 400`). Fully dead code path today. |
| QW-2 | Drop `static/models/brooklyn3smodel.glb` reference, point default at the file that exists (`/static/sample_model.glb`) | `app.js:308, 327` | Today the 3D step silently 404s and shows a fallback sphere. Users assume the engine is broken. |
| QW-3 | Stop double-dividing `edge_crop` by 100 | `app.js:232` and `app.py:165` | JS sends `0.1`; server reads it as `10` and divides again → `0.001`. Pick one place. |
| QW-4 | Add `OrbitControls` to the 3D scene | `app.js:339-355` | One import + 4 lines. Right now the user can't rotate the model. This is the single biggest UX win in the dashboard. |
| QW-5 | Load `studioformodels.hdr` as `scene.environment` | `app.js:339-355` | The HDR file already exists in `static/`. Lights up the PBR maps you spent so much code generating. |
| QW-6 | Move DB UPDATE in `/api/generate/<id>` to AFTER successful generation | `app.py:343-368` | If generation crashes, the row currently says `has_maps=1` with the new (possibly bad) settings. |
| QW-7 | Generate `requirements.txt` | new file at repo root or `fabric textures/dashboard/` | Anyone fresh-cloning today can't run this. `pip freeze | grep -i "flask\|opencv\|numpy\|werkzeug" > requirements.txt`. |
| QW-8 | Show slider values numerically | `app.js:151-176` | `<span id="b-val">${...}</span>` next to each `<input>`. 5 minutes; massive feedback improvement. |
| QW-9 | Remove the hardcoded Gemini API key default | `sofaab-advisor.jsx:11` | Replace `useState("AIzaSy…")` with `useState("")`. Key in git history is already documented as compromised in `.claude/rules/security.md`. Revoke in GCP Console. |
| QW-10 | Add a `manage_models` JSON request guard for `data is None` | `app.py:387` | If a non-multipart non-JSON POST hits this route, `data = request.json` is `None` and `'leg_configs' in data` throws. |

---

## 2. Bugs that ship today (HIGH)

These are not opinions — these are user-visible regressions today.

### B-1 · `json` is used but never imported

**File:** `app.py:389`, `app.py:400`
**Impact:** Both branches of the `leg_configs` save path raise `NameError`. The "Legs" tab is empty in the UI, so this isn't *hit* yet, but the next person to wire up legs will trip immediately.

### B-2 · Default 3D model file is missing

**File:** `app.js:308, 327` reference `/static/models/brooklyn3smodel.glb`. The `static/` directory contains `sample_model.glb` and several HDR/JPEGs, but no `models/` subdirectory.
**Impact:** Every fresh load of step 3 fails the GLB fetch, swallows the error in the `(err) => …` callback (`app.js:370`), and falls back to a sphere. Users assume the engine is broken; you've also lost the ability to actually see the Brooklyn sofa with the new fabric.
**Fix options:** (a) move/rename `sample_model.glb` to `static/models/brooklyn3smodel.glb`, or (b) change the JS path to the file that exists. Plus add a *visible* error message instead of silently swapping in a sphere.

### B-3 · `edge_crop` is divided by 100 twice (off by 100×)

**Files:** `app.js:232` sends `parseFloat(cropEl.value) / 100`; `app.py:165` then does `float(options.get('edge_crop', 10)) / 100.0`.
**Why it "works" today:** The slider element `#adj-crop` (`app.js:227`) doesn't exist in the HTML, so `cropEl` is `null`, `edge_crop` is never sent, and the server falls back to `10 / 100 = 0.1`. The default works only by accident. Wire up the slider and it instantly breaks.
**Fix:** Decide once where the percent-to-fraction conversion happens. Recommend keeping it server-side; the JS contract becomes "send the user-visible number 0..100".

### B-4 · DB row updated *before* PBR generation runs

**File:** `app.py:343-365`
**Impact:** If `generate_pbr` raises (bad image, disk full, OOM), the row already has the new settings and `has_maps=1`. The frontend will then ask for map URLs that don't exist on disk. On reload, step 3 tries to render a broken state.
**Fix:** Wrap the `UPDATE` and `generate_pbr(...)` in a transaction, or just move the `UPDATE` after the generator returns `True`.

### B-5 · No camera controls on the 3D preview

**File:** `app.js:331-355` (`LuxuryEngine.init`)
**Impact:** Camera is fixed at `(0, 1, 4)`. No orbit, no zoom, no pan. The whole point of step 3 is to inspect the fabric on a model from different angles. Without controls, users are looking at one frozen view.
**Fix:** `import { OrbitControls } from 'three/addons/controls/OrbitControls.js'` (matches existing importmap pattern), instantiate in `init()` after the renderer, call `controls.update()` in `animate()`.

### Adjacent issues (Medium, same area)

- **B-6** · UI sends only `brightness`, `contrast`, `saturation`, `edge_crop` to `/api/generate` (`app.js:228-233`). Server-side accepts `hue`, `mirror_tiling`, `normal_strength`, `resolution`, `tint_color`. The other knobs are dead from the UI's perspective. Either add sliders or trim the contract.
- **B-7** · `LuxuryEngine.init()` is declared `async` but called from the constructor without `await` (`app.js:334`). Today nothing depends on init completing before subsequent calls, but it's a footgun.
- **B-8** · `updateTextures` lazily creates `this.material` (`app.js:381`). `loadModel`'s `traverse` callback applies `this.material` to nodes (`app.js:368`). The async GLB load + async texture load mean the model can render with `material === undefined` for a frame if the GLB resolves before any texture does. Initialise the material in `init()`, not in `updateTextures`.
- **B-9** · `list_textures()` (`app.py:272-322`) mutates the DB during a GET and then *recursively* calls itself if it found new files. Side-effects in a GET and a recursion that can loop on a write-race. Move the sync to an explicit endpoint (e.g. `POST /api/textures/sync`) or run it only at upload time.

---

## 3. Architecture (MEDIUM)

### A-1 · One PBR algorithm, three implementations

`generate_pbr_maps.py` (108 LOC), `generate_model_viewer_pbr.py` (142 LOC), and `app.py:generate_pbr` (113 LOC) all reimplement variants of the same Albedo → Normal → Roughness → AO → ORM pipeline with slightly different parameters (sigmoid vs cosine seamless, with vs without bilateral filter, with vs without delight, Y-inverted vs not, different roughness ranges 150-255 vs 120-240, different gamma values 1.5 vs 2.0).

**Recommendation:** Extract a single `pbr.py` module exposing functions `adjust_color`, `delight`, `make_seamless`, `derive_normal`, `derive_roughness`, `derive_ao`, `pack_orm`. The dashboard calls it directly; the two CLIs become 30-line wrappers that take CLI args and forward to the module. This eliminates ~200 LOC and ensures behavior parity.

`.claude/rules/architecture.md` already names the dashboard's `generate_pbr` as the source of truth — make it actually so.

### A-2 · `app.py` is doing too many jobs

437 lines mixing: Flask app setup, DB schema, DB connection helper, three image-math helpers, the full PBR pipeline, six route handlers, and two file servers. Approaching the 500-line "god file" threshold.

**Recommendation (3-file split, in line with the project's "fewer, flatter files" preference):**
- `app.py` — Flask app, route handlers, ~150 LOC
- `pbr.py` — pure image-processing functions (the deduplicated one from A-1), ~150 LOC
- `db.py` — connection helper, schema, ~50 LOC

Keep it flat; no `blueprints/` directory, no Application Factory pattern. The point is readability, not enterprise structure.

### A-3 · `manage_models` route conflates two operations

`POST /api/models` is both "upload a `.glb`" (multipart) and "save leg configs" (JSON). The branch on `'file' in request.files` works but adds cognitive load and makes the contract ambiguous.

**Recommendation:** Split into `POST /api/models` (upload only) and `PUT /api/models/<id>/legs` (config save). Net: ~+5 LOC, much clearer surface.

### A-4 · Frontend state is implicit globals

`window.luxuryEngine`, `window.setStep`, `window.refreshAssetList`, `window.resetSettings`, and four module-level `let`s in `app.js`. Works but is fragile — adding a second engine or a second `currentAsset` reference will fight the existing one.

**Recommendation:** Wrap state in a single object (e.g. `const state = { tab, asset, step, engine }`) and dispatch through a `render()` function. Don't introduce a framework — this is fine to keep imperative at this size.

### A-5 · `init_db()` runs at module import time

`app.py:42` calls `init_db()` immediately, which creates `database.db` on disk wherever you import `app.py` from. Fine in production-on-rails, surprising in tests/scripts.

**Recommendation:** Move to `if __name__ == '__main__'` block, or expose as `flask --app app init-db` CLI. Not urgent.

---

## 4. Code quality (LOW/MEDIUM)

### Q-1 · Magic numbers without names

Examples:
- `app.py:89` sigmoid steepness `-10`
- `app.py:176` safe-dim factor `0.6`
- `app.py:233` roughness range `(120, 240)`
- `app.py:243` AO gamma `2.0`
- `app.py:219` normal Z denominator `2048.0`
- `app.js:388, 396` UV repeat default `8`

Extract as module-level constants with a one-line comment explaining the choice. `.claude/rules/workflows.md` already has a "Tuning intuition" table that documents some of these — make the code match.

### Q-2 · Dead / placeholder code

- `app.py:53-55` `hex_to_rgb()` — defined, never called.
- `app.py:166` `tint_hex = options.get('tint_color', '#ffffff')` — parsed, never applied to the image. The `/api/generate` JSON contract in `docs/api-reference.md` even calls this out.
- `app.js:272` `window.refreshAssetList = refreshAssetList` — assigns an undefined identifier (`refreshAssetList` isn't defined anywhere in the file).
- HTML status badge `READY FOR 2D` (`index.html:69`) is static text, never updated to reflect actual step.

### Q-3 · No type hints in Python

For a 1.7k LOC codebase, missing hints aren't urgent, but `generate_pbr(image_path, base_name, options)` would benefit from a `TypedDict` for `options` — it's the same dict shape used in three places and the API contract.

### Q-4 · Print-based logging in CLIs, no logging in Flask

`generate_pbr_maps.py` and `generate_model_viewer_pbr.py` use `print()`. `app.py` is silent. When PBR generation fails, you get a 500 with `{"error": "Failed to load image"}` and no stack trace anywhere.

**Recommendation:** `import logging; log = logging.getLogger(__name__)`, configure once at module top, replace prints. Even a single-line format is enough.

### Q-5 · `.gitignore` artifact

Line 6: `fabric textures/dashboard/dashboard/` — a doubled-up path that suggests an accidental commit was caught once and committed to the ignore. Either confirm and keep, or remove.

### Q-6 · CSS theme mismatch with brand

`index.css:2-4` defines `--primary-teal: #0d9488` and uses teal throughout. The advisor (`sofaab-advisor.jsx:90, 105`) uses `#c8843a` (SOFAAB brand orange/brown). Two surfaces, two color systems. Pick one and reference it from both.

---

## 5. UX of the dashboard (MEDIUM)

Things a designer/user would call out in 10 minutes of testing.

| # | Issue | Fix |
|---|---|---|
| U-1 | Slider values not shown numerically | Add `<output>` element bound via `oninput`. |
| U-2 | No live preview of generated maps in step 2; only the raw scan | Show a small grid of generated thumbnails after first generation. |
| U-3 | No way to regenerate from step 3 — must navigate back to step 2 | Add a "Regenerate" button in the step-3 controls panel. |
| U-4 | Models and Legs tabs are empty placeholders | Either stub a "Coming soon" state or hide the tabs. |
| U-5 | Search box (`#asset-search`, `index.html:37`) has no event handler | Wire up a simple `filter()` on `asset-list` children. |
| U-6 | No delete-asset or rename-asset action | Add a row-level action menu; `DELETE /api/textures/<id>` is missing on the backend. |
| U-7 | Generation silently runs for several seconds at high resolutions | Add a progress UI; even a determinate-ish spinner with "Generating normal map…" stages helps. |
| U-8 | Server returns 500 strings, no toast in the UI | Single global toast component triggered from `fetch().catch()`. |
| U-9 | Status badge always reads `READY FOR 2D` | Derive from `currentStep` + `currentAsset.has_maps`. |
| U-10 | UV slider doesn't show its current value | Same fix as U-1. |
| U-11 | Three.js scene has no environment map (HDR ignored), so PBR looks flat | See QW-5. |

---

## 6. Dependencies (MEDIUM)

From the doc-research pass against current versions (May 2026):

| Stack item | Current | Latest (2026-05) | Action |
|---|---|---|---|
| Three.js | `0.160.0` (ESM via unpkg) | `0.184.0` | 24 minor versions behind. Notable: WebGPU production support since r171; `MeshPhysicalMaterial.sheen/sheenColor` semantics adjusted (your code sets `sheen` + `sheenRoughness` which is still valid; adding `sheenColor` gives proper tinted highlights). Upgrade is one line in the importmap; smoke-test the GLB load and the sheen slider. |
| `opencv-python` | unpinned | `4.13.0` | No code changes required; **avoid 4.12.0** specifically — has a 4× perf regression in `cv2.compare` on Windows. Pin `>=4.13.0`. |
| Flask | unpinned | `3.1.x` | No breaking changes for your usage. Pin for reproducibility. |
| `werkzeug` | unpinned | tracks Flask 3.1.x | Pin together. |
| `numpy` | unpinned | `2.x` for Python 3.9+ | Pin; OpenCV 4.13 expects 2.x. |
| Gemini API model | `gemini-2.5-flash` | Still GA and recommended | No change needed on the model name. **But:** Google's June 2026 deadline enforces API-key restrictions — unrestricted keys will be blocked. Even for a local-only tool, restrict the key to your IP / referrer in GCP Console after revoking the committed one. |
| React (in `.jsx`) | unspecified | `19.x` | No build setup at all — `.jsx` ships as source. Either add a Vite host or note "this is paste-bin code" in the file header. |

**Action:** Add `requirements.txt` (or `pyproject.toml`) and pin those four Python packages. Add a comment line in `index.html` next to the importmap noting "Three.js r160 — upgrade tracked at <internal-ticket>".

---

## 7. Documentation (LOW)

Strong baseline (`CLAUDE.md` + four `.claude/rules/` files + three `docs/` files). Gaps for a team-shared repo:

- **No `README.md` at root.** Anyone landing from a Git URL sees `CLAUDE.md` (which is great for Claude, less obvious to a human). Either rename or add a 30-line `README.md` that points at it.
- **No setup section** for someone fresh-cloning: which Python version, how to install OpenCV on Windows, where uploads/generated land. `workflows.md` is close but starts assuming you already have everything installed.
- **No CHANGELOG / ADRs.** For a one-commit repo this is fine to skip until the second meaningful refactor lands.
- **The `app.py` known issues block** in `python.md` is great and should grow — add the bugs from §2 of this report as you fix them so future-Claude has the receipts.

---

## 8. Security (LOW/MEDIUM — local-only context)

Most of the security checklist doesn't apply to a localhost tool. What remains:

- **S-1 (already documented)** · Hardcoded Gemini API key in `sofaab-advisor.jsx:11`, in git history (`675ce23`). Revoke in GCP; replace default with empty string. The advisor is the only surface that ever talks to the public internet, and the key being client-side means *anyone* you ever share that file with becomes a Gemini-billed identity.
- **S-2 (already documented)** · `app.py:437` `debug=True`. Fine on localhost; **the failure mode is "I tunneled this through ngrok for a demo"** and now anyone with the URL gets a Python REPL. Add an `os.environ.get("FLASK_DEBUG") == "1"` gate and default off.
- **S-3** · Upload route accepts any file extension. For a local tool it's not exploitable, but `cv2.imread()` returning `None` on a non-image is the *only* content validation. If someone drops a 50MB binary into uploads/, it sits there forever. Add an extension allowlist (~3 lines).
- **S-4** · `secure_filename` strips Unicode and special characters; the user-visible asset name is the same field as the disk-safe ID. A texture called "soft beige linen №1" becomes `soft_beige_linen_1` on every screen. Add a separate `display_name` column.

---

## 9. Testing (HIGH — but appropriate scope)

There are no tests. For a 1.7k LOC internal tool with one developer, a minimum viable suite is:

1. **Smoke test of `generate_pbr`** on a known image, asserting all 6 output files exist and are non-empty (pytest, one file, ~30 LOC).
2. **API contract test** via Flask test client: upload → generate → export → assert zip contains 6 files (~50 LOC).
3. **A `make test` or `poetry run pytest`** wired into the README's setup.

That's enough to catch the bugs in §2 next time. Browser tests / Playwright would be overkill at this scope.

---

## 10. Out of scope (don't recommend right now)

Calling these out so they don't derail the meeting:

- Auth / multi-user
- Postgres or any non-SQLite DB
- Containerisation (Docker / docker-compose)
- A JS build pipeline (Vite, esbuild, Webpack) — 400 lines of plain JS doesn't need it
- Tailwind / a CSS framework — the existing CSS is fine
- A frontend framework (React/Svelte/Vue) — same reason
- CI/CD — useful when there's a second contributor or a deploy target
- Observability (Sentry, Langfuse, etc.) — local-only

---

## 11. Suggested sequencing (if you want a plan)

**Session 1 (~2 hours):** All ten quick wins (§1). Each is independent; commit each one.
**Session 2 (~3 hours):** Extract `pbr.py` (A-1) + collapse the two CLIs into thin wrappers. Run the smoke test in §9.1 to verify parity.
**Session 3 (~2 hours):** Split `app.py` per A-2; wire `requirements.txt`; add the first three tests in §9.
**Session 4 (~3 hours):** Frontend cleanups — OrbitControls (done in QW-4 already), HDR (QW-5), slider values, regenerate button, toast component, search box.

That's a ~10-hour total path from C+ to B / B+. Discuss whether all four sessions are worth it or if you stop at session 2.

---

## Appendix · Files touched in each finding

| Finding | Files |
|---|---|
| B-1 | `fabric textures/dashboard/app.py:1-9, 389, 400` |
| B-2 | `fabric textures/dashboard/static/app.js:308, 327`; `fabric textures/dashboard/static/` |
| B-3 | `fabric textures/dashboard/static/app.js:232`; `app.py:165` |
| B-4 | `app.py:343-365` |
| B-5 | `app.js:331-355` |
| B-6 | `app.js:228-233`; `app.py:343-365` |
| B-7..B-9 | `app.js:334, 367-378, 381`; `app.py:272-322` |
| A-1 | `app.py:80-266`; `generate_pbr_maps.py`; `generate_model_viewer_pbr.py` |
| A-2 | `app.py` (whole file) |
| A-3 | `app.py:370-402` |
| A-4 | `app.js:3-7, 271-273, 301` |
| A-5 | `app.py:42` |
| Q-1..Q-6 | various, listed inline |
| U-1..U-11 | `static/app.js`, `templates/index.html`, `static/index.css` |
| S-1..S-4 | `sofaab-advisor.jsx:11`; `app.py:325-341, 437` |
