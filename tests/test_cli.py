"""Tests for the CLI argument handling."""

import os
from pathlib import Path

import pytest

from dac.cli import build_parser, main


class TestParser:

    def test_d2c_and_c2d(self):
        p = build_parser()
        assert p.parse_args(["d2c", "x.drawio"]).mode == "d2c"
        assert p.parse_args(["c2d", "x"]).file == "x"

    def test_export_env_fallbacks(self, monkeypatch):
        monkeypatch.setenv("CONFLUENCE_URL", "https://x.atlassian.net")
        monkeypatch.setenv("CONFLUENCE_API_TOKEN", "tok")
        monkeypatch.setenv("CONFLUENCE_BASE_PAGE_ID", "123")
        args = build_parser().parse_args(["export-confluence", "--user", "me"])
        assert args.url == "https://x.atlassian.net"
        assert args.token == "tok" and args.base_page_id == "123" and args.user == "me"
        assert args.root == "diagrams" and not args.dry_run

    def test_requires_command(self):
        with pytest.raises(SystemExit):
            build_parser().parse_args([])


class TestMain:

    def test_d2c_then_c2d(self, temp_dir, single_diagram_xml):
        os.chdir(temp_dir)
        Path("t.drawio").write_text(single_diagram_xml)
        main(["d2c", "t.drawio"])
        assert Path("t/_manifest.yaml").exists()
        Path("t.drawio").unlink()
        main(["c2d", "t"])
        assert 'name="Test Diagram"' in Path("t.drawio").read_text()

    def test_export_missing_credentials_exits(self, monkeypatch, capsys):
        for k in ("CONFLUENCE_URL", "CONFLUENCE_USER", "CONFLUENCE_API_TOKEN"):
            monkeypatch.delenv(k, raising=False)
        with pytest.raises(SystemExit) as exc:
            main(["export-confluence", "--base-page-id", "1"])
        assert exc.value.code == 2
        assert "--url" in capsys.readouterr().out

    def test_export_missing_target_exits(self, monkeypatch, capsys):
        for k in ("CONFLUENCE_BASE_PAGE_ID", "CONFLUENCE_SPACE_KEY", "CONFLUENCE_BASE_TITLE"):
            monkeypatch.delenv(k, raising=False)
        with pytest.raises(SystemExit) as exc:
            main(["export-confluence", "--url", "u", "--user", "u", "--token", "t"])
        assert exc.value.code == 2
        assert "--base-page-id" in capsys.readouterr().out

    def test_export_runs_with_fake_client(self, monkeypatch, temp_dir, single_diagram_xml, capsys):
        from dac import diagram_to_code
        from tests.test_confluence import FakeConfluence

        root = Path(temp_dir) / "diagrams"
        root.mkdir()
        os.chdir(root)
        Path("a.drawio").write_text(single_diagram_xml)
        diagram_to_code("a")
        os.chdir(temp_dir)

        fake = FakeConfluence()
        base = fake.add_page("Diagrams")
        monkeypatch.setattr("dac.confluence.ConfluenceClient", lambda *a, **k: fake)
        main([
            "export-confluence", "--url", "https://x.atlassian.net", "--user", "u", "--token", "t",
            "--base-page-id", base["id"], "--root", "diagrams", "--commit", "abcdef0",
        ])
        out = capsys.readouterr().out
        assert "1 created, 0 updated, 0 unchanged" in out
        assert fake.find_page("7", "a") is not None
