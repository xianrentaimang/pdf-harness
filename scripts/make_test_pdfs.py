"""生成三类测试 PDF：文本版 / 影印版(扫描) / 混合版，用于验证解析效果。"""
import os, sys
import pymupdf as fitz
from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "..", "tests", "pdfs")
os.makedirs(OUT, exist_ok=True)


def font_path():
    for p in [
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc",
    ]:
        if os.path.exists(p):
            return p
    return None


def draw_chart(path, title="产品季度销量趋势"):
    """生成一张图表图片（折线图）。"""
    img = Image.new("RGB", (700, 380), "white")
    d = ImageDraw.Draw(img)
    f = None
    try:
        f = ImageFont.truetype(font_path(), 20)
    except Exception:
        f = ImageFont.load_default()
    d.text((250, 10), title, fill="black", font=f)
    d.rectangle([60, 50, 660, 320], outline="black", width=2)
    # 坐标轴刻度
    xs = [80, 190, 300, 410, 520, 630]
    labels = ["Q1", "Q2", "Q3", "Q4", "Q5", "Q6"]
    vals = [80, 150, 120, 220, 190, 300]
    for x, lb in zip(xs, labels):
        d.text((x - 15, 325), lb, fill="black", font=f)
        d.line([x, 315, x, 55], fill="lightgray", width=1)
    pts = []
    for x, v in zip(xs, vals):
        y = 315 - v
        d.ellipse([x - 4, y - 4, x + 4, y + 4], fill="blue")
        pts.append((x, y))
    d.line(pts, fill="blue", width=3)
    for (x, y), v in zip(pts, vals):
        d.text((x - 10, y - 28), str(v), fill="black", font=f)
    img.save(path)


def draw_photo(path):
    """生成一张风景照片风格的图（渐变+山形）。"""
    img = Image.new("RGB", (600, 350), (135, 206, 250))
    d = ImageDraw.Draw(img)
    d.rectangle([0, 200, 600, 350], fill=(34, 139, 34))  # 草地
    d.polygon([(150, 200), (300, 60), (450, 200)], fill=(105, 105, 105))  # 山
    d.polygon([(350, 200), (520, 40), (600, 200)], fill=(139, 139, 139))
    d.ellipse([80, 50, 180, 150], fill=(255, 255, 0))  # 太阳
    try:
        f = ImageFont.truetype(font_path(), 22)
        d.text((180, 300), "山间风景图", fill="white", font=f)
    except Exception:
        pass
    img.save(path)


