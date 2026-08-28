# AGENTS.md

Guidance for AI coding agents and human contributors working in this
repository. Read this before making changes.

## What this project is

**DAC (Diagrams As Code)** is a small Python CLI/library that converts
draw.io `.drawio` files to a directory of YAML files (one per diagram tab plus
a manifest) and back again, losslessly. The point is to keep diagrams in git
as reviewable text. It can also publish all diagram directories to Confluence
as a page hierarchy (`dac export-confluence`), which the
`confluence-export.yml` workflow does on every merge to `master`.
See [README.md](README.md) for user-facing docs.

## Repository layout

```
.
├── src/dac/
│   ├── __init__.py       # public API re-exports + __version__
│   ├── cli.py            # argparse entry point (`dac` console script): d2c, c2d, export-confluence
│   ├── converter.py      # all conversion logic (file-based and in-memory helpers)
│   └── confluence.py     # Confluence REST client + export (pages, attachments, versioning)
├── diagrams/
│   └── example/          # sample diagram directory; what the Confluence workflow publishes
├── tests/
│   ├── conftest.py       # fixtures: temp_dir, single_diagram_xml, multi_diagram_xml
│   ├── test_dac.py       # converter unit + round-trip + edge-case tests
│   ├── test_confluence.py# exporter tests against FakeConfluence; client tests with stubbed urlopen
│   └── test_cli.py       # argument parsing and main()
├── .github/workflows/
│   ├── tests.yml         # pytest with coverage on push/PR to master
│   └── confluence-export.yml  # publish diagrams/ to Confluence on push to master
├── pyproject.toml        # setuptools build, deps, pytest config
├── README.md             # user documentation
├── AGENTS.md             # this file
└── CLAUDE.md             # pointer to this file for Claude Code
```

## How it works

1. `converter.diagram_to_code(base)` reads `<base>.drawio`, parses it with
   `xmltodict.parse`, splits `mxfile/diagram` into a list, and writes:
   - `<base>/_manifest.yaml` — the `@`-attributes of `<mxfile>` plus an
     ordered `diagrams: [{name, file}]` list;
   - `<base>/<sanitised_name>.yaml` — `{'diagram': <diagram dict>}` for each tab.
2. `converter.code_to_diagram(base)` reads the manifest, loads each diagram
   file in manifest order, rebuilds the `mxfile` dict (a single diagram is a
   dict, several are a list — `xmltodict` requires this) and writes
   `<base>.drawio` via `xmltodict.unparse(pretty=True)`.
3. `sanitize_filename` maps tab names to filesystem-safe names
   (`[<>:"/\|?*]` → `_`, space → `_`). Names are never de-duplicated: two tabs
   whose names sanitise identically will overwrite each other.

Data model conventions come from `xmltodict`: attributes are `@key`, text is
`#text`, repeated elements are lists. Do not "clean up" these keys — they are
what makes the round-trip lossless.

`converter.load_mxfile(dir)` / `build_drawio_xml(dir)` are the in-memory,
exception-raising versions of `code_to_diagram`; `find_diagram_dirs(root)`
locates every directory containing a `_manifest.yaml`. Use these from other
code rather than the CLI-oriented functions.

### Confluence export (`confluence.py`)

- `ConfluenceClient` is a stdlib-only (`urllib`) client for Confluence
  **Cloud**: REST v2 for spaces/pages/content-properties, REST v1
  `PUT /rest/api/content/{id}/child/attachment` for uploads (v2 has none).
  Base URL is the site root; `/wiki` is added automatically.
- `export_to_confluence(client, root, ...)` is the orchestration:
  1. `collect_diagrams` builds a `DiagramSource` (title = directory name,
     attachment `<name>.drawio`, XML, tab list, sha256 hash) per diagram dir.
  2. The base page is resolved by id, or by space key + title (created under
     `parent_page_id` if missing).
  3. For each diagram: find the child page by title under the base page →
     create, or compare the hash stored in the `dac-export` content property
     and update only when changed (or `force`). Updates upload the attachment,
     bump the page version with message `DAC export from <sha>`, and rewrite
     the property.
  4. Rewrite the base page body with an index (unless `update_index=False`)
     when anything changed.
- Page bodies are Confluence *storage format* built in `diagram_page_body` /
  `index_page_body`. The diagram is embedded with
  `<ac:structured-macro ac:name="drawio">` whose `diagramName` and
  `attachment` parameters equal the attachment filename. Always `escape()`
  user-derived strings that go into the body.
