import os
import json
import requests
import logging

logger = logging.getLogger(__name__)

# 从config模块导入配置加载函数
from aichecker.config import load_model_config, load_agent_config, load_mcp_config
from aichecker.tools import tavily_search, execute_mcp_tool

# 调用AI代理
def call_agent(agent_name, prompt):
    """
    调用指定的AI代理
    
    参数:
    - agent_name: 代理名称
    - prompt: 提示文本
    
    返回:
    - str: AI代理的响应
    """
    try:
        logger.info(f"=== 开始调用代理: {agent_name} ===")
        
        # 加载配置
        logger.info(f"加载 {agent_name} 代理配置...")
        config = load_model_config()
        agent_config = load_agent_config(agent_name)
        mcp_config = load_mcp_config()
        
        # 构建请求数据 - 初始不包含tools参数
        model_config = config["models"]["default"]
        logger.info(f"使用模型: {model_config['name']}")
        
        payload = {
            "model": model_config["name"],
            "messages": [
                {"role": "system", "content": agent_config[agent_name]["system_prompt"]},
                {"role": "user", "content": prompt}
            ],
            "max_tokens": model_config["max_tokens"],
            "temperature": model_config["temperature"]
        }
        
        # 检查是否需要工具调用，如果需要才添加tools参数
        agent_key = list(agent_config.keys())[0]  # 获取代理配置的键
        if ("available_tools" in agent_config[agent_name] and "use_mcp_tool" in agent_config[agent_name]["available_tools"]) or "available_mcp_servers" in agent_config[agent_key]:
            logger.info(f"{agent_name} 代理启用了工具调用功能")
            payload["tools"] = [
                {
                    "type": "function",
                    "function": {
                        "name": "use_mcp_tool",
                        "description": "调用MCP服务器提供的外部工具",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                 "tool_name": {
                                    "type": "string",
                                    "description": "MCP服务器名称"
                                },
                                "query": {
                                    "type": "string",
                                    "description": "搜索查询词"
                                },
                                "urls": {
                                    "type": "array",
                                    "items": {
                                        "type": "string"
                                    },
                                    "description": "要提取内容的URL列表"
                                },
                                "extract_depth": {
                                    "type": "string",
                                    "description": "提取深度: basic或advanced",
                                    "enum": ["basic", "advanced"]
                                },
                                "format": {
                                    "type": "string",
                                    "description": "输出格式: markdown或text",
                                    "enum": ["markdown", "text"]
                                }
                            },
                            "required": ["server_name"]
                        }
                    }
                }
            ]
        
        # 处理工具调用的循环
        call_count = 0
        while True:
            call_count += 1
            logger.info(f"=== 发送第 {call_count} 次请求到 AI 模型 ===")
            
            # 发送请求到AI模型API
            logger.info(f"请求URL: {model_config['base_url']}/chat/completions")
            response = requests.post(
                f"{model_config['base_url']}/chat/completions",
                headers={
                    "Authorization": f"Bearer {model_config['api_key']}",
                    "Content-Type": "application/json"
                },
                json=payload
            )
            response.raise_for_status()
            
            # 解析响应
            result = response.json()
            message = result["choices"][0]["message"]
            
            logger.info(f"收到响应，角色: {message['role']}")
            
            # 检查是否有工具调用
            if "tool_calls" in message:
                tool_call = message["tool_calls"][0]
                function_name = tool_call["function"]["name"]
                function_args = json.loads(tool_call["function"]["arguments"])
                
                logger.info(f"检测到工具调用: {function_name}")
                logger.info(f"模型调用的工具参数: {json.dumps(function_args, ensure_ascii=False)}")
                
                if function_name == "use_mcp_tool":
                    server_name = function_args.get("server_name") or function_args.get("tool_name", "ddg-search")
                    query = function_args.get("query")
                    urls = function_args.get("urls")
                    extract_depth = function_args.get("extract_depth", "advanced")
                    format = function_args.get("format", "markdown")
                    
                    # 验证server_name是否为有效的MCP工具名称
                    valid_mcp_tools = list(mcp_config['mcpServers'].keys())
                    if server_name not in valid_mcp_tools:
                        logger.warning(f"无效的MCP工具名称: '{server_name}', 有效工具: {valid_mcp_tools}")
                        # 使用默认工具名称
                        server_name = "ddg-search"
                        logger.warning(f"已自动切换到默认工具: {server_name}")
                    
                    # 调用工具函数
                    logger.info(f"开始执行工具: {function_name}")
                    
                    # 如果是tavily工具，使用原有的tavily_search函数保持兼容性
                    if server_name == "tavily":
                        tool_result = tavily_search(query, urls, extract_depth, format)
                    elif server_name == "ddg-search":
                        # 处理DDG Search工具的特殊情况
                        if query:
                            # 使用search方法
                            tool_input = {
                                "tool_name": "search",
                                "query": query,
                                "max_results": 10  # 默认返回10个结果
                            }
                            logger.info(f"工具输入: {json.dumps(tool_input, ensure_ascii=False)}")
                            tool_result = execute_mcp_tool(server_name, tool_input)
                        elif urls:
                            # 使用fetch_content方法，逐个处理URL
                            results = []
                            for url in urls:
                                tool_input = {
                                    "tool_name": "fetch_content",
                                    "url": url
                                }
                                logger.info(f"工具输入: {json.dumps(tool_input, ensure_ascii=False)}")
                                url_result = execute_mcp_tool(server_name, tool_input)
                                results.append(f"URL: {url}\nContent:\n{url_result}")
                            tool_result = "\n" + "\n" + "\n".join(results) + "\n"
                        else:
                            tool_result = "错误：DDG搜索需要提供query或url参数"
                    else:
                        # 其他工具的默认处理
                        tool_input = {}
                        if query:
                            tool_input["query"] = query
                        if urls:
                            tool_input["urls"] = urls
                        
                        logger.info(f"工具输入: {json.dumps(tool_input, ensure_ascii=False)}")
                        tool_result = execute_mcp_tool(server_name, tool_input)
                    
                    logger.info(f"工具执行完成，结果:\n{tool_result}")
                    
                    # 将工具调用结果添加到对话历史
                    logger.info(f"将工具调用结果添加到对话历史")
                    payload["messages"].append(message)
                    payload["messages"].append({
                        "role": "tool",
                        "tool_call_id": tool_call["id"],
                        "name": function_name,
                        "content": tool_result
                    })
                else:
                    logger.warning(f"未知的工具: {function_name}")
                    break
            else:
                # 没有工具调用，直接获取结果
                logger.info(f"=== 代理 {agent_name} 调用完成 ===")
                logger.info(f"响应内容:\n{message['content']}")
                return message["content"]
        
        # 返回AI响应
        logger.info(f"=== 代理 {agent_name} 调用完成 ===")
        logger.info(f"响应内容:\n{message['content']}")
        return message["content"]
        
    except Exception as e:
        logger.error(f"=== 代理 {agent_name} 调用失败 ===")
        logger.error(f"错误信息: {str(e)}")
        raise