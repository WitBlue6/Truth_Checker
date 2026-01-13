from aichecker.workflow import aichecker_workflow
import logging

logging.basicConfig(level=logging.INFO,
                        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                        datefmt='%Y-%m-%d %H:%M:%S',
                        filename='./output/checker.log',
                        filemode='w')   
logger = logging.getLogger(__name__)

if __name__ == "__main__":
    desc = "北京理工大学徐博闻是2022级信息与电子学院学生"
    link = []
    res = aichecker_workflow(desc, link)
    print(res)
