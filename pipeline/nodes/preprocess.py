"""节点：预处理 —— 渲染页面、抽取文本层、计算图片覆盖、估算版面。"""
import os

import pymupdf as fitz

import config


def preprocess(state):
    task_id = state["task_id"]
    pdf_path = state["pdf_path"]
    out_dir = state["out_dir"]
    images_dir = state["images_dir"]
    pages_dir = os.path.join(out_dir, "pages")
    os.makedirs(pages_dir, exist_ok=True)
    os.makedirs(images_dir, exist_ok=True)

    logs = []
    try:
        doc = fitz.open(pdf_path)
        total = doc.page_count
        page_img_paths, page_texts, page_coverages, page_has_imgs = [], [], [], []

        for i, page in enumerate(doc):
            # 1) 渲染页面（供视觉模型与网页预览）
            zoom = config.RENDER_ZOOM
            mat = fitz.Matrix(zoom, zoom)
            pix = page.get_pixmap(matrix=mat, alpha=False)
            # 控制宽度上限，避免超长图
            if pix.width > config.VISION_MAX_W * 1.5:
                z2 = (config.VISION_MAX_W * 1.5) / pix.width
                mat = fitz.Matrix(zoom * z2, zoom * z2)
                pix = page.get_pixmap(matrix=mat, alpha=False)
            img_path = os.path.join(pages_dir, f"page_{i + 1:03d}.png")
            pix.save(img_path)
            page_img_paths.append(img_path)

            # 2) 文本层
            text = page.get_text("text", sort=True) or ""
            page_texts.append(text)

            # 3) 图片覆盖占比（跳过整页背景图），并标记页面是否含独立图片
            coverage = 0.0
            has_img = False
            try:
                blocks = page.get_text("dict", sort=True).get("blocks", [])
                pw, ph = page.rect.width, page.rect.height
                area = pw * ph
                for b in blocks:
                    if b.get("type") != 1:
                        continue
                    bx = b["bbox"]
                    bw, bh = bx[2] - bx[0], bx[3] - bx[1]
                    if bh <= 0 or bw <= 0:
                        continue
                    if bw * bh / area > config.BACKGROUND_IMG_COVERAGE:
                        has_img = True
                        continue  # 背景/整页图不算独立图片
                    has_img = True
                    coverage += bw * bh / area
            except Exception:
                pass
            page_coverages.append(round(coverage, 3))
            page_has_imgs.append(has_img)

        doc.close()
        return {
            "total_pages": total,
            "page_img_paths": page_img_paths,
            "page_texts": page_texts,
            "page_coverages": page_coverages,
            "page_has_imgs": page_has_imgs,
            "status": "running",
            "logs": logs + [f"预处理完成：{total} 页，已渲染页面图片并抽取文本层"],
        }
    except Exception as e:
        return {"status": "error", "error": f"预处理失败: {e}", "logs": logs}
