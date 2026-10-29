"""多格式解析器（M-S2-T02）：纯函数 bytes→text，无状态。

- 输入文件字节 + 文件名，输出纯文本；不碰数据库与对象存储
  （状态流转与存储属 T04 摄取管线）；
- PDF：pypdf 逐页提取文本层；仅对无文本层（或文本层为空）的页面触发
  OCR（PyMuPDF 渲染该页为图片 → RapidOCR 识别）——有文本层的页面
  绝不过 OCR（P-S2 硬约束，控制成本）；各页按页序拼接；
- OCR 引擎懒加载（首次用到才初始化，模块导入不加载模型），
  并维护触发计数（ocr_call_count() 供验证/测试佐证）；
- 失败显式暴露（细则 6）：不支持的扩展名与解析过程异常一律 KN-422，
  不静默吞错。
"""

import io
import logging
from pathlib import PurePosixPath

from app.core.errors import AppError

log = logging.getLogger("app.services.parser")

TEXT_SUFFIXES = {".md", ".txt"}  # UTF-8 直读（.txt 为同路径自然补充）

_ocr_engine = None  # 懒加载单例
_ocr_calls = 0  # OCR 触发计数（佐证"有文本层页面 0 次 OCR"）


def ocr_call_count() -> int:
    """返回本次进程内 OCR 已触发页数（验证/测试用）。"""
    return _ocr_calls


def _get_ocr_engine():
    global _ocr_engine
    if _ocr_engine is None:
        from rapidocr_onnxruntime import RapidOCR

        _ocr_engine = RapidOCR()
        log.info("OCR 引擎初始化完成（懒加载，仅首次触发）")
    return _ocr_engine


def _ocr_image(png_bytes: bytes) -> str:
    """对单页 PNG 图片做 OCR，返回按识别顺序拼接的文本。"""
    global _ocr_calls
    import cv2
    import numpy as np

    engine = _get_ocr_engine()
    img = cv2.imdecode(
        np.frombuffer(png_bytes, dtype=np.uint8), cv2.IMREAD_COLOR
    )
    result, _elapse = engine(img)
    _ocr_calls += 1
    log.info("OCR 触发（累计 %d 页）", _ocr_calls)
    if not result:
        return ""
    return "\n".join(line[1] for line in result)


def _render_pdf_page_png(pdf_bytes: bytes, page_index: int) -> bytes:
    """用 PyMuPDF 将指定页渲染为 PNG（200dpi，保证 OCR 识别率）。"""
    import fitz  # pymupdf

    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    try:
        pix = doc[page_index].get_pixmap(dpi=200)
        return pix.tobytes("png")
    finally:
        doc.close()


def _parse_pdf(data: bytes) -> str:
    import pypdf

    reader = pypdf.PdfReader(io.BytesIO(data))
    pages: list[str] = []
    for i, page in enumerate(reader.pages):
        text = (page.extract_text() or "").strip()
        if text:
            pages.append(text)  # 有文本层：绝不过 OCR（P-S2 硬约束）
        else:
            pages.append(_ocr_image(_render_pdf_page_png(data, i)))
    return "\n\n".join(pages)


def _parse_docx(data: bytes) -> str:
    from docx import Document

    doc = Document(io.BytesIO(data))
    return "\n".join(p.text for p in doc.paragraphs if p.text.strip())


def parse_document(data: bytes, filename: str) -> str:
    """按扩展名分派解析；不支持/失败 → KN-422（显式暴露，细则 6）。"""
    ext = PurePosixPath(filename).suffix.lower()
    try:
        if ext == ".pdf":
            return _parse_pdf(data)
        if ext == ".docx":
            return _parse_docx(data)
        if ext in TEXT_SUFFIXES:
            return data.decode("utf-8")
        raise AppError("KN-422", f"不支持的文件类型: {ext or '(无扩展名)'}")
    except AppError:
        raise
    except Exception as exc:
        log.warning(
            "解析失败 filename=%s type=%s", filename, type(exc).__name__
        )
        raise AppError("KN-422", "文件解析失败") from exc
