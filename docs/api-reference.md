# API Reference

<!-- AUTO-GENERATED START -->

Flask routes exposed by `fabric textures/dashboard/app.py`. Base URL: `http://127.0.0.1:8081`.

## Endpoints

| Method | Path | Purpose |
|---|---|---|
| GET | `/` | Render `templates/index.html` SPA shell |
| GET | `/api/textures` | List all fabric textures (also scans `uploads/` for new files and syncs them into SQLite) |
| POST | `/api/upload` | Upload a fabric scan (multipart `file`) |
| POST | `/api/generate/<base_name>` | Update settings + regenerate PBR maps |
| GET | `/api/export/<base_name>` | Stream a ZIP of the generated maps |
| GET, POST | `/api/models` | List models, or upload a `.glb` (multipart), or save `leg_configs` (JSON) |
| GET | `/uploads/<filename>` | Serve a raw scan |
| GET | `/generated/<path:filename>` | Serve a generated map |

## `GET /api/textures` — response shape

```json
[
  {
    "id": "linen_beige_01",
    "name": "linen_beige_01",
    "raw_url": "/uploads/linen_beige_01.jpg",
    "has_maps": true,
    "settings": {
      "brightness": 0,
      "contrast": 1.0,
      "hue": 0,
      "saturation": 1.0,
      "edge_crop": 0.1,
      "mirror_tiling": false,
      "normal_strength": 2.0,
      "resolution": 2048
    },
    "maps": {
      "basecolor": "/generated/linen_beige_01/linen_beige_01_diffuse.jpg",
      "normal":    "/generated/linen_beige_01/linen_beige_01_normal.jpg",
      "orm":       "/generated/linen_beige_01/linen_beige_01_orm.jpg"
    }
  }
]
```

Note: when `has_maps` is `false`, all `maps.*` values are `null`. The frontend gates step 3 on `has_maps`.

## `POST /api/generate/<base_name>` — request body

All fields optional; defaults applied server-side.

| Field | Type | Default | Range |
|---|---|---|---|
| `brightness` | number | 0 | -100..100 |
| `contrast` | number | 1.0 | 0.1..3.0 |
| `hue` | number | 0 | -180..180 (OpenCV maps to 0..179) |
| `saturation` | number | 1.0 | 0..2 |
| `edge_crop` | number | 0.1 | 0..1 (fraction) or 0..100 (percent — JS sends `/100`) |
| `mirror_tiling` | bool / "true"/"false" | false | — |
| `normal_strength` | number | 2.0 | typical 0.5..5 |
| `resolution` | int | 2048 | 512 / 1024 / 2048 / 4096 |
| `tint_color` | string | `#ffffff` | hex; currently parsed but unused server-side |

Returns `{ "success": true }` or `{ "error": "..." }` with appropriate status.

## Map file naming

All generated under `fabric textures/dashboard/generated/<base_name>/`:

- `<base>_diffuse.jpg` — albedo / base color
- `<base>_normal.jpg` — tangent-space normal (Y inverted for OpenGL)
- `<base>_roughness.jpg` — single-channel grayscale stored as JPEG
- `<base>_occlusion.jpg` — AO grayscale
- `<base>_metallic_roughness.jpg` — `B=metallic, G=roughness, R=0` (glTF metallic-roughness texture)
- `<base>_orm.jpg` — `B=metallic, G=roughness, R=AO` (`<model-viewer>` ORM)

## Env config

No env vars wired up yet. Hardcoded:

| Constant | Source | Value |
|---|---|---|
| Port | `app.py:437` | 8081 |
| Max upload | `app.py:48` | 100 MB |
| DB path | `app.py:20` | `<dashboard>/database.db` |
| Debug | `app.py:437` | `True` |

## Auth flow

There is no auth. Treat the dashboard as localhost-only until that changes.

<!-- AUTO-GENERATED END -->
