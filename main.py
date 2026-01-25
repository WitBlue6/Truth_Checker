from aichecker.workflow import aichecker_workflow
from aichecker.agents import call_agent_with_memory
from aichecker.mcp_host import get_mcp_host, stop_all_mcp_servers
import logging
import argparse
import uuid

# 配置日志格式
log_format = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
date_format = '%Y-%m-%d %H:%M:%S'

# 配置根日志记录器
root_logger = logging.getLogger()
root_logger.setLevel(logging.DEBUG)

# 添加文件处理器
file_handler = logging.FileHandler('./output/checker.log', mode='a')
file_handler.setLevel(logging.DEBUG)
file_formatter = logging.Formatter(fmt=log_format, datefmt=date_format)
file_handler.setFormatter(file_formatter)
root_logger.addHandler(file_handler)

# 添加控制台处理器
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.WARNING)
console_formatter = logging.Formatter(fmt=log_format, datefmt=date_format)
console_handler.setFormatter(console_formatter)
root_logger.addHandler(console_handler)

logger = logging.getLogger(__name__)

def main():
    # 创建命令行参数解析器
    parser = argparse.ArgumentParser(description='AI Truth Checker CLI Tool')
    
    # 创建子解析器来处理两种模式
    subparsers = parser.add_subparsers(dest='mode', help='运行模式')
    
    # 验真模式
    check_parser = subparsers.add_parser('check', help='验真模式')
    check_parser.add_argument('-d', '--desc', required=True, help='需要验真的描述')
    check_parser.add_argument('-l', '--link', action='append', default=[], help='可参考的链接（可多次使用）')
    
    # 通用agent模式
    agent_parser = subparsers.add_parser('agent', help='通用agent模式')
    agent_parser.add_argument('-p', '--prompt', help='无头模式，传递给agent的prompt（可选，如果不提供则进入交互式模式）')
    agent_parser.add_argument('-a', '--agent', default='assistant', help='指定使用的agent（默认：assistant）')
    agent_parser.add_argument('-m', '--memory', help='指定记忆ID（可选）')
    agent_parser.add_argument('--max-tool-calls', type=int, default=30, help='每轮对话的最大工具调用次数（默认：30）')
    agent_parser.add_argument('--max-repeated-calls', type=int, default=5, help='连续相同参数重复调用相同工具的最大次数（默认：5）')
    
    # 解析命令行参数
    args = parser.parse_args()
    
    # 根据模式执行不同的功能
    if args.mode == 'check':
        # 验真模式
        res = aichecker_workflow(args.desc, args.link)
        print(res)
    elif args.mode == 'agent':
        # 通用agent模式
        
        # 如果没有提供记忆ID，生成一个新的
        if not args.memory:
            memory_id = f"memory_{uuid.uuid4().hex[:8]}"
            print(f"生成新的记忆ID: {memory_id}")
        else:
            memory_id = args.memory
            print(f"使用指定的记忆ID: {memory_id}")
        
        # 如果提供了初始提示，先执行一次
        if args.prompt:
            res = call_agent_with_memory(
                args.agent, 
                args.prompt, 
                memory_id,
                max_tool_calls_per_round=args.max_tool_calls,
                max_repeated_tool_calls=args.max_repeated_calls
            )
            print("\n=== Agent 回复 ===")
            print(res)
        
        # 进入交互式模式
        print("\n=== 进入交互式模式 ===")
        print("输入消息与Agent对话，输入 ':q' 结束对话")
        print("-" * 50)
        
        while True:
            # 获取用户输入
            try:
                user_input = input(f"\n当前记忆ID: {memory_id} \n用户: ")
            except EOFError:
                print("\n输入结束，退出对话")
                break
            
            # 检查是否退出
            if user_input.strip() == ":q":
                print("\n退出对话")
                break
            
            # 调用Agent处理用户输入
            try:
                res = call_agent_with_memory(
                    args.agent, 
                    user_input, 
                    memory_id,
                    max_tool_calls_per_round=args.max_tool_calls,
                    max_repeated_tool_calls=args.max_repeated_calls
                )
                print("\n=== Agent 回复 ===")
                print(res)
                print("-" * 50)
            except Exception as e:
                print(f"\n发生错误: {str(e)}")
                print("-" * 50)
                
        # 对话结束后，停止所有MCP服务器
        mcp_host = get_mcp_host()
        if mcp_host:
            stop_all_mcp_servers(mcp_host)
    else:
        # 如果没有指定模式，显示帮助信息
        parser.print_help()

if __name__ == "__main__":
    main()