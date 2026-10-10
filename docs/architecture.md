# 运行时与业务 Agent

这个仓库分成两层。运行时给所有 Agent 共用。每个业务自己带提示词、工具和协作方式，放在 `agents` 下面。

现在只有一个业务 Agent：命令行助手 `assistant`。下一个业务在 `src/agentdev/agents/` 里新增一个包，不要改运行时的派生规则，也不要往助手的工具列表里塞无关能力。

## 两层各管什么

运行时负责和具体业务无关的执行机制：

- 读取模型配置，创建聊天模型
- 保存和恢复会话
- 让一个 Agent 在自己的工具循环里调用工具
- 只允许主循环派生子 Agent，并发最多 3 个，满了就在路由层拒绝
- 中心任务表只由主循环改写，子 Agent 只返回字符串

业务 Agent 负责这个产品要做什么：

- 系统提示词，以及规划、检索、计算、工程、写作、审校各自的提示词
- 这个助手可以调用的工具：时间、位置、天气、算术、读文件、写文件、改文件、执行命令
- 怎样把用户目标拆成子任务，审校不通过时怎样退回规划

运行时不导入 `agents`。业务 Agent 可以导入运行时。

## 目录

```text
src/agentdev/
  cli.py                         转发给助手的命令行入口
  runtime/
    config.py                    环境变量和项目根目录
    model.py                     创建模型，提取回复文本
    state.py                     会话状态和中心任务表的一行
    memory.py                    把会话写到 .agent/session.json
    loop.py                      单个 Agent 的工具循环
    orchestrator.py              派生、并发上限、并行汇合
  agents/
    assistant/
      agent.py                   助手的提示词和工具清单
      tools.py                   时间、位置、天气、算术
      workspace.py               文件和命令
      planning.py                单 Agent 规划
      graph.py                   这个助手的协作图
      cli.py                     命令行对话
```

## 一轮对话怎么走

用户输入进入 `agents/assistant/cli.py`，由 `graph.py` 规划本轮任务。检索、计算、工程互不依赖，交给 `runtime/orchestrator.py` 并行执行。主循环挂起，等它们全部返回，再把结果写进任务表。写作和审校要等这些结果，所以留在助手自己的图里。审校不通过时回到规划。

子 Agent 拿到的工具列表里没有派生入口。即使有代码调用 `route_spawn`，调用方不是主循环时也会整批拒绝。

## 新增一个业务 Agent

1. 在 `src/agentdev/agents/` 下新建包，例如 `support`。
2. 在这个包里写提示词、工具，以及需要的协作图。
3. 工具循环、会话、模型和 `run_workers` 从 `agentdev.runtime` 引入。
4. 不要把新业务的工具加进 `assistant` 的 `AGENT_TOOLS`。
5. 权限差很多时再单独部署，仍然引用同一套运行时。例如能执行命令的助手，和只能查询业务接口的客服，不要共用同一份工具清单。

协作图只有在这个业务真的需要多个子 Agent 时才写。只有一个提示词和一组工具时，调用 `runtime.loop` 即可。
