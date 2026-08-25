"""节点：单页内容提取（map 阶段，通过 Send 并行）。

- text 页：文本层按读取顺序抽取 + 内嵌图片裁剪 + LLM 结构整理
- scanned/mixed 页：多模态视觉模型整页提取 + 图片区域检测
"""
import os
import re

import pymupdf as fitz

import config
from pipeline.llm import chat_text, chat_vision, extract_json_after_marker

# 图片占位符，例如 [[IMG:img_001.png|图表说明]]
PLACEHOLDER_RE = re.compile(r"\[\[IMG:([^\]]+)\]\]")

STRUCT_SYSTEM = (
    "你是专业的 PDF 文本层转 Markdown 整理器。对给定文本进行忠实整理，"
    "不增删、不改写内容，不编造原文没有的信息。"
)
STRUCT_USER = """下面是 PDF 某页的文本层内容（可能包含 [[IMG:文件名]] 图片占位符，必须原样保留，一个都不能少、不能改）。
请整理为规范 Markdown：
- 标题识别层级（# 一级 / ## 二级 / ### 三级）
- 列表、段落用标准 markdown 表示
- 按空格/制表符对齐的表格识别为 Markdown 表格（表头用 | --- |）
- 保持内容忠实原文，不得合并、省略或编造任何文字
- 直接输出 Markdown 正文，不要用代码块包裹

文本内容：
\"\"\"
{raw}
\"\"\"
"""

VISION_SYSTEM = (
    "你是专业的中文 PDF 扫描件转 Markdown 引擎，输出准确、忠实原文的内容。"
    "转录规则：不得在任何字符之间插入多余空格，数字、英文单词、中文句子必须保持原文的连贯写法（例如 1200 不能写成 1 2 0 0）；"
    "不得改写、不得总结、不得遗漏、不得翻译。"
)
VISION_USER = """请分析这张 PDF 页面图片，输出规范 Markdown：
1. 逐字准确转录页面上所有文字（中文/英文/数字，保持原文连贯写法，不要添加多余空格，不要改写、不要总结、不要遗漏、不要翻译）。
2. 标题用 #/##/### 层级；列表用 - 或数字；段落用空行分隔。
3. 表格转为 Markdown 表格（表头用 | --- |），单元格内容保持原文。
4. 页面上的独立图片/图表/插图（非文字），在正文相应位置插入占位符 {{IMG_序号}}（序号从 1 开始递增），并用中文简短描述其内容作为 alt。
5. 输出末尾单独一行输出图片位置 JSON 区块：
###JSON###
[{{"n":1,"bbox":[x1,y1,x2,y2],"alt":"图片描述"}}]
其中 bbox 是图片矩形相对页面宽高的百分比（0~100，坐标原点在页面左上角），有几张图就列几项。
6. 水印、页眉页脚装饰内容不要输出。
只输出 Markdown 正文与 JSON 区块，不要输出任何解释。"""

# 内嵌图片内容识别：是表格就转录，否则给描述
CROP_SYSTEM = (
    "你是 PDF 图片内容识别器。只做两件事：把表格转成 Markdown 表格，或给非表格图片写一句简短中文描述。"
)
CROP_USER = """这是从 PDF 页面中裁剪出的一张图片。请判断：
- 如果它是一张表格：输出完整的 Markdown 表格（| --- | 表头），保留所有单元格内容，不要遗漏；
- 如果它是普通图片/图表/照片/示意图：只输出一行简短中文描述（说明画的是什么）；
不要输出任何解释或多余内容。"""

# 扫描页插图补检：首轮未检出图片时，专门找一次插图区域
FIG_SYSTEM = "你是 PDF 扫描页插图检测器。"
FIG_USER = """这张图是 PDF 的一个扫描页面。页面上除了文字，可能还包含独立的插图/照片/图表（例如一张风景照片、一张示意图）。
如果存在这样的独立插图，输出：
###JSON###
[{{"n":1,"bbox":[x1,y1,x2,y2],"alt":"插图描述"}}]
bbox 为该插图相对页面宽高的百分比（0~100，左上角为原点）。有几张就列几项。
如果整页就是一张扫描图、没有明显独立的插图，输出：###JSON###
[]
只输出 JSON 区块，不要输出其他内容。"""