def make_text_pdf(path):
    """文本版 PDF：标题/段落/列表/表格 + 内嵌图表。"""
    doc = fitz.open()
    page = doc.new_page(width=595, height=842)  # A4
    font = "china-s"
    y = 60
    page.insert_text((72, y), "智能营销系统产品白皮书", fontsize=22, fontname=font)
    y += 40
    page.insert_text((72, y), "版本 1.0 | 2025 年 8 月", fontsize=12, fontname=font)
    y += 40
    page.insert_text((72, y), "一、系统概述", fontsize=16, fontname=font)
    y += 28
    paras = [
        "本白皮书介绍智能营销系统（SmartMarketing Pro）的整体架构、核心能力与商业价值。系统基于大数据与机器学习技术，为企业在获客、转化、留存三个环节提供端到端的自动化营销能力。",
        "系统当前已服务超过 1200 家企业客户，覆盖零售、金融、教育、医疗等多个行业。2025 年第二季度整体营收同比增长 32%，续费率达到 86%。",
    ]
    for p in paras:
        page.insert_textbox(fitz.Rect(72, y, 523, y + 60), p, fontsize=11, fontname=font, align=fitz.TEXT_ALIGN_LEFT)
        y += 65
    page.insert_text((72, y), "二、核心功能模块", fontsize=16, fontname=font)
    y += 28
    items = [
        "1. 客户画像：基于行为数据构建 360 度用户画像，支持千人千面推荐；",
        "2. 智能触达：覆盖短信、邮件、站内信等多渠道，自动选择最优触达时间；",
        "3. 效果分析：实时 ROI 分析，支持 A/B 实验与归因模型；",
        "4. 自动化流程：可视化编排营销旅程，支持条件分支与延迟节点。",
    ]
    for it in items:
        page.insert_text((90, y), it, fontsize=11, fontname=font)
        y += 22
    y += 10
    page.insert_text((72, y), "三、产品版本对比", fontsize=16, fontname=font)
    y += 30
    # 表格（用文本对齐绘制）
    cols = [(72, 200), (200, 90), (290, 90), (380, 90), (470, 60)]
    headers = ["版本", "用户数", "自动化", "AI 洞察", "价格"]
    rows = [
        ["基础版", "≤500", "基础流程", "无", "¥9,999/年"],
        ["专业版", "≤5000", "全部流程", "基础", "¥39,999/年"],
        ["企业版", "不限", "全部流程", "高级", "¥99,999/年"],
    ]
    def draw_row(cy, cells, bold=False):
        for (x, w), c in zip(cols, cells):
            page.insert_text((x + 5, cy + 8), c, fontsize=10, fontname=font)
        return cy
    # 表头下划线
    page.draw_line((72, y + 20), (530, y + 20), color=(0, 0, 0))
    y += 24
    y = draw_row(y, headers)
    page.draw_line((72, y + 8), (530, y + 8), color=(0, 0, 0))
    for r in rows:
        y += 22
        y = draw_row(y, r)
        page.draw_line((72, y + 8), (530, y + 8), color=(0.8, 0.8, 0.8))
    y += 30
    # 插入内嵌图表图片
    chart = os.path.join(OUT, "_chart.png")
    draw_chart(chart)
    page.insert_image(fitz.Rect(120, y - 14, 475, y + 150), filename=chart)
    y += 178
    page.insert_text((72, y), "图 1：产品季度销量趋势（2024Q1-2025Q2）", fontsize=10, fontname=font)
    y += 28
    page.insert_text((72, y), "四、总结", fontsize=16, fontname=font)
    y += 28
    page.insert_textbox(fitz.Rect(72, y, 523, y + 80), "智能营销系统通过数据驱动的方式显著提升了企业的营销效率。未来将持续引入大模型能力，提供更智能的营销策略生成与自然语言交互体验。", fontsize=11, fontname=font)
    doc.save(path)
    print("text pdf ->", path)


def make_scanned_pdf(path, pages=3):
    """影印版 PDF：把排版好的页面渲染成图片，模拟扫描件（无文本层）。"""
    # 先用文本版生成一页，再渲染成图
    tmp = os.path.join(OUT, "_tmp_text.pdf")
    make_text_pdf(tmp)
    src = fitz.open(tmp)
    page0 = src[0]
    pix = page0.get_pixmap(matrix=fitz.Matrix(2.0, 2.0))
    img_path = os.path.join(OUT, "_scan_src.png")
    pix.save(img_path)

    doc = fitz.open()
    for i in range(pages):
        page = doc.new_page(width=595, height=842)
        if i == 0:
            img = img_path
        else:
            # 后续页用纯文字图片
            img2 = os.path.join(OUT, f"_scan_text_{i}.png")
            im = Image.new("RGB", (1190, 1684), "white")
            d = ImageDraw.Draw(im)
            try:
                f = ImageFont.truetype(font_path(), 34)
            except Exception:
                f = ImageFont.load_default()
            lines = [
                f"影印版第 {i} 页",
                "",
                "本页内容说明：影印版 PDF 没有可选择的文本层，",
                "所有内容都以图片形式存在。需要借助 OCR 或多模态大模型",
                "才能把内容准确还原为可编辑的文字。",
                "",
                "表格示例：",
                "科目      数量      单价      金额",
                "笔记本    100       30        3000",
                "显示器    20        1200      24000",
                "键盘      50        100       5000",
            ]
            yy = 80
            for ln in lines:
                d.text((60, yy), ln, fill="black", font=f)
                yy += 60
            im.save(img2)
            img = img2
        page.insert_image(fitz.Rect(0, 0, 595, 842), filename=img)
    doc.save(path)
    print("scanned pdf ->", path)


