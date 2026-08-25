"""PDF → Markdown 转换服务（FastAPI + LangGraph）。

接口：
  GET  /                      网页
  GET  /api/health            健康检查
  POST /api/upload            上传 PDF 并启动解析（multipart file）
  GET  /api/tasks             任务列表
  GET  /api/task/{id}         任务详情
  GET  /api/task/{id}/markdown  Markdown 原文
  GET  /api/task/{id}/page/{n}  页面渲染图
  GET  /api/task/{id}/images/{f} 图片资源
  GET  /api/task/{id}/pdf     原始 PDF
  GET  /api/task/{id}/download 打包下载（output.md + images）
  POST /api/task/{id}/rerun   重新解析
  DELETE /api/task/{id}       删除任务
"""
import io
import json
import os
import shutil
import threading
import time
import uuid
import zipfile
from datetime import datetime

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles

import config
from pipeline.graph import compiled_graph

app = FastAPI(title="PDF → Markdown", docs_url="/docs")
config.ensure_dirs()

REGISTRY = os.path.join(config.DATA_DIR, "tasks.json")
_lock = threading.Lock()


# ---------------- 任务注册表 ----------------
def _load_registry():
    if os.path.exists(REGISTRY):
        try:
            with open(REGISTRY, encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}


def _save_registry(reg):
    with open(REGISTRY, "w", encoding="utf-8") as f:
        json.dump(reg, f, ensure_ascii=False, indent=2)


def _task_dir(task_id):
    return os.path.join(config.TASKS_DIR, task_id)


def _safe_name(name: str) -> str:
    return "".join(c for c in (name or "upload.pdf") if c.isalnum() or c in "._- ").strip() or "upload.pdf"


