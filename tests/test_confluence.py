"""Tests for the Confluence exporter (no network: uses an in-memory fake client)."""

import json
import os
from pathlib import Path

import pytest

from dac import diagram_to_code
from dac.confluence import (
    PROPERTY_KEY,
    ConfluenceClient,
    ConfluenceError,
    GitContext,
    collect_diagrams,
    detect_git_context,
    diagram_page_body,
    export_to_confluence,
    index_page_body,
    normalize_repo_url,
)


# =============================================================================
# Fake client
# =============================================================================

class FakeConfluence:
    """In-memory stand-in for ConfluenceClient with the same interface."""

    def __init__(self):
        self.pages = {}         # id -> page dict
        self.attachments = {}   # page id -> {filename: bytes}
        self.properties = {}    # page id -> {key: property dict}
        self.calls = []
        self._next = 100

    def _new_id(self):
        self._next += 1
        return str(self._next)

    # helpers for tests
    def add_page(self, title, parent_id=None, space_id="7", body=""):
        pid = self._new_id()
        self.pages[pid] = {
            "id": pid, "title": title, "spaceId": space_id, "parentId": parent_id,
            "version": {"number": 1, "message": ""},
            "body": {"storage": {"value": body}},
            "_links": {"webui": f"/spaces/X/pages/{pid}", "base": "https://x.atlassian.net/wiki"},
        }
        return self.pages[pid]

    # client interface
    def get_space_id(self, key):
        self.calls.append(("get_space_id", key))
        if key != "DOC":
            raise ConfluenceError(f"Space '{key}' not found.")
        return "7"

    def get_page(self, page_id):
        self.calls.append(("get_page", page_id))
        try:
            return self.pages[str(page_id)]
        except KeyError:
            raise ConfluenceError("HTTP 404")

    def find_page(self, space_id, title, parent_id=None):
        self.calls.append(("find_page", title, parent_id))
        for p in self.pages.values():
            if p["title"] == title and p["spaceId"] == space_id and (
                parent_id is None or p["parentId"] == str(parent_id)
            ):
                return p
        return None

    def create_page(self, space_id, title, body, parent_id=None):
        self.calls.append(("create_page", title, parent_id))
        if any(p["title"] == title for p in self.pages.values()):
            raise ConfluenceError("HTTP 400: title already exists")
        return self.add_page(title, str(parent_id) if parent_id else None, space_id, body)

    def update_page(self, page_id, title, body, version_number, message=""):
        self.calls.append(("update_page", page_id, version_number, message))
        page = self.pages[str(page_id)]
        assert version_number == page["version"]["number"] + 1, "version must increment"
        page["title"] = title
        page["body"] = {"storage": {"value": body}}
        page["version"] = {"number": version_number, "message": message}
        return page

    def page_url(self, page):
        return f"https://x.atlassian.net/wiki/spaces/X/pages/{page['id']}"

    def upload_attachment(self, page_id, filename, content, comment="", content_type="application/xml"):
        self.calls.append(("upload_attachment", page_id, filename))
        self.attachments.setdefault(str(page_id), {})[filename] = content
        return {"results": [{"id": "att1", "title": filename}]}

    def get_property(self, page_id, key):
        return self.properties.get(str(page_id), {}).get(key)

    def set_property(self, page_id, key, value):
        self.calls.append(("set_property", page_id, key))
        props = self.properties.setdefault(str(page_id), {})
        existing = props.get(key)
        number = existing["version"]["number"] + 1 if existing else 1
        props[key] = {"id": "p1", "key": key, "value": value, "version": {"number": number}}
        return props[key]


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture
def diagrams_root(temp_dir, single_diagram_xml, multi_diagram_xml):
    """A `diagrams/` root with two diagram directories, built via d2c."""
    root = Path(temp_dir) / "diagrams"
    root.mkdir()
    os.chdir(root)
    (root / "alpha.drawio").write_text(single_diagram_xml)
    (root / "beta.drawio").write_text(multi_diagram_xml)
    diagram_to_code("alpha")
    diagram_to_code("beta")
    (root / "alpha.drawio").unlink()
    (root / "beta.drawio").unlink()
    os.chdir(temp_dir)
    return root


