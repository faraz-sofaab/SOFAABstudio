---
description: Python conventions for the OpenCV PBR pipeline and Flask dashboard
paths:
  - "fabric textures/**/*.py"
---

# Python conventions

## Dependencies

No `requirements.txt` / `pyproject.toml` exists yet. Imports in use:

- `flask`, `werkzeug` (dashboard server + `secure_filename`)
- `opencv-python` → `cv2` (all image math)
- `numpy`
- `sqlite3`, `zipfile`, `io`, `glob`, `os`, `mimetypes` (stdlib)

When adding a dependency, write a `requirements.txt` (or migrate to Poetry — global preference per `~/.claude/CLAUDE.md`).

## OpenCV gotchas

- **Channel order is BGR**, not RGB. When packing maps with `np.stack([a, b, c], axis=-1)` the first element is the Blue channel.
  - ORM packing for glTF: `np.stack([metallic, roughness, ao])` → file decodes as `R=AO, G=Roughness, B=Metallic`.
  - Normal maps: `np.stack([normal_z, normal_y, normal_x])` → file decodes as `R=X, G=Y, B=Z` (standard tangent-space normal).
- **Y axis convention.** Three.js / OpenGL want `+Y up` in normal maps. The dashboard inverts gradient Y: `normal_y = -grad_y * strength` (`app.py:217`). The two CLI scripts do NOT invert. Keep the dashboard's convention as canonical.
- **Border handling.** Gaussian blurs in `delight_image()` use `BORDER_REPLICATE` to avoid edge halos when used on flat scans. Don't drop this when refactoring.
- **Division by zero.** When dividing by a blurred map for AO, always `arr[arr == 0] = 1` first (see `app.py:238`).

## Flask app structure

- `BASE_DIR = os.path.dirname(os.path.abspath(__file__))` is used everywhere. Don't `cd` before running — paths are absolute.
- `MAX_CONTENT_LENGTH = 100 MB` to allow high-res scans.
- `init_db()` runs at import time, not via CLI. Importing `app.py` creates `database.db` if missing.
- `get_db()` returns a fresh connection per call with `row_factory = sqlite3.Row`. No connection pool — Flask's threading model + SQLite serializes writes.

## Filenames and IDs

- Asset `id` = filename without extension (after `secure_filename`).
- `id` is used both as DB primary key and as the output directory name under `generated/`. Anything that breaks `secure_filename` (Unicode, slashes) is rejected upstream by Werkzeug.

## Known issues to flag in review

- `app.py:389` references `json.dumps` but `json` is never imported. The model `leg_configs` save path is dead code right now.
- `app.py` runs `app.run(debug=True, port=8081)` unconditionally. Wrap with `if __name__ == "__main__":` env-gating before any deploy.
