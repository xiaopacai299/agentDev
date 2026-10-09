---
name: module-layout
description: >-
  按代码规范组织 Python 模块：常量与内部方法放在上面，对外入口集中放在下面。
  Use when writing or rearranging Python modules, tools, or feature files,
  or when the user mentions 代码规范, 工具放一起, 方法放上面, or module layout.
---

# 模块布局

一个模块只分上下两段。先读上面能知道实现，再读下面能知道对外提供什么。

## 上面：实现

按这个顺序放置：

1. import
2. 常量、脚本、映射表
3. 被入口调用的方法

内部方法之间不要插入对外入口。

## 下面：入口

模块对外的入口放在文件底部，并集中在一起。例如 Agent 工具、`build_agent`、命令行 `main`。

## 不要做的事

- 不要把一个工具的实现插在两个工具中间。
- 不要为了布局去拆文件；一个功能模块仍然放在一个文件里。
- import 和单行常量不算需要单独挪位的入口。
