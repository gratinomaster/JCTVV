#!/usr/bin/env python3
"""Teste somente-leitura das URLs de lista5.m3u (nao altera a lista)."""
import concurrent.futures
import json
import sys

import testar_lista5_20261004 as T

OUT = "l5_readonly_results.json"


def main():
    entries = T.parse_m3u("lista5.m3u")
    urls, seen = [], set()
    for e in entries:
        for u in e["urls"]:
            if u not in seen:
                seen.add(u)
                urls.append(u)
    print(f"Entradas: {len(entries)} | URLs unicas: {len(urls)}\n")
    res = {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=T.WORKERS) as ex:
        futs = {ex.submit(T.test_url, u): u for u in urls}
        for i, f in enumerate(concurrent.futures.as_completed(futs), 1):
            u, ok, why = f.result()
            res[u] = {"ok": ok, "reason": why}
            print(f"[{i}/{len(urls)}] {'OK   ' if ok else 'FALHA'} {why}")
    with open(OUT, "w") as fh:
        json.dump(res, fh, indent=2, ensure_ascii=False)
    ok = sum(1 for v in res.values() if v["ok"])
    print(f"\nURLs OK: {ok}/{len(urls)}")
    print("\n=== por canal ===")
    for e in entries:
        name = T.name_of(e)
        oks = [u for u in e["urls"] if res.get(u, {}).get("ok")]
        if oks:
            why = res[oks[0]]["reason"]
        else:
            why = res.get(e["urls"][0], {}).get("reason", "?") if e["urls"] else "?"
        print(f"  {'OK   ' if oks else 'FALHA'} {name[:48]:48} {why}")
    print(f"\nJSON: {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