- `GitContext` / `detect_git_context` supply the commit, browsable repo URL,
  ref and workflow-run URL (from `GITHUB_*` env vars, else `git`) used for
  permalinks (`<repo>/tree/<sha>/<rel_path>`) and version messages.
- Nothing is ever deleted in Confluence. Pages are matched by title, and
  Confluence requires titles to be unique per space — `--title-prefix`
  exists for that.

## Conventions

- **Python ≥ 3.9**, no type-checker enforced; keep functions small and
  documented with docstrings.
- **Dependencies:** only `xmltodict` and `PyYAML` at runtime; the Confluence
  client deliberately uses `urllib` instead of `requests`. Adding a runtime
  dependency needs a good reason; prefer an optional extra in
  `pyproject.toml` (`[project.optional-dependencies]`) with a lazy import.
- **Secrets** (Confluence token etc.) come from CLI flags or `CONFLUENCE_*`
  env vars only. Never log them, never write them to files, never add them
  to test fixtures.
- **Errors in CLI paths** print a message and `sys.exit(1)`; library-style
  helpers should raise exceptions instead so they are usable from other code.
- **Output paths are derived from the base name** (`<base>.drawio` ↔
  `<base>/`). Keep this symmetry; the CLI strips the extension/path with
  `Path(arg).stem`, so commands are expected to run from the diagram's
  directory.
- **YAML output:** `default_flow_style=False, allow_unicode=True`, keys in
  the order `xmltodict` produces. Don't sort keys.
- **Version** is duplicated in `pyproject.toml`, `src/dac/__init__.py` and
  `src/dac/cli.py` (`--version`). Bump all three together.
- Console output uses `✓` prefixes; keep messages short and consistent with
  the existing style.

## Testing

```bash
pip install -e ".[dev]"
pytest                     # all tests, verbose by default (see pyproject addopts)
pytest tests/test_dac.py -k roundtrip
```

- Tests write real files: use the `temp_dir` fixture and `os.chdir(temp_dir)`
  as the existing tests do, because the converter works relative to the CWD.
- Every new conversion behaviour needs a **round-trip test** (`d2c` then
  `c2d`, then assert on the regenerated XML).
- Confluence export tests use `FakeConfluence` in `tests/test_confluence.py`
  (same method surface as `ConfluenceClient`). Extend the fake when you add a
  client method; never hit the network from tests. Request-shape tests for
  the real client stub `dac.confluence.request.urlopen`.
- The workflow is a skeleton: it runs only when `CONFLUENCE_BASE_PAGE_ID` or
  `CONFLUENCE_SPACE_KEY` repository variables exist. It cannot be verified in
  CI without real credentials; test manually with `--dry-run` first.
- Fixtures in `tests/conftest.py` provide a single-tab and a three-tab
  draw.io XML; extend those rather than embedding large XML strings in tests
  unless the case is truly one-off.
- CI runs `pytest tests/ -v --tb=short --cov=src/dac` on Python 3.12
  (`.github/workflows/tests.yml`). Keep it green.

## Making changes

- Small, focused commits with imperative subject lines
  (`Add …`, `Fix …`, `Document …`).
- Update `README.md` when user-facing behaviour or CLI flags change, and this
  file when project structure or conventions change.
- Don't commit generated artefacts (`*.egg-info`, `__pycache__`,
  `.pytest_cache` are git-ignored).
- Don't reformat unrelated code; the codebase has no formatter configured.

## Known limitations / gotchas

- Compressed draw.io files (base64 `diagram` bodies) round-trip but produce
  unreadable YAML. Ask users to disable *Extras → Compressed* in draw.io.
- `xmltodict.unparse` emits `<?xml version="1.0" encoding="utf-8"?>`; the
  original file's declaration casing is not preserved. draw.io doesn't care.
- Tab names that differ only by unsafe characters collide on disk (see above).
- Confluence Data Center/Server is untested: the v2 endpoints used for pages
  and properties are Cloud-only. Supporting DC would mean a v1-only client
  path (`/rest/api/content`) — keep `ConfluenceClient`'s method surface
  stable so the exporter doesn't need to change.
- The draw.io macro parameters (`diagramName`, `attachment`) follow the
  documented Cloud behaviour; if a Confluence instance renders the page but
  not the diagram, check the attachment name matches `diagramName` exactly.
