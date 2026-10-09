import pytest

from agentdev.tools import evaluate_expression, format_location, get_current_time


def test_calculate_arithmetic():
    assert evaluate_expression("(2 + 3) * 4") == "20"
    assert evaluate_expression("10 / 4") == "2.5"


def test_calculate_rejects_names():
    with pytest.raises(ValueError):
        evaluate_expression("__import__('os').system('echo hi')")


def test_current_time_is_iso():
    value = get_current_time.invoke({})
    assert "T" in value


def test_format_location_includes_coordinates():
    text = format_location(
        {
            "status": "Ready",
            "permission": "Granted",
            "is_unknown": False,
            "latitude": 31.2,
            "longitude": 121.5,
            "accuracy_meters": 80,
        }
    )
    assert "31.200000" in text
    assert "121.500000" in text
    assert "80 米" in text


def test_format_location_explains_denied_permission():
    text = format_location(
        {"status": "Disabled", "permission": "Denied", "is_unknown": True}
    )
    assert "未授权" in text
