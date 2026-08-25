"""节点：页面分类 —— 依据文本层字符数与图片覆盖占比决定解析路线。"""
import config


def classify(state):
    page_texts = state["page_texts"]
    page_coverages = state["page_coverages"]
    page_has_imgs = state.get("page_has_imgs") or [False] * len(page_texts)
    total = state["total_pages"]
    page_types = []
    for i in range(total):
        text = (page_texts[i] or "").strip()
        n = len(text)
        cov = page_coverages[i] if i < len(page_coverages) else 0.0
        has_img = page_has_imgs[i] if i < len(page_has_imgs) else False
        if n < 5 and not has_img:
            t = "blank"             # 无文字无图片 → 空白页
        elif n < config.TEXT_PAGE_MIN_CHARS:
            t = "scanned"           # 几乎没有可复制文本（但含整页/大图）→ 影印页
        elif cov >= config.MIXED_IMG_COVERAGE:
            t = "mixed"             # 有文本但图片占比高 → 视觉页
        else:
            t = "text"              # 以文本层为准
        page_types.append(t)
    counts = {t: page_types.count(t) for t in set(page_types)}
    return {
        "page_types": page_types,
        "status": "running",
        "logs": [f"页面分类：{counts}"],
    }
