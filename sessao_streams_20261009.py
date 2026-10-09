#!/usr/bin/env python3
"""Sessao 2026-10-09: testa (1) URLs da lista baixada e (2) candidatos de reposicao.

Teste de 3 camadas (manifest -> variante -> segmento de midia real), rejeita
DRM/somente-audio/somente-video. Salva JSON com o resultado de cada URL.
"""
import concurrent.futures
import importlib.util
import json
import sys

BASE = "/home/runner/work/JCTVV/JCTVV/"
spec = importlib.util.spec_from_file_location("t", BASE + "testar_lista5_20261005_v2.py")
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


def urls_da_lista(path=BASE + "lista5.m3u"):
    out = []
    for l in open(path, encoding="utf-8"):
        l = l.strip()
        if l.startswith("http") and l not in out:
            out.append(l)
    return out


CANDIDATOS = [
    # ABC News Live (nacional, sem DRM)
    "https://abcnews-livestreams.akamaized.net/out/v1/6a597119dbd5428a82dc11a2f514a1a2/abcn-live-10-cmaf-manifest/abcn-live-10-index.m3u8",
    "https://abcnews-livestreams.akamaized.net/out/v1/173a6e46d5c5423d9611bc7fb7899c73/abcn-live-05-cmaf-manifest/abcn-live-05-index.m3u8",
    # CBS News 24/7 (substitui dai.google.com 410)
    "https://cbsn-us.cbsnstream.cbsnews.com/out/v1/55a8648e8f134e82a470f83d562deeca/master.m3u8",
    "https://cbsn-2.cbsnstream.cbsnews.com/out/v1/a6a897e8f4f74cfc896223dfd822482f/master.m3u8",
    "https://cbsn-us-vtt.cbsnstream.cbsnews.com/out/v1/ef868690d34144509eda696884bf1619/master.m3u8",
    # Fox News / Fox Business (substitui 247.foxnews token expirado)
    "https://247preview.foxnews.com/hls/live/2020027/fncv3preview/primary.m3u8",
    "https://247preview.foxnews.com/hls/live/2020027/fncv3preview/index.m3u8",
    "https://247preview.foxbusiness.com/hls/live/2020026/fbnv3preview/primary.m3u8",
    "https://247preview.foxbusiness.com/hls/live/2020026/fbnv3preview/index.m3u8",
]


def main():
    urls = urls_da_lista()
    for u in CANDIDATOS:
        if u not in urls:
            urls.append(u)
    print(f"URLs a testar: {len(urls)} ({len(urls)-len(CANDIDATOS)} da lista + {len(CANDIDATOS)} candidatos)")
    res = {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=6) as ex:
        for u, ok, why in ex.map(m.test_url, urls):
            res[u] = {"ok": ok, "motivo": why}
            print(f"{'OK  ' if ok else 'FALHA'} {why[:80]:80} | {u[:70]}")
    with open(BASE + "sessao_streams_20261009.json", "w", encoding="utf-8") as f:
        json.dump(res, f, indent=2, ensure_ascii=False)
    ok = sum(1 for v in res.values() if v["ok"])
    print(f"\nTotal {len(res)} | OK {ok} | FALHA {len(res)-ok}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
