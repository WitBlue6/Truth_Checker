import requests
import logging
import re
import os
import json
import subprocess
from inspect import signature
from functools import wraps

logger = logging.getLogger(__name__)

# 从config模块导入配置加载函数
from aichecker.config import load_mcp_config
from aichecker.mcp_host import get_mcp_host

# 工具注册表，用于存储所有已注册的工具
TOOL_REGISTRY = {}

# 工具装饰器，用于自动注册工具
def tool(name=None, description=None, group=None):
    """工具装饰器，用于注册工具"""
    def decorator(func):
        tool_name = name or func.__name__
        
        # 生成工具的函数签名信息
        sig = signature(func)
        parameters = {}
        required = []
        
        for param_name, param in sig.parameters.items():
            param_info = {
                "type": "string",  # 默认类型为string，可以根据需要扩展
                "description": "参数描述"  # 可以从函数文档字符串中提取
            }
            
            # 检查是否有默认值
            if param.default is not param.empty:
                param_info["default"] = param.default
            else:
                required.append(param_name)
            
            parameters[param_name] = param_info
        
        # 注册工具
        TOOL_REGISTRY[tool_name] = {
            "function": func,
            "name": tool_name,
            "description": description or func.__doc__ or "",
            "group": group,
            "parameters": parameters,
            "required": required
        }
        
        @wraps(func)
        def wrapper(*args, **kwargs):
            return func(*args, **kwargs)
        
        return wrapper
    return decorator

# 执行注册的工具
def execute_tool(exec_tool_name, **kwargs):
    """执行指定的工具"""
    try:
        if exec_tool_name not in TOOL_REGISTRY:
            return f"错误: 未知的工具 '{exec_tool_name}'"
        
        tool_info = TOOL_REGISTRY[exec_tool_name]
        tool_func = tool_info["function"]
        
        logger.debug(f"执行工具: {exec_tool_name}")
        logger.debug(f"工具参数: {json.dumps(kwargs, ensure_ascii=False)}")
        
        result = tool_func(**kwargs)
        
        logger.debug(f"工具执行完成")
        return result
    except Exception as e:
        logger.error(f"工具调用失败: {str(e)}")
        return f"工具调用失败: {str(e)}"

# 获取所有注册的工具
def get_all_tools():
    """获取所有注册的工具"""
    return TOOL_REGISTRY

# 获取指定工具的信息
def get_tool_info(tool_name):
    """获取指定工具的信息"""
    return TOOL_REGISTRY.get(tool_name)

# 获取指定分组的工具
def get_tools_by_group(group_name):
    """获取指定分组的工具"""
    return {name: info for name, info in TOOL_REGISTRY.items() if info["group"] == group_name}

# 清理内容中的冗余格式
def clean_content(content):
    """清理内容中的冗余格式，包括HTML标签、各种链接、特殊字符等"""
    if not content:
        return content
    
    # 1. 清理HTML标签
    content = re.sub(r'<[^>]+>', '', content)
    
    # 2. 清理各种链接格式
    # Wiki链接格式：[显示文本](/wiki/链接内容)
    content = re.sub(r'\[([^\]]+)\]\(/wiki/[^\)]+\)', r'\1', content)
    # 带标题的Wiki链接：[显示文本](/wiki/链接内容 "标题")
    content = re.sub(r'\[([^\]]+)\]\(/wiki/[^\)]+\s+"[^"]+"\)', r'\1', content)
    # 外部链接：[显示文本](http://example.com) 或 [显示文本](https://example.com)
    content = re.sub(r'\[([^\]]+)\]\(https?://[^\)]+\)', r'\1', content)
    # 内部链接：[显示文本](/path/to/page)
    content = re.sub(r'\[([^\]]+)\]\(/[^\)]+\)', r'\1', content)
    # Markdown链接：[显示文本](link)
    content = re.sub(r'\[([^\]]+)\]\([^\)]+\)', r'\1', content)
    # 纯URL链接
    content = re.sub(r'https?://[^\s]+', '', content)
    
    # 3. 清理各种标记和格式
    # 清理加粗、斜体等标记
    content = re.sub(r'[*_]{1,3}([^*_]+)[*_]{1,3}', r'\1', content)
    # 清理引用标记
    content = re.sub(r'>\s*', '', content)
    # 清理代码块标记
    content = re.sub(r'```[^`]*```', '', content, flags=re.DOTALL)
    content = re.sub(r'`([^`]+)`', r'\1', content)
    
    # 4. 清理特殊字符和多余空格
    # 清理连续的空格
    content = re.sub(r'\s+', ' ', content)
    # 清理行首行尾的空格
    content = content.strip()
    
    # 5. 清理多余的空行
    content = re.sub(r'\n\s*\n', '\n\n', content)
    
    # 6. 清理表格格式（简单处理，保留内容）
    content = re.sub(r'\|\s*', ' ', content)
    content = re.sub(r'\s*\|', ' ', content)
    content = re.sub(r'-{3,}', '', content)
    
    # 7. 清理列表格式（保留内容，去除标记）
    content = re.sub(r'^\s*[\*\+\-]\s+', '', content, flags=re.MULTILINE)
    content = re.sub(r'^\s*\d+\.\s+', '', content, flags=re.MULTILINE)
    
    return content

