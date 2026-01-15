import logging
import sys
import os

root_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(root_path)

from aichecker.workflow import aichecker_workflow

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

if __name__ == "__main__":
    desc = "周瑜那匹马叫萌萌的说法啊，我在网上查了一下，说是出自《荆益风物志·骠马第十二》“荆襄有马，其名曰萌，本为前部大督周瑜坐骑，建安十三年十一月诞於赤壁”，但这本书是找不到的，所以大概率是瞎编出来的，而萌萌这个名字是出自《赤壁》里那句著名雷人台词“既然它生在荆楚之地，就叫它萌萌吧”，考虑到《荆益》这个说法在互联网上最早可以溯源到2011年，而《赤壁》上映于08年，所以大概率可能是该片粉丝为了给台词找补编出来的谎言。"
    link = []
    res = aichecker_workflow(desc, link)
    print(res)