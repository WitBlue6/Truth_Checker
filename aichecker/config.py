import os
import json
from dotenv import load_dotenv
from aichecker.mcp_host import start_all_mcp_servers, stop_all_mcp_servers

load_dotenv()

def get_config_path(filename: str) -> str:
    return os.path.join(os.path.dirname(__file__), "..", "config", filename)

# 加载模型配置
def load_model_config():
    config_path = get_config_path("models.json")
    with open(config_path, "r") as f:
        config = json.load(f)
    # 读取环境变量
    if os.getenv("AI_MODEL_NAME"):
        config["models"]["default"]["name"] = os.getenv("AI_MODEL_NAME")
    if os.getenv("AI_MODEL_API_KEY"):
        config["models"]["default"]["api_key"] = os.getenv("AI_MODEL_API_KEY")
    if os.getenv("AI_MODEL_BASE_URL"):
        config["models"]["default"]["base_url"] = os.getenv("AI_MODEL_BASE_URL")
    return config

# 加载工具配置
def load_tools_config():
    tool_path = get_config_path(f"tools/tools.json")
    with open(tool_path, "r") as f:
        tool_config = json.load(f)
    return tool_config

# 加载MCP配置
def load_mcp_config():
    mcp_path = get_config_path(f"tools/mcp.json")
    with open(mcp_path, "r") as f:
        mcp_config = json.load(f)
    # 读取环境变量
    if os.getenv("TAVILY_API_KEY"):
        # 检查是否有tavily配置
        mcp_servers = mcp_config.get("mcpServers", {})
        if "tavily" in mcp_servers:
            tavily_server = mcp_servers["tavily"]
            if "env" in tavily_server:
                tavily_server["env"]["TAVILY_API_KEY"] = os.getenv("TAVILY_API_KEY")
    return mcp_config

# 加载代理配置
def load_agent_config(agent_name: str):
    agent_path = get_config_path(f"agents/{agent_name}.json")
    with open(agent_path, "r") as f:
        agent_config = json.load(f)
    # 加载工具配置
    tool_config = load_tools_config()
    
    agent_key = list(agent_config.keys())[0]  # 获取代理配置的键
    if "available_tools" in agent_config[agent_key]:
        updated_tools = []
        for tool in agent_config[agent_key]["available_tools"]:
            if tool in tool_config["tool_groups"]:
                group_tools = tool_config["tool_groups"][tool]["tools"]
                updated_tools.extend(group_tools)
                # 处理mcp-tools
                if tool == "mcp-tools":
                    mcp_config = load_mcp_config()
                    available_mcp_servers = []
                    mcp_tools_info = {}  # server_name -> [tool_names]
                    for server_name, server_cfg in mcp_config.get("mcpServers", {}).items():
                        available_mcp_servers.append(server_name)
                        # 启动临时 MCP Host 获取工具列表
                        temp_host = start_all_mcp_servers({"mcpServers": {server_name: server_cfg}})
                        tools_on_server = list(temp_host.tools.keys())  # full_tool_name
                        # 只取实际工具名
                        tool_names = [t.split(".")[1] if "." in t else t for t in tools_on_server]
                        mcp_tools_info[server_name] = tool_names
                        stop_all_mcp_servers(temp_host)
                        
                    agent_config[agent_key]["available_mcp_servers"] = available_mcp_servers
                    agent_config[agent_key]["available_mcp_tools"] = mcp_tools_info
            else:
                updated_tools.append(tool)
        agent_config[agent_key]["available_tools"] = updated_tools
    return agent_config
