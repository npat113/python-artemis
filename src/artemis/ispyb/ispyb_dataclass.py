from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional

from dataclasses_json import config, dataclass_json
from src.artemis.utils import Point2D, Point3D


@dataclass_json
@dataclass
class IspybParams:
    visit_path: str
    undulator_gap: float
    pixels_per_micron_x: float
    pixels_per_micron_y: float

    upper_left: Point2D = field(
        metadata=config(
            encoder=lambda mytuple: mytuple._asdict(),
            decoder=lambda mydict: Point2D(**mydict),
        )
    )

    position: Point3D = field(
        metadata=config(
            encoder=lambda mytuple: mytuple._asdict(),
            decoder=lambda mydict: Point3D(**mydict),
        )
    )

    synchrotron_mode: str
    xtal_snapshots: List[str]
    transmission: float
    flux: float
    wavelength: float
    beam_size_x: float
    beam_size_y: float
    slit_gap_size_x: float
    slit_gap_size_y: float
    focal_spot_size_x: float
    focal_spot_size_y: float
    comment: str
    resolution: float

    sample_id: Optional[int] = None
    sample_barcode: Optional[str] = None


class Orientation(Enum):
    HORIZONTAL = "horizontal"
    VERTICAL = "vertical"
