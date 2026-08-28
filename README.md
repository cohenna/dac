# Diagrams As Code (DAC)

[![Tests](https://github.com/cohenna/dac/actions/workflows/tests.yml/badge.svg)](https://github.com/cohenna/dac/actions/workflows/tests.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.9+](https://img.shields.io/badge/python-3.9%2B-blue.svg)](pyproject.toml)

**DAC** converts [draw.io](https://www.drawio.com/) (`.drawio`) diagrams into
plain YAML files so they can live in a code repository — reviewed, diffed and
merged like any other source — and converts those YAML files back into a
`.drawio` file that opens unchanged in draw.io.

```
architecture.drawio  ──── dac d2c ────▶  architecture/
                                          ├── _manifest.yaml
                                          ├── Overview.yaml
                                          └── Data_Flow.yaml
architecture.drawio  ◀─── dac c2d ────   architecture/
```

## Why

A `.drawio` file is a single XML document. Multi-tab diagrams become one large,
hard-to-review blob, and two people editing different tabs still produce merge
conflicts. DAC splits the file so that:

- **each diagram tab is its own YAML file** — small, readable diffs;
- **the round-trip is lossless** — every element and attribute of the original
  XML is preserved (`XML → YAML → XML`);
- **tab order and file-level metadata are kept** in a small `_manifest.yaml`;
- **YAML is easy to edit by hand** (or by tooling) between conversions.

## Installation

```bash
pip install git+https://github.com/cohenna/dac.git
```

For development (editable install with test dependencies):

```bash
git clone https://github.com/cohenna/dac.git
cd dac
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
```

Requires Python 3.9+. Runtime dependencies are only
[`xmltodict`](https://github.com/martinblech/xmltodict) and
[`PyYAML`](https://pyyaml.org/).

## Usage

The CLI has two modes. Both take a *base name* and derive the input and output
from it: `foo.drawio` on the diagram side, `foo/` on the code side.

### Diagram → Code (`d2c`)

```bash
dac d2c architecture.drawio
```

Reads `architecture.drawio` and creates `architecture/` containing:

| File | Contents |
|------|----------|
| `_manifest.yaml` | The `<mxfile>` attributes (host, version, …) and the ordered list of diagrams with their file names |
| `<Tab_Name>.yaml` | One file per diagram tab, holding the full `<diagram>` element |

Tab names are sanitised for the filesystem: spaces become `_` and the
characters `< > : " / \ | ? *` become `_`. The original, unsanitised name is
kept in the manifest and inside the YAML (`'@name'`).

### Code → Diagram (`c2d`)

```bash
dac c2d architecture
```

Reads `architecture/_manifest.yaml`, loads each listed diagram file in order,
and writes `architecture.drawio`. The output is a normal draw.io file that can
be opened in the desktop app, the web app, or the VS Code extension.

> **Note:** the CLI derives the base name from the argument's file stem, so
> `dac d2c diagrams/foo.drawio` looks for `foo.drawio` in the *current*
> directory. Run the CLI from the directory that contains the diagram (or the
> YAML directory).

### Typical workflow

```bash
# 1. Draw in draw.io, save as architecture.drawio
# 2. Convert to YAML and commit the YAML directory
dac d2c architecture.drawio
git add architecture/ && git commit -m "Add architecture diagrams"

# 3. Later: regenerate the .drawio to edit it visually again
dac c2d architecture
#    ...edit in draw.io, then re-run d2c and commit the diff
```

Whether you also commit the `.drawio` file is up to you; the YAML directory is
the source of truth and the `.drawio` can always be regenerated.

## File format

DAC uses [`xmltodict`](https://github.com/martinblech/xmltodict) conventions:
XML attributes become keys prefixed with `@`, text content becomes `#text`,
and repeated child elements become lists.

`_manifest.yaml`:

```yaml
mxfile:
  '@host': Electron
  '@version': 28.2.5
  '@pages': '3'
diagrams:
- name: Overview
  file: Overview.yaml
- name: Data Flow
  file: Data_Flow.yaml
```

`Overview.yaml` (abridged):

```yaml
diagram:
  '@id': abc123
  '@name': Overview
  mxGraphModel:
    '@dx': '100'
    '@dy': '100'
    root:
      mxCell:
      - '@id': '0'
      - '@id': '1'
        '@parent': '0'
      - '@id': '2'
        '@value': Hello
        '@style': rounded=1;
        '@vertex': '1'
        '@parent': '1'
        mxGeometry:
          '@x': '100'
          '@y': '100'
          '@width': '80'
          '@height': '40'
          '@as': geometry
```

draw.io must be configured to save **uncompressed** XML (the default in recent
versions: *Extras → Compressed* unchecked). Compressed diagrams contain a
base64 blob instead of an `mxGraphModel` tree; they still round-trip, but the
YAML is not human-readable.

## Python API

The CLI is a thin wrapper around `dac.converter`:

```python
from dac import diagram_to_code, code_to_diagram
from dac import xml_to_yaml_lossless, yaml_to_xml_lossless

diagram_to_code("architecture")      # architecture.drawio -> architecture/
code_to_diagram("architecture")      # architecture/       -> architecture.drawio

yaml_text = xml_to_yaml_lossless(open("x.drawio").read())
xml_text  = yaml_to_xml_lossless(yaml_text)
```

## Development

```bash
pip install -e ".[dev]"
pytest                       # run the test suite
pytest --cov=src/dac         # with coverage
```

Tests run in CI on every push and pull request to `master`
(`.github/workflows/tests.yml`).

Project layout, conventions and guidance for contributors and AI coding agents
are in [AGENTS.md](AGENTS.md).

## License

[MIT](LICENSE)