def _block_text(b: dict) -> str:
    """从文本块重建文本，按 x 间距补空格，避免单词粘连。"""
    lines_out = []
    for line in b.get("lines", []):
        parts = []
        prev_end = None
        for s in line.get("spans", []):
            if prev_end is not None and s["bbox"][0] - prev_end > 3:
                parts.append(" ")
            parts.append(s.get("text", ""))
            prev_end = s["bbox"][2]
        lines_out.append("".join(parts))
    return "\n".join(lines_out)


def _looks_like_caption(text: str) -> str:
    """粗略判断下一段是否为图注，返回去掉编号后的说明文字。"""
    t = (text or "").strip().replace("\n", " ")
    m = re.match(r"^(图|表|Figure|Table)\s*[\d.。:：\-]*(.*)$", t, re.I)
    if m and len(m.group(2).strip()) > 2:
        return m.group(2).strip()
    return ""


def _save_image_block(block: dict, bbox_px, images_dir, fname) -> bool:
    """优先保存内嵌原始图像，失败返回 False 交给渲染裁剪兜底。"""
    try:
        raw = block.get("image")
        ext = block.get("ext") or "png"
        if not raw:
            return False
        bw, bh = block.get("width", 0), block.get("height", 0)
        # 原图分辨率不应明显低于渲染裁剪的分辨率
        if bw * bh < (bbox_px[2] - bbox_px[0]) * (bbox_px[3] - bbox_px[1]) * 0.6:
            return False
        with open(os.path.join(images_dir, fname), "wb") as f:
            f.write(raw)
        return True
    except Exception:
        return False


def _describe_crop(image_path: str) -> tuple:
    """对裁剪出的内嵌图片做内容识别。返回 (kind, content)：kind 为 table / desc。"""
    try:
        out = chat_vision(image_path, CROP_SYSTEM, CROP_USER, max_tokens=2000).strip()
        if out.startswith("```"):
            out = out.strip("`")
            if out.lower().startswith("markdown"):
                out = out[len("markdown"):].strip()
        if "|" in out and ("---" in out or "—" in out or out.count("|") >= 4):
            return "table", out
        # 去掉可能的引号
        desc = out.strip("\"' ")
        return "desc", desc or "图片"
    except Exception:
        return "desc", "图片"


def _extract_text_page(pdf_path, idx, images_dir, out_dir) -> dict:
    """text 页：文本层 + 内嵌图片。"""
    doc = fitz.open(pdf_path)
    page = doc[idx]
    zoom = config.RENDER_ZOOM
    pw, ph = page.rect.width, page.rect.height
    area = pw * ph

    # 先渲染一版，供图片裁剪兜底
    pix = page.get_pixmap(matrix=fitz.Matrix(zoom, zoom), alpha=False)

    blocks = page.get_text("dict", sort=True).get("blocks", [])
    parts = []
    saved = []

    n_blocks = len(blocks)
    for bi, b in enumerate(blocks):
        if b.get("type") == 0:
            t = _block_text(b)
            parts.append(t)
        elif b.get("type") == 1:
            bb = b["bbox"]
            bw, bh = bb[2] - bb[0], bb[3] - bb[1]
            if bw <= 0 or bh <= 0:
                continue
            if bw * bh / area > config.BACKGROUND_IMG_COVERAGE:
                continue  # 整页背景图跳过
            fname = f"img_{idx + 1:03d}_{len(saved) + 1:03d}.png"
            # 像素坐标 = pt * zoom
            bbox_px = [int(x * zoom) for x in bb]
            ok = _save_image_block(b, bbox_px, images_dir, fname)
            if not ok:
                try:
                    crop = pix.subset_pixmap(bbox_px)
                    crop.save(os.path.join(images_dir, fname))
                except Exception:
                    continue
            # 向前查找图注（紧随图片之后的文本块）
            alt = "图片"
            for k in range(bi + 1, min(bi + 4, n_blocks)):
                nb = blocks[k]
                if nb.get("type") != 0:
                    break
                c = _looks_like_caption(_block_text(nb))
                if c:
                    alt = c
                    break
                break  # 非图注文本则停止查找
            saved.append({"file": fname, "alt": alt, "page": idx + 1, "token": None})
            parts.append(f"[[IMG:{fname}]]")
    doc.close()

    raw = "\n\n".join(parts)
    md = raw
    try:
        if raw.strip():
            md = chat_text(STRUCT_SYSTEM, STRUCT_USER.format(raw=raw), max_tokens=config.MAX_TOKENS_PAGE)
    except Exception as e:
        md = raw  # LLM 失败时退回原始文本层

    # 对每张内嵌图做内容识别（表格转录 / 描述），替换占位符
    def _to_img(m):
        tok = m.group(1)
        info = next((s for s in saved if s["file"] == tok), None)
        alt = info["alt"] if info else "图片"
        fpath = os.path.join(images_dir, tok)
        if os.path.exists(fpath) and config.OCR_EMBEDDED_IMAGES:
            kind, content = _describe_crop(fpath)
            if kind == "table":
                return f"<!-- 表格原图: images/{tok} -->\n\n{content}"
            alt = content
        return f"![{alt}](images/{tok})"

    md = PLACEHOLDER_RE.sub(_to_img, md)
    # 防漏：若某张已保存图片未出现在 md 中，追加在页尾
    for s in saved:
        if s["file"] not in md:
            md += f"\n\n![{s['alt']}](images/{s['file']})\n"
    return {"idx": idx, "type": "text", "md": md, "image_regions": [], "saved_images": saved}


