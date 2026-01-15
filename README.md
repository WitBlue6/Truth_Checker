# Truth Checker 项目说明

## 项目概述

Truth Checker 是一个基于AI的真伪验证系统，旨在通过多维度分析和对比，帮助用户判断信息的真实性。该系统结合了自然语言处理、知识图谱和可信来源验证技术，适用于新闻、社交媒体内容、学术论文等各类信息的真伪检测。

## 主要功能

- **文本真实性分析**：对输入文本进行语义理解与逻辑一致性检查。
- **来源可信度评估**：根据发布机构、历史记录和权威性评分来源可信度。
- **跨平台比对**：自动检索多个公开数据源，进行事实交叉验证。
- **生成报告**：输出结构化报告，包含置信度评分、证据链和改进建议。
- **可扩展提示模板**：支持自定义提示（prompts），便于适应不同领域需求。

## 项目结构

```
truth_checker/
├── aichecker/               # 核心AI验证模块
│   ├── __init__.py
│   └── checker.py            # 真实性检测主逻辑
├── config/                  # 配置文件目录
│   ├── settings.json       # 系统配置
│   └── api_keys.json       # API密钥管理
├── prompts/                 # 提示模板目录
│   ├── fact_check_prompt.txt
│   └── source_relevance_prompt.txt
├── output/                  # 输出结果存储目录
├── main.py                  # 入口脚本
├── update_prompts.py        # 提示模板更新工具
├── pyproject.toml           # 项目依赖与构建配置
├── README.md                # 项目说明文档
├── .gitignore               # Git忽略规则
└── .env                     # 环境变量配置
```

## 快速开始

1. 安装依赖：
   ```bash
   pip install -r requirements.txt
   ```

2. 配置环境变量：
   将API密钥等敏感信息写入 `.env` 文件。

3. 运行主程序：
   ```bash
   python main.py "这是一条待验证的信息"
   ```

4. 查看输出结果：
   结果将保存在 `output/` 目录下，包括原始输入、分析过程和最终结论。

## 贡献指南

欢迎提交 Pull Request 来改进项目！请遵循以下步骤：

- Fork 项目仓库
- 创建新分支（`feature/xxx` 或 `fix/xxx`）
- 提交你的更改
- 推送到分支
- 提交 Pull Request

## 许可证

MIT License

---

> 项目由 AI 技术驱动，致力于提升信息可信度，推动理性讨论。