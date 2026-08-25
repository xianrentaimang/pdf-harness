"""OpenAI 兼容的 LLM 客户端：文本整理 + 多模态视觉提取，带重试与 JSON 容错。"""
import base64
import json
import re
import time

from openai import OpenAI

from config import VISION, TEXT_LLM, VISION_TIMEOUT, TEXT_TIMEOUT, RETRIES


def _b64(path: str) -> str:
    with open(path, "rb") as f:
        return base64.b64encode(f.read()).decode()


def _chat(client: OpenAI, model: str, messages, max_tokens: int, timeout: int):
    return client.chat.completions.create(
        model=model,
        messages=messages,
        max_tokens=max_tokens,
        timeout=timeout,
    )


def _retry(fn, retries: int = RETRIES, base=2.0):
    last = None
    for i in range(retries + 1):
        try:
            return fn()
        except Exception as e:  # noqa: BLE001
            last = e
            if i >= retries:
                break
            time.sleep(base * (i + 1))
    raise RuntimeError(f"LLM 调用失败: {last}")


def chat_text(system: str, user: str, max_tokens: int = 4000) -> str:
    """文本整理（deepseek-chat）。"""
    client = OpenAI(base_url=TEXT_LLM["base_url"], api_key=TEXT_LLM["api_key"])
    def call():
        resp = _chat(client, TEXT_LLM["model"], [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ], max_tokens=max_tokens, timeout=TEXT_TIMEOUT)
        return resp.choices[0].message.content or ""
    return _retry(call)


def chat_vision(image_path: str, system: str, user: str, max_tokens: int = 4000) -> str:
    """多模态视觉提取（doubao-seed-evolving）。"""
    client = OpenAI(base_url=VISION["base_url"], api_key=VISION["api_key"])
    b64 = _b64(image_path)
    content = [
        {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64}"}},
        {"type": "text", "text": user},
    ]
    def call():
        resp = _chat(client, VISION["model"], [
            {"role": "system", "content": system},
            {"role": "user", "content": content},
        ], max_tokens=max_tokens, timeout=VISION_TIMEOUT)
        return resp.choices[0].message.content or ""
    return _retry(call)


def extract_json_after_marker(text: str, marker: str = "###JSON###") -> list:
    """从模型输出中提取标记后的 JSON 数组，容错处理代码块。"""
    if marker in text:
        text = text.split(marker, 1)[1]
    text = re.sub(r"```(?:json)?", "", text).strip()
    text = re.sub(r"```", "", text).strip()
    # 找第一个 [ 到最后一个 ]
    start = text.find("[")
    end = text.rfind("]")
    if start == -1 or end == -1 or end <= start:
        return []
    raw = text[start:end + 1]
    try:
        return json.loads(raw)
    except Exception:
        m = re.search(r"\[\s*\{.*?\}\s*\]", raw, re.S)
        if m:
            try:
                return json.loads(m.group(0))
            except Exception:
                return []
        return []


def replace_tokens(md: str, token_map: dict) -> str:
    """把 {{IMG_N}} 占位符替换为 markdown 图片引用。"""
    for token, img_md in token_map.items():
        md = md.replace(token, img_md)
    return md
