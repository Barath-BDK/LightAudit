"""LightAudit: explainable lighting-consistency auditing. A flag means "send for human review"."""
from .config import Config, calibrated, load_calib  # noqa: F401

__version__ = "1.0.0"


def backends_available() -> dict:
    """Which optional heavy backends can be used (no model downloads happen here)."""
    from .normals import backends_available as _b
    return _b()
