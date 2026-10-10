from agentdev.runtime.providers import find_provider
from agentdev.runtime.setup import run_setup, save_home_settings


def test_find_provider_by_number_or_name():
    assert find_provider("2").key == "deepseek"
    assert find_provider("openai").label == "OpenAI"
    assert find_provider("9") is None


def test_setup_saves_key_without_printing_it(tmp_path, monkeypatch, capsys):
    home = tmp_path / "home"
    monkeypatch.setattr("agentdev.runtime.setup.home_dir", lambda: home)
    answers = iter(["2", "1", ""])

    def ask(_prompt: str) -> str:
        return next(answers)

    settings = run_setup(input_fn=ask, secret_fn=lambda _prompt: "sk-test-secret")
    saved = (home / ".env").read_text(encoding="utf-8")
    assert "OPENAI_API_KEY=sk-test-secret" in saved
    assert "MODEL=deepseek-chat" in saved
    assert "OPENAI_BASE_URL=https://api.deepseek.com" in saved
    assert settings.model == "deepseek-chat"
    assert settings.api_key == "sk-test-secret"
    assert "sk-test-secret" not in capsys.readouterr().out


def test_save_home_settings_replaces_model_and_keeps_other_lines(tmp_path, monkeypatch):
    home = tmp_path / "home"
    home.mkdir()
    (home / ".env").write_text("TEMPERATURE=0.2\nMODEL=old\n", encoding="utf-8")
    monkeypatch.setattr("agentdev.runtime.setup.home_dir", lambda: home)
    save_home_settings("sk-new", "gpt-4o-mini", None)
    text = (home / ".env").read_text(encoding="utf-8")
    assert "MODEL=gpt-4o-mini" in text
    assert "OPENAI_API_KEY=sk-new" in text
    assert "MODEL=old" not in text
