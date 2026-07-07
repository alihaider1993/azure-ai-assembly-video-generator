def get_camera_code():
    return """
xs = [obj.location.x for obj in objects]
ys = [obj.location.y for obj in objects]
zs = [obj.location.z for obj in objects]

center = (
    (min(xs) + max(xs)) / 2,
    (min(ys) + max(ys)) / 2,
    (min(zs) + max(zs)) / 2
)

size_x = max(xs) - min(xs)
size_y = max(ys) - min(ys)
size_z = max(zs) - min(zs)
max_size = max(size_x, size_y, size_z, 4)

camera_distance = max_size * 2.6

bpy.ops.object.camera_add(
    location=(center[0] + camera_distance, center[1] - camera_distance, center[2] + camera_distance * 0.8)
)

camera = bpy.context.object
look_at(camera, center)
camera.data.lens = 28
bpy.context.scene.camera = camera
"""