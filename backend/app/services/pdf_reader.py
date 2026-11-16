import threading
from functools import lru_cache
from io import BytesIO
from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from docling.document_converter import DocumentConverter


_one_at_a_time = threading.Lock()
MAX_PAGES = 5


class PdfReader(Protocol):
    def read(self, data: bytes, filename: str) -> str: ...


@lru_cache
def _converter() -> DocumentConverter:
    from docling.datamodel.base_models import InputFormat
    from docling.datamodel.pipeline_options import PdfPipelineOptions
    from docling.document_converter import DocumentConverter, PdfFormatOption

    options = PdfPipelineOptions(
        do_ocr=False, layout_batch_size=1, table_batch_size=1, queue_max_size=1
    )
    return DocumentConverter(
        format_options={InputFormat.PDF: PdfFormatOption(pipeline_options=options)}
    )


class DoclingReader:
    def read(self, data: bytes, filename: str) -> str:
        from docling.datamodel.base_models import DocumentStream

        source = DocumentStream(name=filename, stream=BytesIO(data))
        with _one_at_a_time:
            result = _converter().convert(source, page_range=(1, MAX_PAGES))
        return result.document.export_to_markdown()