@pytest.fixture
def ctx():
    return GitContext(
        repo_url="https://github.com/acme/diagrams",
        commit="0123456789abcdef0123456789abcdef01234567",
        ref="master",
        run_url="https://github.com/acme/diagrams/actions/runs/42",
        generated_at="2026-08-28 12:00:00 UTC",
    )


@pytest.fixture
def fake():
    return FakeConfluence()


def export(fake, root, temp_dir, ctx, **kw):
    kw.setdefault("repo_root", temp_dir)
    kw.setdefault("log", lambda *_: None)
    return export_to_confluence(fake, root, ctx=ctx, **kw)


# =============================================================================
# Discovery and page bodies
# =============================================================================

class TestCollectDiagrams:

    def test_finds_all_diagram_dirs(self, diagrams_root, temp_dir):
        sources = collect_diagrams(diagrams_root, repo_root=temp_dir)
        assert [s.title for s in sources] == ["alpha", "beta"]
        assert sources[0].rel_path == "diagrams/alpha"
        assert sources[0].attachment_name == "alpha.drawio"
        assert sources[1].tabs == ["First Page", "Second Page", "Third/Special Page"]
        assert "<mxfile" in sources[1].xml and sources[1].xml.count("<diagram") == 3

    def test_title_prefix(self, diagrams_root, temp_dir):
        sources = collect_diagrams(diagrams_root, title_prefix="Arch: ", repo_root=temp_dir)
        assert sources[0].title == "Arch: alpha"

    def test_content_hash_is_stable(self, diagrams_root, temp_dir):
        a = collect_diagrams(diagrams_root, repo_root=temp_dir)[0]
        b = collect_diagrams(diagrams_root, repo_root=temp_dir)[0]
        assert a.content_hash == b.content_hash

    def test_missing_root_raises(self, temp_dir):
        with pytest.raises(FileNotFoundError):
            collect_diagrams(Path(temp_dir) / "nope", repo_root=temp_dir)


class TestPageBodies:

    def test_diagram_page_embeds_macro_and_version(self, diagrams_root, temp_dir, ctx):
        source = collect_diagrams(diagrams_root, repo_root=temp_dir)[1]
        body = diagram_page_body(source, ctx)
        assert '<ac:structured-macro ac:name="drawio"' in body
        assert '<ac:parameter ac:name="diagramName">beta.drawio</ac:parameter>' in body
        assert '<ac:parameter ac:name="attachment">beta.drawio</ac:parameter>' in body
        assert 'ri:attachment ri:filename="beta.drawio"' in body
        # version section with permalinks
        assert "https://github.com/acme/diagrams/commit/0123456789abcdef0123456789abcdef01234567" in body
        assert "https://github.com/acme/diagrams/tree/0123456789abcdef0123456789abcdef01234567/diagrams/beta" in body
        assert "actions/runs/42" in body
        assert "2026-08-28 12:00:00 UTC" in body
        # tab names are escaped
        assert "<li>Third/Special Page</li>" in body

    def test_diagram_page_without_repo_info(self, diagrams_root, temp_dir):
        source = collect_diagrams(diagrams_root, repo_root=temp_dir)[0]
        body = diagram_page_body(source, GitContext())
        assert "unknown" in body
        assert "<a href" not in body

    def test_index_page_lists_entries(self, ctx):
        body = index_page_body(
            [{"title": "A & B", "rel_path": "diagrams/a", "tabs": 2, "status": "created @ 0123456"}], ctx
        )
        assert 'ri:content-title="A &amp; B"' in body
        assert "created @ 0123456" in body
        assert "/tree/0123456789abcdef0123456789abcdef01234567/diagrams/a" in body


# =============================================================================
# Export flow
# =============================================================================

