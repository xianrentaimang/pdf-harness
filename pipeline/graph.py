"""LangGraph 工作流：PDF → Markdown。

流程：
  preprocess（渲染页面+文本层） → classify（页面分类）
  → fan-out 按页 Send → extract_page（文本层/视觉提取）
  → join extract_images（图片裁剪） → assemble（合并输出）
"""
from langgraph.graph import END, START, StateGraph
from langgraph.types import Send

from pipeline.state import PDFState
from pipeline.nodes.preprocess import preprocess
from pipeline.nodes.classify import classify
from pipeline.nodes.extract_page import extract_page
from pipeline.nodes.images import extract_images
from pipeline.nodes.assemble import assemble


def _fan_out(state):
    """按页扇出：每页一个 Send 任务。"""
    sends = []
    for i in range(state["total_pages"]):
        sends.append(Send("extract_page", {
            "idx": i,
            "pdf_path": state["pdf_path"],
            "out_dir": state["out_dir"],
            "images_dir": state["images_dir"],
            "page_type": state["page_types"][i],
            "page_img_path": state["page_img_paths"][i],
        }))
    return sends


def build_graph():
    g = StateGraph(PDFState)
    g.add_node("preprocess", preprocess)
    g.add_node("classify", classify)
    g.add_node("extract_page", extract_page)
    g.add_node("extract_images", extract_images)
    g.add_node("assemble", assemble)

    g.add_edge(START, "preprocess")
    g.add_edge("preprocess", "classify")
    g.add_conditional_edges("classify", _fan_out, ["extract_page"])
    g.add_edge("extract_page", "extract_images")
    g.add_edge("extract_images", "assemble")
    g.add_edge("assemble", END)
    return g.compile()


compiled_graph = build_graph()
