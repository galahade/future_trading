import os

from dotenv import load_dotenv

load_dotenv()
SYSTEM_CONFIG_PATH = os.getenv("SYSTEM_CONFIG_PATH")
FUTURE_CONFIG_PATH = os.getenv("FUTURE_CONFIG_PATH")
ENV_NAME = os.environ["ENV_NAME"]
TQKQ_NUMBER = int(os.environ["TQKQ_NUMBER"])
PUSH_KEY = "PDU20739T7ZemNBLmqiMV8CYNKUm665tYsoAshLKo"
