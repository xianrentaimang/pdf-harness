"""节点：组装 —— 合并各页 markdown、替换图片占位符、写文件与清单。"""
import json
import os
import re
from datetime import datetime

TOKEN_RE = re.compile(r"\{\{IMG_(\d+)\}\}")


def _finalize_page_md(md: str, saved_images: list) -> str:
    """把视觉页的 {{IMG_n}} 占位符替换为 markdown 图片引用（页内作用域）。"""
    by_token = {}
    for s in saved_images or []:
        if s.get("token"):
            by_token[s["token"]] = f"![{s.get('alt') or '图片'}](images/{s['file']})"
    for tok, img_md in by_token.items():
        md = md.replace(tok, img_md)
    # 若还有残留的 {{IMG_n}}（模型报了但没裁出来），清理
    md = TOKEN_RE.sub("", md)
    return md.strip()


def assemble(state):
    out_dir = state["out_dir"]
    images_dir = state["images_dir"]
    page_results = sorted(state.get("page_results") or [], key=lambda x: x["idx"])

    parts = []
    all_saved = []
    for pr in page_results:
        md = _finalize_page_md(pr.get("md") or "", pr.get("saved_images") or [])
        parts.append(md)
        all_saved.extend(pr.get("saved_images") or [])
    all_saved.extend(state.get("saved_images") or [])

    # 去重
    seen_files = set()
    dedup = []
    for s in all_saved:
        if s["file"] not in seen_files:
            seen_files.add(s["file"])
            dedup.append(s)

    # 组装：页间分隔
    final = "\n\n---\n\n".join(parts)
    final = final.strip() + "\n"

    # 写文件
    os.makedirs(out_dir, exist_ok=True)
    md_path = os.path.join(out_dir, "output.md")
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(final)
    # 每页单独存
    for pr in page_results:
        with open(os.path.join(out_dir, f"page_{pr['idx'] + 1:03d}.md"), "w", encoding="utf-8") as f:
            f.write(_finalize_page_md(pr.get("md") or "", pr.get("saved_images") or []))

    manifest = {
        "task_id": state["task_id"],
        "status": "done",
        "updated": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "total_pages": state["total_pages"],
        "page_types": state.get("page_types") or [],
        "output_md": "output.md",
        "images_dir": "images",
        "images": dedup,
        "metrics": state.get("metrics") or {},
        "logs": (state.get("logs") or []) + [f"组装完成：{len(page_results)} 页 → output.md，共 {len(dedup)} 张图片"],
    }
    with open(os.path.join(out_dir, "manifest.json"), "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)

    return {
        "final_markdown": final,
        "status": "done",
        "metrics": {"images": len(dedup), "pages": len(page_results), "chars": len(final)},
        "logs": [f"组装完成：{len(page_results)} 页 → output.md，共 {len(dedup)} 张图片"],
    }
