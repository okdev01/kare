"""Conservative photo exports: separate destination, no overwrite, no metadata."""
from dataclasses import dataclass
import os
from pathlib import Path
import warnings
from uuid import uuid4

from PIL import Image, ImageOps

Image.MAX_IMAGE_PIXELS = 40_000_000
FORMATS = {"JPEG": ".jpg", "PNG": ".png", "WEBP": ".webp"}


@dataclass(frozen=True)
class Settings:
    width: int = 1920
    height: int = 1920
    format: str = "JPEG"
    quality: int = 90
    rotation: int = 0

    def validate(self):
        if not 16 <= self.width <= 12000 or not 16 <= self.height <= 12000:
            raise ValueError("Boyutlar 16–12000 piksel arasında olmalı")
        if self.format not in FORMATS or not 1 <= self.quality <= 100 or self.rotation not in (0, 90, 180, 270):
            raise ValueError("Geçersiz dönüştürme ayarı")


def inspect(path):
    path = Path(path)
    with warnings.catch_warnings():
        warnings.simplefilter("error", Image.DecompressionBombWarning)
        with Image.open(path) as image:
            if getattr(image, "n_frames", 1) > 1:
                raise ValueError("Animasyonlu veya çok sayfalı görseller desteklenmiyor")
            image.verify()
        with Image.open(path) as image:
            size = image.size
            if image.getexif().get(274, 1) in (5, 6, 7, 8):
                size = size[::-1]
            return {"name": path.name, "width": size[0], "height": size[1],
                    "format": image.format, "bytes": path.stat().st_size}


def export_one(source, output_dir, settings):
    settings.validate()
    source, output_dir = Path(source).resolve(), Path(output_dir).resolve()
    if source.parent == output_dir:
        raise ValueError("Orijinalleri korumak için farklı bir çıktı klasörü seçin")
    inspect(source)
    output_dir.mkdir(parents=True, exist_ok=True)
    if not output_dir.is_dir():
        raise ValueError("Çıktı klasörü geçersiz")
    temp = output_dir / f".kare-{uuid4().hex}.tmp"
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(source) as original:
                image = ImageOps.exif_transpose(original)
                if settings.rotation:
                    image = image.rotate(-settings.rotation, expand=True)
                image.thumbnail((settings.width, settings.height), Image.Resampling.LANCZOS)
                rgba = image.convert("RGBA")
                if settings.format == "JPEG":
                    result = Image.new("RGB", rgba.size, "white")
                    result.paste(rgba, mask=rgba.getchannel("A"))
                else:
                    result = Image.new("RGBA", rgba.size)
                    result.paste(rgba)
                # New image carries no EXIF/GPS/ICC/XMP metadata from the source.
                options = {"quality": settings.quality} if settings.format != "PNG" else {}
                with temp.open("xb") as stream:
                    result.save(stream, format=settings.format, **options)
                    stream.flush()
                    os.fsync(stream.fileno())
                size = result.size
        index = 0
        while True:
            suffix = "" if index == 0 else f"-{index}"
            target = output_dir / f"{source.stem}-kare{suffix}{FORMATS[settings.format]}"
            try:
                if os.name == "nt":
                    os.rename(temp, target)
                else:
                    os.link(temp, target)
                    temp.unlink()
                return {"source": str(source), "output": str(target), "width": size[0], "height": size[1]}
            except FileExistsError:
                index += 1
    finally:
        temp.unlink(missing_ok=True)


def export_batch(sources, output_dir, settings):
    settings.validate()
    if not sources:
        raise ValueError("En az bir fotoğraf seçin")
    output = Path(output_dir).resolve()
    if any(Path(p).resolve().parent == output for p in sources):
        raise ValueError("Çıktı klasörü kaynak fotoğrafların klasöründen farklı olmalı")
    results = []
    for source in sources:
        try:
            results.append({"ok": True, **export_one(source, output, settings)})
        except (OSError, ValueError, Image.DecompressionBombError, Image.DecompressionBombWarning) as exc:
            results.append({"ok": False, "source": str(source), "error": str(exc)})
    return results
