import os
import logging
from datetime import datetime
import time
import sys
import re
from typing import Dict, Optional, List, Union
import json

from aichecker.agents import call_agent
from aichecker.tools import extract_url_content

logger = logging.getLogger(__name__)

current_python = sys.executable
print(f"当前环境Python路径：{current_python}")

def extract_urls(input_text: Optional[Union[str, List[str]]]) -> List[str]:
    """
    从输入文本中提取所有URL链接，支持多种格式输入
    :param input_text: 输入文本，可以是字符串、列表或None
    :return: 提取的URL列表
    """
    if not input_text:
        return []
    
    # 如果输入已经是列表，先合并为字符串
    if isinstance(input_text, list):
        input_text = "\n".join(input_text)
    
    # URL正则表达式模式
    url_pattern = r'https?://[^\s<>"\']+'
    
    # 提取所有匹配的URL
    urls = re.findall(url_pattern, input_text)
    
    # 去重并返回
    return list(set(urls))

def factual_workflow(desc: str, link: Optional[Union[str, List[str]]], **kwargs) -> Dict[str, Union[str, List[Dict[str, str]]]]:
    """
    事实型工作流，保持现有流程
    :param desc: 待检查的事实描述
    :param link: 相关链接，支持单个URL或URL列表
    :param kwargs: 其他参数，包括logger
    """
    logger = kwargs.get('logger', logging.getLogger(__name__))
    
    # 使用truth_split代理提取事实
    fact_content = call_agent("truth_split", f"[DESCRIPTION]\n{desc}\n Extract Facts from description.")
    logger.info(f"Fact List: \n{fact_content}")
    
    # 第二步：链接内容获取与汇总
    logger.info("Step 2: Start Search Link Info")
    logger.info(f"Link Content: \n{link}")

    # 提取URL列表
    urls = extract_urls(link)
    logger.info(f"Extracted URLs: \n{urls}")
    cached_url_content = ""

    if urls:
        # 创建专门用于提取URL内容的prompt
        url_extraction_prompt = f"""[LINK_URLS]
{urls}

Task:
[Using tavily] Extract the content from all the URLs provided above.
Please extract the content in detail, including all relevant information.
Return ONLY the extracted content in a clear format, without any additional explanation or summary.
"""
                
        # 调用link_reader代理提取URL内容
        cached_url_content = call_agent("link_reader", url_extraction_prompt)
        logger.info(f"已缓存的URL内容: {cached_url_content}") 
    
    # 链接内容总结
    link_info = ""
    fact_list = json.loads(fact_content)
    for i, fact in enumerate(fact_list):
        # 构建链接汇总提示
        link_summary_prompt = f"""[FACTS]
{fact}

[CACHED_URL_CONTENT]
{cached_url_content}

Task:
Based on the specific fact provided below, summary the relevant information from the cached URL content.
"""
            
        # 使用link_summary代理获取链接内容
        link_info += f"{i+1}. {call_agent('link_summary', link_summary_prompt)}\n\n"
    
    logger.info(f"Link Info: \n{link_info}")

    # 第三步：联网搜索
    logger.info("Step 3: Start Search Truth")
    
    # 构建事实判断提示
    link_searcher_prompt = f"""[FACTS]
{fact_content}

Task:
[Using tavily] Search the info of every fact using the reference info.
"""
    
    # 使用link_searcher代理进行联网搜索
    search_content = call_agent("link_searcher", link_searcher_prompt)
    logger.info(f"Link Search Result: \n{search_content}")
    
    # 第四步：真实性判断
    logger.info("Step 4: Start Truth Check")
    
    # 构建最终判断提示
    truth_judge_prompt = f"""[FACT LIST]
{fact_content}

[SEARCH RESULT]
{search_content}

[REFERENCE_INFO]
{link_info}

Task:
Check the truth of every fact using the search result and reference info that provided above.
"""
    
    # 使用truth_judge代理进行最终判断
    res_content = call_agent("truth_judge", truth_judge_prompt)
    logger.info(f"Truth Check: {res_content}")

    return {
        "truth": res_content,
        "facts": fact_content,
        "link_info": link_info,
        "truth_reason": res_content,
        "search_result": search_content,
        "intent": "factual"
    }

