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

## 发给别人用

代码放 GitHub，方便看源码和提问题。别人用 `pip` / `pipx` 安装时，包要传到 [PyPI](https://pypi.org)。PyPI 是下载处，GitHub 不是。

发布前在 [pypi.org](https://pypi.org/account/register/) 注册账号，安装 `twine`，按 PyPI 的说明上传这个项目打出来的包。发布到 PyPI 的名字是 `wkagent`。`agentdev` 这个名字已经被别人占用了。

别人装好之后：

```powershell
pipx install wkagent
wkagent
```

第一次运行会在终端里选择服务商并输入 API Key。也可以先执行 `wkagent setup`。支持 OpenAI、DeepSeek、Kimi、通义千问、智谱 GLM、OpenRouter，以及任何 OpenAI 兼容接口。密钥写在对方自己的 `~/.agent/.env`，不会包进代码里。

## 配置

开发时仍可以在项目目录放 `.env`，它会覆盖主目录里的同名配置。日常使用不必手写这个文件，用 `wkagent setup` 即可。

## 安装到终端

开发时仍用上面的虚拟环境。要在任意目录直接运行，用 pipx 装一次：

```powershell
py -3.13 -m pip install pipx
py -3.13 -m pipx ensurepath
pipx install --python py -3.13 .
```

新开一个终端后，进入某个项目目录，执行 `wkagent`。

密钥放在用户主目录 `~/.agent/.env`。当前目录如果也有 `.env`，其中的模型名会覆盖主目录的配置。会话、项目记忆和引用写在当前目录的 `.agent/`。用户记忆和个人反馈写在 `~/.agent/memory/`。

## 运行

在仓库里开发时：

```powershell
.\.venv\Scripts\wkagent.exe
```

或：

```powershell
.\.venv\Scripts\python.exe -m agentdev.cli
```

两层怎么划分、怎样新增业务 Agent，见 [docs/architecture.md](docs/architecture.md)。

输入 `/help` 查看命令，`/model` 更换模型，`/status` 查看当前接通的模型，`/new` 清空会话，`/exit` 退出。

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
