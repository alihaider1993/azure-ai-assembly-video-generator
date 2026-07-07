def get_material_name(object_name: str, material: str = "") -> str:
    name = object_name.lower()
    material = material.lower()

    if any(x in name for x in ["screw", "bolt", "nut", "washer", "fastener"]):
        return "metal"

    if any(x in name for x in ["leg", "vertical support"]):
        return "dark_wood"

    if any(x in name for x in ["rail", "support"]):
        return "medium_wood"

    if any(x in name for x in ["tabletop", "surface", "panel", "seat", "shelf"]):
        return "light_wood"

    if "plastic" in material:
        return "plastic"

    if "fabric" in material or "cushion" in name:
        return "fabric"

    return "light_wood"