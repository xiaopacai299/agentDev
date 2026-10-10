from agentdev.runtime.memory_store import load_memory, remember_command, render_memory
from agentdev.runtime.state import new_state


def test_remember_four_kinds_and_render(tmp_path):
    folder = tmp_path / "memory"
    assert remember_command("记住用户：背景=后端，熟悉 Python；颗粒度=少术语", folder) == "已记住用户。"
    assert (
        remember_command(
            "记住反馈：规则=先给结论；原因=用户不爱长文；场景=解释方案时；范围=personal",
            folder,
        )
        == "已记住反馈（personal）。"
    )
    assert (
        remember_command(
            "记住反馈：规则=工具入口放文件底部；原因=方便查阅对外接口；场景=改 Python 模块时；范围=project",
            folder,
        )
        == "已记住反馈（project）。"
    )
    assert (
        remember_command("记住项目：进度=编排已落地；截止=2026-10-17；动机=先跑通助手", folder)
        == "已记住项目。"
    )
    assert (
        remember_command(
            "记住引用：标题=错误面板；地址=https://example.com/bugs；类型=bug；何时=查线上错误",
            folder,
        )
        == "已记住引用。"
    )

    memory = load_memory(folder)
    text = render_memory(memory)
    assert memory.user.background == "后端，熟悉 Python"
    assert memory.user.granularity == "少术语"
    assert {item.scope for item in memory.feedback} == {"personal", "project"}
    assert memory.project.deadline == "2026-10-17"
    assert memory.references[0].url == "https://example.com/bugs"
    assert "沟通颗粒度：少术语" in text
    assert "[project] 工具入口放文件底部" in text
    assert "2026-10-17" in text
    assert "https://example.com/bugs" in text
    assert "background" not in new_state().to_dict()


def test_remember_rejects_garbage_and_relative_dates(tmp_path):
    folder = tmp_path / "memory"
    assert "代码模式和路径" in remember_command("记住用户：背景=去改 src/agentdev/loop.py", folder)
    assert "git 历史" in remember_command("记住项目：进度=看 git log 最近一次 commit", folder)
    assert "修复和调试细节" in remember_command("记住反馈：规则=看 Traceback；原因=报错；场景=调试时；范围=personal", folder)
    assert "配置里的任务" in remember_command("记住项目：进度=完成配置里的 TODO", folder)
    assert "临时任务状态" in remember_command("记住项目：进度=本轮任务 status=running", folder)
    assert "绝对日期" in remember_command("记住项目：截止=下周五", folder)
    assert "外部链接" in remember_command(
        "记住引用：标题=本地文件；地址=src/agentdev/loop.py；类型=wiki；何时=改代码",
        folder,
    )
    assert load_memory(folder).user.background == ""
    assert load_memory(folder).feedback == []
    assert load_memory(folder).project.deadline == ""
    assert load_memory(folder).references == []


def test_same_feedback_rule_replaces_instead_of_duplicating(tmp_path):
    folder = tmp_path / "memory"
    remember_command("记住反馈：规则=先给结论；原因=太长；场景=解释时；范围=个人", folder)
    remember_command("记住反馈：规则=先给结论；原因=方便扫读；场景=任何回答；范围=personal", folder)
    items = load_memory(folder).feedback
    assert len(items) == 1
    assert items[0].reason == "方便扫读"
    assert items[0].scope == "personal"


def test_personal_memory_follows_home_and_project_memory_follows_workspace(tmp_path, monkeypatch):
    home = tmp_path / "home"
    work = tmp_path / "work"
    monkeypatch.setattr("agentdev.runtime.memory_store.home_dir", lambda: home)
    monkeypatch.setattr("agentdev.runtime.memory_store.workspace_root", lambda: work)

    remember_command("记住用户：背景=后端，熟悉 Python")
    remember_command("记住反馈：规则=先给结论；原因=不爱长文；场景=解释时；范围=personal")
    remember_command("记住反馈：规则=入口在文件底部；原因=方便查阅；场景=改模块时；范围=project")
    remember_command("记住项目：进度=编排已落地；截止=2026-10-17；动机=先跑通助手")
    remember_command("记住引用：标题=错误面板；地址=https://example.com/bugs；类型=bug；何时=查线上错误")

    assert (home / "memory" / "user.json").exists()
    assert "先给结论" in (home / "memory" / "feedback.json").read_text(encoding="utf-8")
    assert (work / ".agent" / "memory" / "project.json").exists()
    assert "入口在文件底部" in (work / ".agent" / "memory" / "feedback.json").read_text(encoding="utf-8")
    assert "https://example.com/bugs" in (work / ".agent" / "memory" / "references.json").read_text(encoding="utf-8")

    memory = load_memory()
    assert memory.user.background == "后端，熟悉 Python"
    assert {item.scope for item in memory.feedback} == {"personal", "project"}
    assert memory.project.deadline == "2026-10-17"
