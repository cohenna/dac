"""Diagrams As Code (DAC) - Convert draw.io diagrams to/from YAML."""

__version__ = "0.2.0"

from .converter import (
    diagram_to_code,
    code_to_diagram,
    build_drawio_xml,
    find_diagram_dirs,
    load_mxfile,
    xml_to_yaml_lossless,
    yaml_to_xml_lossless,
    sanitize_filename,
)

__all__ = [
    "diagram_to_code",
    "code_to_diagram",
    "build_drawio_xml",
    "find_diagram_dirs",
    "load_mxfile",
    "xml_to_yaml_lossless",
    "yaml_to_xml_lossless",
    "sanitize_filename",
]