def normative_explanatory_workflow(desc: str, link: Optional[Union[str, List[str]]], intent_content: Dict, **kwargs) -> Dict[str, Union[str, List[Dict[str, str]]]]:
    """
    规范型或解释型工作流
    :param desc: 待检查的事实描述
    :param link: 相关链接，支持单个URL或URL列表
    :param intent_content: 意图分类结果
    :param kwargs: 其他参数，包括logger
    """
    logger = kwargs.get('logger', logging.getLogger(__name__))
    
    # 提取URL列表
    urls = extract_urls(link)
    logger.info(f"Extracted URLs: \n{urls}")
    
    # 提取URL内容
    cached_url_content = ""
    if urls:
        url_extraction_prompt = f"""[LINK_URLS]
{urls}

Task:
[Using tavily] Extract the content from all the URLs provided above.
Please extract the content in detail, including all relevant information.
Return ONLY the extracted content in a clear format, without any additional explanation or summary.
"""
        cached_url_content = call_agent("link_reader", url_extraction_prompt)
        logger.info(f"已缓存的URL内容: {cached_url_content}")
    
    # 根据limited_factual_anchor决定处理方式
    limited_factual_anchor = intent_content["actions"]["limited_factual_anchor"]
    search_needed = intent_content["actions"]["search_external"]
    
    if limited_factual_anchor:
        # 提取一条最重要的核心事实要素
        logger.info("limited_factual_anchor为true，提取一条最重要的核心事实要素")
        fact_content = call_agent("anchor_split", f"[DESCRIPTION]\n{desc}\n Extract limited factual anchors from description.")
        logger.info(f"Extracted Core Fact: \n{fact_content}")
        
        # 解析事实列表
        fact_list = json.loads(fact_content)
        if not fact_list:
            logger.warning("未能提取到核心事实要素")
            return {
                "final_truth": "UNCERTAIN",
                "final_truth_reason": "未能提取到核心事实要素进行判断"
            }
        
        # 只保留第一条核心事实
        if isinstance(fact_list, list) and len(fact_list) > 0:
            core_fact = fact_list[0]
            fact_content = json.dumps([core_fact], ensure_ascii=False)
    else:
        # 直接使用原desc作为事实
        logger.info("limited_factual_anchor为false，直接使用原desc作为事实")
        fact_content = json.dumps([{"fact": desc, "info_type": ["综合"], "fact_role": "critical"}], ensure_ascii=False)
    
    logger.info(f"Final Fact Content: \n{fact_content}")
    
    # 根据search_needed决定是否进行联网搜索
    search_content = ""
    if search_needed:
        logger.info("search为true，进行联网搜索")
        link_searcher_prompt = f"""[FACTS]
{fact_content}

Task:
[Using tavily] Search the info of every fact using the reference info.
"""
        search_content = call_agent("link_searcher", link_searcher_prompt)
        logger.info(f"Link Search Result: \n{search_content}")
    else:
        logger.info("search为false，不进行联网搜索")
    
    # 链接内容总结
    link_info = ""
    fact_list = json.loads(fact_content)
    for i, fact in enumerate(fact_list):
        link_summary_prompt = f"""[FACTS]
{fact}

[CACHED_URL_CONTENT]
{cached_url_content}

Task:
Based on the specific fact provided below, summary the relevant information from the cached URL content.
"""
        link_info += f"{i+1}. {call_agent('link_summary', link_summary_prompt)}\n\n"
    
    logger.info(f"Link Info: \n{link_info}")
    
    # 真实性判断
    logger.info("Step 4: Start Truth Check")
    
    if search_needed:
        # 使用truth_judge进行判断
        truth_judge_prompt = f"""[FACT LIST]
{fact_content}

[SEARCH RESULT]
{search_content}

[REFERENCE_INFO]
{link_info}

Task:
Check the truth of every fact using the search result and reference info that provided above.
"""
        res_content = call_agent("truth_judge_normative_explanatory", truth_judge_prompt)
    else:
        # 使用truth_judge_wo_search进行判断
        truth_judge_prompt = f"""[FACT LIST]
{fact_content}

[REFERENCE_INFO]
{link_info}

Task:
Check the truth of every fact using the reference info only.
"""
        res_content = call_agent("truth_judge_normative_explanatory", truth_judge_prompt)
    
    logger.info(f"Truth Check: {res_content}")

    # 判断最终结果
    final_prompt = f"""[FACT LIST]
{fact_content}

[TRUTH CHECK RESULT]
{res_content}

Task:
Decide the final truth using the info.
"""
    final_content = call_agent("final_truth", final_prompt)

    logger.info("\n工作流执行完成！")
    logger.info(f"\nTruth Result: {final_content}")
    
    # 从最终结果中解析出最终判断结果 TRUE/FALSE/UNCERTAIN
    final_result = "TRUE" if "TRUE" in final_content else "FALSE" if "FALSE" in final_content else "UNCERTAIN"
    
    return {
        "final_truth": final_result,
        "final_truth_reason": final_content,
        "facts": fact_content,
        "link_info": link_info,
        "truth_reason": res_content,
        "search_result": search_content,
        "intent": intent_content
    }

