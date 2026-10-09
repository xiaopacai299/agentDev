---
name: feature-module-comments
description: >-
  给功能模块的每个主要代码块加上带步骤序号的简体中文注释。
  Use when creating or editing a feature module, or when the user mentions
  功能模块, 中文注释, 步骤序号, or step comments.
---

# 功能模块注释

功能模块里的每个主要块，都在块的正上方写一条简体中文注释，并标上步骤序号。

## 格式

```python
# 步骤 1：读取本机定位
payload = read_windows_location()
```

- 固定以 `# 步骤 N：` 开头，N 从 1 连续递增。
- 冒号后面用一句中文说明这个块做什么。
- 注释写在块的上一行，不要写在行尾。

## 两层编号

模块和函数各自从步骤 1 编号，互不接续。

1. **模块级**：文件从上到下，每一段主要职责编号。一段可以是一组常量、一个内部方法，或底部集中的那组入口。
2. **函数级**：函数里有两个及以上先后阶段时，在函数内部从步骤 1 重新编号。

只有一个语句的函数不再拆内部步骤。并列分支不是先后步骤，不要编成 1、2、3；模块级的那一条注释已经够用。

## 不注释的内容

- import
- 测试文件
- 纯样板，例如 `if __name__ == "__main__"`

## 示例

```python
# 步骤 1：把表达式算成文本
def evaluate_expression(expression: str) -> str:
    # 步骤 1：解析成语法树
    tree = ast.parse(expression, mode="eval")
    # 步骤 2：按白名单求值
    value = _eval_node(tree.body)
    # 步骤 3：整数结果去掉小数点
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value)
```
