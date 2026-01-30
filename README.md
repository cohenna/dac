# Diagrams As Code (DAC)

Convert draw.io diagrams to YAML files for version control and text-based editing, then convert back to draw.io format.

## Features

- **Split multi-page diagrams**: Each diagram tab becomes a separate YAML file
- **Lossless round-trip**: XML → YAML → XML preserves all data
- **Git-friendly**: YAML files are easy to diff and merge
- **Manifest tracking**: Preserves diagram order and mxfile attributes

## Installation

```bash
pip install git+https://github.com/cohenna/dac.git
```

### For development

```bash
git clone https://github.com/cohenna/dac.git
cd dac
pip install -e ".[dev]"
```

## Usage

### Convert draw.io to YAML (Diagram to Code)

```bash
dac d2c mydiagram.drawio
```

This creates a `mydiagram/` directory containing:
- `_manifest.yaml` - Metadata and diagram order
- `<DiagramName>.yaml` - One file per diagram tab

### Convert YAML back to draw.io (Code to Diagram)

```bash
dac c2d mydiagram
```

This reads the `mydiagram/` directory and creates `mydiagram.drawio`.

## Example

```bash
# Convert to YAML files
python dac.py d2c architecture.drawio

# Edit the YAML files...
# Then convert back
python dac.py c2d architecture
```

## Directory Structure

```
mydiagram/
├── _manifest.yaml          # mxfile attributes + diagram order
├── Overview.yaml           # First tab
├── Component_Details.yaml  # Second tab
└── Data_Flow.yaml          # Third tab
```

## Running Tests

```bash
pytest tests/ -v
```

## License

MIT
