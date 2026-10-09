"""Tools the agent can call."""

from __future__ import annotations

import ast
import json
import operator
import subprocess
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


# 步骤 3：按节点类型递归求值，拒绝白名单以外的语法
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


# 步骤 4：把整段表达式算成文本
def evaluate_expression(expression: str) -> str:
    # 步骤 1：解析成语法树
    tree = ast.parse(expression, mode="eval")
    # 步骤 2：按白名单求值
    value = _eval_node(tree.body)
    # 步骤 3：整数结果去掉小数点
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value)


# 步骤 5：向 Windows 读取当前定位
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


# 步骤 6：把定位结果写成中文说明
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


# 步骤 7：注册 Agent 可调用的工具
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