def extract_url_content(urls):
    """提取URL内容的简化接口"""
    return tavily_search(urls=urls)

# 实现Tavily搜索和提取功能
@tool(name="tavily_search", description="调用Tavily进行联网搜索或URL内容提取", group="mcp-tools")
def tavily_search(query=None, urls=None, extract_depth="advanced", format="markdown"):
    """调用Tavily API进行搜索或URL内容提取
    
    参数:
    query (str, 可选): 搜索查询字符串。如果提供urls参数，则忽略此参数。
    urls (list of str, 可选): 要提取内容的URL列表。如果提供query参数，则忽略此参数。
    extract_depth (str, 可选): 提取深度，默认"advanced"。
    format (str, 可选): 输出格式，默认"markdown"。
    
    返回:
    str: 包含搜索结果或URL内容提取结果的字符串。
    """
    try:
        # 获取Tavily API密钥
        mcp_config = load_mcp_config()
        tavily_api_key = mcp_config["mcpServers"]["tavily"]["env"]["TAVILY_API_KEY"]
        
        if urls:
            # URL内容提取模式
            response = requests.post(
                "https://api.tavily.com/extract",
                headers={
                    "Content-Type": "application/json"
                },
                json={
                    "api_key": tavily_api_key,
                    "urls": urls,
                    "extract_depth": extract_depth,
                    "format": format
                }
            )
            response.raise_for_status()
            extract_result = response.json()
            
            # 格式化提取结果
            result = "URL内容提取结果:\n"
             # 处理所有URL，包括成功和失败的
            processed_urls = set()
            
            # 先处理失败的URL
            for i, failed_item in enumerate(extract_result.get("failed_results", [])):
                url = failed_item.get('url', '无URL')
                result += f"=== URL {i+1}: {url} ===\n"
                result += f"标题: 工具无法提取到链接内容\n"
                result += f"内容:\n工具无法提取到链接内容\n\n"
                processed_urls.add(url)
            
            # 再处理成功提取的URL
            for i, item in enumerate(extract_result.get("results", [])):
                url = item.get('url', '无URL')
                # 避免重复处理同一个URL
                if url not in processed_urls:
                    result += f"=== URL {len(processed_urls) + i + 1}: {url} ===\n"
                    result += f"标题: {item.get('title', '无标题')}\n"
                    raw_content = item.get('raw_content', '无内容')

                     # 检测是否被拦截
                    blocked_keywords = ['拦截', 
                                        'Your IP is not allowed to visit this website',
                                        '点击进行人机验证',
                                        '人机验证',
                                        '验证您的身份',
                                        'captcha',
                                        'CAPTCHA',
                                        '请拖动滑块',
                                        '拖动验证',
                                        '安全验证',
                                        '反爬虫',
                                        '访问限制',
                                        '请点击',
                                        'verify',
                                        'authentication']
                    is_blocked = any(keyword in raw_content for keyword in blocked_keywords)
                    
                    if is_blocked:
                        result += f"内容:\n【访问被拦截】该网站已拦截当前IP的访问请求\n\n"
                    else:
                        cleaned_content = clean_content(raw_content)
                        result += f"内容:\n{cleaned_content}\n\n"
                    processed_urls.add(url)
            
            # 如果没有处理任何URL，说明可能API返回了意外格式
            if not processed_urls:
                result += "工具无法提取到链接内容\n"
            
            return result
        elif query:
            # 搜索模式
            response = requests.post(
                "https://api.tavily.com/search",
                headers={
                    "Content-Type": "application/json"
                },
                json={
                    "api_key": tavily_api_key,
                    "query": query,
                    "search_depth": "basic",
                    "include_answer": True,
                    "include_raw_content": False,
                    "max_results": 5
                }
            )
            response.raise_for_status()
            search_result = response.json()
            
            # 记录完整的搜索结果到日志
            logger.debug(f"完整的搜索结果JSON: {json.dumps(search_result, ensure_ascii=False, indent=2)}")
            
            # 格式化搜索结果
            if "answer" in search_result and search_result["answer"]:
                result = f"答案: {search_result['answer']}\n"
            else:
                result = "未找到直接答案\n"
            
            result += "搜索结果:\n"
            for i, item in enumerate(search_result.get("results", [])):
                result += f"{i+1}. {item.get('title', '无标题')}\n"
                result += f"   链接: {item.get('url', '无链接')}\n"
                result += f"   摘要: {item.get('content', '无摘要')[:200]}...\n\n"
            
            return result
        else:
            return "错误: 必须提供query或urls参数"
    except Exception as e:
        logger.error(f"Tavily API调用失败: {str(e)}")
        # 如果是URL提取模式且有URL参数，返回友好的错误信息
        if urls:
            result = "URL内容提取结果:\n"
            for i, url in enumerate(urls):
                result += f"=== URL {i+1}: {url} ===\n"
                result += f"标题: 工具无法提取到链接内容\n"
                result += f"内容:\n工具无法提取到链接内容\n\n"
            return result
        return f"操作失败: {str(e)}"

