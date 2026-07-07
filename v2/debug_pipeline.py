import json
import subprocess
import sys
from pathlib import Path


BLENDER_EXE = r"C:\Program Files\Blender Foundation\Blender 5.1\blender.exe"


STAGES = [
    {
        "name": "PDF to Images",
        "cmd": [sys.executable, "utils/pdf_to_images.py"],
        "outputs": ["temp/pages"],
    },
    {
        "name": "Page State Agent",
        "cmd": [sys.executable, "v2/agents/page_state_agent.py"],
        "outputs": ["v2/outputs/json/page_states.json"],
    },
    {
        "name": "State Difference Engine",
        "cmd": [sys.executable, "v2/rendering/state_difference_engine.py"],
        "outputs": ["v2/outputs/json/assembly_deltas.json"],
    },
    {
        "name": "Assembly Action Extractor",
        "cmd": [sys.executable, "v2/rendering/assembly_action_extractor.py"],
        "outputs": ["v2/outputs/json/assembly_actions.json"],
    },
    {
        "name": "Universal Graph Engine",
        "cmd": [sys.executable, "v2/rendering/universal_graph_engine.py"],
        "outputs": ["v2/outputs/json/universal_assembly_graph.json"],
    },
    {
        "name": "Motion Planner",
        "cmd": [sys.executable, "v2/rendering/motion_planner.py"],
        "outputs": ["v2/outputs/json/motion_plan.json"],
    },
    {
        "name": "Scene Layout Engine",
        "cmd": [sys.executable, "v2/rendering/scene_layout_engine.py"],
        "outputs": ["v2/outputs/json/scene_layout.json"],
    },
    {
        "name": "Diagram Analyzer",
        "cmd": [sys.executable, "v2/agents/diagram_analyzer_agent.py"],
        "outputs": ["v2/outputs/json/diagram_analysis.json"],
    },
    {
        "name": "Copy Diagram Analysis",
        "cmd": ["powershell", "-Command", "copy v2\\outputs\\json\\diagram_analysis.json v2\\output\\diagram_analysis.json"],
        "outputs": ["v2/output/diagram_analysis.json"],
    },
    {
        "name": "Copy Scene Layout",
        "cmd": ["powershell", "-Command", "copy v2\\outputs\\json\\scene_layout.json v2\\output\\scene_layout.json"],
        "outputs": ["v2/output/scene_layout.json"],
    },
    {
        "name": "Part Shape Extractor",
        "cmd": [sys.executable, "v2/agents/part_shape_extractor_agent.py"],
        "outputs": ["v2/output/part_shapes.json"],
    },
    {
        "name": "Proxy Geometry Builder",
        "cmd": [sys.executable, "v2/builders/proxy_geometry_builder.py"],
        "outputs": ["v2/output/proxy_geometry.json"],
    },
    {
        "name": "Blender Script Builder",
        "cmd": [sys.executable, "v2/rendering/blender_builder_v2.py"],
        "outputs": ["blender/generated/v2_generated_blender_scene.py"],
    },
]


def preview_json(path: Path):
    try:
        data = json.loads(path.read_text(encoding="utf-8"))

        print("\n--- JSON PREVIEW ---")

        if isinstance(data, list):
            print(f"Type: list")
            print(f"Items: {len(data)}")
            if data:
                print("First item keys:", list(data[0].keys()))
                print(json.dumps(data[0], indent=2)[:1200])

        elif isinstance(data, dict):
            print("Type: dict")
            print("Keys:", list(data.keys()))

            for key in ["parts", "objects", "steps", "diagrams", "assemblies", "connections"]:
                if key in data and isinstance(data[key], list):
                    print(f"{key}: {len(data[key])}")

            print(json.dumps(data, indent=2)[:1200])

        print("--- END PREVIEW ---\n")

    except Exception as e:
        print(f"Could not preview JSON: {e}")


def inspect_output(output):
    path = Path(output)

    if path.is_dir():
        files = list(path.glob("*"))
        print(f"Output folder exists: {path}")
        print(f"Files: {len(files)}")
        print("First files:", [str(f) for f in files[:5]])
        return

    if path.exists():
        print(f"Output file exists: {path}")
        print(f"Size: {path.stat().st_size:,} bytes")

        if path.suffix.lower() == ".json":
            preview_json(path)

        return

    print(f"❌ Missing output: {path}")


def run_stage(stage):
    print("\n" + "=" * 90)
    print(f"STAGE: {stage['name']}")
    print("COMMAND:", " ".join(stage["cmd"]))
    print("=" * 90)

    result = subprocess.run(stage["cmd"], shell=False)

    if result.returncode != 0:
        print(f"\n❌ Stage failed: {stage['name']}")
        sys.exit(result.returncode)

    print(f"\n✅ Stage complete: {stage['name']}")

    for output in stage["outputs"]:
        inspect_output(output)

    input("\nPress ENTER to continue to next stage...")


def main():
    print("DEBUG PIPELINE STARTED")
    print("This will pause after every stage.\n")

    for stage in STAGES:
        run_stage(stage)

    print("\n✅ Debug pipeline completed up to Blender script generation.")
    print("Next optional render command:")
    print(f'& "{BLENDER_EXE}" --background --python blender/generated/v2_generated_blender_scene.py')


if __name__ == "__main__":
    main()