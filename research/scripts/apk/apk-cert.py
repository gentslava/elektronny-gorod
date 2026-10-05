#!/usr/bin/env python3
"""Проверить подпись APK (схема v2) и показать отпечаток подписанта.

Зачем: `keytool -printcert -jarfile` на этих пакетах говорит «Not a signed
jar file» — v1-подписи (META-INF) в них нет, а `apksigner` тянет за собой
весь Android SDK.

Главное применение — доверие к файлу, скачанному с зеркала. Но одного
совпадения отпечатка мало, и это не теория: если взять подлинный пакет,
перевернуть байт в середине и не тронуть блок подписи, отпечаток
останется прежним. Поэтому здесь проверяется всё, что определяет схему v2:

1. подпись над `signed data` проверяется открытым ключом подписанта;
2. сертификат подписанта сверяется с ключом из той же записи;
3. дайджест содержимого пересчитывается по всему файлу и сравнивается с
   заявленным в `signed data`.

Только пройдя все три, файл можно считать тем, что выпустил издатель.

    ./apk-cert.py new.apk                     # проверить и показать отпечаток
    ./apk-cert.py known-good.apk new.apk      # ещё и сверить подписанта

Возвращает ненулевой код, если проверка не прошла или подписанты разошлись.
"""
from __future__ import annotations

import hashlib
import struct
import sys

MAGIC = b"APK Sig Block 42"
V2_SCHEME = 0x7109871A
CHUNK = 1024 * 1024
EOCD_SIG = b"PK\x05\x06"

# id алгоритма → (хеш, вид подписи). Покрыты те, что реально встречаются
# у Play-сборок; остальные помечаются как неподдержанные, а не «прошло».
ALGORITHMS: dict[int, tuple[str, str]] = {
    0x0101: ("sha256", "rsa-pss"),
    0x0102: ("sha512", "rsa-pss"),
    0x0103: ("sha256", "rsa-pkcs1"),
    0x0104: ("sha512", "rsa-pkcs1"),
    0x0201: ("sha256", "ecdsa"),
    0x0202: ("sha512", "ecdsa"),
    0x0301: ("sha256", "dsa"),
}


class Broken(Exception):
    """Файл не проходит проверку — не путать с ошибкой окружения."""


def _u32(buf: bytes, off: int) -> int:
    return struct.unpack_from("<I", buf, off)[0]


def _chunk(buf: bytes, off: int) -> tuple[bytes, int]:
    """Кусок с 4-байтовым префиксом длины."""
    size = _u32(buf, off)
    return buf[off + 4 : off + 4 + size], off + 4 + size


def _items(buf: bytes):
    """Последовательность length-prefixed элементов."""
    off = 0
    while off < len(buf):
        item, off = _chunk(buf, off)
        yield item


def _layout(data: bytes) -> tuple[int, int, int]:
    """Смещения: начало блока подписи, начало central directory, начало EOCD.

    Блок ищется не поиском по файлу, а там, где его место по спецификации:
    его 16-байтная сигнатура кончается ровно на начале central directory.
    Поиск `rfind` находил чужой блок — у XAPK это блок вложенного base-APK,
    и неизменённый контейнер объявлялся подделкой, — и пропускал вставку
    байтов между блоком и central directory, которую Android отвергает.
    """
    eocd_at = data.rfind(EOCD_SIG)
    if eocd_at < 0:
        raise Broken("нет EOCD: это не zip")
    if eocd_at + 22 > len(data):
        raise Broken("EOCD обрезан: файл повреждён")
    cd_offset = _u32(data, eocd_at + 16)
    magic_at = cd_offset - 16
    if magic_at < 8 or data[magic_at:cd_offset] != MAGIC:
        raise Broken("вплотную перед central directory нет APK Signing Block: "
                     "пакет не подписан схемой v2/v3, между блоком и central "
                     "directory вставлены байты, или это контейнер "
                     "(XAPK/APKS — распакуйте и проверяйте .apk)")
    size_end = struct.unpack_from("<Q", data, magic_at - 8)[0]
    block_start = cd_offset - 8 - size_end
    if block_start < 0 or struct.unpack_from("<Q", data, block_start)[0] != size_end:
        raise Broken("размеры блока подписи не сошлись — файл повреждён")
    return block_start, cd_offset, eocd_at


def _pairs(data: bytes, block_start: int, magic_at: int):
    """Пары id/value внутри блока подписи."""
    block = data[block_start + 8 : magic_at - 8]
    off = 0
    while off + 12 <= len(block):
        length = struct.unpack_from("<Q", block, off)[0]
        yield _u32(block, off + 8), block[off + 12 : off + 8 + length]
        off += 8 + length