# 文件操作功能
@tool(name="read_file", description="读取文件内容", group="file-tools")
def read_file(file_path):
    """读取文件内容
    参数:
    file_path (str): 要读取的文件路径
    
    返回:
    str: 文件内容的字符串表示，或错误消息
    """
    try:
        # 安全检查：只允许读取当前目录及其子目录的文件
        file_path = os.path.abspath(file_path)
        current_dir = os.path.abspath('.')
        
        if not file_path.startswith(current_dir):
            return f"错误: 不允许读取当前目录外的文件"
        
        if not os.path.exists(file_path):
            # 获取目录路径
            dir_path = os.path.dirname(file_path)
            # 获取文件名
            filename = os.path.basename(file_path)
            
            error_msg = f"错误: 文件 '{file_path}' 不存在\n"
            
            # 如果目录存在，建议使用list_files查看目录内容
            if os.path.exists(dir_path):
                error_msg += "建议：\n"
                error_msg += f"1. 使用 list_files('{dir_path}') 查看该目录下的文件和子目录\n"
                error_msg += f"2. 检查文件名是否拼写错误，当前文件名: {filename}\n"
            
            return error_msg
        
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        logger.debug(f"成功读取文件: {file_path}")
        return content
    except Exception as e:
        logger.error(f"读取文件失败: {str(e)}")
        return f"错误: {str(e)}"

@tool(name="write_file", description="写入文件内容", group="file-tools")
def write_file(file_path, content, overwrite=False):
    """写入文件内容
    参数:
    file_path (str): 要写入的文件路径
    content (str): 要写入的内容
    overwrite (bool, 可选): 是否覆盖已存在文件，默认False
    
    返回:
    str: 成功消息或错误消息
    """
    try:
        # 安全检查：只允许写入当前目录及其子目录的文件
        file_path = os.path.abspath(file_path)
        current_dir = os.path.abspath('.')
        
        if not file_path.startswith(current_dir):
            return f"错误: 不允许写入当前目录外的文件"
        
        # 检查文件是否存在
        if os.path.exists(file_path) and not overwrite:
            return f"错误: 文件已存在，请设置overwrite=True覆盖"
        
        # 创建目录（如果不存在）
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)
        
        logger.debug(f"成功写入文件: {file_path}")
        return f"成功写入文件: {file_path}"
    except Exception as e:
        logger.error(f"写入文件失败: {str(e)}")
        return f"错误: {str(e)}"

