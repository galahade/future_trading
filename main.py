from headquarters.headquarters import Commander
from utils import common
import sys
import logging
from utils import global_var as gvar
import warnings
# 忽略所有警告信息
warnings.filterwarnings("ignore")

now = common.now
is_back_test = False
start_year = now.year
start_month = 1
end_year = now.year
log_level = "debug"
trade_type = 2


logger = logging.getLogger(__name__)


def main():
    try:
        log_config_file = f'log_config_{gvar.ENV_NAME}'
        common.setup_log_config(log_level, log_config_file)
        commander = Commander()
        commander.start_work()
    except Exception as e:
        logger.exception(e)


if __name__ == "__main__":
    sys.exit(main())
