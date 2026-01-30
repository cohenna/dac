"""Command-line interface for DAC."""

import argparse
from pathlib import Path

from .converter import diagram_to_code, code_to_diagram


def get_base_filename(file_path):
    """Extract base filename without extension."""
    return Path(file_path).stem


def main():
    """Main entry point for the CLI."""
    parser = argparse.ArgumentParser(
        prog="dac",
        description="Diagrams As Code (DAC) - Convert between draw.io XML and YAML formats"
    )
    parser.add_argument(
        '--version',
        action='version',
        version='%(prog)s 0.1.0'
    )
    parser.add_argument(
        'mode',
        choices=['d2c', 'c2d'],
        help="d2c: diagram to code (XML → YAML), c2d: code to diagram (YAML → XML)"
    )
    parser.add_argument(
        'file',
        help="Input file (.drawio) or directory (for YAML). Output will have the same base name."
    )
    
    args = parser.parse_args()
    
    base_filename = get_base_filename(args.file)
    
    if args.mode == 'd2c':
        diagram_to_code(base_filename)
    else:
        code_to_diagram(base_filename)


if __name__ == '__main__':
    main()
