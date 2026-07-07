ROLE_KEYWORDS = {
    "main_surface": [
        "tabletop", "top", "seat", "base", "platform", "surface"
    ],
    "vertical_support": [
        "leg", "post", "upright", "vertical support"
    ],
    "horizontal_support": [
        "rail", "beam", "apron", "crossbar", "support bar"
    ],
    "side_panel": [
        "side panel", "left panel", "right panel", "side"
    ],
    "back_panel": [
        "back panel", "backrest", "rear panel"
    ],
    "shelf_panel": [
        "shelf", "shelves"
    ],
    "door_panel": [
        "door", "drawer front", "front panel"
    ],
    "fastener": [
        "screw", "bolt", "nut", "washer", "dowel", "fastener"
    ],
    "connector": [
        "bracket", "hinge", "connector", "plate", "cam lock"
    ],
    "cushion": [
        "cushion", "pad", "seat pad", "sofa cushion"
    ],
}


def infer_role(name: str, role: str = "") -> str:
    text = f"{name} {role}".lower()

    for semantic_role, keywords in ROLE_KEYWORDS.items():
        if any(keyword in text for keyword in keywords):
            return semantic_role

    return "generic_component"