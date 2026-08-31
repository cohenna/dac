"""Command-line interface for DAC."""

import argparse
import os
import sys
from pathlib import Path

from . import __version__
from .converter import diagram_to_code, code_to_diagram


def get_base_filename(file_path):
    """Extract base filename without extension."""
    return Path(file_path).stem


def _env_default(name):
    """Return {'default': value} if the env var is set, so argparse can fall back to it."""
    value = os.environ.get(name)
    return {"default": value} if value else {}


def _netrc_credentials(url):
    """Return (login, password) for the URL's host from ~/.netrc, or (None, None).

    Used as a last-resort fallback after CLI flags and CONFLUENCE_* env vars.
    A missing or unparsable netrc file is treated the same as no entry.
    """
    import netrc
    from urllib.parse import urlsplit

    host = urlsplit(url).hostname
    if not host:
        return None, None
    try:
        entry = netrc.netrc().authenticators(host)
    except (OSError, netrc.NetrcParseError):
        return None, None
    if not entry:
        return None, None
    login, _, password = entry
    return login or None, password or None


def build_parser():
    parser = argparse.ArgumentParser(
        prog="dac",
        description="Diagrams As Code (DAC) - Convert between draw.io XML and YAML formats",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    sub = parser.add_subparsers(dest="mode", metavar="command")
    sub.required = True

    p = sub.add_parser("d2c", help="diagram to code (XML → YAML)")
    p.add_argument("file", help="Input .drawio file. Output directory has the same base name.")

    p = sub.add_parser("c2d", help="code to diagram (YAML → XML)")
    p.add_argument("file", help="Input YAML directory. Output .drawio has the same base name.")

    p = sub.add_parser(
        "export-confluence",
        help="build every diagram directory under a root and publish them to Confluence",
        description=(
            "Publish all diagram directories (those containing _manifest.yaml) under ROOT "
            "as child pages of a Confluence base page, attaching and embedding the generated "
            ".drawio files. Credentials and page targets can also be given via environment "
            "variables (shown in brackets)."
        ),
    )
    p.add_argument("--root", default="diagrams", help="Directory containing diagram directories (default: diagrams)")
    p.add_argument("--url", **_env_default("CONFLUENCE_URL"), help="Site URL, e.g. https://example.atlassian.net [CONFLUENCE_URL]")
    p.add_argument("--user", **_env_default("CONFLUENCE_USER"), help="Atlassian account email [CONFLUENCE_USER, else ~/.netrc]")
    p.add_argument("--token", **_env_default("CONFLUENCE_API_TOKEN"), help="Atlassian API token [CONFLUENCE_API_TOKEN, else ~/.netrc]")
    p.add_argument("--base-page-id", **_env_default("CONFLUENCE_BASE_PAGE_ID"), help="ID of the existing base page [CONFLUENCE_BASE_PAGE_ID]")
    p.add_argument("--space", **_env_default("CONFLUENCE_SPACE_KEY"), help="Space key, used with --base-title when no base page id is given [CONFLUENCE_SPACE_KEY]")
    p.add_argument("--base-title", **_env_default("CONFLUENCE_BASE_TITLE"), help="Title of the base page to find or create [CONFLUENCE_BASE_TITLE]")
    p.add_argument("--parent-page-id", **_env_default("CONFLUENCE_PARENT_PAGE_ID"), help="Parent under which a new base page is created [CONFLUENCE_PARENT_PAGE_ID]")
    p.add_argument("--title-prefix", default="", help="Prefix for diagram page titles (titles must be unique per space)")
    p.add_argument("--repo-url", help="Browsable repository URL for permalinks (auto-detected from GitHub Actions or git remote)")
    p.add_argument("--commit", help="Commit SHA to reference (auto-detected)")
    p.add_argument("--out-dir", help="Also write the generated .drawio files here")
    p.add_argument("--force", action="store_true", help="Update pages even when the diagram content is unchanged")
    p.add_argument("--no-index", action="store_true", help="Leave the base page body untouched")
    p.add_argument("--dry-run", action="store_true", help="Read-only: report what would be created/updated")
    return parser


def _run_export(args):
    from .confluence import ConfluenceClient, ConfluenceError, detect_git_context, export_to_confluence

    if args.url and (not args.user or not args.token):
        login, password = _netrc_credentials(args.url)
        args.user = args.user or login
        args.token = args.token or password

    missing = [n for n, v in (("--url", args.url), ("--user", args.user), ("--token", args.token)) if not v]
    if missing:
        print(f"Error: missing {', '.join(missing)} (or the matching CONFLUENCE_* environment variable, or a ~/.netrc entry for the site).")
        sys.exit(2)
    if not args.base_page_id and not (args.space and args.base_title):
        print("Error: give --base-page-id, or --space together with --base-title.")
        sys.exit(2)

    ctx = detect_git_context(args.root, repo_url=args.repo_url, commit=args.commit)
    client = ConfluenceClient(args.url, args.user, args.token)
    print(f"Exporting {args.root}/ at {ctx.short_commit}{' (dry run)' if args.dry_run else ''}")
    try:
        result = export_to_confluence(
            client, args.root,
            base_page_id=args.base_page_id,
            space_key=args.space,
            base_title=args.base_title,
            parent_page_id=args.parent_page_id,
            title_prefix=args.title_prefix,
            ctx=ctx,
            force=args.force,
            dry_run=args.dry_run,
            update_index=not args.no_index,
            out_dir=args.out_dir,
        )
    except (ConfluenceError, FileNotFoundError) as exc:
        print(f"Error: {exc}")
        sys.exit(1)

    print(
        f"\n✓ {len(result.created)} created, {len(result.updated)} updated, "
        f"{len(result.skipped)} unchanged → {result.base_page_url}"
    )


def main(argv=None):
    """Main entry point for the CLI."""
    args = build_parser().parse_args(argv)

    if args.mode == "d2c":
        diagram_to_code(get_base_filename(args.file))
    elif args.mode == "c2d":
        code_to_diagram(get_base_filename(args.file))
    elif args.mode == "export-confluence":
        _run_export(args)


if __name__ == "__main__":
    main()
