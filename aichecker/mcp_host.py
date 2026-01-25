import json
import os
import subprocess
import logging
import threading
import queue
import uuid
import time
from typing import Dict, List, Optional, Any

logger = logging.getLogger(__name__)

from aichecker.config import load_mcp_config, load_tools_config
from aichecker.tools import TOOL_REGISTRY, execute_tool


class MCPHost:
    """
    MCP Host 实现，用于管理 MCP 服务器和工具调用路由
    
    功能：
    1. 读取 MCP JSON 配置
    2. 使用 subprocess 启动 MCP 服务器
    3. 实现 MCP stdio 协议
    4. 执行 tool schema 注入
    5. 处理 tool call 路由
    """
    
    def __init__(self):
        """初始化 MCP Host"""
        self.mcp_config = load_mcp_config()
        self.tools_config = load_tools_config()
        self.mcp_servers = {}  # 存储启动的 MCP 服务器进程
        self.tool_schemas = {}  # 存储工具 schema
        self.request_responses = {}  # 存储请求的响应，键为request_id
        self.request_conditions = {}  # 存储请求的条件变量，键为request_id
        self.server_ready = {}  # 存储服务器是否就绪的状态
        self._initialize_tool_schemas()
        
    def _initialize_tool_schemas(self):
        """初始化工具 schema"""
        # 加载本地工具 schema
        for tool_name, tool_info in TOOL_REGISTRY.items():
            self.tool_schemas[tool_name] = {
                "name": tool_info["name"],
                "description": tool_info["description"],
                "parameters": tool_info["parameters"],
                "required": tool_info["required"]
            }
        
        # 加载工具组信息
        for group_name, group_info in self.tools_config["tool_groups"].items():
            if hasattr(self, f"_process_{group_name}_tools"):
                getattr(self, f"_process_{group_name}_tools")(group_info)
    
    def _process_mcp_tools(self, group_info: Dict):
        """处理 MCP 工具组"""
        # MCP 工具组需要特殊处理，因为它们是通过 MCP 服务器提供的
        pass
    
    def start_mcp_server(self, server_name: str) -> bool:
        """
        启动指定的 MCP 服务器
        
        参数:
            server_name: MCP 服务器名称
            
        返回:
            bool: 启动是否成功
        """
        if server_name in self.mcp_servers:
            logger.info(f"MCP 服务器 {server_name} 已经在运行")
            return True
        
        if server_name not in self.mcp_config["mcpServers"]:
            logger.error(f"未找到 MCP 服务器配置: {server_name}")
            return False
        
        server_config = self.mcp_config["mcpServers"][server_name]
        
        # 构建命令
        cmd = [server_config["command"]]
        cmd.extend(server_config.get("args", []))
        
        # 设置环境变量
        env = os.environ.copy()
        for key, value in server_config.get("env", {}).items():
            env[key] = value
        
        logger.info(f"启动 MCP 服务器: {cmd}")
        
        try:
            # 启动进程，使用管道进行通信
            process = subprocess.Popen(
                cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                env=env
            )
            
            # 创建线程处理输出
            output_thread = threading.Thread(
                target=self._process_mcp_output,
                args=(server_name, process.stdout),
                daemon=True
            )
            output_thread.start()
            
            # 创建线程处理错误
            error_thread = threading.Thread(
                target=self._process_mcp_error,
                args=(server_name, process.stderr),
                daemon=True
            )
            error_thread.start()
            
            # 存储服务器信息
            self.mcp_servers[server_name] = {
                "process": process,
                "input_queue": queue.Queue(),
                "output_thread": output_thread,
                "error_thread": error_thread,
                "running": True
            }
            
            # 标记服务器未就绪
            self.server_ready[server_name] = False
            
            # 等待服务器启动并发送就绪信号（最多等待5秒）
            max_wait_time = 5
            start_time = time.time()
            while not self.server_ready[server_name] and time.time() - start_time < max_wait_time:
                time.sleep(0.1)
            
            if not self.server_ready[server_name]:
                logger.warning(f"MCP 服务器 {server_name} 启动后未收到就绪信号，但仍将继续")
            
            # 执行 tool schema 注入
            if not self._inject_tool_schemas(server_name):
                logger.error(f"工具 schema 注入失败")
                return False
            
            logger.info(f"MCP 服务器 {server_name} 启动成功")
            return True
        except Exception as e:
            logger.error(f"启动 MCP 服务器 {server_name} 失败: {str(e)}")
            return False
    
    def stop_mcp_server(self, server_name: str) -> bool:
        """
        停止指定的 MCP 服务器
        
        参数:
            server_name: MCP 服务器名称
            
        返回:
            bool: 停止是否成功
        """
        if server_name not in self.mcp_servers:
            logger.info(f"MCP 服务器 {server_name} 未运行")
            return True
        
        server_info = self.mcp_servers[server_name]
        process = server_info["process"]
        
        try:
            # 发送停止信号（如果支持）
            try:
                process.stdin.close()
            except:
                pass
            
            # 等待进程终止，最多等待5秒
            process.wait(timeout=5)
            
            # 标记服务器为未运行
            server_info["running"] = False
            
            # 清理服务器信息
            del self.mcp_servers[server_name]
            if server_name in self.server_ready:
                del self.server_ready[server_name]
            
            logger.info(f"MCP 服务器 {server_name} 已停止")
            return True
        except subprocess.TimeoutExpired:
            # 超时，强制终止进程
            process.kill()
            logger.warning(f"MCP 服务器 {server_name} 超时，已强制终止")
        except Exception as e:
            logger.error(f"停止 MCP 服务器 {server_name} 失败: {str(e)}")
        
        # 清理服务器信息
        if server_name in self.mcp_servers:
            del self.mcp_servers[server_name]
        if server_name in self.server_ready:
            del self.server_ready[server_name]
        
        return False
    
    def stop_all_mcp_servers(self):
        """停止所有运行中的 MCP 服务器"""
        for server_name in list(self.mcp_servers.keys()):
            self.stop_mcp_server(server_name)
    
    def _process_mcp_output(self, server_name: str, stdout):
        """处理 MCP 服务器的标准输出"""
        try:
            buffer = ""
            while True:
                # 检查服务器是否仍在运行
                if server_name not in self.mcp_servers or not self.mcp_servers[server_name]["running"]:
                    break
                
                line = stdout.readline()
                if not line:
                    break
                
                logger.debug(f"从MCP服务器 {server_name} 读取到原始输出: {repr(line)}")
                buffer += line
                try:
                    # 尝试解析 JSON
                    message = json.loads(buffer)
                    logger.debug(f"成功解析JSON: {message}")
                    buffer = ""
                    
                    # 检查是否是服务器就绪消息
                    if "method" in message and message["method"] == "ready":
                        logger.info(f"MCP 服务器 {server_name} 已就绪")
                        self.server_ready[server_name] = True
                    else:
                        self._handle_mcp_message(server_name, message)
                except json.JSONDecodeError as e:
                    # 记录JSON解析失败的信息
                    logger.debug(f"JSON解析失败，当前buffer: {repr(buffer)}, 错误: {e}")
                    # 不完整的 JSON，继续读取
                    continue
        except Exception as e:
            logger.error(f"处理 MCP 服务器 {server_name} 输出失败: {str(e)}")
            # 确保服务器已经停止
            if server_name in self.mcp_servers:
                self.stop_mcp_server(server_name)
    
    def _process_mcp_error(self, server_name: str, stderr):
        """处理 MCP 服务器的标准错误"""
        try:
            while True:
                # 检查服务器是否仍在运行
                if server_name not in self.mcp_servers or not self.mcp_servers[server_name]["running"]:
                    break
                
                line = stderr.readline()
                if not line:
                    break
                logger.error(f"MCP 服务器 {server_name} 错误: {line.strip()}")
        except Exception as e:
            logger.error(f"处理 MCP 服务器 {server_name} 错误失败: {str(e)}")
            # 确保服务器已经停止
            if server_name in self.mcp_servers:
                self.stop_mcp_server(server_name)
    
    def _handle_mcp_message(self, server_name: str, message: Dict):
        """处理收到的 MCP 消息"""
        logger.debug(f"收到 MCP 消息: {message}")
        
        # 处理 JSON-RPC 请求
        if "method" in message:
            self._handle_mcp_request(server_name, message)
        
        # 处理 JSON-RPC 响应
        elif "result" in message or "error" in message:
            self._handle_mcp_response(server_name, message)
    
    def _handle_mcp_request(self, server_name: str, request: Dict):
        """处理 MCP 请求"""
        method = request["method"]
        params = request.get("params", {})
        request_id = request.get("id")
        
        if method == "get_tool_definitions":
            # 返回工具定义
            result = self.tool_schemas
        elif method == "call_tool":
            # 处理工具调用
            result = self._route_tool_call(params)
        else:
            # 未知方法
            error = {"code": -32601, "message": f"Method not found: {method}"}
            self._send_mcp_response(server_name, request_id, None, error)
            return
        
        self._send_mcp_response(server_name, request_id, result, None)

    def _handle_mcp_response(self, server_name: str, response: Dict):
        """处理 MCP 响应"""
        request_id = response.get("id")
        if request_id and request_id in self.request_responses:
            # 存储响应
            self.request_responses[request_id] = response
            # 通知等待的线程
            if request_id in self.request_conditions:
                condition = self.request_conditions[request_id]
                with condition:
                    condition.notify()
    
    def _send_mcp_message(self, server_name: str, message: Dict):
        """发送 MCP 消息"""
        if server_name not in self.mcp_servers:
            logger.error(f"MCP 服务器 {server_name} 未运行")
            return
        
        try:
            server_info = self.mcp_servers[server_name]
            json_message = json.dumps(message) + "\n"
            server_info["process"].stdin.write(json_message)
            server_info["process"].stdin.flush()
            logger.debug(f"发送 MCP 消息: {json_message.strip()}")
        except Exception as e:
            logger.error(f"发送 MCP 消息到服务器 {server_name} 失败: {str(e)}")
            self.stop_mcp_server(server_name)
    
    def _inject_tool_schemas(self, server_name: str) -> bool:
        """将工具 schema 注入到 MCP 服务器"""
        logger.info(f"注入工具 schema 到 MCP 服务器 {server_name}")
        
        # 创建条件变量用于等待响应
        condition = threading.Condition()
        request_id = self._send_mcp_request(server_name, "set_tool_definitions", {
            "tools": self.tool_schemas
        })
        
        if not request_id:
            return False
        
        # 注册请求
        self.request_responses[request_id] = None
        self.request_conditions[request_id] = condition
        
        # 等待响应，超时时间为5秒
        with condition:
            condition.wait(timeout=5)
        
        # 获取响应
        response = self.request_responses.get(request_id)
        
        # 清理
        if request_id in self.request_responses:
            del self.request_responses[request_id]
        if request_id in self.request_conditions:
            del self.request_conditions[request_id]
        
        if not response:
            logger.warning(f"工具 schema 注入超时")
            return True  # 继续运行，即使注入超时
        
        if "error" in response:
            logger.error(f"工具 schema 注入失败: {response['error']['message']}")
            return False
        
        logger.info(f"工具 schema 注入成功")
        return True
    
    def _route_tool_call(self, params: Dict) -> Dict:
        """
        路由工具调用
        
        参数:
            params: 工具调用参数，包含 tool_name 和 parameters
            
        返回:
            Dict: 工具调用结果
        """
        tool_name = params.get("tool_name")
        tool_params = params.get("parameters", {})
        
        if not tool_name:
            return {"error": {"code": 400, "message": "缺少 tool_name 参数"}}
        
        # 检查工具是否存在
        if tool_name not in TOOL_REGISTRY:
            return {"error": {"code": 404, "message": f"工具不存在: {tool_name}"}}
        
        try:
            # 执行工具
            result = execute_tool(tool_name, **tool_params)
            
            # 格式化结果
            return {"result": result}
        except Exception as e:
            logger.error(f"工具调用失败: {str(e)}")
            return {"error": {"code": 500, "message": f"工具调用失败: {str(e)}"}}
    
    def get_available_tools(self) -> List[Dict]:
        """获取所有可用的工具定义"""
        return list(self.tool_schemas.values())
    
    def _send_mcp_request(self, server_name: str, method: str, params: Dict) -> str:
        """
        发送 MCP 请求
        
        参数:
            server_name: MCP 服务器名称
            method: 请求方法
            params: 请求参数
            
        返回:
            str: 请求 ID
        """
        if server_name not in self.mcp_servers:
            logger.error(f"MCP 服务器 {server_name} 未运行")
            return None
        
        request_id = str(uuid.uuid4())
        request = {
            "jsonrpc": "2.0",
            "id": request_id,
            "method": method,
            "params": params
        }
        
        # 发送请求
        self._send_mcp_message(server_name, request)
        
        return request_id
    
    def call_mcp_tool(self, server_name: str, tool_name: str, **kwargs) -> Dict:
        """
        调用 MCP 服务器上的工具
        
        参数:
            server_name: MCP 服务器名称
            tool_name: 工具名称
            **kwargs: 工具参数
            
        返回:
            Dict: 工具调用结果
        """
        if server_name not in self.mcp_servers:
            logger.error(f"MCP 服务器 {server_name} 未运行")
            return {"error": {"code": 503, "message": f"MCP 服务器 {server_name} 未运行"}}
        
        # 确保服务器就绪
        max_wait_time = 10
        start_time = time.time()
        while not self.server_ready.get(server_name, False) and time.time() - start_time < max_wait_time:
            time.sleep(0.1)
        
        if not self.server_ready.get(server_name, False):
            logger.warning(f"MCP 服务器 {server_name} 未确认就绪，但仍将尝试调用工具")
        
        # 创建条件变量用于等待响应
        condition = threading.Condition()
        request_id = self._send_mcp_request(server_name, "call_tool", {
            "tool_name": tool_name,
            "parameters": kwargs
        })
        
        if not request_id:
            return {"error": {"code": 500, "message": "发送请求失败"}}
        
        # 注册请求
        self.request_responses[request_id] = None
        self.request_conditions[request_id] = condition
        
        # 等待响应，超时时间为30秒
        with condition:
            condition.wait(timeout=30)
        
        # 获取响应
        response = self.request_responses.get(request_id)
        
        # 清理
        if request_id in self.request_responses:
            del self.request_responses[request_id]
        if request_id in self.request_conditions:
            del self.request_conditions[request_id]
        
        if not response:
            return {"error": {"code": 504, "message": "请求超时，未收到响应"}}
        
        return response


# 创建全局 MCP Host 实例
mcp_host = MCPHost()

def start_all_mcp_servers():
    """启动所有配置的 MCP 服务器"""
    for server_name in mcp_host.mcp_config["mcpServers"].keys():
        mcp_host.start_mcp_server(server_name)

def stop_all_mcp_servers():
    """停止所有 MCP 服务器"""
    mcp_host.stop_all_mcp_servers()