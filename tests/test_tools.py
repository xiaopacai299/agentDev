import pytest

from agentdev.tools import evaluate_expression, get_current_time


def test_calculate_arithmetic():
    assert evaluate_expression("(2 + 3) * 4") == "20"
    assert evaluate_expression("10 / 4") == "2.5"


def test_calculate_rejects_names():
    with pytest.raises(ValueError):
        evaluate_expression("__import__('os').system('echo hi')")


def test_current_time_is_iso():
    value = get_current_time.invoke({})
    assert "T" in value