class TestExport:

    def test_first_export_creates_pages_under_base(self, fake, diagrams_root, temp_dir, ctx):
        base = fake.add_page("Diagrams")
        result = export(fake, diagrams_root, temp_dir, ctx, base_page_id=base["id"])

        assert result.created == ["alpha", "beta"]
        assert result.updated == [] and result.skipped == []
        children = [p for p in fake.pages.values() if p["parentId"] == base["id"]]
        assert sorted(p["title"] for p in children) == ["alpha", "beta"]

        alpha = fake.find_page("7", "alpha")
        assert b"<mxfile" in fake.attachments[alpha["id"]]["alpha.drawio"]
        assert fake.properties[alpha["id"]][PROPERTY_KEY]["value"]["commit"] == ctx.commit
        assert 'ac:name="drawio"' in alpha["body"]["storage"]["value"]

        # index written on the base page with a version message referencing the commit
        assert fake.pages[base["id"]]["version"]["number"] == 2
        assert fake.pages[base["id"]]["version"]["message"] == "DAC export from 0123456"
        assert 'ri:content-title="alpha"' in fake.pages[base["id"]]["body"]["storage"]["value"]
        assert result.base_page_url.endswith(base["id"])

    def test_second_export_unchanged_skips(self, fake, diagrams_root, temp_dir, ctx):
        base = fake.add_page("Diagrams")
        export(fake, diagrams_root, temp_dir, ctx, base_page_id=base["id"])
        fake.calls.clear()

        result = export(fake, diagrams_root, temp_dir, ctx, base_page_id=base["id"])
        assert result.skipped == ["alpha", "beta"]
        assert not result.changed
        assert not any(c[0] in ("update_page", "upload_attachment", "create_page") for c in fake.calls)
        assert fake.pages[base["id"]]["version"]["number"] == 2  # index not rewritten

    def test_changed_diagram_updates_page_and_version(self, fake, diagrams_root, temp_dir, ctx):
        base = fake.add_page("Diagrams")
        export(fake, diagrams_root, temp_dir, ctx, base_page_id=base["id"])

        yaml_path = diagrams_root / "alpha" / "Test_Diagram.yaml"
        yaml_path.write_text(yaml_path.read_text().replace("Hello", "Goodbye"))
        new_ctx = GitContext(repo_url=ctx.repo_url, commit="fedcba9876543210fedcba9876543210fedcba98", ref="master")

        result = export(fake, diagrams_root, temp_dir, new_ctx, base_page_id=base["id"])
        assert result.updated == ["alpha"]
        assert result.skipped == ["beta"]

        alpha = fake.find_page("7", "alpha")
        assert alpha["version"]["number"] == 2
        assert alpha["version"]["message"] == "DAC export from fedcba9"
        assert b"Goodbye" in fake.attachments[alpha["id"]]["alpha.drawio"]
        assert fake.properties[alpha["id"]][PROPERTY_KEY]["version"]["number"] == 2
        assert "fedcba9876543210fedcba9876543210fedcba98" in alpha["body"]["storage"]["value"]
        # base index refreshed
        assert fake.pages[base["id"]]["version"]["number"] == 3
        assert "updated @ fedcba9" in fake.pages[base["id"]]["body"]["storage"]["value"]

    def test_force_updates_unchanged(self, fake, diagrams_root, temp_dir, ctx):
        base = fake.add_page("Diagrams")
        export(fake, diagrams_root, temp_dir, ctx, base_page_id=base["id"])
        result = export(fake, diagrams_root, temp_dir, ctx, base_page_id=base["id"], force=True)
        assert result.updated == ["alpha", "beta"]

    def test_base_page_found_by_title(self, fake, diagrams_root, temp_dir, ctx):
        base = fake.add_page("Diagrams")
        result = export(fake, diagrams_root, temp_dir, ctx, space_key="DOC", base_title="Diagrams")
        assert result.base_page_id == base["id"]
        assert not any(c[0] == "create_page" and c[1] == "Diagrams" for c in fake.calls)

    def test_base_page_created_by_title(self, fake, diagrams_root, temp_dir, ctx):
        parent = fake.add_page("Engineering")
        result = export(
            fake, diagrams_root, temp_dir, ctx,
            space_key="DOC", base_title="Diagrams", parent_page_id=parent["id"],
        )
        base = fake.pages[result.base_page_id]
        assert base["title"] == "Diagrams" and base["parentId"] == parent["id"]
        assert sorted(result.created) == ["alpha", "beta"]
        assert "alpha" in base["body"]["storage"]["value"]

    def test_requires_target(self, fake, diagrams_root, temp_dir, ctx):
        with pytest.raises(ConfluenceError):
            export(fake, diagrams_root, temp_dir, ctx)

    def test_unknown_space(self, fake, diagrams_root, temp_dir, ctx):
        with pytest.raises(ConfluenceError):
            export(fake, diagrams_root, temp_dir, ctx, space_key="NOPE", base_title="Diagrams")

    def test_no_index_leaves_base_untouched(self, fake, diagrams_root, temp_dir, ctx):
        base = fake.add_page("Diagrams", body="<p>hand written</p>")
        export(fake, diagrams_root, temp_dir, ctx, base_page_id=base["id"], update_index=False)
        assert fake.pages[base["id"]]["body"]["storage"]["value"] == "<p>hand written</p>"
        assert fake.pages[base["id"]]["version"]["number"] == 1

    def test_dry_run_writes_nothing(self, fake, diagrams_root, temp_dir, ctx):
        base = fake.add_page("Diagrams")
        result = export(fake, diagrams_root, temp_dir, ctx, base_page_id=base["id"], dry_run=True)
        assert result.created == ["alpha", "beta"]
        assert len(fake.pages) == 1
        assert not fake.attachments
        assert not any(c[0] in ("create_page", "update_page", "upload_attachment", "set_property") for c in fake.calls)

    def test_out_dir_receives_drawio_files(self, fake, diagrams_root, temp_dir, ctx):
        base = fake.add_page("Diagrams")
        out = Path(temp_dir) / "build"
        result = export(fake, diagrams_root, temp_dir, ctx, base_page_id=base["id"], out_dir=out)
        assert sorted(p.name for p in out.iterdir()) == ["alpha.drawio", "beta.drawio"]
        assert len(result.built) == 2
        assert "<mxfile" in (out / "beta.drawio").read_text()

    def test_empty_root_raises(self, fake, temp_dir, ctx):
        root = Path(temp_dir) / "empty"
        root.mkdir()
        with pytest.raises(ConfluenceError):
            export(fake, root, temp_dir, ctx, base_page_id="1")


