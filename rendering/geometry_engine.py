from rendering.geometries.generic_geometry import GenericGeometry
from rendering.geometries.chair_geometry import ChairGeometry


class GeometryEngine:
    def build_objects(self, product):
        product_type = product.get("product_type", "").lower()
        product_name = product.get("product_name", "").lower()

        if "chair" in product_type or "chair" in product_name:
            return ChairGeometry().build(product)

        return GenericGeometry().build(product)