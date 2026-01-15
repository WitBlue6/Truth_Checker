import os
import json
import requests
import logging

logger = logging.getLogger(__name__)

# 从config模块导入配置加载函数
from aichecker.config import load_model_config, load_agent_config, load_mcp_config
from aichecker.tools import TOOL_REGISTRY, execute_tool

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
        tools = []
        agent_key = agent_name
        
        if ("available_tools" in agent_config[agent_key]):
            logger.info(f"为 {agent_name} 代理添加工具...")
            
            for tool_name in agent_config[agent_key]["available_tools"]:
                if tool_name in TOOL_REGISTRY:
                    tool_info = TOOL_REGISTRY[tool_name]
                    
                    # 构建工具定义
                    tool_def = {
                        "type": "function",
                        "function": {
                            "name": tool_info["name"],
                            "description": tool_info["description"],
                            "parameters": {
                                "type": "object",
                                "properties": tool_info["parameters"],
                                "required": tool_info["required"]
                            }
                        }
                    }
                    tools.append(tool_def)
        
        # 如果有工具，添加到payload
        if tools:
            payload["tools"] = tools
            payload["tool_choice"] = "auto"  # 让模型自动选择是否调用工具
        
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
            
            # 检查是否有工具调用
            if "tool_calls" in message:
                for tool_call in message["tool_calls"]:
                    function_name = tool_call["function"]["name"]
                    function_args = json.loads(tool_call["function"]["arguments"])
                    
                    logger.info(f"检测到工具调用: {function_name}")
                    logger.info(f"模型调用的工具参数: {json.dumps(function_args, ensure_ascii=False)}")
                    
                    # 执行工具
                    tool_result = execute_tool(function_name, **function_args)
                    
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
                # 没有工具调用，直接获取结果
                logger.info(f"=== 代理 {agent_name} 调用完成 ===")
                logger.info(f"响应内容:\n{message['content']}")
                return message["content"]
        
    except Exception as e:
        logger.error(f"=== 代理 {agent_name} 调用失败 ===")
        logger.error(f"错误信息: {str(e)}")
        raise