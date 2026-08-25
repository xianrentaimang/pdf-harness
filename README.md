# PDF → Markdown 智能转换系统

基于 **Python + LangGraph + 多模态大模型** 的 PDF 转 Markdown 系统，支持文本版 / 影印版（扫描件）/ 混合版 PDF 的高质量内容提取。

## 核心能力

- **三类页面自适应**：
  - `text` 文本页 → 直接抽取 PDF 文本层（准确无损），LLM 结构整理（标题层级/列表/表格还原）
  - `scanned` 影印页 → 多模态大模型（doubao-seed-evolving 视觉）整页逐字 OCR + 版面还原
  - `mixed` 混合页 → 视觉模型提取，并自动检测/裁剪独立图片
- **图片资源提取**：内嵌图片按读取顺序裁剪保存到 `images/`，自动识别图注作为 alt；表格图片自动转录为 Markdown 表格；扫描页内嵌照片/插图自动定位裁剪
- **LangGraph 流水线**：`preprocess → classify → [按页 Send 扇出 extract_page] → extract_images(汇合) → assemble`，map-reduce 架构，可扩展并行
- **网页操作台**：拖拽上传 → 任务列表 → 渲染预览 / Markdown 源码 / 页面预览 / 图片资源 / 日志，支持重新解析、打包下载（zip）、删除

## 架构

```
app.py                FastAPI 服务 + 后台解析线程
config.py             LLM 提供商 / 解析参数配置
pipeline/
  state.py            LangGraph 状态定义（含 reducer）
  graph.py            工作流编排（Send 扇出/汇合）
  llm.py              OpenAI 兼容客户端（文本/视觉/JSON 容错）
  nodes/
    preprocess.py     渲染页面、抽取文本层、图片覆盖统计
    classify.py       页面分类（text/scanned/mixed/blank）
    extract_page.py   单页提取（文本层路线 / 视觉路线）+ 内嵌图片表格识别
    images.py         按视觉检测 bbox 裁剪保存图片
    assemble.py       合并各页 markdown、替换占位符、写 manifest
static/index.html     前端单页
```

## 页面分类规则

| 条件 | 分类 | 提取方式 |
|---|---|---|
| 无文字 & 无图片 | blank | 跳过 |
| 可复制文本 < 30 字符 | scanned | 视觉模型 OCR |
| 文本 >= 30 且图片覆盖 >= 25% | mixed | 视觉模型 + 图片裁剪 |
| 其他 | text | 文本层 + LLM 整理 |

## 快速开始

```bash
./start.sh            # 启动（默认端口 16082）
./start.sh stop       # 停止
./start.sh restart    # 重启
```

访问：`http://<IP>:16082/`

## 生成测试 PDF 并跑管线

```bash
/home/hz1/miniconda3/envs/openclaw/bin/python3 scripts/make_test_pdfs.py   # 生成文本版/影印版/混合版测试 PDF
/home/hz1/miniconda3/envs/openclaw/bin/python3 scripts/run_pipeline.py tests/pdfs/test_text.pdf
```

## 配置项（环境变量）

| 变量 | 默认 | 说明 |
|---|---|---|
| PORT | 16082 | 服务端口 |
| RENDER_ZOOM | 2.5 | 页面渲染倍率（72dpi 基准），越大 OCR 越准越慢 |
| MAX_TOKENS_PAGE | 3000 | 每页生成 token 预算 |
| OCR_EMBEDDED_IMAGES | 1 | 文本页内嵌图片是否做表格识别/描述 |
| FIG_SECOND_PASS | 1 | 扫描页是否做插图补检 |
| VISION_MODEL/API_KEY | doubao | 视觉模型（火山方舟） |
| TEXT_MODEL/API_KEY | deepseek-chat | 文本整理模型 |

## 输出目录

```
data/tasks/<task_id>/
  input.pdf        原始 PDF
  pages/page_*.png 每页渲染图
  images/img_*.png 提取的图片资源
  output.md        最终 Markdown
  page_*.md        每页 Markdown
  manifest.json    任务清单
```
