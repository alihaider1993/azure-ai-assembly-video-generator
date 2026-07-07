import json
from pathlib import Path


PART_SHAPES = Path("v2/output/part_shapes.json")
PROXY_GEOMETRY = Path("v2/output/proxy_geometry.json")


def load(path):
    assert path.exists(), f"Missing file: {path}"
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def test_part_shapes_file_exists():
    data = load(PART_SHAPES)
    assert "parts" in data
    assert len(data["parts"]) > 0


def test_each_part_has_required_fields():
    data = load(PART_SHAPES)

    required = [
        "part_uid",
        "source_page",
        "source_diagram_uid",
        "shape_type",
        "aspect_ratio",
        "holes",
        "anchor_points",
        "confidence",
    ]

    for part in data["parts"]:
        for field in required:
            assert field in part, f"Missing {field} in {part.get('part_uid')}"


def test_shape_types_are_valid():
    data = load(PART_SHAPES)

    allowed = {
        "cylinder",
        "long_cylinder",
        "thin_plate",
        "rounded_panel",
        "rectangular_beam",
        "proxy_block",
    }

    for part in data["parts"]:
        assert part["shape_type"] in allowed


def test_proxy_geometry_file_exists():
    data = load(PROXY_GEOMETRY)
    assert "objects" in data
    assert len(data["objects"]) > 0


def test_proxy_objects_have_required_fields():
    data = load(PROXY_GEOMETRY)

    required = [
        "object_uid",
        "part_uid",
        "primitive",
        "dimensions",
        "location",
        "rotation",
        "holes",
        "anchor_points",
    ]

    for obj in data["objects"]:
        for field in required:
            assert field in obj, f"Missing {field} in {obj.get('object_uid')}"


def test_proxy_dimensions_are_valid():
    data = load(PROXY_GEOMETRY)

    for obj in data["objects"]:
        dims = obj["dimensions"]
        assert len(dims) == 3
        assert all(isinstance(x, (int, float)) for x in dims)
        assert all(x > 0 for x in dims)


def test_proxy_locations_are_valid():
    data = load(PROXY_GEOMETRY)

    for obj in data["objects"]:
        loc = obj["location"]
        assert len(loc) == 3
        assert all(isinstance(x, (int, float)) for x in loc)


def test_no_duplicate_proxy_object_ids():
    data = load(PROXY_GEOMETRY)

    ids = [obj["object_uid"] for obj in data["objects"]]
    assert len(ids) == len(set(ids)), "Duplicate object_uid found"