def content_digest(data: bytes, algo: str) -> bytes:
    """Дайджест содержимого по схеме v2.

    Считается по трём частям — записи zip, central directory и EOCD, — где
    в копии EOCD смещение central directory подменяется смещением блока
    подписи. Иначе добавление самого блока меняло бы то, что он заверяет.
    """
    block_start, cd_offset, eocd_at = _layout(data)

    eocd = bytearray(data[eocd_at:])
    struct.pack_into("<I", eocd, 16, block_start)
    sections = [data[:block_start], data[cd_offset:eocd_at], bytes(eocd)]

    digests = []
    for section in sections:
        for start in range(0, len(section), CHUNK):
            piece = section[start : start + CHUNK]
            h = hashlib.new(algo)
            h.update(b"\xa5" + struct.pack("<I", len(piece)) + piece)
            digests.append(h.digest())

    top = hashlib.new(algo)
    top.update(b"\x5a" + struct.pack("<I", len(digests)) + b"".join(digests))
    return top.digest()


def _verify_signature(public_key_der: bytes, algo_id: int, sig: bytes, signed: bytes) -> None:
    from cryptography.exceptions import InvalidSignature
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.asymmetric import ec, padding, utils
    from cryptography.hazmat.primitives.serialization import load_der_public_key

    algo, kind = ALGORITHMS[algo_id]
    key = load_der_public_key(public_key_der)
    digest = {"sha256": hashes.SHA256(), "sha512": hashes.SHA512()}[algo]

    try:
        if kind == "rsa-pkcs1":
            key.verify(sig, signed, padding.PKCS1v15(), digest)
        elif kind == "rsa-pss":
            key.verify(
                sig,
                signed,
                padding.PSS(mgf=padding.MGF1(digest), salt_length=digest.digest_size),
                digest,
            )
        elif kind == "ecdsa":
            key.verify(sig, signed, ec.ECDSA(digest))
        else:
            raise Broken(f"алгоритм 0x{algo_id:04x} здесь не реализован")
    except InvalidSignature:
        raise Broken(f"подпись не сходится (алгоритм 0x{algo_id:04x})") from None


def verify(path: str) -> str:
    """Проверить пакет целиком. Возвращает SHA-256 сертификата подписанта."""
    data = open(path, "rb").read()
    block_start, cd_offset, _ = _layout(data)
    magic_at = cd_offset - 16

    value = next((v for pid, v in _pairs(data, block_start, magic_at) if pid == V2_SCHEME), None)
    if value is None:
        raise Broken("в блоке подписи нет схемы v2")

    signers, _ = _chunk(value, 0)
    fingerprints: set[str] = set()
    for signer in _items(signers):
        signed_data, off = _chunk(signer, 0)
        signatures, off = _chunk(signer, off)
        public_key, _ = _chunk(signer, off)

        digests_blob, inner = _chunk(signed_data, 0)
        certificates, _ = _chunk(signed_data, inner)

        declared = {}
        for entry in _items(digests_blob):
            declared[_u32(entry, 0)] = _chunk(entry, 4)[0]

        checked = 0
        for entry in _items(signatures):
            algo_id = _u32(entry, 0)
            if algo_id not in ALGORITHMS:
                continue
            _verify_signature(public_key, algo_id, _chunk(entry, 4)[0], signed_data)
            expected = declared.get(algo_id)
            if expected is None:
                raise Broken(f"нет дайджеста под алгоритм 0x{algo_id:04x}")
            if content_digest(data, ALGORITHMS[algo_id][0]) != expected:
                raise Broken("дайджест содержимого не сходится — файл изменён после подписи")
            checked += 1
        if not checked:
            raise Broken("ни одного поддержанного алгоритма подписи")

        certs = list(_items(certificates))
        if not certs:
            raise Broken("в подписи нет сертификата")
        # Первый сертификат — сам подписант; ключ в нём обязан совпадать с
        # тем, которым проверена подпись, иначе отпечаток относился бы к
        # постороннему сертификату, приложенному рядом.
        from cryptography.x509 import load_der_x509_certificate
        from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat

        cert = load_der_x509_certificate(certs[0])
        if cert.public_key().public_bytes(
            Encoding.DER, PublicFormat.SubjectPublicKeyInfo
        ) != public_key:
            raise Broken("сертификат не соответствует ключу, которым подписан пакет")
        fingerprints.add(hashlib.sha256(certs[0]).hexdigest())

    if len(fingerprints) != 1:
        raise Broken(f"подписантов не один, а {len(fingerprints)}")
    return fingerprints.pop()


def main(paths: list[str]) -> int:
    if not paths:
        raise SystemExit(__doc__)
    seen: set[str] = set()
    failed = False
    for path in paths:
        try:
            digest = verify(path)
        except Broken as err:
            print(f"🔴 {path}\n   ПРОВЕРКА НЕ ПРОЙДЕНА: {err}")
            failed = True
            continue
        print(f"✅ {path}\n   подпись v2 сходится, дайджест содержимого сходится"
              f"\n   SHA-256 сертификата {digest}")
        seen.add(digest)

    if failed:
        return 1
    if len(paths) > 1:
        print()
        if len(seen) == 1:
            print("✅ подписант один и тот же")
            return 0
        print(f"🔴 РАЗНЫЕ подписанты ({len(seen)}) — файлу с зеркала верить нельзя")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
