from pathlib import Path

import pytest

from agentdev.workspace import edit_file_text, read_file_text, resolve_path, run_command, write_file_text


def test_write_then_read_and_edit(tmp_path: Path):
    write_file_text("notes/plan.txt", "总花费 1000 元\n", tmp_path)
    assert "1|总花费 1000 元" in read_file_text("notes/plan.txt", root=tmp_path)
    message = edit_file_text("notes/plan.txt", "1000", "1573", tmp_path)
    assert "1 处" in message
    assert "1573" in read_file_text("notes/plan.txt", root=tmp_path)


def test_edit_rejects_repeated_text(tmp_path: Path):
    write_file_text("notes/plan.txt", "元\n元\n", tmp_path)
    with pytest.raises(ValueError, match="2 次"):
        edit_file_text("notes/plan.txt", "元", "块", tmp_path)


def test_path_can_leave_project(tmp_path: Path):
    root = tmp_path / "project"
    root.mkdir()
    resolved = resolve_path("../outside.txt", root)
    assert resolved == (tmp_path / "outside.txt").resolve()


def test_delete_waits_for_confirmation(tmp_path: Path):
    target = tmp_path / "note.txt"
    target.write_text("keep", encoding="utf-8")
    output = run_command(
        f"Remove-Item -LiteralPath '{target}'",
        root=tmp_path,
        confirm=lambda command: False,
    )
    assert output == "已取消删除，命令未执行"
    assert target.read_text(encoding="utf-8") == "keep"


def test_delete_runs_after_confirmation(tmp_path: Path):
    target = tmp_path / "note.txt"
    target.write_text("gone", encoding="utf-8")
    output = run_command(
        f"Remove-Item -LiteralPath '{target}'",
        root=tmp_path,
        confirm=lambda command: True,
    )
    assert "退出码: 0" in output
    assert target.exists() is False


def test_bash_runs_in_project_root(tmp_path: Path):
    output = run_command("Write-Output hello-workspace", root=tmp_path)
    assert "退出码: 0" in output
    assert "hello-workspace" in output
