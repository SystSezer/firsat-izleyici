"""Ortam degiskenlerini .env dosyasindan yukler.

.env .gitignore'da. Depoya gitmez, ekrana basilmaz, log'a dusmez.
Ayni degisken hem ortamda hem .env'de varsa ORTAM kazanir — boylece
gecici olarak baska bir deger vermek icin dosyayi degistirmek gerekmez.
"""
from __future__ import annotations

import os
from pathlib import Path


def yukle(yol: str | Path | None = None) -> int:
    p = Path(yol) if yol else Path(__file__).with_name(".env")
    if not p.exists():
        return 0
    kac = 0
    for satir in p.read_text(encoding="utf-8").splitlines():
        satir = satir.strip()
        if not satir or satir.startswith("#") or "=" not in satir:
            continue
        ad, _, deger = satir.partition("=")
        ad, deger = ad.strip(), deger.strip().strip('"').strip("'")
        if ad and deger and ad not in os.environ:
            os.environ[ad] = deger
            kac += 1
    return kac
