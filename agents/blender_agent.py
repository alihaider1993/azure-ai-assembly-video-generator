import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

from rendering.blender_builder import BlenderBuilder


class BlenderAgent:
    def generate_blender_script(
        self,
        scene_graph_path="outputs/json/scene_graph_layout.json",
        output_script_path="blender/generated/generated_blender_scene.py"
    ):
        builder = BlenderBuilder()
        builder.build_script(scene_graph_path, output_script_path)


if __name__ == "__main__":
    BlenderAgent().generate_blender_script()