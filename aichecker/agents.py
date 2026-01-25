import os
import json
import requests
import logging
from collections import defaultdict

logger = logging.getLogger(__name__)

# 从config模块导入配置加载函数
from aichecker.config import load_model_config, load_agent_config, load_mcp_config
from aichecker.tools import TOOL_REGISTRY, execute_tool, get_tools_by_group
from aichecker.memory import load_memory, save_memory
from aichecker.task_manager import get_task

# 调用AI代理（带记忆功能）
def call_agent_with_memory(agent_name, prompt, memory_id=None, max_tool_calls_per_round=5, max_repeated_tool_calls=3):
    """
    调用指定的AI代理（带记忆功能）
    
    参数:
    - agent_name: 代理名称
    - prompt: 提示文本
    - memory_id: 记忆ID（可选）
    - max_tool_calls_per_round: 每轮对话（用户请求到助手最终响应）的最大工具调用次数，默认为5
    - max_repeated_tool_calls: 连续重复调用相同工具的最大次数，默认为3
    
    返回:
    - str: AI代理的响应
    """
    try:
        # 如果没有提供记忆ID，使用默认的随机ID
        if not memory_id:
            import uuid
            memory_id = f"memory_{uuid.uuid4().hex[:8]}"
            logger.debug(f"未提供记忆ID，生成新的记忆ID: {memory_id}")
        
        logger.info(f"=== 开始调用代理: {agent_name} (记忆ID: {memory_id}) ===")
        
        # 加载配置
        logger.debug(f"加载 {agent_name} 代理配置...")
        config = load_model_config()
        agent_config = load_agent_config(agent_name)
        mcp_config = load_mcp_config()
        
        # 构建请求数据
        model_config = config["models"]["default"]
        logger.debug(f"使用模型: {model_config['name']}")
        
        # 加载记忆
        memory_content = load_memory(memory_id)
        
        # 构建消息历史，包括系统提示和记忆内容
        system_prompt = agent_config[agent_name]["system_prompt"]

        # 添加可用MCP工具信息
        if "available_mcp_servers" in agent_config[agent_name]:
            available_mcp_servers = agent_config[agent_name]["available_mcp_servers"]
            if available_mcp_servers:
                system_prompt += f"\n\n可用的MCP工具列表：{', '.join(available_mcp_servers)}"

        messages = [
            {"role": "system", "content": system_prompt}
        ]
        
        # 添加历史记忆
        messages.extend(memory_content)

        # 获取任务列表
        task_list, task_list_id = get_task(prompt, messages, model_config, memory_id)
        # 将任务列表添加到系统消息中
        messages.append({
            "role": "system", 
            "content": f"以下是当前的任务列表，请按照任务列表逐步完成用户请求。在执行过程中，请根据实际进展及时更新任务状态。\n\n"
                       f"开始执行任务前，请先将需要执行的任务的状态更新为'进行中'。完成一个任务后，请及时将其状态更新为'已完成'并记录结果，然后将下一个任务的状态更新为'进行中'。\n\n"
                       f"每个任务都有一个唯一的任务ID，你需要根据任务ID来更新任务状态。任务ID从1开始递增，属于整型数值。\n\n"
                       f"完成用户请求后，请重新检查用户要求，直接或间接回答用户问题，并总结你做了什么工作，直接告诉用户。\n\n"
                       f"任务列表id是字符串类型，当前任务列表id: {task_list_id}\n\n",
            "task_list": task_list
        })
        
        # 添加当前用户提示
        messages.append({"role": "user", "content": prompt})
        memory_content.append({"role": "user", "content": prompt})
        
        payload = {
            "model": model_config["name"],
            "messages": messages,
            "max_tokens": model_config["max_tokens"],
            "temperature": model_config["temperature"]
        }
        
        # 检查是否需要工具调用，如果需要才添加tools参数
        tools = []
        agent_key = agent_name
        
        if ("available_tools" in agent_config[agent_key]):
            logger.debug(f"为 {agent_name} 代理添加工具...")
            
            for tool_spec in agent_config[agent_key]["available_tools"]:
                # 检查是否是工具组
                if tool_spec.endswith("-tools"):
                    # 加载工具组中的所有工具
                    group_tools = get_tools_by_group(tool_spec)
                    for tool_name, tool_info in group_tools.items():
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
                elif tool_spec in TOOL_REGISTRY:
                    # 单个工具
                    tool_info = TOOL_REGISTRY[tool_spec]
                    
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
        logger.debug(f"为 {agent_name} 代理添加的工具: {tools}")
        if tools:
            payload["tools"] = tools
            payload["tool_choice"] = "auto"  # 让模型自动选择是否调用工具
        
        # 处理工具调用的循环
        call_count = 0
        tool_call_count = 0
        
        # 跟踪工具调用历史，防止重复调用
        tool_call_history = []
        repeated_tool_calls = defaultdict(int)
        
        while True:
            call_count += 1
            logger.debug(f"=== 发送第 {call_count} 次请求到 AI 模型 ===")
            
            # 发送请求到AI模型API
            logger.debug(f"请求URL: {model_config['base_url']}/chat/completions")
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
                # 增加工具调用计数
                tool_call_count += 1
                
                # 检查本对话轮次的工具调用次数是否超过限制
                if tool_call_count > max_tool_calls_per_round:
                    logger.warning(f"本轮对话工具调用次数超过限制 ({max_tool_calls_per_round})，建议简化请求")
                    # 不直接终止，而是继续，但提示模型简化
                    payload["messages"].append(message)
                    payload["messages"].append({
                        "role": "tool",
                        "tool_call_id": "system_warning",
                        "name": "system",
                        "content": f"工具调用次数已达本轮限制 ({max_tool_calls_per_round})，请尝试直接回答用户问题，或使用更精简的工具调用序列。"
                    })
                    continue
                
                for tool_call in message["tool_calls"]:
                    function_name = tool_call["function"]["name"]
                    function_args = json.loads(tool_call["function"]["arguments"])
                    
                    # 创建工具调用标识（用于检测重复调用）
                    tool_call_key = f"{function_name}:{json.dumps(function_args, sort_keys=True)}"
                    
                    # 检查是否重复调用相同工具和参数
                    if tool_call_history and tool_call_history[-1] == tool_call_key:
                        repeated_tool_calls[tool_call_key] += 1
                        if repeated_tool_calls[tool_call_key] >= max_repeated_tool_calls:
                            logger.warning(f"重复调用相同工具和参数超过限制 ({max_repeated_tool_calls})，可能存在无限循环")
                            # 不直接终止，而是提示模型
                            payload["messages"].append(message)
                            payload["messages"].append({
                                "role": "tool",
                                "tool_call_id": "system_warning",
                                "name": "system",
                                "content": f"重复调用相同工具和参数已达限制 ({max_repeated_tool_calls})，可能存在无限循环。请尝试不同的工具或参数，或直接回答用户问题。"
                            })
                            # 重置重复计数
                            repeated_tool_calls[tool_call_key] = 0
                            continue
                    else:
                        # 新的工具调用，重置重复计数
                        repeated_tool_calls[tool_call_key] = 1
                    
                    # 添加到工具调用历史
                    tool_call_history.append(tool_call_key)
                    
                    logger.debug(f"检测到工具调用: {function_name}")
                    logger.info(f"模型调用的工具参数: {json.dumps(function_args, ensure_ascii=False)}")
                    
                    # 执行工具
                    tool_result = execute_tool(function_name, **function_args)
                    
                    logger.info(f"工具执行完成，结果:\n{tool_result}")
                    
                    # 将工具调用结果添加到对话历史
                    logger.debug(f"将工具调用结果添加到对话历史")
                    payload["messages"].append(message)
                    payload["messages"].append({
                        "role": "tool",
                        "tool_call_id": tool_call["id"],
                        "name": function_name,
                        "content": tool_result
                    })
                    # 更新记忆，保留工具返回结果
                    memory_content.append({
                        "role": "tool",
                        "content": f"工具调用 {function_name} \n参数{json.dumps(function_args, ensure_ascii=False)}\n返回结果:\n{tool_result[:150]}..."
                    })
            else:
                # 没有工具调用，直接获取结果
                logger.info(f"=== 代理 {agent_name} 调用完成 ===")
                logger.info(f"响应内容:\n{message['content']}")
                
                # 更新记忆（只保留用户和系统的消息，不保留工具调用的中间结果）
                updated_memory = memory_content
                
                # 只添加当前对话的用户和助手消息到记忆
                updated_memory.append({"role": "assistant", "content": message["content"]})
                
                # 保存更新后的记忆
                save_memory(memory_id, updated_memory)
                
                # 输出记忆ID供用户参考
                logger.info(f"本次对话使用的记忆ID: {memory_id}")
                
                return message["content"]
        
    except Exception as e:
        logger.error(f"=== 代理 {agent_name} 调用失败 ===")
        logger.error(f"错误信息: {str(e)}")
        raise

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