def aichecker_workflow(desc: str, link: Optional[Union[str, List[str]]], project_name: str = "AIChecker", **kwargs) -> Dict[str, Union[str, List[Dict[str, str]]]]:
    """
    AIChecker工作流，实现事实校验流程
    :param desc: 待检查的事实描述
    :param link: 相关链接，支持单个URL或URL列表
    :param project_name: 项目名称，默认值"AIChecker"
    :param kwargs: 其他参数，包括logger
    """
    logger = kwargs.get('logger', logging.getLogger(__name__))
    
    # 1. 初始化参数
    timestamp = int(time.time())  # 获取Unix时间戳（秒级）
    session_id = f"project-{project_name}-{timestamp}"
    logger.info(f"当前会话ID: {session_id}")

    # 2. 创建输出目录（确保目录存在，避免写入失败）
    output_dir = "./output"
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
        logger.info(f"创建输出目录: {output_dir}")

    try:
        # 第一步：意图分类与约束类型识别
        logger.info("Step 1: Start Intent Classification")
        logger.info(f"Description Content: \n{desc}")

        # 调用intent_classifier代理进行意图分类
        intent_content = call_agent("intent_classifier", f"[DESCRIPTION]\n{desc}\n Classify the intent of the description.")
        intent_content = json.loads(intent_content)
        logger.info(f"Intent Classification Result: {json.dumps(intent_content, ensure_ascii=False, indent=2)}")

        # 根据意图分类调用不同的工作流
        intent = intent_content["intent"]
        if intent in ["normative", "explanatory"]:
            logger.info(f"Intent is {intent}, using normative_explanatory_workflow")
            return normative_explanatory_workflow(desc, link, intent_content, **kwargs)
        elif intent == "factual":
            logger.info(f"Intent is {intent}, using factual_workflow")
            return factual_workflow(desc, link, **kwargs)
        else:
            logger.warning(f"Unknown intent: {intent}, using factual_workflow as default")
            return factual_workflow(desc, link, **kwargs)
        
    except Exception as e:
        logger.error(f"未知错误：{e}")
        raise

# 本地测试
if __name__ == "__main__":
    # 测试用例
    test_desc = "G2667 的开通年份为 2020 年"
    test_link = ["https://www.chuzhou.gov.cn/ztzl/mslyfwzt/jtcx/xgzx/1109459786.html"]
    
    result = aichecker_workflow(desc=test_desc, link=test_link)
    print(f"最终结果: {result['final_truth']}")
    print(f"最终原因: {result['final_truth_reason']}")

