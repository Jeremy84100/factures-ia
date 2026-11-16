import threading
from functools import lru_cache
from io import BytesIO
from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from docling.document_converter import DocumentConverter


_one_at_a_time = threading.Lock()


class PdfReader(Protocol):
    def read(self, data: bytes, filename: str) -> str: ...


@lru_cache
def _converter() -> DocumentConverter:
    from docling.document_converter import DocumentConverter

    return DocumentConverter()


class DoclingReader:
    def read(self, data: bytes, filename: str) -> str:
        from docling.datamodel.base_models import DocumentStream

        source = DocumentStream(name=filename, stream=BytesIO(data))
        with _one_at_a_time:
            result = _converter().convert(source)
        return result.document.export_to_markdown()
