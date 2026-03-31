"""
配置模块 — 集中管理 API Key 和全局设置
优先从环境变量读取，也支持 .env 文件
"""

import os

# ────────────────────── Kimi 配置 ──────────────────────

KIMI_API_KEY = os.getenv("KIMI_API_KEY", "")
KIMI_MODEL = os.getenv("KIMI_MODEL", "moonshot-v1-8k")  # 可选: moonshot-v1-8k / 32k / 128k

# ────────────────────── 摘要设置 ──────────────────────

# 摘要目标语言
SUMMARY_LANGUAGE = os.getenv("SUMMARY_LANGUAGE", "中文")
# 摘要最大长度（字）
SUMMARY_MAX_LENGTH = int(os.getenv("SUMMARY_MAX_LENGTH", "300"))
# 是否自动在抓取后进行摘要
AUTO_SUMMARIZE = os.getenv("AUTO_SUMMARIZE", "false").lower() == "true"


def load_dotenv():
    """简易 .env 加载器，不依赖第三方库"""
    env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
    if not os.path.exists(env_path):
        return
    with open(env_path) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" in line:
                key, _, value = line.partition("=")
                key = key.strip()
                value = value.strip().strip('"').strip("'")
                os.environ.setdefault(key, value)


# 启动时加载
load_dotenv()

# 重新读取（.env 可能刚设置了环境变量）
KIMI_API_KEY = os.getenv("KIMI_API_KEY", KIMI_API_KEY)
KIMI_MODEL = os.getenv("KIMI_MODEL", KIMI_MODEL)
