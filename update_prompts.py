import os
import json

# prompt文件与json配置文件映射关系
PROMPT_TO_AGENT_MAP = {
    "truth_split.md": "truth_split.json",
    "truth_judge.md": "truth_judge.json",
    "link_searcher.md": "link_searcher.json",
    "link_reader.md": "link_reader.json",
    "link_summary.md": "link_summary.json",
    "intent_classifier.md": "intent_classifier.json",
    "truth_judge_normative_explanatory.md": "truth_judge_normative_explanatory.json",
    "anchor_split.md": "anchor_split.json",
    "final_truth.md": "final_truth.json"
}

def update_agent_prompt(prompt_file, agent_file):
    """
    将markdown格式的prompt文件更新到对应json配置文件
    """
    try:  
        # 读取prompt文件内容
        with open(prompt_file, "r") as f:
            prompt_content = f.read()
        # 读取json配置文件内容
        with open(agent_file, "r") as f:
            agent_config = json.load(f)
        # 更新json配置文件中的system_prompt
        agent_key = list(agent_config.keys())[0]  # 获取代理配置的键
        agent_config[agent_key]["system_prompt"] = prompt_content
        # 写入更新后的json配置文件
        with open(agent_file, "w", encoding="utf-8") as f:
            json.dump(agent_config, f, indent=4, ensure_ascii=False)
        print(f"成功更新 {os.path.basename(agent_file)} 中的 system_prompt")
        return True
    except Exception as e:
        print(f"更新 {os.path.basename(agent_file)} 失败: {e}")
        return False

def main():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    # 遍历PROMPT_TO_AGENT_MAP中的每个映射关系
    for prompt_file, agent_file in PROMPT_TO_AGENT_MAP.items():
        # 构建完整的文件路径
        prompt_path = os.path.join(script_dir, "prompts", prompt_file)
        agent_path = os.path.join(script_dir, "config", "agents", agent_file)
        if not os.path.exists(prompt_path):
            print(f"警告: {prompt_path} 不存在")
            continue
        if not os.path.exists(agent_path):
            print(f"警告: {agent_path} 不存在")
            continue
        # 更新对应json配置文件
        update_agent_prompt(prompt_path, agent_path)

if __name__ == "__main__":
    main()