@tool(name="append_file", description="追加文件内容", group="file-tools")
def append_file(file_path, content):
    """追加文件内容
    参数:
    file_path (str): 要追加的文件路径
    content (str): 要追加的内容
    
    返回:
    str: 成功消息或错误消息
    """
    try:
        # 安全检查：只允许操作当前目录及其子目录的文件
        file_path = os.path.abspath(file_path)
        current_dir = os.path.abspath('.')
        
        if not file_path.startswith(current_dir):
            return f"错误: 不允许操作当前目录外的文件"
        
        # 创建目录（如果不存在）
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        
        with open(file_path, 'a', encoding='utf-8') as f:
            f.write(content)
        
        logger.debug(f"成功追加到文件: {file_path}")
        return f"成功追加到文件: {file_path}"
    except Exception as e:
        logger.error(f"追加文件失败: {str(e)}")
        return f"错误: {str(e)}"

@tool(name="list_files", description="列出目录内容", group="file-tools")
def list_files(directory, depth=1):
    """列出目录下的文件和子目录
    参数:
    directory (str): 要列出内容的目录路径
    depth (int, 可选): 递归查看子目录的深度，默认1（只查看当前目录），最大支持3
    
    返回:
    str: 目录内容的字符串表示，或错误消息
    """
    try:
        # 安全检查：只允许操作当前目录及其子目录
        directory = os.path.abspath(directory)
        current_dir = os.path.abspath('.')
        
        if not directory.startswith(current_dir):
            return f"错误: 不允许操作当前目录外的文件"
        
        # 限制最大递归深度，避免信息过载
        max_depth = 3
        if depth < 1 or depth > max_depth:
            return f"错误: 递归深度必须在1到{max_depth}之间"
        
        result = f"目录: {directory}\n"
        result += f"递归深度: {depth}\n"
        result += "文件和子目录:\n"
        
        def list_dir_recursive(dir_path, current_depth, indent=""):
            """递归列出目录内容"""
            items = os.listdir(dir_path)
            for item in items:
                item_path = os.path.join(dir_path, item)
                if os.path.isdir(item_path):
                    yield f"{indent}[目录] {item}\n"
                    if current_depth < depth:
                        # 递归查看子目录
                        yield from list_dir_recursive(item_path, current_depth + 1, indent + "  ")
                else:
                    yield f"{indent}[文件] {item}\n"
        
        # 调用递归函数生成目录列表
        for line in list_dir_recursive(directory, 1):
            result += line
        
        logger.debug(f"成功列出目录: {directory} (递归深度: {depth})")
        return result
    except Exception as e:
        logger.error(f"列出目录失败: {str(e)}")
        return f"错误: {str(e)}"
    
@tool(name="execute_command", description="执行命令行命令", group="command-tools")
def execute_command(command, args=None, cwd=".", timeout=30, capture_output=True):
    """
    执行命令行命令
    
    参数:
    command (str): 要执行的命令（可以包含参数）
    args (str): 命令参数，多个参数用空格分隔，默认为None
    cwd (str): 命令执行的工作目录，默认为当前目录
    timeout (int): 命令执行的超时时间（秒），默认为30
    capture_output (bool): 是否捕获命令输出，默认为True
    
    返回:
    str: 命令执行结果的字符串表示
    """
    try:
        # 清理命令中的多余反引号
        command = command.replace('`', '')
        
        # 安全检查：禁止执行的危险命令列表
        dangerous_commands = ['rm', 'mv', 'cp', 'chmod', 'chown', 'sudo', 'su', 'passwd', 
                              'shutdown', 'reboot', 'rmdir', 'dd', 'mkfs', 'format']
        import shlex

        # 统一用 shlex 解析
        cmd_list = shlex.split(command)
        if args:
            cmd_list.extend(shlex.split(args))

        if not cmd_list:
            return "错误: 空命令"
        
        # 检查命令是否在危险列表中
        if cmd_list[0] in dangerous_commands:
            return f"错误: 禁止执行危险命令 '{cmd_list[0]}'，以保护系统安全"
        
        # 执行命令
        logger.debug(f"执行命令: {''.join(cmd_list)} (工作目录: {cwd})")
        result = subprocess.run(
            cmd_list,
            cwd=cwd,
            timeout=timeout,
            capture_output=capture_output,
            text=True,
            check=True
        )
        
        # 处理结果
        output = ""
        if capture_output:
            if result.stdout:
                output += f"标准输出:\n{result.stdout}\n\n"
            if result.stderr:
                output += f"标准错误:\n{result.stderr}\n\n"
        
        output += f"命令执行成功，返回码: {result.returncode}"
        return output
        
    except subprocess.TimeoutExpired:
        return f"错误: 命令执行超时（超过 {timeout} 秒）"
    except subprocess.CalledProcessError as e:
        error_output = f"错误: 命令执行失败，返回码: {e.returncode}\n"
        if capture_output:
            if e.stdout:
                error_output += f"标准输出:\n{e.stdout}\n"
            if e.stderr:
                error_output += f"标准错误:\n{e.stderr}\n"
        return error_output
    except Exception as e:
        return f"错误: {str(e)}"
    
