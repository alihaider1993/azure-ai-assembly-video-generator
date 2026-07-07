import json
from pathlib import Path


class GraphAnimationEngine:
    def build_animation_sequence(
        self,
        graph_path="outputs/json/assembly_graph.json"
    ):
        graph = json.loads(Path(graph_path).read_text(encoding="utf-8"))

        timeline = []
        frame = 1

        for edge in graph["edges"]:
            relation = edge["relationship"]
            motion = edge["motion"]

            if relation == "connects_to":
                duration = 50
            elif relation == "supports":
                duration = 60
            elif relation == "secures_connection":
                duration = 45
            else:
                duration = 50

            timeline.append({
                "object_id": edge["from"],
                "target_id": edge["to"],
                "relationship": relation,
                "motion": motion,
                "start_frame": frame,
                "end_frame": frame + duration
            })

            frame += duration + 8

        return timeline


if __name__ == "__main__":
    engine = GraphAnimationEngine()
    timeline = engine.build_animation_sequence()
    print(json.dumps(timeline, indent=2))