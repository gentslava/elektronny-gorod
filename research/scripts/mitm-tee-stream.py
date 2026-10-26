"""mitmproxy addon: пропускать видеопоток насквозь и одновременно писать его в файл.

Видеопоток оператора (`video/x-flv` с `forpost-N:18081`) — бесконечный ответ.
Без стриминга mitmproxy копит тело целиком, и приложение показывает «Видео
недоступно». Со `stream_large_bodies` поток идёт насквозь, но тело в flow не
сохраняется. Этот addon включает стриминг для видео и параллельно пишет байты
в `<dump_dir>/streams/<host>-<n>.<ext>` — и приложение работает, и запись есть.

Запуск: `mitmdump -s research/scripts/mitm-tee-stream.py --set tee_dir=<dir>`.
Имя файла — хост + порядковый номер, без токенов ссылки; сами байты —
видео. Каталог под `.gitignore`.
"""
from __future__ import annotations

import itertools
import os

from mitmproxy import ctx, http

_EXT = {"video/x-flv": "flv", "video/mp4": "mp4", "video/mp2t": "ts"}


class TeeStream:
    def __init__(self) -> None:
        self._seq = itertools.count(1)

    def load(self, loader) -> None:
        loader.add_option("tee_dir", str, "research/api/streams", "Куда писать видеопотоки")

    def responseheaders(self, flow: http.HTTPFlow) -> None:
        ctype = flow.response.headers.get("content-type", "").split(";")[0].strip().lower()
        if not ctype.startswith("video/"):
            return
        os.makedirs(ctx.options.tee_dir, exist_ok=True)
        name = f"{flow.request.host.split('.')[0]}-{next(self._seq):03d}.{_EXT.get(ctype, 'bin')}"
        path = os.path.join(ctx.options.tee_dir, name)
        out = open(path, "wb")  # noqa: SIM115 — закрывается в последнем чанке
        flow.metadata["tee_path"] = path
        ctx.log.info(f"tee {ctype} → {path}")

        def tee(chunk: bytes) -> bytes:
            if chunk:
                out.write(chunk)
            else:
                out.close()
            return chunk

        flow.response.stream = tee


addons = [TeeStream()]
