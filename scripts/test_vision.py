"""快速验证火山方舟 doubao 视觉能力 + 测试解析管线的辅助脚本。"""
import base64, json, io, sys
from PIL import Image, ImageDraw, ImageFont

from openai import OpenAI

BASE = ""
# KEY
VISION_MODEL = ""


def make_sample_image(path="tests/sample_vision.png", text="2025 年第一季度营收报告\n总营收 12.8 亿元，同比增长 23.5%\n利润表：研发投入 3.2 亿 | 销售费用 1.9 亿"):
    img = Image.new("RGB", (900, 400), "white")
    d = ImageDraw.Draw(img)
    try:
        font = ImageFont.truetype("/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc", 24)
    except Exception:
        font = ImageFont.load_default()
    d.text((40, 40), text, fill="black", font=font)
    # 画个表格框
    d.rectangle([40, 200, 860, 360], outline="black", width=2)
    d.line([300, 200, 300, 360], fill="black", width=2)
    d.line([600, 200, 600, 360], fill="black", width=2)
    d.line([40, 280, 860, 280], fill="black", width=2)
    d.text((80, 220), "指标", fill="black", font=font)
    d.text((340, 220), "数值", fill="black", font=font)
    d.text((640, 220), "同比", fill="black", font=font)
    d.text((80, 300), "营收", fill="black", font=font)
    d.text((340, 300), "12.8 亿", fill="black", font=font)
    d.text((640, 300), "+23.5%", fill="black", font=font)
    img.save(path)
    # print("saved", path)


def call_vision(image_path, prompt="请完整提取这张图的内容，输出为 Markdown 格式，表格用 markdown 表格表示。"):
    with open(image_path, "rb") as f:
        b64 = base64.b64encode(f.read()).decode()
    client = OpenAI(base_url=BASE, api_key=KEY)
    resp = client.chat.completions.create(
        model=VISION_MODEL,
        messages=[{
            "role": "user",
            "content": [
                {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64}"}},
                {"type": "text", "text": prompt},
            ],
        }],
        max_tokens=1500,
    )
    return resp.choices[0].message.content


if __name__ == "__main__":
    img = sys.argv[1] if len(sys.argv) > 1 else "tests/sample_vision.png"
    make_sample_image() if img == "tests/sample_vision.png" else None
    out = call_vision(img)
    print("=== VISION OUTPUT ===")
    print(out)
