import pytest

from agentdev.agents.assistant.tools import (
    evaluate_expression,
    forecast_window,
    format_daily_lines,
    format_location,
    format_weather,
    get_current_time,
    place_label,
)


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


def test_place_label_skips_duplicate_names():
    assert place_label({"name": "北京", "admin1": "北京", "country": "中国"}, "北京") == "北京，中国"


def test_format_weather_includes_conditions():
    text = format_weather(
        "北京",
        {
            "current": {
                "temperature_2m": 22.1,
                "apparent_temperature": 22.2,
                "relative_humidity_2m": 45,
                "weather_code": 0,
                "wind_speed_10m": 2.1,
                "precipitation": 0.0,
            },
            "daily": {"temperature_2m_max": [25.8], "temperature_2m_min": [13.8]},
        },
    )
    assert "天气: 晴" in text
    assert "22.1°C" in text
    assert "今日最高/最低: 25.8°C / 13.8°C" in text
    assert "Open-Meteo" in text


def test_forecast_window_counts_forward_from_start():
    start, end, count = forecast_window("2026-10-10", 3)
    assert (start, end, count) == ("2026-10-10", "2026-10-12", 3)
    assert forecast_window("", 1) == (None, None, 1)
    assert forecast_window("2026-10-10", 30)[2] == 16


def test_format_daily_lines_lists_each_day():
    lines = format_daily_lines(
        {
            "time": ["2026-10-10", "2026-10-11"],
            "weather_code": [0, 61],
            "temperature_2m_max": [26, 22],
            "temperature_2m_min": [14, 15],
            "precipitation_sum": [0, 3.2],
            "precipitation_probability_max": [10, 70],
        }
    )
    assert "2026-10-10 周六: 晴，14–26°C" in lines[0]
    assert "降水概率 70%" in lines[1]
    assert "小雨" in lines[1]


def test_format_location_explains_denied_permission():
    text = format_location(
        {"status": "Disabled", "permission": "Denied", "is_unknown": True}
    )
    assert "未授权" in text
