"""File discovery stays inside configured roots and has bounded work."""
import pytest
import asyncio
from fastmcp import Client

from qlab_mcp import media


def test_search_paths_limits_and_symlinks(tmp_path, monkeypatch):
    root = tmp_path / "media"
    root.mkdir()
    nested = root / "nested"
    nested.mkdir()
    sound = nested / "Trueno.wav"
    sound.write_bytes(b"sound")
    outside = tmp_path / "Trueno-secret.wav"
    outside.write_bytes(b"secret")
    (root / "Trueno-link.wav").symlink_to(outside)
    (root / "external").symlink_to(tmp_path, target_is_directory=True)
    result = media.search_media_files((str(root),), "trueno", 10)
    assert result["files"] == [{"path": str(sound), "name": "Trueno.wav", "size_bytes": 5}]
    assert not result["truncated"]
    assert media.search_media_files((str(root),), "trueno", 1)["truncated"]
    monkeypatch.setattr(media, "MAX_SCAN_ENTRIES", 1)
    assert media.search_media_files((str(root),), "missing", 10)["truncated"]


def test_search_requires_root_and_nonempty_query(tmp_path):
    with pytest.raises(ValueError, match="directory"):
        media.search_media_files((), "trueno", 10)
    with pytest.raises(ValueError, match="query"):
        media.search_media_files((str(tmp_path),), "   ", 10)
    result = media.search_media_files((str(tmp_path / "missing"),), "trueno", 10)
    assert result["warnings"] and not result["files"]


def test_mcp_search_and_strict_inputs(tmp_path, monkeypatch):
    from pathlib import Path
    from qlab_mcp.server import mcp
    (tmp_path / "Thunder.wav").write_bytes(b"audio")
    monkeypatch.setattr(Path, "home", lambda: tmp_path)

    async def check():
        async with Client(mcp) as client:
            result = await client.call_tool("qlab_search_media_files", {"query": "thunder"})
            assert result.structured_content["files"][0]["path"] == str(tmp_path / "Thunder.wav")
            for args in ({"query": "x", "max_results": True}, {"query": "x", "max_results": "2"},
                         {"query": "x", "max_results": 101}, {"query": 123}, {"query": " "}):
                with pytest.raises(Exception):
                    await client.call_tool("qlab_search_media_files", args)
    asyncio.run(check())


def test_search_time_budget(tmp_path, monkeypatch):
    monkeypatch.setattr(media, "SCAN_SECONDS", 0)
    result = media.search_media_files((str(tmp_path),), "sound", 10)
    assert result["truncated"] and result["scanned_entries"] == 0
