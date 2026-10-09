"""Tools the agent can call."""

from __future__ import annotations

import ast
import json
import operator
import subprocess
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime

from langchain.tools import tool

# 步骤 1：只允许这些算术运算符
_BINARY_OPS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
}
_UNARY_OPS = {
    ast.UAdd: operator.pos,
    ast.USub: operator.neg,
}

# 步骤 2：准备读取本机定位的脚本
_LOCATION_SCRIPT = r"""
$OutputEncoding = [Console]::OutputEncoding = [System.Text.UTF8Encoding]::new()
Add-Type -AssemblyName System.Device
$watcher = New-Object System.Device.Location.GeoCoordinateWatcher
$watcher.Start()
$deadline = (Get-Date).AddSeconds(8)
while (($watcher.Status -ne 'Ready') -and ((Get-Date) -lt $deadline)) {
    Start-Sleep -Milliseconds 200
}
$coord = $watcher.Position.Location
[ordered]@{
    status = [string]$watcher.Status
    permission = [string]$watcher.Permission
    is_unknown = [bool]$coord.IsUnknown
    latitude = if ($coord.IsUnknown) { $null } else { $coord.Latitude }
    longitude = if ($coord.IsUnknown) { $null } else { $coord.Longitude }
    accuracy_meters = if ($coord.IsUnknown) { $null } else { $coord.HorizontalAccuracy }
} | ConvertTo-Json -Compress
"""

# 步骤 3：把天气现象代码译成中文
_WEATHER_LABELS = {
    0: "晴",
    1: "大部晴朗",
    2: "多云",
    3: "阴",
    45: "雾",
    48: "雾凇",
    51: "小毛毛雨",
    53: "中毛毛雨",
    55: "大毛毛雨",
    56: "冻毛毛雨",
    57: "强冻毛毛雨",
    61: "小雨",
    63: "中雨",
    65: "大雨",
    66: "冻雨",
    67: "强冻雨",
    71: "小雪",
    73: "中雪",
    75: "大雪",
    77: "雪粒",
    80: "小阵雨",
    81: "中阵雨",
    82: "大阵雨",
    85: "小阵雪",
    86: "大阵雪",
    95: "雷暴",
    96: "雷暴伴小冰雹",
    99: "雷暴伴大冰雹",
}


# 步骤 4：按节点类型递归求值，拒绝白名单以外的语法
def _eval_node(node: ast.AST) -> float:
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
        return node.value
    if isinstance(node, ast.BinOp) and type(node.op) in _BINARY_OPS:
        left = _eval_node(node.left)
        right = _eval_node(node.right)
        if isinstance(node.op, ast.Pow) and abs(right) > 8:
            raise ValueError("指数过大")
        return _BINARY_OPS[type(node.op)](left, right)
    if isinstance(node, ast.UnaryOp) and type(node.op) in _UNARY_OPS:
        return _UNARY_OPS[type(node.op)](_eval_node(node.operand))
    raise ValueError("只支持数字和 + - * / // % ** 以及括号")


# 步骤 5：把整段表达式算成文本
def evaluate_expression(expression: str) -> str:
    # 步骤 1：解析成语法树
    tree = ast.parse(expression, mode="eval")
    # 步骤 2：按白名单求值
    value = _eval_node(tree.body)
    # 步骤 3：整数结果去掉小数点
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value)


