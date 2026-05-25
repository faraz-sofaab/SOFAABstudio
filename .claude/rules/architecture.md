---
description: Module map and data flow across the digitisation pipeline
---

# Architecture

Two independent surfaces share this repo. They do not import each other.

## 1. Fabric digitisation pipeline (`fabric textures/`)

Single entry point: the Flask dashboard at `dashboard/app.py`.

| Entry point | Purpose | Output |
|---|---|---|
| `dashboard/app.py` | Flask web app with SQLite, per-texture settings, UI-driven generation | `generated/<base>/<base>_{diffuse,normal,roughness,occlusion,orm,metallic_roughness}.jpg` |

`generate_pbr()` includes `delight_image()` (high-pass to flatten lighting gradients) and tunable parameters (brightness, contrast, hue, saturation, edge crop, mirror tiling, normal strength, resolution). Earlier history had two standalone CLI scripts (`generate_pbr_maps.py`, `generate_model_viewer_pbr.py`) — these were removed as redundant; the dashboard's `generate_pbr` is the source of truth.

## 2. AI Advisor (`sofaab-advisor.jsx`)

Single-file React component. Stateless, calls Gemini `generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent` directly from the browser. No backend. Conversation history kept in a `useRef`.

System prompt is hardcoded in the file at line 3 — covers SOFAAB foam construction (32D top + 38D bottom dual-layer).

## Data flow — dashboard

```
User uploads JPG/PNG/TIFF
  → POST /api/upload
  → werkzeug.secure_filename → uploads/<filename>
  → INSERT OR REPLACE into textures table (id = filename without ext)

User tunes sliders in step 2, clicks "Generate Maps"
  → POST /api/generate/<id> with settings JSON
  → UPDATE textures row (writes settings BEFORE generation)
  → generate_pbr(raw_path, base_name, options)
    → adjust_color → center crop → resize → delight_image → make_seamless
    → derives normal/roughness/ao/orm from grayscale
    → writes 6 files to generated/<base_name>/

User exports
  → GET /api/export/<id> → zip of 6 maps streamed back
```

## SQLite schema

`textures(id PK, name, original_file, brightness, contrast, hue, saturation, edge_crop, mirror_tiling, normal_strength, resolution, has_maps, created_at)`

`models(id PK, name, file_path, leg_configs JSON-as-text, created_at)`

Schema is initialised on import via `init_db()` at module load (`app.py:42`).

## Frontend

`templates/index.html` is a single SPA shell with three tabs (Fabrics / Models / Legs) and three workflow steps per asset type. `static/app.js` renders each step's HTML imperatively into `#fabric-step-{1,2,3}` containers — no framework.

The 3D preview uses a single `LuxuryEngine` class (`app.js:331`) built on Three.js (`MeshPhysicalMaterial`, ESM importmap from unpkg). Maps are loaded with a cache-busting `?t=<ts>` query.
