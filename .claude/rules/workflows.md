---
description: Common dev tasks for the dashboard and PBR pipeline
---

# Workflows

PowerShell commands — this is a Windows dev environment.

## Run the dashboard

```powershell
cd "fabric textures/dashboard"
python app.py
# open http://127.0.0.1:8081
```

Folders `uploads/`, `generated/`, and `database.db` are created on first run inside `fabric textures/dashboard/`.

## Reset local state

To wipe the library and start clean:

```powershell
cd "fabric textures/dashboard"
Remove-Item database.db -ErrorAction SilentlyContinue
Remove-Item -Recurse uploads -ErrorAction SilentlyContinue
Remove-Item -Recurse generated -ErrorAction SilentlyContinue
```

## Batch-generate maps from the CLI (no dashboard)

```powershell
# Seamless ORM-packed for <model-viewer>
python "fabric textures/generate_model_viewer_pbr.py" --input_dir <scans-folder> --output_dir <out> --resolution 2048

# Plain PBR set (no tiling)
python "fabric textures/generate_pbr_maps.py" --input_dir <scans-folder> --output_dir <out>
```

## Inspect generated maps for a single texture (dashboard mode)

Files land at `fabric textures/dashboard/generated/<base_name>/<base_name>_*.jpg`. Re-running `/api/generate/<id>` with new settings overwrites them in place.

## Tuning intuition

| Slider | Range | Effect |
|---|---|---|
| Brightness | -100..100 | Linear offset on BGR before processing |
| Contrast | 0.1..3.0 | Linear gain (alpha) on BGR |
| Saturation | 0..2 | HSV multiplier (1.0 = no change) |
| Edge crop | 0..100 (%) | Extra zoom on top of the safe 60% center crop |
| Mirror tiling | bool | Replaces sigmoid blend with 2×2 mirrored grid resized back |
| Normal strength | 0.1..5+ | Sobel gradient scale; higher = deeper apparent weave |
| Resolution | 512/1024/2048/4096 | Output square px (web max ~4096) |

The center crop already discards 40% of the scan edges (`safe_dim = min(h,w) * 0.6`) to avoid flatbed white borders.

## Three.js preview behaviour

`static/app.js:LuxuryEngine.updateTextures` binds the same ORM jpg to `roughnessMap` and `metalnessMap`. Sheen (`updateSheen`) controls fabric-style soft reflectance via `MeshPhysicalMaterial.sheen`.

UV repeat defaults to `8×8`; change with the "Texture Tiling (UV)" slider. Cache-bust via `?t=<Date.now()>` is appended on load so re-generated maps refresh.
