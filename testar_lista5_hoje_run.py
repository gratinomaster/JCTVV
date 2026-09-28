#!/usr/bin/env python3
"""Testa todos os canais do lista5.m3u (HLS) e reescreve o arquivo sem os que nao funcionam.

Criterio de "funcionando":
  - a URL responde 200 e devolve um manifest HLS valido;
  - playlists master sao seguidas ate uma playlist de midia;
  - a playlist de midia entrega segmentos baixaveis (init map + segmentos) com volume real.
"""
import asyncio
import re
import shutil
import time
import urllib.parse

import aiohttp

ARQ = "lista5.m3u"
BAK = "lista5.m3u.bak.pre_teste_hoje"
REL = "relatorio_lista5_teste_hoje.txt"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0 Safari/537.36")
HEADERS = {
    "User-Agent": UA,
    "Accept": "*/*",
    "Accept-Language": "en-US,en;q=0.9",
}
TIMEOUT = aiohttp.ClientTimeout(total=25, connect=12)
MIN_BYTES = 3000


def parse(path):
    with open(path, encoding="utf-8", errors="replace") as f:
        raw = f.read().splitlines()
    header, entries, cur = [], [], []
    for line in raw:
        s = line.strip()
        if not s:
            continue
        if s.startswith("#EXTM3U"):
            header.append(line)
        elif s.startswith("#EXTINF"):
            cur = [line]
        elif s.startswith("#"):
            continue
        else:
            cur.append(s)
            entries.append((cur[0], s))
            cur = []
    return header, entries


def map_uri(text):
    m = re.search(r'#EXT-X-MAP:.*?URI="([^"]+)"', text)
    return m.group(1) if m else None


def segment_uris(text, limit=3):
    segs, out = None, []
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if segs is None:
            segs = []
        segs.append(line)
        if len(segs) >= limit:
            break
    return segs or []


async def get(session, url, referer=None):
    h = {"Referer": referer} if referer else {}
    async with session.get(url, headers=h) as r:
        return r.status, str(r.url), await r.content.read(600000)


async def check_media(session, base, media_text, page):
    """Valida init map + segmentos de uma playlist de midia."""
    total = 0
    init = map_uri(media_text)
    targets = ([init] if init else []) + segment_uris(media_text, 3)
    if not targets:
        return False, f"{page}: playlist sem segmentos", 0

    for t in targets:
        url = urllib.parse.urljoin(base, t)
        try:
            st, _, data = await get(session, url, referer=page)
        except Exception as e:  # noqa: BLE001
            return False, f"{page}: {t.split('/')[-1]} {type(e).__name__}", total
        if st != 200:
            return False, f"{page}: {t.split('/')[-1]} HTTP {st}", total
        total += len(data)
        if len(data) < 200:
            return False, f"{page}: {t.split('/')[-1]} vazio", total

    if total < MIN_BYTES:
        return False, f"{page}: dados insuficientes ({total} bytes)", total
    return True, f"{page}: {total} bytes ok", total


async def check(session, url, depth=0):
    try:
        st, final, body = await get(session, url)
    except asyncio.TimeoutError:
        return False, "timeout", 0
    except Exception as e:  # noqa: BLE001
        return False, type(e).__name__, 0

    if st != 200:
        return False, f"HTTP {st}", 0

    text = body.decode("utf-8", "replace")
    if "#EXTM3U" not in text[:500]:
        return False, "resposta nao e m3u8", 0

    if "#EXTINF" in text:
        ok, det, n = await check_media(session, final, text, url)
        return ok, det, n

    if depth >= 3:
        return False, "master sem variantes", 0

    variants = segment_uris(text, 6)
    if not variants:
        return False, "master vazio", 0

    errors = []
    for v in variants:
        sub = urllib.parse.urljoin(final, v)
        ok, det, n = await check(session, sub, depth + 1)
        if ok:
            return True, det, n
        errors.append(det)
    return False, "variantes falharam: " + " | ".join(errors[:3]), 0


async def main():
    header, entries = parse(ARQ)
    urls = [u for _, u in entries]
    uniq = sorted(set(urls))
    print(f"Entradas: {len(entries)} | URLs unicas: {len(uniq)}\n")

    result, detail = {}, {}
    connector = aiohttp.TCPConnector(limit=6, ssl=False)
    async with aiohttp.ClientSession(headers=HEADERS, timeout=TIMEOUT,
                                     connector=connector) as session:
        sem = asyncio.Semaphore(6)

        async def one(u):
            async with sem:
                for attempt in range(2):
                    ok, det, _ = await check(session, u)
                    if ok:
                        break
                    await asyncio.sleep(2)
                result[u] = ok
                detail[u] = det
                print(f"[{'OK ' if ok else 'ERR'}] {det[:60]:<60} {u[:80]}")

        await asyncio.gather(*(one(u) for u in uniq))

    keep = [e for e in entries if result.get(e[1])]
    drop = [e for e in entries if not result.get(e[1])]

    shutil.copy2(ARQ, BAK)
    with open(ARQ, "w", encoding="utf-8") as f:
        f.write("\n".join(header) + "\n")
        for ext, url in keep:
            f.write(ext + "\n" + url + "\n")

    with open(REL, "w", encoding="utf-8") as f:
        f.write(f"Teste: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"Total entradas: {len(entries)}\n")
        f.write(f"Funcionais: {len(keep)}\n")
        f.write(f"Removidos: {len(drop)}\n\n")
        f.write("=== REMOVIDOS ===\n")
        for ext, url in drop:
            f.write(f"{ext}\n  {url}\n  -> {detail.get(url)}\n\n")
        f.write("=== MANTIDOS ===\n")
        for ext, url in keep:
            f.write(f"{ext}\n  {url}  [{detail.get(url)}]\n\n")

    print(f"\nTotal: {len(entries)} | Mantidos: {len(keep)} | Removidos: {len(drop)}")
    print(f"Backup: {BAK} | Relatorio: {REL}")


if __name__ == "__main__":
    asyncio.run(main())