# =============================================================================
# Git context
# =============================================================================

class TestGitContext:

    @pytest.mark.parametrize("url,expected", [
        ("git@github.com:acme/dac.git", "https://github.com/acme/dac"),
        ("https://github.com/acme/dac.git", "https://github.com/acme/dac"),
        ("https://github.com/acme/dac/", "https://github.com/acme/dac"),
        (None, None),
    ])
    def test_normalize_repo_url(self, url, expected):
        assert normalize_repo_url(url) == expected

    def test_github_actions_env(self, monkeypatch, temp_dir):
        monkeypatch.setenv("GITHUB_SERVER_URL", "https://github.com")
        monkeypatch.setenv("GITHUB_REPOSITORY", "acme/dac")
        monkeypatch.setenv("GITHUB_SHA", "abc1234def")
        monkeypatch.setenv("GITHUB_REF_NAME", "master")
        monkeypatch.setenv("GITHUB_RUN_ID", "99")
        c = detect_git_context(temp_dir)
        assert c.repo_url == "https://github.com/acme/dac"
        assert c.commit == "abc1234def" and c.short_commit == "abc1234"
        assert c.ref == "master"
        assert c.run_url == "https://github.com/acme/dac/actions/runs/99"
        assert c.tree_url("diagrams/x") == "https://github.com/acme/dac/tree/abc1234def/diagrams/x"

    def test_explicit_values_win(self, monkeypatch, temp_dir):
        monkeypatch.setenv("GITHUB_SERVER_URL", "https://github.com")
        monkeypatch.setenv("GITHUB_REPOSITORY", "acme/dac")
        monkeypatch.setenv("GITHUB_SHA", "abc")
        c = detect_git_context(temp_dir, repo_url="https://example.com/r.git", commit="fff")
        assert c.repo_url == "https://example.com/r" and c.commit == "fff"

    def test_outside_git_without_env(self, monkeypatch, temp_dir):
        for k in ("GITHUB_SERVER_URL", "GITHUB_REPOSITORY", "GITHUB_SHA", "GITHUB_REF_NAME", "GITHUB_RUN_ID"):
            monkeypatch.delenv(k, raising=False)
        c = detect_git_context(temp_dir)  # temp dir is not a git repo
        assert c.commit is None and c.repo_url is None and c.run_url is None
        assert c.commit_url() is None and c.tree_url("x") is None