@tool(name="ripgrep", description="使用ripgrep在文件中搜索文本", group="command-tools")
def ripgrep(pattern, path=".", file_types=None, ignore_case=False, invert_match=False, show_line_numbers=True, max_results=100):
    """
    使用ripgrep在文件中搜索文本
    
    参数:
    pattern (str): 要搜索的正则表达式模式
    path (str): 搜索路径，默认为当前目录
    file_types (str): 要搜索的文件类型（如"py,js"），默认为所有文件
    ignore_case (bool): 是否忽略大小写，默认为False
    invert_match (bool): 是否返回不匹配的行，默认为False
    show_line_numbers (bool): 是否显示行号，默认为True
    max_results (int): 最大返回结果数，默认为100
    
    返回:
    str: 搜索结果的字符串表示
    """
    try:
        # 构建ripgrep命令
        cmd = ["rg"]
        
        # 添加参数
        if ignore_case:
            cmd.append("-i")
        if invert_match:
            cmd.append("-v")
        if show_line_numbers:
            cmd.append("-n")
        if file_types:
            cmd.extend(["-t", file_types])
        
        # 限制结果数量
        cmd.extend(["-m", str(max_results)])
        
        # 添加搜索模式和路径
        cmd.append(pattern)
        cmd.append(path)
        
        # 执行命令
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=True
        )
        
        # 处理结果
        output = result.stdout
        if not output:
            return "未找到匹配的结果"
        
        return f"搜索结果 (模式: {pattern}, 路径: {path}):\n\n{output}"
    except subprocess.CalledProcessError as e:
        # ripgrep在未找到匹配时返回非零退出码，但这不是错误
        if e.returncode == 1:
            return "未找到匹配的结果"
        return f"ripgrep执行失败: {e.stderr}"
    except Exception as e:
        return f"错误: {str(e)}"
    
@tool(name="use_mcp_host_tool", description="使用 MCP Host 工具执行操作", group="mcp-tools")
def use_mcp_host_tool(mcp_server, tool_name, **kwargs):
    """
    使用 MCP Host 工具执行操作

    参数:
    mcp_server (MCPServerProcess): MCP 服务器进程对象
    tool_name (str): 要使用的工具名称
    **kwargs: 工具的具体参数
    """
    try:
        # 情况1：LLM 传来的是字符串服务器名
        if isinstance(mcp_server, str):
            mcp_host = get_mcp_host(load_mcp_config())
            if mcp_host is None:
                raise RuntimeError("GLOBAL_MCP_HOST 未初始化")
            if mcp_server not in mcp_host.servers:
                raise RuntimeError(f"未知 MCP 服务器: {mcp_server}")
            server = mcp_host.servers[mcp_server]

        # 情况2：你内部已经传了对象
        else:
            server = mcp_server
        # 如果 LLM 传入的 kwargs 里还嵌套了 "kwargs" 字符串，解析成 dict
        if "kwargs" in kwargs and isinstance(kwargs["kwargs"], str):
            try:
                inner_kwargs = json.loads(kwargs["kwargs"])
            except Exception:
                inner_kwargs = {}
        else:
            inner_kwargs = kwargs

        tool_result = server.call("tools/call", {
            "name": tool_name,
            "arguments": inner_kwargs
        })
        
        # 格式化结果
        return json.dumps(tool_result, indent=2, ensure_ascii=False)
    except Exception as e:
        logger.error(f"MCP Host 工具调用失败: {str(e)}")
        return f"工具调用失败: {str(e)}"