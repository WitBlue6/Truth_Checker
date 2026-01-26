# Truth Checker

## 项目概述

Truth Checker 是一个基于AI的真伪验证系统，旨在通过多维度分析和对比，帮助用户判断信息的真实性。该系统结合了MCP、Agent调用和可信来源验证技术，适用于新闻、社交媒体内容、学术论文等各类信息的真伪检测。

## 主要功能

- **文本真实性分析**：对输入文本进行语义理解与逻辑一致性检查。
- **来源可信度评估**：根据发布机构、历史记录和权威性评分来源可信度。
- **跨平台比对**：自动检索多个公开数据源，进行事实交叉验证。
- **生成报告**：输出结构化报告，包含置信度评分、证据链和改进建议。
- **可扩展提示模板**：支持自定义提示（prompts），便于适应不同领域需求。
- **MCP工具集成**：通过MCP Host集成外部工具（如tavily-search），扩展系统功能。

## 项目结构

```plaintext
truth_checker/
├── aichecker/               # 核心AI验证模块
│   ├── __pycache__/         # Python编译缓存
│   ├── agents.py            # AI代理实现
│   ├── config.py            # 配置加载与管理
│   ├── mcp_host.py          # MCP Host工具集成
│   ├── memory.py            # 记忆管理
│   ├── task_manager.py      # 任务管理
│   ├── tools.py             # 工具实现
│   └── workflow.py          # 工作流管理
├── config/                  # 配置文件目录
│   ├── agents/              # 代理配置
│   ├── models.json          # 模型配置
│   └── tools/               # 工具配置
├── output/                  # 输出结果存储目录
│   ├── memories/            # 记忆存储
│   └── tasks/               # 任务结果
├── prompts/                 # 提示模板目录
├── tests/                   # 测试文件
├── main.py                  # 入口脚本
├── update_prompts.py        # 提示模板更新工具
├── pyproject.toml           # 项目依赖与构建配置
├── uv.lock                  # uv包管理器锁文件
├── README.md                # 项目说明文档
├── .gitignore               # Git忽略规则
├── .env                     # 环境变量配置
└── .venv/                   # 虚拟环境
```

**代码结构说明**
- aichecker/agents.py：实现代理调用逻辑，包括记忆管理和工具调用
- aichecker/config.py：加载和管理各类配置
- aichecker/mcp_host.py：实现MCP Host功能，支持外部工具集成
- aichecker/tools.py：实现各类工具，包括MCP工具的封装
- aichecker/workflow.py：管理验真工作流逻辑

## 快速开始

1. 安装依赖：
   ```bash
   uv sync
   ```

2. 配置环境变量：
   将API密钥等敏感信息写入 `.env` 文件。

3. 运行主程序：
   ```bash
   uv run main.py agent
   ```

4. 使用验真工具：
   ```bash
   uv run main.py check -d "<需要验真的信息>" -l "<可选的链接提供>"
   ```

5. 无头模式：
   ```bash
   uv run main.py agent -p "<用户提示词>"
   ```

## MCP工具集成
项目支持通过MCP Host集成外部工具，如tavily-search。使用前需要确保MCP服务器已配置并启动：
1. 配置MCP Host：
   在`config/tools/mcp.json`中配置MCP Host指令，例如tavily-search
```json
   {
    "mcpServers":{
        "tavily":{
            "command": "npx",
            "args":[
                "-y",
                "tavily-mcp@0.2.3"
            ],
            "env":{
                "TAVILY_API_KEY": "${TAVILY_API_KEY}"
            },
            "disabled": false,
            "alwaysAllow": []
        },
    }
}
```

2. 启动MCP服务
如需手动调用MCP服务，可在Python脚本中使用以下代码启动所有MCP服务器：
```python
from aichecker.mcp_host import start_all_mcp_servers, stop_all_mcp_servers

# 启动所有MCP服务器
start_all_mcp_servers()

# 使用完成后停止
stop_all_mcp_servers()
```

3. 调用MCP工具
在agent中已经实现MCP工具调用，如需手动调用，参考
```python
from aichecker.mcp_host import call_mcp_tool

# 调用tavily-search工具
result = call_mcp_tool("tavily", "tavily.tavily-search", {
    "query": "Truth Checker 项目",
    "max_results": 5
})
```

## Agent配置
在`config/agents/`目录下配置不同的agent，每个agent对应一个JSON文件，文件中包含该agent的配置信息，如模型、工具、提示模板等。

项目已包含多个AI代理，用于不同的验证任务：
- intent_classifier：意图分类
- truth_split：事实拆分
- link_searcher：链接搜索
- link_reader：链接内容读取
- link_summary：链接内容摘要
- truth_judge：事实判断
- final_truth：最终结论生成

## Prompt模板更新
项目提供`update_prompts.py`脚本，用于批量更新Prompt模板。运行以下命令即可更新所有模板：
```bash
uv run update_prompts.py
```

## 贡献指南

欢迎提交 Pull Request 来改进项目！请遵循以下步骤：

- Fork 项目仓库
- 创建新分支
- 提交你的更改
- 推送到分支
- 提交 Pull Request

## 许可证

MIT License

---