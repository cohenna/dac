"""Diagrams As Code (DAC) - Convert draw.io diagrams to/from YAML."""

__version__ = "0.1.0"

from .converter import (
    diagram_to_code,
    code_to_diagram,
    xml_to_yaml_lossless,
    yaml_to_xml_lossless,
    sanitize_filename,
)

__all__ = [
    "diagram_to_code",
    "code_to_diagram",
    "xml_to_yaml_lossless",
    "yaml_to_xml_lossless",
    "sanitize_filename",
]
