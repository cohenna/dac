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
- **YAML is easy to edit by hand** (or by tooling) between conversions;
- **diagrams can be published to Confluence** automatically on every merge,
  as a page hierarchy with the `.drawio` embedded and a permalink to the
  commit they came from (see [Confluence export](#confluence-export)).

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

The CLI has two conversion commands and one publishing command. The
conversion commands take a *base name* and derive the input and output from
it: `foo.drawio` on the diagram side, `foo/` on the code side.

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

## Confluence export

`dac export-confluence` publishes every diagram directory under a root
(default `diagrams/`) to Confluence Cloud:

```
Confluence space
└── Diagrams                      ← base page (index of all diagrams + version info)
    ├── architecture              ← one child page per diagram directory
    │     ├── architecture.drawio ← attached, embedded via the draw.io macro
    │     └── Version: commit, permalink, timestamp, workflow run
    └── network
```

- **Pages are created on first export and updated in place afterwards**, so
  links stay stable. Pages are never deleted by DAC.
- **Only changed diagrams are updated.** A content hash is stored as a page
  property; unchanged diagrams are skipped (use `--force` to re-publish).
- **Every page carries a *Version* section** with the commit SHA, a permalink
  to the diagram's source directory at that commit, the branch, the
  generation time and (in CI) the workflow run. The Confluence page version
  message is `DAC export from <sha>`, so the page history doubles as an
  export log.
- The base page body is replaced by an index table (pass `--no-index` to
  keep a hand-written base page).
- Requires the [draw.io for Confluence](https://marketplace.atlassian.com/apps/1210933/draw-io-diagrams-for-confluence)
  app for the embedded diagram to render; without it the page still shows
  the version info and a download link to the attached `.drawio`.

### Running it by hand

```bash
export CONFLUENCE_URL=https://example.atlassian.net
export CONFLUENCE_USER=you@example.com
export CONFLUENCE_API_TOKEN=...            # https://id.atlassian.com/manage-profile/security/api-tokens

# Target an existing page by id...
dac export-confluence --root diagrams --base-page-id 123456789

# ...or find/create the base page by title in a space
dac export-confluence --root diagrams --space DOC --base-title "Architecture diagrams"

dac export-confluence --dry-run       # report only, no writes
dac export-confluence --force         # re-publish even if unchanged
dac export-confluence --out-dir build # also write the generated .drawio files
```

Every option has a `CONFLUENCE_*` environment-variable fallback
(`dac export-confluence --help` lists them). Instead of exporting the
credentials you can keep them in `~/.netrc` (must be `chmod 600`); flags and
environment variables take precedence:

```
machine example.atlassian.net
  login you@example.com
  password <api-token>
```

The repository URL and commit
are auto-detected from GitHub Actions variables or the local git checkout;
override with `--repo-url` / `--commit`.

### Automating with GitHub Actions

`.github/workflows/confluence-export.yml` runs the export on every push to
`master` that touches `diagrams/**` (and on manual dispatch). To enable it,
add in *Settings → Secrets and variables → Actions*:

| Kind | Name | Value |
|------|------|-------|
| Secret | `CONFLUENCE_URL` | `https://<site>.atlassian.net` |
| Secret | `CONFLUENCE_USER` | account email that owns the token |
| Secret | `CONFLUENCE_API_TOKEN` | Atlassian API token |
| Variable | `CONFLUENCE_BASE_PAGE_ID` | id of the base page, **or** … |
| Variable | `CONFLUENCE_SPACE_KEY` + `CONFLUENCE_BASE_TITLE` | space key and base page title (created if missing; `CONFLUENCE_PARENT_PAGE_ID` optional) |

The job is skipped until one of the targeting variables is set, so the
workflow is safe to merge before Confluence is configured. Generated
`.drawio` files are also uploaded as a workflow artifact.

The example diagram set in `diagrams/example/` is what the workflow publishes
for this repository; replace it with your own diagram directories.

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

The CLI is a thin wrapper around `dac.converter` and `dac.confluence`:

```python
from dac import diagram_to_code, code_to_diagram, build_drawio_xml, find_diagram_dirs
from dac import xml_to_yaml_lossless, yaml_to_xml_lossless

diagram_to_code("architecture")      # architecture.drawio -> architecture/
code_to_diagram("architecture")      # architecture/       -> architecture.drawio

xml_text = build_drawio_xml("architecture")          # in-memory, no file written
for d in find_diagram_dirs("diagrams"):              # every dir with a _manifest.yaml
    print(d, build_drawio_xml(d)[:40])

yaml_text = xml_to_yaml_lossless(open("x.drawio").read())
xml_text  = yaml_to_xml_lossless(yaml_text)
```

```python
from dac.confluence import ConfluenceClient, export_to_confluence

client = ConfluenceClient("https://example.atlassian.net", "you@example.com", token)
result = export_to_confluence(client, "diagrams", base_page_id="123456789")
print(result.created, result.updated, result.skipped, result.base_page_url)
```

## Development

```bash
pip install -e ".[dev]"
pytest                       # run the test suite
pytest --cov=src/dac         # with coverage
```

Tests run in CI on every push and pull request to `master`
(`.github/workflows/tests.yml`). The Confluence exporter is tested against an
in-memory fake client, so the suite needs no network or credentials.

Project layout, conventions and guidance for contributors and AI coding agents
are in [AGENTS.md](AGENTS.md).

## License

[MIT](LICENSE)
