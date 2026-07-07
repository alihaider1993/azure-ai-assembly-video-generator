from typing import List, Optional
from pydantic import BaseModel, Field


class Dimensions(BaseModel):
    length: float = 1.0
    width: float = 1.0
    height: float = 1.0
    unit: str = "generic"


class Position(BaseModel):
    x: float
    y: float
    z: float


class Rotation(BaseModel):
    axis: str = "z"
    degrees: float = 0


class SceneObject(BaseModel):
    object_id: str
    name: str
    shape: str = "cuboid"
    dimensions: Dimensions
    start_position: Position
    end_position: Position
    rotation: Optional[Rotation] = None


class Camera(BaseModel):
    angle: str = "isometric"
    zoom: float = 1.0
    focus_object: Optional[str] = None


class SceneGraph(BaseModel):
    scene_number: int
    title: str
    manual_category: str
    duration_seconds: float = 8
    objects: List[SceneObject]
    camera: Camera
    narration: str
    warnings: List[str] = Field(default_factory=list)