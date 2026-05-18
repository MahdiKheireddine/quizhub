# env.py
import environ
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

env = environ.Env()

# Read .env file
env.read_env(BASE_DIR / ".env")