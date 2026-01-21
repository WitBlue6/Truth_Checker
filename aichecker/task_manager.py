import os
import json
import logging
import requests
from typing import List, Dict, Optional

logger = logging.getLogger(__name__)

# 导入工具装饰器
from aichecker.tools import tool

# 任务文件存储目录
TASKS_DIR = "./output/tasks"

# 任务状态枚举
TASK_STATUS = {
    "TODO": "待完成",
    "IN_PROGRESS": "进行中",
    "COMPLETED": "已完成",
    "SKIPPED": "已跳过",
    "FAILED": "失败"
}

# 保存任务列表到文件
def save_task_list(task_list_id: str, task_list_content: Dict) -> None:
    # 确保任务目录存在
    if not os.path.exists(TASKS_DIR):
        os.makedirs(TASKS_DIR, exist_ok=True)
    task_file = os.path.join(TASKS_DIR, f"{task_list_id}.json")
    with open(task_file, 'w', encoding='utf-8') as f:
        json.dump(task_list_content, f, ensure_ascii=False, indent=2)
    logger.debug(f"任务列表已保存到文件: {task_file}")

# 加载任务列表从文件
def load_task_list(task_list_id: str) -> Optional[Dict]:
    task_file = os.path.join(TASKS_DIR, f"{task_list_id}.json")
    if os.path.exists(task_file):
        with open(task_file, 'r', encoding='utf-8') as f:
            task_list_content = json.load(f)
        logger.debug(f"从文件加载任务列表: {task_file}")
        return task_list_content
    else:
        logger.debug(f"任务列表文件不存在: {task_file}")
        return None

# 创建任务列表
def create_task_list(memory_id: str, initial_tasks: Optional[List[str]] = None) -> Dict:
    import uuid
    from datetime import datetime
    
    task_list_id = f"task_list_{uuid.uuid4().hex[:8]}"
    now = datetime.now().isoformat()
    
    # 创建任务列表基础结构
    task_list = {
        "task_list_id": task_list_id,
        "memory_id": memory_id,
        "created_at": now,
        "updated_at": now,
        "tasks": []
    }
    
    # 添加初始任务
    if initial_tasks:
        for i, desc in enumerate(initial_tasks, 1):
            task = {
                "id": i,
                "description": desc,
                "status": TASK_STATUS["TODO"],
                "result": "",
                "created_at": now,
                "updated_at": now
            }
            task_list["tasks"].append(task)
    
    # 保存任务列表
    save_task_list(task_list_id, task_list)
    
    logger.info(f"创建了新的任务列表: {task_list_id}")
    return task_list

# 更新任务状态 - 注册为工具
@tool(name="update_task_status", description="更新任务状态", group="agent-tools")
def update_task_status(task_list_id: str, task_id: int, status: str, result: str = "") -> str:
    """
    更新任务状态
    
    参数:
    - task_list_id: 任务列表ID
    - task_id: 任务ID（int类型）
    - status: 新的任务状态（待完成/进行中/已完成/已跳过）
    - result: 任务结果（可选）
    
    返回:
    - str: 操作结果消息
    """
    from datetime import datetime
    
    # 验证状态值
    valid_statuses = list(TASK_STATUS.values())
    if status not in valid_statuses:
        return f"错误：无效的任务状态。请使用以下状态之一：{', '.join(valid_statuses)}"
    
    # 加载任务列表
    task_list = load_task_list(task_list_id)
    if not task_list:
        return f"错误：任务列表不存在"
    
    # 更新任务状态
    task_found = False
    for task in task_list["tasks"]:
        if task["id"] == int(task_id):
            task["status"] = status
            task["result"] = result
            task["updated_at"] = datetime.now().isoformat()
            task_found = True
            break
    
    if not task_found:
        return f"错误：任务ID不存在"
    
    # 更新任务列表的更新时间
    task_list["updated_at"] = datetime.now().isoformat()
    
    # 保存更新后的任务列表
    save_task_list(task_list_id, task_list)
    
    logger.debug(f"更新了任务状态: 任务列表={task_list_id}, 任务ID={task_id}, 状态={status}")
    return f"任务 {task_id} 的状态已更新为 {status}。"

# 添加新任务 - 注册为工具
@tool(name="add_task", description="添加新任务", group="agent-tools")
def add_task(task_list_id: str, task_description: str) -> str:
    """
    添加新任务到任务列表
    
    参数:
    - task_list_id: 任务列表ID
    - task_description: 新任务描述
    
    返回:
    - str: 操作结果消息
    """
    from datetime import datetime
    
    # 加载任务列表
    task_list = load_task_list(task_list_id)
    if not task_list:
        return f"错误：任务列表不存在"
    
    # 生成新任务ID
    if task_list["tasks"]:
        new_task_id = max(task["id"] for task in task_list["tasks"]) + 1
    else:
        new_task_id = 1
    
    # 创建新任务
    new_task = {
        "id": new_task_id,
        "description": task_description,
        "status": TASK_STATUS["TODO"],
        "result": "",
        "created_at": datetime.now().isoformat(),
        "updated_at": datetime.now().isoformat()
    }
    
    # 添加新任务到任务列表
    task_list["tasks"].append(new_task)
    
    # 更新任务列表的更新时间
    task_list["updated_at"] = datetime.now().isoformat()
    
    # 保存更新后的任务列表
    save_task_list(task_list_id, task_list)
    
    logger.debug(f"添加了新任务: 任务列表={task_list_id}, 任务ID={new_task_id}, 描述={task_description}")
    return f"已添加新任务 {new_task_id}：{task_description}"

