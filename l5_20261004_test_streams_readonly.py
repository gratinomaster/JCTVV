#!/usr/bin/env python3
"""Testa as URLs de lista5.m3u sem modificar o arquivo (leitura + relatorio)."""
import concurrent.futures
import json
import sys
from datetime import datetime

import testar_lista5_20261004 as T


def main():
    entries = T.parse_m3u("lista5.m3u")
    urls = []
    seen = set()
    for e in entries:
        for u in e["urls"]:
            if u not in seen:
                seen.add(u)
                urls.append(u)
    print(f"Entradas: {len(entries)} | URLs unicas: {len(urls)}\n")
    res = {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=6) as ex:
        futs = {ex.submit(T.test_url, u): u for u in urls}
        for i, f in enumerate(concurrent.futures.as_completed(futs), 1):
            u, ok, why = f.result()
            res[u] = {"ok": ok, "reason": why}
            print(f"[{i}/{len(urls)}] {'OK   ' if ok else 'FALHA'} {why}")
            print(f"         {T.name_of(entries[0]) if not entries else ''} {u[:110]}")
    with open("l5_stream_results_20261004.json", "w") as fh:
        json.dump(res, fh, indent=2, ensure_ascii=False)
    ok = sum(1 for v in res.values() if v["ok"])
    print(f"\nOK: {ok}/{len(urls)}")
    for e in entries:
        name = T.name_of(e)
        for u in e["urls"]:
            print(f"  {name[:45]:45} {'OK' if res.get(u, {}).get('ok') else 'FALHA'}  {res.get(u, {}).get('reason', '')}")
    print("Data:", datetime.now().isoformat(timespec="seconds"))
    return 0


if __name__ == "__main__":
    sys.exit(main())