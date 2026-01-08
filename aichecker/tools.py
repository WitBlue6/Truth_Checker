import requests
import logging
import re
import os
import json
import subprocess

logger = logging.getLogger(__name__)

# 从config模块导入配置加载函数
from aichecker.config import load_mcp_config

# 执行MCP工具命令
def execute_mcp_tool(tool_name, input_data):
    """执行指定的MCP工具命令"""
    try:
        mcp_config = load_mcp_config()
        # 获取工具配置
        if tool_name not in mcp_config['mcpServers']:
            return f"错误: 未知的MCP工具 '{tool_name}'"
        
        tool_config = mcp_config['mcpServers'][tool_name]
        
        # 构建命令
        cmd = [tool_config['command']]
        cmd.extend(tool_config.get('args', []))
        
        # 设置环境变量
        env = os.environ.copy()
        for key, value in tool_config.get('env', {}).items():
            env[key] = value
        
        # 执行命令
        logger.info(f"执行MCP命令: {cmd}")
        logger.info(f"命令输入: {json.dumps(input_data, ensure_ascii=False)}")
        
        process = subprocess.run(
            cmd,
            input=json.dumps(input_data, ensure_ascii=False).encode('utf-8'),
            capture_output=True,
            text=False,
            env=env
        )
        
        # 处理输出
        if process.stdout:
            result = process.stdout.decode('utf-8')
        else:
            result = process.stderr.decode('utf-8') if process.stderr else "命令执行成功但无输出"
        
        logger.info(f"工具结果:\n{result}")
        return result
    except Exception as e:
        logger.error(f"MCP工具调用失败: {str(e)}")
        return f"工具调用失败: {str(e)}"

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

# 实现Tavily搜索和提取功能
def tavily_search(query=None, urls=None, extract_depth="advanced", format="markdown"):
    """调用Tavily API进行搜索或URL内容提取"""
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
            
            # # 记录完整的API响应到日志
            # logger.info(f"完整的URL提取结果JSON: {json.dumps(extract_result, ensure_ascii=False, indent=2)}")
            
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
                    # 额外检测：如果内容中包含大量导航链接但缺少实际文章内容
                    # 通过检测是否包含多个常见的网站导航关键词
                    # navigation_keywords = ['登录', '注册', '购物车', '行业报告', '联系我们', '关于我们', '热门关键词']
                    # nav_keyword_count = sum(1 for keyword in navigation_keywords if keyword in raw_content)
                    
                    if is_blocked:  # 如果包含5个以上导航关键词，可能是被拦截
                        result += f"内容:\n【访问被拦截】该网站已拦截当前IP的访问请求\n\n"
                    else:
                        cleaned_content = clean_content(raw_content)
                        # # 如果还过长
                        # if len(cleaned_content) > 8000:
                        #     cleaned_content = cleaned_content[:8000] + "..."
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
            logger.info(f"完整的搜索结果JSON: {json.dumps(search_result, ensure_ascii=False, indent=2)}")
            
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

def extract_url_content(urls):
    """提取URL内容的简化接口"""
    return tavily_search(urls=urls)