"""Photos taken with a phone become one-page PDFs, so they follow the same path."""

from io import BytesIO

from PIL import Image, ImageOps, UnidentifiedImageError

SIGNATURES = (b"\xff\xd8\xff", b"\x89PNG\r\n\x1a\n")
MAX_SIDE = 2400
# Cap decoded image pixels (~75 MB RGB) to prevent decompression bombs on 1 GiB Cloud Run.
Image.MAX_IMAGE_PIXELS = 25_000_000


class ImageError(Exception):
    pass


def is_image(data: bytes) -> bool:
    is_webp = data[:4] == b"RIFF" and data[8:12] == b"WEBP"
    return data.startswith(SIGNATURES) or is_webp


def image_to_pdf(data: bytes) -> bytes:
    try:
        with Image.open(BytesIO(data)) as opened:
            image = ImageOps.exif_transpose(opened).convert("RGB")
    except (Image.DecompressionBombError, UnidentifiedImageError, OSError) as e:
        raise ImageError(str(e)) from e
    image.thumbnail((MAX_SIDE, MAX_SIDE))
    out = BytesIO()
    image.save(out, format="PDF", resolution=200)
    return out.getvalue()
