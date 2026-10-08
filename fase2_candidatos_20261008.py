#!/usr/bin/env python3
"""Testa candidatos de substituicao (CBS / Fox) 3 camadas."""
import concurrent.futures, importlib.util, json, sys
spec = importlib.util.spec_from_file_location("t", "/home/runner/work/JCTVV/JCTVV/testar_lista5_20261005_v2.py")
m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)

CANDS = [
 "https://cbsn-us.cbsnstream.cbsnews.com/out/v1/55a8648e8f134e82a470f83d562deeca/master.m3u8",
 "https://cbsn-2.cbsnstream.cbsnews.com/out/v1/a6a897e8f4f74cfc896223dfd822482f/master.m3u8",
 "https://cbsn-us-vtt.cbsnstream.cbsnews.com/out/v1/ef868690d34144509eda696884bf1619/master.m3u8",
 "https://247preview.foxnews.com/hls/live/2020027/fncv3preview/primary.m3u8",
 "https://247preview.foxnews.com/hls/live/2020027/fncv3preview/index.m3u8",
 "https://247preview.foxbusiness.com/hls/live/2020026/fbnv3preview/primary.m3u8",
 "https://247preview.foxbusiness.com/hls/live/2020026/fbnv3preview/index.m3u8",
]
res = {}
with concurrent.futures.ThreadPoolExecutor(max_workers=7) as ex:
    for u, ok, why in ex.map(lambda u: m.test_url(u), CANDS):
        res[u] = (ok, why)
        print(f"{'OK  ' if ok else 'FALHA'} | {why[:80]} | {u}", flush=True)
json.dump({k: {"ok": v[0], "reason": v[1]} for k, v in res.items()},
          open("/home/runner/work/JCTVV/JCTVV/fase2_candidatos_20261008.json", "w"), indent=1)
print(f"\nOK {sum(1 for v in res.values() if v[0])}/{len(res)}")
