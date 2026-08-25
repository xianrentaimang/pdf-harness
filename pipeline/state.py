"""LangGraph 状态定义。"""
import operator
from typing import Annotated, Any, TypedDict


class PDFState(TypedDict, total=False):
    task_id: str
    pdf_path: str                    # 输入 PDF 路径
    out_dir: str                     # 任务输出目录
    images_dir: str                  # 资源目录 data/tasks/<id>/images
    status: str                      # running/done/error
    error: str
    total_pages: int
    page_img_paths: list[str]        # 每页渲染图（供视觉模型 / 网页预览）
    page_texts: list[str]            # 每页文本层
    page_coverages: list[float]      # 每页图片覆盖占比
    page_has_imgs: list[bool]        # 每页是否含独立图片
    page_types: list[str]            # text / mixed / scanned / blank
    # map-reduce 汇总：每个元素 = 一页的处理结果
    page_results: Annotated[list[dict[str, Any]], operator.add]
    # 视觉页检测出的图片区域（裁剪后记录）— 由 images 节点补充
    saved_images: Annotated[list[dict[str, Any]], operator.add]
    final_markdown: str
    logs: Annotated[list[str], operator.add]
    metrics: dict[str, Any]
