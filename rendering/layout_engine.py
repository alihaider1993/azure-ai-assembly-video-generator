def get_scene_frames(total_scenes: int = 5, scene_length: int = 60):
    frames = []

    for i in range(total_scenes):
        start = 1 + i * scene_length
        end = start + scene_length - 10
        frames.append((start, end))

    return frames