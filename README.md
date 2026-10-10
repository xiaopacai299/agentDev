# agentdev

一个最小可运行的 LangChain Agent。命令行对话，带两个工具：当前时间和四则运算。模型走 OpenAI 兼容接口，可以接官方 OpenAI，也可以接 DeepSeek 等兼容服务。

## 环境

- Python 3.11 及以上（本机使用 3.13）
- 虚拟环境：项目内 `.venv`
- 依赖：`langchain`、`langchain-openai`、`python-dotenv`

## 安装

```powershell
py -3.13 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -U pip
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
```

## 配置

复制 `.env.example` 为 `.env`，填入密钥。

官方 OpenAI：

```env
OPENAI_API_KEY=sk-...
MODEL=gpt-4o-mini
```

DeepSeek：

```env
OPENAI_API_KEY=sk-...
OPENAI_BASE_URL=https://api.deepseek.com
MODEL=deepseek-chat
```

## 运行

```powershell
.\.venv\Scripts\agent.exe
```

或：

```powershell
.\.venv\Scripts\python.exe -m agentdev.cli
```

两层怎么划分、怎样新增业务 Agent，见 [docs/architecture.md](docs/architecture.md)。

输入 `exit` 退出，输入 `new` 清空已保存的会话。

每一轮会先规划步骤，再调用工具，并把状态写到 `.agent/session.json`。下次启动会恢复这次会话。

## 测试

工具不依赖模型密钥：

```powershell
.\.venv\Scripts\python.exe -m pytest
```

## 目录

```text
src/agentdev/runtime/          运行时：状态、模型、工具循环、派生调度
src/agentdev/agents/assistant/ 业务 Agent：提示词、工具和协作图
src/agentdev/cli.py            转发到助手的命令行入口
```