def _extract_vision_page(pdf_path, idx, page_img_path, out_dir) -> dict:
    """scanned/mixed 页：视觉模型整页提取 + 图片区域检测。"""
    md = ""
    try:
        md = chat_vision(page_img_path, VISION_SYSTEM, VISION_USER, max_tokens=config.MAX_TOKENS_PAGE)
    except Exception as e:
        md = f"> [第 {idx + 1} 页视觉提取失败: {e}]\n"
    regions = extract_json_after_marker(md)
    # 从正文中剥离 JSON 区块
    if "###JSON###" in md:
        md = md.split("###JSON###")[0]
    md = md.strip()

    # 首轮未检出图片时，做一次专门的插图补检（如扫描页内嵌照片/示意图）
    if not regions and config.FIG_SECOND_PASS:
        try:
            fig_out = chat_vision(page_img_path, FIG_SYSTEM, FIG_USER, max_tokens=1200)
            extra = extract_json_after_marker(fig_out)
            if extra:
                regions = extra
        except Exception:
            pass

    cleaned_regions = []
    seen = set()
    for r in regions:
        n = int(r.get("n", len(seen) + 1))
        if n in seen:
            continue
        seen.add(n)
        bb = r.get("bbox") or []
        if len(bb) != 4:
            continue
        cleaned_regions.append({
            "page": idx + 1,
            "n": n,
            "bbox": [float(x) for x in bb],
            "alt": str(r.get("alt") or "图片"),
            "token": f"{{{{IMG_{n}}}}}",
        })
    return {"idx": idx, "type": "scanned", "md": md, "image_regions": cleaned_regions, "saved_images": []}


def extract_page(state):
    """单个 Send 实例：处理一页。"""
    idx = state["idx"]
    pdf_path = state["pdf_path"]
    out_dir = state["out_dir"]
    images_dir = state["images_dir"]
    page_type = state["page_type"]
    page_img_path = state["page_img_path"]

    try:
        if page_type == "text":
            result = _extract_text_page(pdf_path, idx, images_dir, out_dir)
        else:
            result = _extract_vision_page(pdf_path, idx, page_img_path, out_dir)
        result["status"] = "ok"
        return {"page_results": [result]}
    except Exception as e:
        result = {"idx": idx, "type": page_type, "md": f"> [第 {idx + 1} 页解析失败: {e}]",
                  "image_regions": [], "saved_images": [], "status": "error"}
        return {"page_results": [result], "logs": [f"第 {idx + 1} 页解析失败: {e}"]}
