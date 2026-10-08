#!/usr/bin/env python3
"""Fase 1: testa todas as URLs de stream da lista5.m3u e grava JSON."""
import concurrent.futures, importlib.util, json, sys, os

spec = importlib.util.spec_from_file_location("t", "/home/runner/work/JCTVV/JCTVV/testar_lista5_20261005_v2.py")
m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)

LISTA = "/home/runner/work/JCTVV/JCTVV/lista5.m3u"
OUT = "/home/runner/work/JCTVV/JCTVV/fase1_streams_20261008.json"

entries = m.parse_m3u(LISTA)
urls, seen = [], set()
for e in entries:
    for u in e["urls"]:
        if u not in seen:
            seen.add(u); urls.append(u)

print(f"entradas={len(entries)} urls_unicas={len(urls)}", flush=True)
results = {}
with concurrent.futures.ThreadPoolExecutor(max_workers=8) as ex:
    futs = {ex.submit(m.test_url, u): u for u in urls}
    for i, f in enumerate(concurrent.futures.as_completed(futs), 1):
        u, ok, why = f.result()
        results[u] = {"ok": ok, "reason": why}
        print(f"[{i}/{len(urls)}] {'OK  ' if ok else 'FALHA'} {why[:70]} | {u[:70]}", flush=True)

json.dump(results, open(OUT, "w"), indent=1, ensure_ascii=False)
print(f"\nOK={sum(1 for v in results.values() if v['ok'])}/{len(urls)} -> {OUT}")
