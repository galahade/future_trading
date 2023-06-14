import os
from headquarters.headquarters import Commander
from utils import common
import sys
import logging

now = common.now
is_back_test = False
start_year = now.year
start_month = 1
end_year = now.year
log_level = "debug"
trade_type = 2
env_name = os.environ['ENV_NAME']


logger = logging.getLogger(__name__)


def main():
    try:
        systemConfig = common.get_argumets()
        log_config_file = f'log_config_{env_name}'
        common.setup_log_config(log_level, log_config_file)
        commander = Commander(systemConfig.is_back_test)
        commander.start_work()
    except Exception as e:
        logger.exception(e)
        return str(e)


if __name__ == "__main__":
    sys.exit(main())
