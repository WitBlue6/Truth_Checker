from aichecker.workflow import aichecker_workflow
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


if __name__ == "__main__":
    desc = "一拳超人第三季在2025年上映"
    link = []
    res = aichecker_workflow(desc, link)
    print(res)
