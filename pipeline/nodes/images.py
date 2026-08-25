"""节点：图片裁剪 —— 将视觉模型检测到的图片区域从渲染页中裁出保存到 images/。"""
import os

from PIL import Image

MIN_CROP = 48  # 小于此尺寸的裁剪视为误检，跳过


def _crop_regions(page_result, page_img_path, images_dir):
    saved = []
    regions = page_result.get("image_regions") or []
    if not regions:
        return saved
    try:
        im = Image.open(page_img_path)
        W, H = im.size
        for r in regions:
            b = r["bbox"]
            if len(b) != 4:
                continue
            x1 = max(0, int(b[0] / 100.0 * W))
            y1 = max(0, int(b[1] / 100.0 * H))
            x2 = min(W, int(b[2] / 100.0 * W))
            y2 = min(H, int(b[3] / 100.0 * H))
            if x2 - x1 < MIN_CROP or y2 - y1 < MIN_CROP:
                continue
            fname = f"img_{r['page']:03d}_{r['n']:03d}.png"
            crop = im.crop((x1, y1, x2, y2))
            crop.save(os.path.join(images_dir, fname))
            saved.append({
                "file": fname,
                "alt": r.get("alt") or "图片",
                "page": r["page"],
                "token": r["token"],
            })
    except Exception as e:
        return saved, str(e)
    return saved, None


def extract_images(state):
    page_results = state.get("page_results") or []
    images_dir = state["images_dir"]
    out_dir = state["out_dir"]
    pages_dir = os.path.join(out_dir, "pages")
    saved_all = list(state.get("saved_images") or [])
    errors = []
    cropped = 0
    for pr in page_results:
        # 文本页已在内嵌图片裁剪时保存的
        saved_all.extend(pr.get("saved_images") or [])
        regions = pr.get("image_regions") or []
        if not regions:
            continue
        page_img = os.path.join(pages_dir, f"page_{pr['idx'] + 1:03d}.png")
        if not os.path.exists(page_img):
            continue
        saved, err = _crop_regions(pr, page_img, images_dir)
        cropped += len(saved)
        saved_all.extend(saved)
        if err:
            errors.append(err)
        pr["saved_images"] = saved
    return {
        "saved_images": saved_all,
        "status": "running",
        "logs": ([f"图片提取：视觉裁剪 {cropped} 张，共 {len(saved_all)} 张图片"] + ([f"裁剪问题: {errors}"] if errors else [])),
    }
