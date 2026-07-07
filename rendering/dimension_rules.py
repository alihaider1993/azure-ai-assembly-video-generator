ROLE_DIMENSIONS = {
    "main_surface": (5.0, 3.0, 0.22),
    "vertical_support": (0.25, 0.25, 2.4),
    "horizontal_support": (4.5, 0.18, 0.25),
    "side_panel": (0.25, 3.0, 2.4),
    "back_panel": (4.5, 0.25, 2.2),
    "shelf_panel": (4.2, 2.5, 0.18),
    "door_panel": (1.8, 0.15, 2.2),
    "fastener": (0.08, 0.08, 0.45),
    "connector": (0.5, 0.15, 0.5),
    "cushion": (1.5, 2.2, 0.35),
    "generic_component": (2.0, 0.3, 1.2),
}


def get_dimensions_for_role(role: str):
    return ROLE_DIMENSIONS.get(role, ROLE_DIMENSIONS["generic_component"])