# 步骤 6：向 Windows 读取当前定位
def read_windows_location() -> dict:
    # 步骤 1：调用 PowerShell 定位服务
    completed = subprocess.run(
        [
            "powershell",
            "-NoProfile",
            "-NonInteractive",
            "-Command",
            _LOCATION_SCRIPT,
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=15,
        check=False,
    )
    # 步骤 2：调用失败时抛出原因
    if completed.returncode != 0:
        detail = (completed.stderr or completed.stdout).strip()
        raise RuntimeError(detail or "Windows 定位调用失败")
    # 步骤 3：解析定位 JSON
    return json.loads(completed.stdout)


# 步骤 7：把定位结果写成中文说明
def format_location(payload: dict) -> str:
    permission = payload.get("permission")
    status = payload.get("status")
    # 步骤 1：权限关闭时说明如何打开
    if permission == "Denied" or status == "Disabled":
        return (
            "无法获取当前位置：Windows 定位未授权。"
            "请打开「设置 > 隐私和安全性 > 位置」，开启定位服务并允许桌面应用访问。"
        )
    latitude = payload.get("latitude")
    longitude = payload.get("longitude")
    # 步骤 2：还没有坐标时返回当前状态
    if payload.get("is_unknown") or latitude is None or longitude is None:
        return f"无法获取当前位置：定位服务还没有结果（状态: {status}）。"

    # 步骤 3：拼出经纬度和精度
    lines = [
        "来源: 本机 Windows 定位服务",
        f"纬度: {float(latitude):.6f}",
        f"经度: {float(longitude):.6f}",
    ]
    accuracy = payload.get("accuracy_meters")
    if isinstance(accuracy, (int, float)):
        lines.append(f"水平精度: {float(accuracy):.0f} 米")
    return "\n".join(lines)


# 步骤 8：请求 JSON 接口
def http_get_json(url: str) -> dict:
    request = urllib.request.Request(url, headers={"User-Agent": "agentdev/0.1"})
    with urllib.request.urlopen(request, timeout=15) as response:
        return json.load(response)


# 步骤 9：把地理编码结果整理成地点名
def place_label(result: dict, fallback: str) -> str:
    parts: list[str] = []
    for key in ("name", "admin1", "country"):
        value = result.get(key)
        if value and value not in parts:
            parts.append(str(value))
    return "，".join(parts) or fallback


# 步骤 10：用地名查询经纬度
def geocode_place(place: str) -> dict:
    # 步骤 1：请求 Open-Meteo 地理编码
    query = urllib.parse.urlencode(
        {"name": place, "count": 1, "language": "zh", "format": "json"}
    )
    payload = http_get_json(
        f"https://geocoding-api.open-meteo.com/v1/search?{query}"
    )
    # 步骤 2：没有匹配时中止
    results = payload.get("results") or []
    if not results:
        raise LookupError(f"没有找到地点：{place}")
    # 步骤 3：取出名称和坐标
    result = results[0]
    return {
        "name": place_label(result, place),
        "latitude": float(result["latitude"]),
        "longitude": float(result["longitude"]),
    }


# 步骤 11：按坐标请求当前天气
def fetch_forecast(latitude: float, longitude: float) -> dict:
    query = urllib.parse.urlencode(
        {
            "latitude": latitude,
            "longitude": longitude,
            "current": (
                "temperature_2m,relative_humidity_2m,apparent_temperature,"
                "weather_code,wind_speed_10m,precipitation"
            ),
            "daily": "temperature_2m_max,temperature_2m_min",
            "timezone": "auto",
            "forecast_days": 1,
        }
    )
    return http_get_json(f"https://api.open-meteo.com/v1/forecast?{query}")


# 步骤 12：把天气结果写成中文说明
def format_weather(place_name: str, payload: dict) -> str:
    # 步骤 1：读取当前天气和今日温度范围
    current = payload["current"]
    daily = payload.get("daily") or {}
    code = int(current["weather_code"])
    # 步骤 2：拼出天气说明
    lines = [
        f"地点: {place_name}",
        f"天气: {_WEATHER_LABELS.get(code, '未知')}",
        f"气温: {current['temperature_2m']}°C",
        f"体感: {current['apparent_temperature']}°C",
        f"湿度: {current['relative_humidity_2m']}%",
        f"风速: {current['wind_speed_10m']} km/h",
        f"降水: {current['precipitation']} mm",
    ]
    highs = daily.get("temperature_2m_max") or []
    lows = daily.get("temperature_2m_min") or []
    if highs and lows:
        lines.append(f"今日最高/最低: {highs[0]}°C / {lows[0]}°C")
    lines.append("数据来源: Open-Meteo")
    return "\n".join(lines)


# 步骤 13：确定地点并查询天气
def lookup_weather(place: str) -> str:
    # 步骤 1：有地名就编码，否则使用本机定位
    place = place.strip()
    if place:
        located = geocode_place(place)
        name = located["name"]
        latitude = located["latitude"]
        longitude = located["longitude"]
    else:
        payload = read_windows_location()
        latitude = payload.get("latitude")
        longitude = payload.get("longitude")
        if payload.get("is_unknown") or latitude is None or longitude is None:
            return format_location(payload)
        name = "当前位置"
        latitude = float(latitude)
        longitude = float(longitude)
    # 步骤 2：请求并格式化天气
    return format_weather(name, fetch_forecast(latitude, longitude))


# 步骤 14：注册 Agent 可调用的工具
@tool
def get_current_time() -> str:
    """返回当前本地日期和时间，格式为 ISO 8601。"""
    return datetime.now().astimezone().isoformat(timespec="seconds")


@tool
def calculate(expression: str) -> str:
    """计算算术表达式。支持 + - * / // % ** 和括号，例如 (2 + 3) * 4。"""
    return evaluate_expression(expression)


@tool
def get_current_location() -> str:
    """通过本机 Windows 定位服务读取当前地理位置，返回纬度和经度。"""
    try:
        # 步骤 1：读取本机定位
        payload = read_windows_location()
        # 步骤 2：格式化成中文说明
        return format_location(payload)
    except (OSError, subprocess.TimeoutExpired, json.JSONDecodeError, RuntimeError) as exc:
        # 步骤 3：调用失败时返回原因
        return f"无法获取当前位置：{exc}"


@tool
def get_weather(place: str = "") -> str:
    """查询当前天气。place 填写城市或地区名，例如北京、上海。留空则查询本机当前位置。"""
    try:
        # 步骤 1：按地点查询天气
        return lookup_weather(place)
    except (
        LookupError,
        OSError,
        urllib.error.URLError,
        TimeoutError,
        subprocess.TimeoutExpired,
        json.JSONDecodeError,
        RuntimeError,
    ) as exc:
        # 步骤 2：调用失败时返回原因
        return f"无法获取天气：{exc}"
