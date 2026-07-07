from rendering.object_roles import infer_role
from rendering.dimension_rules import get_dimensions_for_role
from rendering.position_rules import get_position_for_role


def make_obj(object_id, name, role, shape, dims, start, end, material="wood", rotation=0):
    return {
        "object_id": object_id,
        "name": name,
        "role": role,
        "shape": shape,
        "dimensions": {
            "length": dims[0],
            "width": dims[1],
            "height": dims[2],
            "unit": "generic"
        },
        "start_position": {"x": start[0], "y": start[1], "z": start[2]},
        "end_position": {"x": end[0], "y": end[1], "z": end[2]},
        "rotation": {"axis": "z", "degrees": rotation},
        "material": material
    }


class GenericGeometry:
    def build(self, product):
        objects = []
        role_counts = {}

        components = product.get("components", [])

        for component in components:
            quantity = int(component.get("quantity", 1))
            name = component.get("name", "Component")
            component_role = component.get("role", "")

            role = infer_role(name, component_role)

            for _ in range(quantity):
                index = role_counts.get(role, 0)
                role_counts[role] = index + 1

                dims = get_dimensions_for_role(role)
                start, end = get_position_for_role(role, index)

                objects.append(
                    make_obj(
                        object_id=f"{role}_{index + 1}",
                        name=f"{name} {index + 1}" if quantity > 1 else name,
                        role=role,
                        shape="cylinder" if role == "fastener" else "cuboid",
                        dims=dims,
                        start=start,
                        end=end,
                        material="metal" if role in ["fastener", "connector"] else "wood",
                        rotation=2880 if role == "fastener" else 0
                    )
                )

        return objects