"""命令行测试：直接跑 LangGraph 管线解析单个 PDF。"""
import json
import os
import sys
import time
import uuid

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import config
from pipeline.graph import compiled_graph


def run_pdf(pdf_path, name=None):
    config.ensure_dirs()
    task_id = uuid.uuid4().hex[:12]
    out_dir = os.path.join(config.TASKS_DIR, task_id)
    images_dir = os.path.join(out_dir, "images")
    os.makedirs(images_dir, exist_ok=True)

    initial = {
        "task_id": task_id,
        "pdf_path": os.path.abspath(pdf_path),
        "out_dir": out_dir,
        "images_dir": images_dir,
        "status": "running",
        "logs": [],
    }
    t0 = time.time()
    result = compiled_graph.invoke(initial)
    dt = time.time() - t0

    status = result.get("status")
    print(f"\n===== {name or pdf_path} =====")
    print(f"task_id={task_id}  status={status}  耗时={dt:.1f}s  页数={result.get('total_pages')}")
    print(f"页面类型: {result.get('page_types')}")
    for log in result.get("logs") or []:
        print("  LOG:", log)
    if status == "error":
        print("ERROR:", result.get("error"))
        return task_id, None
    md = result.get("final_markdown") or ""
    print(f"输出 markdown 长度: {len(md)}")
    manifest_path = os.path.join(out_dir, "manifest.json")
    if os.path.exists(manifest_path):
        with open(manifest_path, encoding="utf-8") as f:
            man = json.load(f)
        print(f"图片 {len(man.get('images') or [])} 张:", [i["file"] for i in man.get("images") or []])
    print("---- markdown 预览 ----")
    print(md[:2500])
    return task_id, out_dir


if __name__ == "__main__":
    pdf = sys.argv[1] if len(sys.argv) > 1 else "tests/pdfs/test_text.pdf"
    name = sys.argv[2] if len(sys.argv) > 2 else None
    run_pdf(pdf, name)
