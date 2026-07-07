import json
from pathlib import Path

from rendering.graph_animation_engine import GraphAnimationEngine


class SceneBuilder:

    def build(
        self,
        product_model_path="outputs/json/product_model.json",
        scene_graph_path="outputs/json/scene_graph_layout.json",
        assembly_graph_path="outputs/json/assembly_graph.json",
        output_path="outputs/json/render_scene.json"
    ):

        product = json.loads(Path(product_model_path).read_text(encoding="utf-8"))
        scene = json.loads(Path(scene_graph_path).read_text(encoding="utf-8"))
        graph = json.loads(Path(assembly_graph_path).read_text(encoding="utf-8"))

        timeline = GraphAnimationEngine().build_animation_sequence(
            assembly_graph_path
        )

        render_scene = {

            "metadata": {

                "product_name": product.get("product_name", "DIY Product"),

                "product_type": product.get("product_type", "generic"),

                "duration_seconds": scene.get("duration_seconds", 10)

            },

            "objects": scene["objects"],

            "assembly_graph": graph,

            "timeline": timeline,

            "camera": scene["camera"],

            "materials": {

                "wood": "#b07d42",

                "metal": "#d0d0d0",

                "plastic": "#202020",

                "fabric": "#3b5cff"

            },

            "lighting": {

                "type": "three_point",

                "key_energy": 1200,

                "fill_energy": 400,

                "rim_energy": 250

            }

        }

        Path(output_path).parent.mkdir(parents=True, exist_ok=True)

        Path(output_path).write_text(
            json.dumps(render_scene, indent=2),
            encoding="utf-8"
        )

        print(f"Render Scene saved to {output_path}")

        print(f"Objects : {len(render_scene['objects'])}")

        print(f"Timeline: {len(render_scene['timeline'])}")


if __name__ == "__main__":

    SceneBuilder().build()