def make_mixed_pdf(path):
    """混合版 PDF：文本页 + 影印图片页 + 含内嵌图的文本页。"""
    doc = fitz.open()
    font = "china-s"
    # 第 1 页：纯文本
    p = doc.new_page(width=595, height=842)
    p.insert_text((72, 60), "混合文档示例：目录页", fontsize=20, fontname=font)
    p.insert_text((72, 100), "本页为可复制文本。下一页为扫描图片页，再下一页为带图表页面。", fontsize=12, fontname=font)
    p.insert_text((72, 130), "1. 项目背景", fontsize=12, fontname=font)
    p.insert_text((72, 152), "2. 数据概览", fontsize=12, fontname=font)
    p.insert_text((72, 174), "3. 实施方案", fontsize=12, fontname=font)
    # 第 2 页：扫描图片页（照片 + 文字合成一张扫描图）
    p2 = doc.new_page(width=595, height=842)
    photo = os.path.join(OUT, "_photo.png")
    draw_photo(photo)
    # 合成：上部照片 + 下部说明文字 → 模拟真实扫描页
    page_img = Image.new("RGB", (1190, 1684), "white")
    photo_im = Image.open(photo)
    photo_im = photo_im.resize((1190, 690))
    page_img.paste(photo_im, (0, 0))
    d = ImageDraw.Draw(page_img)
    try:
        f = ImageFont.truetype(font_path(), 34)
    except Exception:
        f = ImageFont.load_default()
    d.text((80, 750), "扫描页说明：这张页面是扫描件，文字和图片融为一体，", fill="black", font=f)
    d.text((80, 820), "只能通过图像识别还原内容。下方还有一段正文。", fill="black", font=f)
    lines = [
        "正文段落：本扫描页展示了项目现场的照片。",
        "项目位于山区，风景优美，施工进度正常。",
        "更多细节请参见后续章节。",
    ]
    yy = 950
    for ln in lines:
        d.text((80, yy), ln, fill="black", font=f)
        yy += 60
    page_img_path = os.path.join(OUT, "_mix_scan.png")
    page_img.save(page_img_path)
    p2.insert_image(fitz.Rect(0, 0, 595, 842), filename=page_img_path)
    # 第 3 页：文本 + 内嵌表格图 + 段落
    p3 = doc.new_page(width=595, height=842)
    p3.insert_text((72, 60), "混合文档示例：数据概览页", fontsize=18, fontname=font)
    p3.insert_text((72, 100), "下表展示了各区域销售业绩，表格以图片形式嵌入：", fontsize=11, fontname=font)
    table_img = os.path.join(OUT, "_table.png")
    timg = Image.new("RGB", (900, 300), "white")
    td = ImageDraw.Draw(timg)
    try:
        tf = ImageFont.truetype(font_path(), 26)
    except Exception:
        tf = ImageFont.load_default()
    td.text((20, 20), "区域 | 销售额(万) | 目标达成率", fill="black", font=tf)
    td.text((20, 80), "华东 | 5200 | 108%", fill="black", font=tf)
    td.text((20, 140), "华南 | 3800 | 96%", fill="black", font=tf)
    td.text((20, 200), "华北 | 4100 | 102%", fill="black", font=tf)
    timg.save(table_img)
    p3.insert_image(fitz.Rect(90, 130, 505, 230), filename=table_img)
    p3.insert_text((72, 280), "结论：华东区表现最佳，华南区需加强跟进。", fontsize=11, fontname=font)
    doc.save(path)
    print("mixed pdf ->", path)


if __name__ == "__main__":
    make_text_pdf(os.path.join(OUT, "test_text.pdf"))
    make_scanned_pdf(os.path.join(OUT, "test_scanned.pdf"), pages=2)
    make_mixed_pdf(os.path.join(OUT, "test_mixed.pdf"))
    print("ALL DONE ->", OUT)
