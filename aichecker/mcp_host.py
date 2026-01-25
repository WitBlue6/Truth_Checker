import json
import os
import subprocess
import logging
import threading
import uuid

logger = logging.getLogger(__name__)

GLOBAL_MCP_HOST = None

class MCPServerProcess:
    def __init__(self, name, command, args, env=None):
        self.name = name
        self.proc = subprocess.Popen(
            [command] + args,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            env=env or os.environ
        )
        self.responses = {}
        self.conds = {}
        threading.Thread(target=self._reader, daemon=True).start()
    def _send_message(self, msg: dict):
        self.proc.stdin.write(json.dumps(msg) + "\n")
        self.proc.stdin.flush()

    def _reader(self):
        for line in self.proc.stdout:
            try:
                msg = json.loads(line)
            except:
                continue
            if "id" in msg and msg["id"] in self.conds:
                self.responses[msg["id"]] = msg
                with self.conds[msg["id"]]:
                    self.conds[msg["id"]].notify()

    def call(self, method, params, timeout=10):
        req_id = str(uuid.uuid4())
        msg = {
            "jsonrpc": "2.0",
            "id": req_id,
            "method": method,
            "params": params if params else {}
        }
        cond = threading.Condition()
        self.conds[req_id] = cond

        self._send_message(msg)

        with cond:
            cond.wait(timeout)

        resp = self.responses.pop(req_id, None)
        self.conds.pop(req_id, None)

        if not resp:
            raise TimeoutError(f"{method} timeout")

        if "error" in resp:
            raise RuntimeError(resp["error"])

        return resp["result"]
    def shutdown(self):
        # 1. 尝试协议级 shutdown
        try:
            self.call("shutdown", {})
        except Exception as e:
            logger.debug(f"[MCP] shutdown not supported, fallback: {e}")

        # 2. 尝试协议级 exit
        try:
            self.notify("exit", {})
        except Exception as e:
            logger.debug(f"[MCP] exit not supported, fallback: {e}")

        # 3. 进程级兜底回收
        if self.proc and self.proc.poll() is None:
            self.proc.terminate()
            try:
                self.proc.wait(timeout=3)
            except:
                self.proc.kill()

    def notify(self, method, params):
        msg = {
            "jsonrpc": "2.0",
            "method": method,
            "params": params if params else {}
        }
        self._send_message(msg)


class MCPHost:
    def __init__(self, config):
        self.config = config
        self.servers = {}
        self.tools = {}  # server.tool_name -> schema

    def start_server(self, name):
        cfg = self.config["mcpServers"][name]
        env = os.environ.copy()
        env.update(cfg.get("env", {}))

        server = MCPServerProcess(
            name=name,
            command=cfg["command"],
            args=cfg.get("args", []),
            env=env
        )

        # 标准初始化
        server.call("initialize", {
            "protocolVersion": "2024-11-05",
            "clientInfo": {
                "name": "aichecker-mcp-host",
                "version": "0.1.0"
            },
            "capabilities": {}
        })

        # 拉取工具列表
        tool_info = server.call("tools/list", {})
        for t in tool_info["tools"]:
            fq_name = f"{name}.{t['name']}"
            self.tools[fq_name] = {
                "server": name,
                "name": t["name"],
                "schema": t
            }

        self.servers[name] = server
        return server

    def call_tool(self, fq_tool_name, arguments):
        tool = self.tools[fq_tool_name]
        server = self.servers[tool["server"]]

        return server.call("tools/call", {
            "name": tool["name"],
            "arguments": arguments
        })
    def stop_server(self, name: str):
        server = self.servers.get(name)
        if not server:
            raise ValueError(f"MCP server {name} not running")

        logger.debug(f"[MCP] stopping {name}")
        server.shutdown()
        del self.servers[name]

    
# # 全局MCP Host实例
# mcp_host = None
# config = None

# def init_mcp_host(mcp_config=None):
#     """初始化全局MCP Host实例"""
#     global mcp_host, config
#     if mcp_config:
#         config = mcp_config
#     if not mcp_host and config:
#         mcp_host = MCPHost(config)
#     return mcp_host

# def start_mcp_server(server_name):
#     """启动指定的MCP服务器（兼容旧接口）"""
#     global mcp_host
#     if not mcp_host:
#         from aichecker.config import load_mcp_config
#         init_mcp_host(load_mcp_config())
#     if server_name not in mcp_host.servers:
#         mcp_host.start_server(server_name)
#     return True

# def call_mcp_tool(server_name, tool_name, **kwargs):
#     """调用MCP工具（兼容旧接口）"""
#     global mcp_host
#     if not mcp_host:
#         from aichecker.config import load_mcp_config
#         init_mcp_host(load_mcp_config())
    
#     # 构建全限定工具名
#     fq_tool_name = f"{server_name}.{tool_name}"
#     if fq_tool_name not in mcp_host.tools:
#         # 如果工具不存在，尝试启动服务器
#         mcp_host.start_server(server_name)
    
#     return mcp_host.call_tool(fq_tool_name, kwargs)

def start_all_mcp_servers(config):
    """启动所有MCP服务器"""
    global mcp_host
    mcp_host = MCPHost(config)
    for name in config["mcpServers"]:
        mcp_host.start_server(name)
    return mcp_host

def stop_all_mcp_servers(host: MCPHost):
    """停止所有MCP服务器"""
    for name in list(host.servers.keys()):
        host.stop_server(name)

def get_mcp_host(config):
    global GLOBAL_MCP_HOST
    if GLOBAL_MCP_HOST is None:
        GLOBAL_MCP_HOST = start_all_mcp_servers(config)
    return GLOBAL_MCP_HOST

