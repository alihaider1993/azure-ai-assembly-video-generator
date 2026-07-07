def get_animation_code(obj, start_frame: int, end_frame: int):
    end = obj["end_position"]

    name = obj.get("name", "").lower()
    role = obj.get("role", "").lower()

    is_fastener = (
        "screw" in name
        or "bolt" in name
        or "fastener" in name
        or "nut" in name
        or role == "fastener"
    )

    if is_fastener:
        return f"""
obj.keyframe_insert(data_path="location", frame={start_frame})
obj.location = ({end["x"]}, {end["y"]}, {end["z"]})
obj.keyframe_insert(data_path="location", frame={end_frame})

obj.rotation_euler[2] = 0
obj.keyframe_insert(data_path="rotation_euler", frame={start_frame})
obj.rotation_euler[2] = math.radians(2880)
obj.keyframe_insert(data_path="rotation_euler", frame={end_frame})
"""

    rotation = obj.get("rotation") or {"degrees": 0}

    return f"""
obj.keyframe_insert(data_path="location", frame={start_frame})
obj.location = ({end["x"]}, {end["y"]}, {end["z"]})
obj.keyframe_insert(data_path="location", frame={end_frame})

obj.rotation_euler[2] = 0
obj.keyframe_insert(data_path="rotation_euler", frame={start_frame})
obj.rotation_euler[2] = math.radians({rotation.get("degrees", 0)})
obj.keyframe_insert(data_path="rotation_euler", frame={end_frame})
"""


def get_step_frames(obj):
    scene_number = int(obj.get("scene_number", 1))
    start = 1 + (scene_number - 1) * 60
    end = start + 45
    return start, end