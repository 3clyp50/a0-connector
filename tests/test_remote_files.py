from __future__ import annotations

import os
from pathlib import Path

import pytest

from agent_zero_cli.remote_files import RemoteFileUtility


def test_remote_file_utility_stat_returns_canonical_metadata(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    target = tmp_path / "sample.txt"
    target.write_text("alpha\nbeta\n", encoding="utf-8")

    utility = RemoteFileUtility(scan_root=str(tmp_path))
    result = utility.handle_file_op(
        {
            "op_id": "op-stat",
            "op": "stat",
            "path": ".\\sample.txt",
        }
    )

    assert result["ok"] is True
    assert result["result"]["file"] == {
        "realpath": os.path.realpath(str(target)),
        "mtime": os.path.getmtime(target),
        "total_lines": 2,
    }


def test_remote_file_utility_roundtrips_read_write_and_patch(tmp_path: Path) -> None:
    utility = RemoteFileUtility(scan_root=str(tmp_path))
    target = tmp_path / "sample.txt"

    write_result = utility.handle_file_op(
        {
            "op_id": "op-write",
            "op": "write",
            "path": str(target),
            "content": "line-1\nline-2\n",
        }
    )
    read_result = utility.handle_file_op(
        {
            "op_id": "op-read",
            "op": "read",
            "path": str(target),
            "line_from": 1,
            "line_to": 2,
        }
    )
    patch_result = utility.handle_file_op(
        {
            "op_id": "op-patch",
            "op": "patch",
            "path": str(target),
            "edits": [{"from": 2, "to": 2, "content": "line-2-updated\n"}],
        }
    )

    assert write_result["ok"] is True
    assert write_result["result"]["message"] == f"{target} written successfully"
    assert write_result["result"]["file"]["realpath"] == os.path.realpath(str(target))
    assert write_result["result"]["file"]["total_lines"] == 2
    assert read_result["ok"] is True
    assert "1 | line-1" in read_result["result"]["content"]
    assert read_result["result"]["file"]["realpath"] == os.path.realpath(str(target))
    assert read_result["result"]["file"]["total_lines"] == 2
    assert patch_result["ok"] is True
    assert patch_result["result"]["message"] == f"{target} patched successfully"
    assert patch_result["result"]["file"]["realpath"] == os.path.realpath(str(target))
    assert patch_result["result"]["file"]["total_lines"] == 2
    assert target.read_text(encoding="utf-8") == "line-1\nline-2-updated\n"


def test_remote_file_utility_context_patch_chains_after_line_shift(tmp_path: Path) -> None:
    utility = RemoteFileUtility(scan_root=str(tmp_path))
    target = tmp_path / "sample.txt"
    target.write_text("alpha\nbeta\ngamma\n", encoding="utf-8")

    first_patch = utility.handle_file_op(
        {
            "op_id": "op-context-patch-1",
            "op": "patch",
            "path": str(target),
            "patch_text": (
                "*** Begin Patch\n"
                "*** Update File: sample.txt\n"
                "@@ alpha\n"
                "+inserted\n"
                "*** End Patch"
            ),
        }
    )
    second_patch = utility.handle_file_op(
        {
            "op_id": "op-context-patch-2",
            "op": "patch",
            "path": str(target),
            "patch_text": (
                "*** Begin Patch\n"
                "*** Update File: sample.txt\n"
                " beta\n"
                "-gamma\n"
                "+gamma-updated\n"
                "*** End Patch"
            ),
        }
    )

    assert first_patch["ok"] is True
    assert first_patch["result"]["file"]["total_lines"] == 4
    assert second_patch["ok"] is True
    assert second_patch["result"]["file"]["total_lines"] == 4
    assert target.read_text(encoding="utf-8") == "alpha\ninserted\nbeta\ngamma-updated\n"


def test_remote_file_utility_context_patch_can_replace_anchor_line(tmp_path: Path) -> None:
    utility = RemoteFileUtility(scan_root=str(tmp_path))
    target = tmp_path / "sample.py"
    target.write_text(
        (
            "def main():\n"
            "    print(greet(\"Agent Zero\"))\n"
            "\n"
            "\n"
            "if __name__ == \"__main__\":\n"
            "    main()\n"
        ),
        encoding="utf-8",
    )

    patch = utility.handle_file_op(
        {
            "op_id": "op-context-patch-anchor-line",
            "op": "patch",
            "path": str(target),
            "patch_text": (
                "*** Begin Patch\n"
                "*** Update File: sample.py\n"
                "@@     print(greet(\"Agent Zero\"))\n"
                "-    print(greet(\"Agent Zero\"))\n"
                "+    print(greet(\"Agent Zero\").upper())\n"
                "*** End Patch"
            ),
        }
    )

    assert patch["ok"] is True
    assert patch["result"]["file"]["total_lines"] == 6
    assert target.read_text(encoding="utf-8") == (
        "def main():\n"
        "    print(greet(\"Agent Zero\").upper())\n"
        "\n"
        "\n"
        "if __name__ == \"__main__\":\n"
        "    main()\n"
    )


def test_remote_file_utility_blocks_writes_and_bounds_tree_snapshots(tmp_path: Path) -> None:
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "a.py").write_text("a\n", encoding="utf-8")
    (tmp_path / "src" / "b.py").write_text("b\n", encoding="utf-8")
    (tmp_path / "README.md").write_text("hello\n", encoding="utf-8")

    utility = RemoteFileUtility(
        scan_root=str(tmp_path),
        allow_writes=False,
        max_depth=3,
        max_files=1,
        max_folders=5,
        max_lines=20,
    )

    blocked = utility.handle_file_op(
        {
            "op_id": "op-write-disabled",
            "op": "write",
            "path": str(tmp_path / "blocked.txt"),
            "content": "hello\n",
        }
    )
    snapshot = utility.build_tree_snapshot()

    assert blocked["ok"] is False
    assert "Press F3" in blocked["error"]
    assert snapshot.root_path == str(tmp_path)
    assert snapshot.tree_hash
    assert "# 1 more file" in snapshot.tree
    assert "src/" in snapshot.tree