# 获取任务列表 - 注册为工具
@tool(name="get_task_list", description="获取当前任务列表", group="agent-tools")
def get_task_list(task_list_id: str) -> str:
    """
    获取当前任务列表
    
    参数:
    - task_list_id: 任务列表ID
    
    返回:
    - str: 格式化的任务列表
    """
    # 加载任务列表
    task_list = load_task_list(task_list_id)
    if not task_list:
        return f"错误：任务列表不存在"
    
    # 生成格式化的任务列表
    return task_list_to_text(task_list)

# 生成任务列表的文本表示
def task_list_to_text(task_list: Dict) -> str:
    if not task_list["tasks"]:
        return "当前没有任务。"
    
    text = "## 任务列表\n"
    for task in task_list["tasks"]:
        status_emoji = {
            TASK_STATUS["TODO"]: "⏳",
            TASK_STATUS["IN_PROGRESS"]: "🔄",
            TASK_STATUS["COMPLETED"]: "✅",
            TASK_STATUS["SKIPPED"]: "⏭️",
            TASK_STATUS["FAILED"]: "❌"
        }.get(task["status"], "")
        
        text += f"{status_emoji} **任务 {task['id']}**: {task['description']}\n"
        text += f"   状态: {task['status']}\n"
        if task['result']:
            text += f"   结果: {task['result']}\n"
        text += "\n"
    
    return text

# 获取任务列表ID - 注册为工具
@tool(name="get_task_list_id", description="获取当前对话的任务列表ID", group="agent-tools")
def get_task_list_id(memory_id: str) -> str:
    """
    获取与指定记忆ID关联的任务列表ID
    
    参数:
    - memory_id: 记忆ID
    
    返回:
    - str: 任务列表ID或错误消息
    """
    import glob
    
    # 确保任务目录存在
    if not os.path.exists(TASKS_DIR):
        return f"错误：没有找到任务列表"
    
    # 查找与记忆ID关联的任务列表
    task_files = glob.glob(os.path.join(TASKS_DIR, "*.json"))
    for task_file in task_files:
        try:
            with open(task_file, 'r', encoding='utf-8') as f:
                task_list = json.load(f)
            if task_list.get("memory_id") == memory_id:
                return task_list.get("task_list_id", "")
        except Exception as e:
            logger.error(f"读取任务文件失败: {task_file}, 错误: {e}")
    
    return f"错误：没有找到与该记忆ID关联的任务列表"

# 获取任务列表（内部使用）
def get_task(prompt, messages, model_config, memory_id):
    """
    获取任务列表

    参数:
    - prompt: 用户提示
    - messages: 对话历史
    - model_config: 模型配置
    - memory_id: 记忆ID

    返回:
    - Dict: 任务列表
    """
    # 检查是否已经有任务列表
    task_list_id = None
    for msg in reversed(messages):
        if msg["role"] == "system" and "task_list" in msg:
            task_list_id = msg["task_list"].get("task_list_id")
            break
        
    # 如果没有任务列表，创建一个
    if not task_list_id:
        # 调用模型生成初始任务列表
        task_generation_prompt = f"""
        ## 输入
        用户请求: {prompt}
        ## 工作流程
        1. 理解用户请求，确定用户需要完成的任务
        2. 分析用户请求，判断是否需要分解任务
        3. 如果需要分解，将复杂任务分解为简单的子任务
        4. 如果不需要分解，直接返回该任务或用户请求中的任务    
        ## 输出
        请以JSON数组格式返回任务列表，每个任务包含description字段（任务描述），不要包含其他字段。
        ### 示例1
        用户输入：帮我生成这个项目的README文件
        输出：
        [
            "查看项目目录结构",
            "根据目录结构，查看项目的主要文件夹和文件内容",
            "根据文件内容，总结项目的主要功能和技术栈",
            "根据总结，生成README文件的内容"
        ]
        ### 示例2
        用户输入：查询上海的天气
        输出：
        [
            "使用联网工具或其他方式查询上海天气"
        ]
        """
            
        # 发送请求生成任务列表
        task_generation_payload = {
            "model": model_config["name"],
            "messages": [
                {"role": "system", "content": "你是一个任务规划专家，擅长将复杂任务分解为简单的子任务。"},
                {"role": "user", "content": task_generation_prompt}
            ],
            "max_tokens": 500,
            "temperature": 0.7
        }
            
        response = requests.post(
            f"{model_config['base_url']}/chat/completions",
            headers={
                "Authorization": f"Bearer {model_config['api_key']}",
                "Content-Type": "application/json"
            },
            json=task_generation_payload
        )
        response.raise_for_status()
            
        # 解析任务列表
        result = response.json()
        task_list_content = result["choices"][0]["message"]["content"]
        logger.debug(f"生成的任务列表内容: {task_list_content}")
            
        try:
            # 尝试解析JSON格式的任务列表
            initial_tasks = json.loads(task_list_content)
        except json.JSONDecodeError:
            # 如果解析失败，使用默认任务列表
            logger.warning("无法解析生成的任务列表，使用默认任务列表")
            initial_tasks = ["理解用户请求", "执行任务", "总结结果"]
            
        # 创建任务列表
        task_list = create_task_list(memory_id, initial_tasks)
        task_list_id = task_list["task_list_id"]
    else:
        # 加载现有的任务列表
        task_list = load_task_list(task_list_id)
    
    return task_list, task_list_id