from __future__ import annotations

import numpy as np
import pytest


def rgba(height: int, width: int, color=(255, 255, 255), alpha: int = 255) -> np.ndarray:
    """A solid-colour RGBA image."""
    img = np.zeros((height, width, 4), dtype=np.uint8)
    img[..., :3] = color
    img[..., 3] = alpha
    return img


@pytest.fixture
def square_mask() -> np.ndarray:
    """A 30 x 30 px square in a 50 x 50 px image."""
    mask = np.zeros((50, 50), dtype=bool)
    mask[10:40, 10:40] = True
    return mask


@pytest.fixture
def donut_mask() -> np.ndarray:
    """A 40 x 40 px square with a 20 x 20 px hole."""
    mask = np.zeros((60, 60), dtype=bool)
    mask[10:50, 10:50] = True
    mask[20:40, 20:40] = False
    return mask


TEMPLATE_SETTINGS = {
    "version": "02.04.00.70",
    "printer_model": "Bambu Lab A1 mini",
    "printer_settings_id": "Bambu Lab A1 mini 0.4 nozzle",
    "printable_area": ["0x0", "180x0", "180x180", "0x180"],
    "nozzle_diameter": ["0.4"],
    "filament_colour": ["#FFFFFF", "#000000", "#FF0000", "#00FF00"],
    "filament_type": ["PLA", "PLA", "PETG", "PLA"],
    "filament_settings_id": ["Bambu PLA Basic @BBL A1M"] * 4,
    "different_settings_to_system": ["", "", "", "", "", ""],
}


def write_bambu_template(path, settings=None, application="BambuStudio-02.04.00.70"):
    """A minimal stand-in for a project 3MF saved by Bambu Studio."""
    import json
    import zipfile

    model = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<model unit="millimeter" xmlns="http://schemas.microsoft.com/3dmanufacturing/core/2015/02">\n'
        f' <metadata name="Application">{application}</metadata>\n'
        " <resources/>\n <build/>\n</model>\n"
    )
    with zipfile.ZipFile(path, "w") as zf:
        zf.writestr("3D/3dmodel.model", model)
        zf.writestr("Metadata/project_settings.config", json.dumps(settings or TEMPLATE_SETTINGS))
    return path


@pytest.fixture
def bambu_template(tmp_path):
    return write_bambu_template(tmp_path / "template.3mf")
