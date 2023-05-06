from utils.common_tools import get_yaml_config


config = get_yaml_config('secrets/system_config.yaml')
print(config['trade']['backtest_days']['start_date'])
