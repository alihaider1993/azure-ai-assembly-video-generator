# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

A Python pipeline that turns a furniture assembly manual (PDF) into an animated assembly video. It uses Azure OpenAI vision to read the manual pages, builds an assembly graph and motion plan, generates a Blender script, renders frames headlessly in Blender, and stitches them into an MP4. A Streamlit UI (`app.py`) wraps the whole run.

Note: `C:\Users\syed_\Desktop\CLAUDE.md` (a parent directory) describes an Astro/pnpm website. It does **not** apply to this repo.

## Commands

All scripts assume the **repo root is the working directory**, because most stages use relative paths like `Path("v2/outputs/json/...")`.

```bash
.venv\Scripts\activate                 # Windows venv
pip install -r requirements.txt        # requirements.txt is UTF-16 encoded

streamlit run app.py                   # UI: upload PDF → full pipeline → video + JSON downloads
python utils/pdf_to_images.py          # uploads/manual.pdf → temp/pages/page_*.png
python v2/run_mvp_pipeline.py          # full v2 pipeline (clears old outputs first)
python v2/debug_pipeline.py            # staged run that checks each stage's expected outputs

python <any stage script>              # each stage is standalone; rerun one to iterate on it

pytest v2/tests                                                     # validates generated JSON, so run the pipeline first
pytest v2/tests/test_mvp_visual_pipeline.py::test_shape_types_are_valid  # single test

python v2/stabilize/validate_outputs.py   # sanity-check generated artifacts
python v2/stabilize/clean_outputs.py      # wipe generated outputs
```

Required environment (`.env`, loaded by `services/foundry.py`):
- `AZURE_OPENAI_ENDPOINT` (required). Auth goes through `DefaultAzureCredential` (e.g. `az login`), not an API key.
- `AZURE_OPENAI_DEPLOYMENT` (default `gpt-4o`), `AZURE_OPENAI_API_VERSION`.
- `BLENDER_EXE`: defaults to `C:\Program Files\Blender Foundation\Blender 5.1\blender.exe`. `v2/debug_pipeline.py` hardcodes this path.

## Architecture

**All pipeline code is in `v2/`.** From the root it only uses `config.py`, `services/foundry.py` and `utils/pdf_to_images.py`. The old v1 code (`agents/`, `rendering/`, `pipeline/`, `models/`) has been removed.

**The pipeline is a chain of standalone scripts connected by JSON files on disk.** It is not an in-process call graph. `v2/run_mvp_pipeline.py` holds the ordered `COMMANDS` list and runs each stage as a subprocess. Each stage reads earlier JSON outputs and writes its own. Central paths live in `config.py`, but many stages hardcode their own `Path("v2/outputs/json/...")` constants. If you rename or move an artifact, grep for every reader.

Stage order (outputs go to `v2/outputs/json/` unless noted):
1. `page_state_agent.py` (LLM vision): per-page parts/state → `page_states.json`
2. `state_difference_engine.py` → `assembly_deltas.json`; `assembly_action_extractor.py` → `assembly_actions.json`
3. `universal_graph_engine.py`, **pass 1** → `universal_assembly_graph.json`
4. `object_identity_tracker.py` → `object_identity_map.json`; `canonical_resolver.py` → `resolved_assembly_actions.json`
5. `action_replicator.py`: expands actions across sibling instances (e.g. 4 rails, 2 legs). It overwrites `resolved_assembly_actions.json` in place.
6. `universal_graph_engine.py`, **pass 2**. The graph engine prefers `resolved_assembly_actions.json` and the identity map when they exist, so the second run picks up the replicated actions. That is why it runs twice.
7. `motion_planner.py` → `motion_plan.json`; `geometry_synthesizer.py` → `geometry_spec.json`; `scene_layout_engine.py` → `scene_layout.json`
8. `diagram_analyzer_agent.py` (LLM). Then `diagram_analysis.json` and `scene_layout.json` are copied into `v2/output/`.
9. `part_shape_extractor_agent.py` → `v2/output/part_shapes.json`; `builders/proxy_geometry_builder.py` → `v2/output/proxy_geometry.json`
10. `blender_builder_v3.py` **generates** a Blender Python script (an f-string template) at `blender/generated/v3_generated_blender_scene.py`. Blender runs it with `--background` and renders PNGs into `outputs/frames_v3/`.
11. `render_video.py` (moviepy) → `outputs/assembly_animation_v3.mp4`

Key points:
- There are two output directories, `v2/outputs/json/` (graph/motion stages) and `v2/output/` (shape/proxy-geometry stages). Tests read `v2/output/`.
- `blender_builder_v3.py` runs under normal Python. Code inside its template string runs inside Blender (`bpy`, `mathutils`), so it can't import project modules unless it adds the project root to `sys.path`. Escape literal braces as `{{ }}` in the template.
- `app.py` follows progress by matching substrings in subprocess stdout (`detect_step`). Changing stage log messages can break the progress display.
- `*_v2` files (`blender_builder_v2.py`, `FRAMES_V2_DIR`, `VIDEO_V2_PATH`) are an earlier render path that only `v2/debug_pipeline.py` still uses. The MVP uses the v3 files.
- Generated outputs (`temp/`, `outputs/`, `blender/generated/`, `v2/outputs/json/*.json`, `v2/output/*.json`) are git-ignored.
- The pipeline copy steps shell out to `powershell`, so the full run is Windows-only as written.
