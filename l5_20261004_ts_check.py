#!/usr/bin/env python3
"""Confere, por parse do MPEG-TS, se o segmento tem video E audio reais (sem ffprobe)."""
import collections
import glob
import sys

STREAM_TYPES = {
    0x00: "reserved", 0x01: "MPEG1-video", 0x02: "MPEG2-video", 0x03: "MPEG1-audio",
    0x04: "MPEG2-audio", 0x0F: "AAC-ADTS", 0x10: "MPEG4-video", 0x11: "AAC-LATM",
    0x1B: "H264", 0x24: "HEVC", 0x02 + 0x100: "?", 0x06: "PRIVATE", 0x15: "ADTS-SYNC",
    0x1C: "AV1?", 0x81: "AC3", 0x87: "EAC3", 0x06 + 0x100: "ID3/private",
}


def analyze(path):
    data = open(path, "rb").read()
    pids = collections.Counter()
    types = {}
    pcr = 0
    sync_err = 0
    for i in range(0, len(data) - 187, 188):
        pkt = data[i:i + 188]
        if len(pkt) < 188 or pkt[0] != 0x47:
            sync_err += 1
            continue
        pid = ((pkt[1] & 0x1F) << 8) | pkt[2]
        pids[pid] += 1
        pusi = pkt[1] & 0x40
        afc = (pkt[3] >> 4) & 0x03
        pcr_flag = (pkt[3] & 0x10) >> 4
        if pcr_flag:
            pcr += 1
        if pusi and afc in (1, 3):
            off = 4
            if afc == 3:
                off = 5 + pkt[4]
            if off < len(pkt):
                sid = pkt[off]
                if 0x00 <= sid <= 0x1C or sid in (0x1B, 0x24, 0x81, 0x87, 0x06):
                    if pid not in types:
                        types[pid] = (sid, STREAM_TYPES.get(sid, f"0x{sid:02X}"))
    return pids, types, pcr, sync_err


for f in sorted(glob.glob("/tmp/opencode/seg/*.ts")):
    pids, types, pcr, sync_err = analyze(f)
    print(f"{f}: pacotes={sum(pids.values())} sync_erros={sync_err} pcr={pcr}")
    for pid, (sid, name) in sorted(types.items()):
        print(f"   PID {pid:5d} pacotes={pids[pid]:5d} type=0x{sid:02X} {name}")
    kinds = {n for _, n in types.values()}
    has_v = any(k in ("H264", "HEVC", "AV1?") for k in kinds)
    has_a = any(k in ("AAC-ADTS", "AAC-LATM", "MPEG2-audio", "MPEG4-audio", "AC3", "EAC3", "MPEG1-audio") for k in kinds)
    print(f"   => VIDEO={has_v} AUDIO={has_a}")