from aichecker.workflow import aichecker_workflow
from aichecker.agents import call_agent
import logging
import argparse

# 配置日志格式
log_format = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
date_format = '%Y-%m-%d %H:%M:%S'

# 配置根日志记录器
root_logger = logging.getLogger()
root_logger.setLevel(logging.INFO)

# 添加文件处理器
file_handler = logging.FileHandler('./output/checker.log', mode='a')
file_handler.setLevel(logging.INFO)
file_formatter = logging.Formatter(fmt=log_format, datefmt=date_format)
file_handler.setFormatter(file_formatter)
root_logger.addHandler(file_handler)

# 添加控制台处理器
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.INFO)
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
    agent_parser.add_argument('-p', '--prompt', required=True, help='传递给agent的提示')
    agent_parser.add_argument('-a', '--agent', default='assistant', help='指定使用的agent（默认：assistant）')
    
    # 解析命令行参数
    args = parser.parse_args()
    
    # 根据模式执行不同的功能
    if args.mode == 'check':
        # 验真模式
        res = aichecker_workflow(args.desc, args.link)
        print(res)
    elif args.mode == 'agent':
        # 通用agent模式
        res = call_agent(args.agent, args.prompt)
        print(res)
    else:
        # 如果没有指定模式，显示帮助信息
        parser.print_help()

if __name__ == "__main__":
    main()