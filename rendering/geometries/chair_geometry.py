from rendering.geometries.generic_geometry import make_obj


class ChairGeometry:
    def build(self, product):
        objects = []

        # Seat frame / seat base
        objects.append(
            make_obj(
                "seat_frame",
                "Seat Frame",
                "main_surface",
                "cuboid",
                (3.2, 3.0, 0.22),
                (0, 0, 2.2),
                (0, 0, 2.2),
                "wood"
            )
        )

        # Backrest panel
        objects.append(
            make_obj(
                "backrest",
                "Backrest",
                "back_panel",
                "cuboid",
                (3.0, 0.22, 2.6),
                (0, 5.0, 3.3),
                (0, 1.35, 3.3),
                "wood"
            )
        )

        # Four chair legs
        leg_positions = [
            ("front_left_leg", "Front Left Leg", (-1.3, -1.2, -1.4), (-1.3, -1.2, 1.1)),
            ("front_right_leg", "Front Right Leg", (1.3, -1.2, -1.4), (1.3, -1.2, 1.1)),
            ("rear_left_leg", "Rear Left Leg", (-1.3, 1.2, -1.4), (-1.3, 1.2, 1.1)),
            ("rear_right_leg", "Rear Right Leg", (1.3, 1.2, -1.4), (1.3, 1.2, 1.1)),
        ]

        for object_id, name, start, end in leg_positions:
            objects.append(
                make_obj(
                    object_id,
                    name,
                    "vertical_support",
                    "cuboid",
                    (0.22, 0.22, 2.4),
                    start,
                    end,
                    "wood"
                )
            )

        # Side/front/back rails
        rails = [
            ("front_rail", "Front Rail", (0, -4, 1.9), (0, -1.3, 1.9), (3.0, 0.16, 0.18)),
            ("back_rail", "Back Rail", (0, 4, 1.9), (0, 1.3, 1.9), (3.0, 0.16, 0.18)),
            ("left_side_rail", "Left Side Rail", (-4, 0, 1.9), (-1.35, 0, 1.9), (0.16, 2.6, 0.18)),
            ("right_side_rail", "Right Side Rail", (4, 0, 1.9), (1.35, 0, 1.9), (0.16, 2.6, 0.18)),
        ]

        for object_id, name, start, end, dims in rails:
            objects.append(
                make_obj(
                    object_id,
                    name,
                    "horizontal_support",
                    "cuboid",
                    dims,
                    start,
                    end,
                    "wood"
                )
            )

        # Diagonal back braces
        braces = [
            ("brace_left", "Left Diagonal Back Brace", (-2.5, 3.8, 2.2), (-0.75, 1.28, 2.8)),
            ("brace_right", "Right Diagonal Back Brace", (2.5, 3.8, 2.2), (0.75, 1.28, 2.8)),
        ]

        for object_id, name, start, end in braces:
            objects.append(
                make_obj(
                    object_id,
                    name,
                    "horizontal_support",
                    "cuboid",
                    (0.15, 0.15, 2.0),
                    start,
                    end,
                    "wood",
                    rotation=25
                )
            )

        # Seat panel installed at the end
        objects.append(
            make_obj(
                "seat_panel",
                "Seat Panel",
                "main_surface",
                "cuboid",
                (3.0, 2.8, 0.16),
                (0, -5, 2.45),
                (0, 0, 2.45),
                "wood"
            )
        )

        # Representative screws
        screw_positions = [
            (-1.2, -1.1), (1.2, -1.1),
            (-1.2, 1.1), (1.2, 1.1),
            (-0.8, 0), (0.8, 0)
        ]

        for i, (x, y) in enumerate(screw_positions, start=1):
            objects.append(
                make_obj(
                    f"screw_{i}",
                    f"Screw {i}",
                    "fastener",
                    "cylinder",
                    (0.08, 0.08, 0.45),
                    (x, y, 4.2),
                    (x, y, 2.35),
                    "metal",
                    rotation=2880
                )
            )

        return objects