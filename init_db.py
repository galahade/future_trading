from utils import future_config_utils
import sys
import logging
from utils.common import get_init_db_args

log_level = "warning"


def main():
    try:
        logger = logging.getLogger(__name__)
        logger.debug("开始向数据库导入期货配置数据")
        future_config_utils.store_future_config_to_db(
            *get_init_db_args()
        )
    except Exception as e:
        logger.exception(e)
        return str(e)


if __name__ == "__main__":
    sys.exit(main())
