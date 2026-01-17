import os
import json
import logging

logger = logging.getLogger(__name__)

# 记忆文件存储目录
MEMORY_DIR = "./output/memories"

# 保存记忆到文件
def save_memory(memory_id, memory_content):
    """
    保存记忆到文件
    
    参数:
    - memory_id: 记忆ID
    - memory_content: 记忆内容（对话历史列表）
    """
    # 确保记忆目录存在
    if not os.path.exists(MEMORY_DIR):
        os.makedirs(MEMORY_DIR, exist_ok=True)
    memory_file = os.path.join(MEMORY_DIR, f"{memory_id}.json")
    with open(memory_file, 'w', encoding='utf-8') as f:
        json.dump(memory_content, f, ensure_ascii=False, indent=2)
    logger.info(f"记忆已保存到文件: {memory_file}")

# 加载记忆从文件
def load_memory(memory_id):
    """
    从文件加载记忆
    
    参数:
    - memory_id: 记忆ID
    
    返回:
    - list: 对话历史列表，如果文件不存在则返回空列表
    """
    memory_file = os.path.join(MEMORY_DIR, f"{memory_id}.json")
    if os.path.exists(memory_file):
        with open(memory_file, 'r', encoding='utf-8') as f:
            memory_content = json.load(f)
        logger.info(f"从文件加载记忆: {memory_file}")
        return memory_content
    else:
        logger.info(f"记忆文件不存在，将创建新记忆: {memory_file}")
        return []