# =============================================================================
# HTTP client (urlopen is stubbed)
# =============================================================================

class TestConfluenceClient:

    @pytest.fixture
    def captured(self, monkeypatch):
        calls = []

        class Resp:
            def __init__(self, payload):
                self._payload = payload
            def read(self):
                return json.dumps(self._payload).encode()
            def __enter__(self):
                return self
            def __exit__(self, *a):
                return False

        def fake_urlopen(req, timeout=None):
            calls.append(req)
            return Resp({"results": [{"id": "5", "version": {"number": 1}}], "id": "5"})

        monkeypatch.setattr("dac.confluence.request.urlopen", fake_urlopen)
        return calls

    def test_auth_and_url(self, captured):
        c = ConfluenceClient("https://x.atlassian.net/", "me@example.com", "tok")
        assert c.get_space_id("DOC") == "5"
        req = captured[0]
        assert req.full_url == "https://x.atlassian.net/wiki/api/v2/spaces?keys=DOC"
        assert req.get_header("Authorization") == "Basic bWVAZXhhbXBsZS5jb206dG9r"

    def test_create_page_payload(self, captured):
        c = ConfluenceClient("https://x.atlassian.net", "u", "t")
        c.create_page("7", "T", "<p/>", parent_id=3)
        req = captured[0]
        assert req.get_method() == "POST"
        body = json.loads(req.data)
        assert body == {
            "spaceId": "7", "status": "current", "title": "T", "parentId": "3",
            "body": {"representation": "storage", "value": "<p/>"},
        }

    def test_update_page_payload(self, captured):
        c = ConfluenceClient("https://x.atlassian.net", "u", "t")
        c.update_page("5", "T", "<p/>", 4, "msg")
        req = captured[0]
        assert req.get_method() == "PUT"
        assert req.full_url.endswith("/api/v2/pages/5")
        assert json.loads(req.data)["version"] == {"number": 4, "message": "msg"}

    def test_upload_attachment_multipart(self, captured):
        c = ConfluenceClient("https://x.atlassian.net", "u", "t")
        c.upload_attachment("5", "a.drawio", b"<mxfile/>", comment="c")
        req = captured[0]
        assert req.get_method() == "PUT"
        assert req.full_url.endswith("/rest/api/content/5/child/attachment")
        assert req.get_header("X-atlassian-token") == "nocheck"
        assert req.get_header("Content-type").startswith("multipart/form-data; boundary=")
        assert b'filename="a.drawio"' in req.data and b"<mxfile/>" in req.data

    def test_set_property_updates_existing(self, captured):
        c = ConfluenceClient("https://x.atlassian.net", "u", "t")
        c.set_property("5", "dac-export", {"hash": "h"})
        get, put = captured
        assert put.get_method() == "PUT" and put.full_url.endswith("/pages/5/properties/5")
        assert json.loads(put.data)["version"] == {"number": 2}

    def test_http_error_becomes_confluence_error(self, monkeypatch):
        from urllib import error
        import io

        def boom(req, timeout=None):
            raise error.HTTPError(req.full_url, 403, "Forbidden", {}, io.BytesIO(b"nope"))

        monkeypatch.setattr("dac.confluence.request.urlopen", boom)
        c = ConfluenceClient("https://x.atlassian.net", "u", "t")
        with pytest.raises(ConfluenceError, match="HTTP 403"):
            c.get_page("1")
