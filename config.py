"""全局配置：LLM 提供商、路径等。"""
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent  # 项目根
DATA_DIR = BASE_DIR / "data"
TASKS_DIR = DATA_DIR / "tasks"

# 解析时渲染页面使用的缩放倍率（1.0=72dpi，2.0=144dpi）
RENDER_ZOOM = float(os.environ.get("RENDER_ZOOM", "2.5"))
# 传给视觉模型的页面图片最大宽度（像素），超过则等比例缩小
VISION_MAX_W = int(os.environ.get("VISION_MAX_W", "1600"))
# 同时并发处理的页数（视觉请求受 API 限制，控制并发）
MAX_PARALLEL_PAGES = int(os.environ.get("MAX_PARALLEL_PAGES", "3"))
# 每页最大 token 预算
MAX_TOKENS_PAGE = int(os.environ.get("MAX_TOKENS_PAGE", "3000"))

# 文本页内嵌图片：是否做内容识别（表格转录 / 描述）
OCR_EMBEDDED_IMAGES = os.environ.get("OCR_EMBEDDED_IMAGES", "1") == "1"
# 扫描页首轮未检出图片时，是否做插图补检
FIG_SECOND_PASS = os.environ.get("FIG_SECOND_PASS", "1") == "1"

# 页面分类阈值
TEXT_PAGE_MIN_CHARS = int(os.environ.get("TEXT_PAGE_MIN_CHARS", "30"))
MIXED_IMG_COVERAGE = float(os.environ.get("MIXED_IMG_COVERAGE", "0.25"))
BACKGROUND_IMG_COVERAGE = float(os.environ.get("BACKGROUND_IMG_COVERAGE", "0.70"))

# ---- LLM 提供商（OpenAI 兼容）----
# 多模态视觉模型（图片页/影印页提取）
VISION = {
    "base_url": os.environ.get("VISION_BASE_URL", "x"),
    "api_key": os.environ.get("VISION_API_KEY", "x"),
    "model": os.environ.get("VISION_MODEL", "x"),
}
# 文本整理模型（文本页结构整理）
TEXT_LLM = {
    "base_url": os.environ.get("TEXT_BASE_URL", "https://api.deepseek.com"),
    "api_key": os.environ.get("TEXT_API_KEY", "sk-edb9df58ff574f8c98df1cd6a425e97c"),
    "model": os.environ.get("TEXT_MODEL", "deepseek-chat"),
}

VISION_TIMEOUT = int(os.environ.get("VISION_TIMEOUT", "600"))
TEXT_TIMEOUT = int(os.environ.get("TEXT_TIMEOUT", "180"))
RETRIES = int(os.environ.get("LLM_RETRIES", "2"))


def ensure_dirs():
    for d in (DATA_DIR, TASKS_DIR):
        d.mkdir(parents=True, exist_ok=True)