# ---------------- 解析执行 ----------------
def _run_parse(task_id, pdf_path, name):
    out_dir = _task_dir(task_id)
    images_dir = os.path.join(out_dir, "images")
    os.makedirs(images_dir, exist_ok=True)
    initial = {
        "task_id": task_id,
        "pdf_path": pdf_path,
        "out_dir": out_dir,
        "images_dir": images_dir,
        "status": "running",
        "logs": [f"开始解析：{name}"],
    }
    t0 = time.time()
    try:
        result = compiled_graph.invoke(initial)
        dt = time.time() - t0
        if result.get("status") == "error":
            with _lock:
                reg = _load_registry()
                if task_id in reg:
                    reg[task_id]["status"] = "failed"
                    reg[task_id]["error"] = result.get("error")
                    reg[task_id]["updated"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    _save_registry(reg)
            return
        # 更新清单耗时
        mp = os.path.join(out_dir, "manifest.json")
        if os.path.exists(mp):
            try:
                with open(mp, encoding="utf-8") as f:
                    man = json.load(f)
                man["elapsed_sec"] = round(dt, 1)
                man["status"] = "done"
                with open(mp, "w", encoding="utf-8") as f:
                    json.dump(man, f, ensure_ascii=False, indent=2)
            except Exception:
                pass
        with _lock:
            reg = _load_registry()
            if task_id in reg:
                reg[task_id]["status"] = "done"
                reg[task_id]["elapsed_sec"] = round(dt, 1)
                reg[task_id]["updated"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                _save_registry(reg)
    except Exception as e:
        with _lock:
            reg = _load_registry()
            if task_id in reg:
                reg[task_id]["status"] = "failed"
                reg[task_id]["error"] = str(e)
                reg[task_id]["updated"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                _save_registry(reg)


def _start_parse(task_id, pdf_path, name):
    t = threading.Thread(target=_run_parse, args=(task_id, pdf_path, name), daemon=True)
    t.start()


# ---------------- 路由 ----------------
@app.get("/api/health")
def health():
    return {"ok": True, "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S")}


@app.post("/api/upload")
async def upload(file: UploadFile = File(...)):
    name = _safe_name(file.filename)
    if not name.lower().endswith(".pdf"):
        raise HTTPException(400, "仅支持 PDF 文件")
    task_id = uuid.uuid4().hex[:12]
    out_dir = _task_dir(task_id)
    os.makedirs(out_dir, exist_ok=True)
    pdf_path = os.path.join(out_dir, "input.pdf")
    content = await file.read()
    if len(content) < 50 or not content.startswith(b"%PDF"):
        shutil.rmtree(out_dir, ignore_errors=True)
        raise HTTPException(400, "文件不是有效的 PDF")
    with open(pdf_path, "wb") as f:
        f.write(content)

    with _lock:
        reg = _load_registry()
        reg[task_id] = {
            "task_id": task_id,
            "name": name,
            "status": "running",
            "created": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "updated": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "size_kb": round(len(content) / 1024, 1),
            "error": None,
        }
        _save_registry(reg)
    _start_parse(task_id, pdf_path, name)
    return {"task_id": task_id, "name": name, "status": "running"}


@app.get("/api/tasks")
def tasks():
    reg = _load_registry()
    items = []
    for tid, info in sorted(reg.items(), key=lambda x: x[1].get("created", ""), reverse=True):
        d = dict(info)
        out = _task_dir(tid)
        d["has_markdown"] = os.path.exists(os.path.join(out, "output.md"))
        n_imgs = 0
        img_dir = os.path.join(out, "images")
        if os.path.isdir(img_dir):
            n_imgs = len([x for x in os.listdir(img_dir) if x.lower().endswith((".png", ".jpg", ".jpeg"))])
        d["images"] = n_imgs
        if os.path.exists(os.path.join(out, "manifest.json")):
            try:
                with open(os.path.join(out, "manifest.json"), encoding="utf-8") as f:
                    man = json.load(f)
                d["total_pages"] = man.get("total_pages")
                d["page_types"] = man.get("page_types")
            except Exception:
                pass
        items.append(d)
    return {"tasks": items}


@app.get("/api/task/{task_id}")
def task_detail(task_id: str):
    out = _task_dir(task_id)
    if not os.path.isdir(out):
        raise HTTPException(404, "任务不存在")
    reg = _load_registry()
    info = dict(reg.get(task_id, {}))
    info["task_id"] = task_id
    info["out_dir"] = out
    man_path = os.path.join(out, "manifest.json")
    if os.path.exists(man_path):
        try:
            with open(man_path, encoding="utf-8") as f:
                info["manifest"] = json.load(f)
        except Exception:
            info["manifest"] = None
    if not os.path.exists(man_path) and info.get("status") == "running":
        info["status"] = "running"
    info["logs"] = (info.get("manifest") or {}).get("logs") or []
    return info


@app.get("/api/task/{task_id}/markdown")
def task_markdown(task_id: str):
    p = os.path.join(_task_dir(task_id), "output.md")
    if not os.path.exists(p):
        raise HTTPException(404, "还没有生成 Markdown")
    with open(p, encoding="utf-8") as f:
        return Response(f.read(), media_type="text/markdown; charset=utf-8")


@app.get("/api/task/{task_id}/page/{n}")
def task_page(task_id: str, n: int):
    p = os.path.join(_task_dir(task_id), "pages", f"page_{n:03d}.png")
    if not os.path.exists(p):
        raise HTTPException(404, "页面不存在")
    return FileResponse(p, media_type="image/png")


@app.get("/api/task/{task_id}/images/{fname}")
def task_image(task_id: str, fname: str):
    p = os.path.join(_task_dir(task_id), "images", os.path.basename(fname))
    if not os.path.exists(p):
        raise HTTPException(404, "图片不存在")
    return FileResponse(p)


@app.get("/api/task/{task_id}/pdf")
def task_pdf(task_id: str):
    p = os.path.join(_task_dir(task_id), "input.pdf")
    if not os.path.exists(p):
        raise HTTPException(404, "PDF 不存在")
    reg = _load_registry()
    name = reg.get(task_id, {}).get("name", "input.pdf")
    return FileResponse(p, media_type="application/pdf", filename=name)


@app.get("/api/task/{task_id}/download")
def task_download(task_id: str):
    out = _task_dir(task_id)
    if not os.path.isdir(out):
        raise HTTPException(404, "任务不存在")
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for root, _, files in os.walk(out):
            for fn in files:
                fp = os.path.join(root, fn)
                if fn == "input.pdf":
                    continue
                arc = os.path.relpath(fp, out)
                z.write(fp, arc)
    buf.seek(0)
    reg = _load_registry()
    name = (reg.get(task_id, {}).get("name") or "task").replace(".pdf", "")
    return Response(buf.getvalue(), media_type="application/zip",
                    headers={"Content-Disposition": f'attachment; filename="{name}_markdown.zip"'})


@app.post("/api/task/{task_id}/rerun")
def task_rerun(task_id: str):
    out = _task_dir(task_id)
    pdf_path = os.path.join(out, "input.pdf")
    if not os.path.exists(pdf_path):
        raise HTTPException(404, "PDF 不存在")
    # 清掉旧产出
    for d in ("images", "pages"):
        shutil.rmtree(os.path.join(out, d), ignore_errors=True)
    for fn in os.listdir(out):
        if fn in ("input.pdf",):
            continue
        fp = os.path.join(out, fn)
        if os.path.isfile(fp):
            os.remove(fp)
        else:
            shutil.rmtree(fp, ignore_errors=True)
    reg = _load_registry()
    if task_id in reg:
        reg[task_id]["status"] = "running"
        reg[task_id]["error"] = None
        reg[task_id]["updated"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        _save_registry(reg)
    _start_parse(task_id, pdf_path, reg.get(task_id, {}).get("name", "input.pdf"))
    return {"task_id": task_id, "status": "running"}


@app.delete("/api/task/{task_id}")
def task_delete(task_id: str):
    out = _task_dir(task_id)
    if not os.path.isdir(out):
        raise HTTPException(404, "任务不存在")
    shutil.rmtree(out, ignore_errors=True)
    with _lock:
        reg = _load_registry()
        reg.pop(task_id, None)
        _save_registry(reg)
    return {"ok": True}


# 静态前端（放在最后，避免覆盖 API）
app.mount("/", StaticFiles(directory=os.path.join(config.BASE_DIR, "static"), html=True), name="static")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", "16082")), log_level="info")
