# Workflow Diagrams

<!-- AUTO-GENERATED START -->

Pipelines and dev flows. Supplementary to `@.claude/rules/workflows.md`.

## Dev loop

```mermaid
flowchart LR
  edit[Edit Python / JS / HTML] --> reload{Which surface?}
  reload -->|Flask app.py| flaskdebug[Flask debug reloads\nauto-restart on save]
  reload -->|app.js / index.html| hardrefresh[Browser hard refresh\nCtrl+Shift+R]
  reload -->|index.css| softrefresh[Soft refresh\nCtrl+R]
  flaskdebug --> verify
  hardrefresh --> verify
  softrefresh --> verify
  verify[Open http://127.0.0.1:8081] --> ok{Working?}
  ok -->|yes| done
  ok -->|no| inspect[Check browser console\n+ Flask stdout]
  inspect --> edit
```

## User journey through the dashboard

```mermaid
stateDiagram-v2
  [*] --> Empty
  Empty --> Selected: click asset in sidebar
  Empty --> Uploaded: click IMPORT ASSET
  Uploaded --> Selected: asset auto-listed after sync

  Selected --> Step1_Import: select Fabrics tab
  Step1_Import --> Step2_2D: PROCEED TO 2D ADJUSTMENTS
  Step2_2D --> Generating: GENERATE MAPS
  Generating --> Step3_3D: success (has_maps=true)
  Generating --> Step2_2D: error
  Step3_3D --> Step2_2D: tweak sliders → regen
  Step3_3D --> Exported: EXPORT FINAL MAPS
  Exported --> [*]: zip downloads
```

## PBR generation decision tree

```mermaid
flowchart TB
  start[Click GENERATE MAPS] --> save_db[Write all sliders to SQLite\n(BEFORE running generation)]
  save_db --> load[cv2.imread raw upload]
  load --> ok{Loaded ok?}
  ok -->|no| err1[Return 500\nrow already updated]
  ok -->|yes| color[adjust_color]
  color --> crop[Center crop to 60% × 1-edge_crop]
  crop --> resize[Resize to N×N]
  resize --> delight[delight_image\nremoves global+local gradients]
  delight --> tile{mirror_tiling true?}
  tile -->|yes| mirror[2×2 mirrored grid + downscale]
  tile -->|no| sigmoid[Sigmoid sequence at 50% offset]
  mirror --> derive
  sigmoid --> derive
  derive[Derive normal/roughness/AO from grayscale]
  derive --> orm[Pack ORM and Metallic-Roughness textures]
  orm --> write[Write 6 jpgs under generated/<base>/]
  write --> ret[Return success]
```

## Map dependency graph

Used by the Three.js `LuxuryEngine` (`static/app.js:331`):

```mermaid
flowchart LR
  basecolor[diffuse.jpg] --> map[material.map]
  normal[normal.jpg] --> nmap[material.normalMap]
  orm[orm.jpg] --> rmap[material.roughnessMap]
  orm --> mmap[material.metalnessMap]
  uvslider[UV slider 1..20] -->|repeat.set v,v| map
  uvslider --> nmap
  uvslider --> rmap
  tint[Color tint hex] --> color[material.color]
  sheen[Sheen 0..1] --> matsheen[material.sheen + sheenRoughness=0.5]
```

## Branching / commits

```mermaid
gitGraph
  commit id: "675ce23 Initial commit"
```

Currently single-branch (`main`) with one commit. No branching strategy formalised yet. When opening PRs, target `main`.

<!-- AUTO-GENERATED END -->
