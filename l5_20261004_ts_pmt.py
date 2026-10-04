#!/usr/bin/env python3
"""Parse MPEG-TS (PMT) para descobrir video/audio reais, sem ffprobe."""
import glob

TYPES = {
    0x01: "MPEG1-video", 0x02: "MPEG2-video", 0x03: "MPEG1-audio", 0x04: "MPEG2-audio",
    0x0F: "AAC-ADTS", 0x10: "MPEG4-video", 0x11: "AAC-LATM", 0x1B: "H264", 0x24: "HEVC",
    0x81: "AC3", 0x87: "EAC3", 0x06: "PRIVATE/ID3", 0x1C: "AV1",
}


def parse_pmt(pkt):
    off = 4
    pointer = pkt[off]
    off += 1 + pointer
    if off >= 188 or pkt[off] != 0x02:
        return None
    pmt = pkt[off:]
    if len(pmt) < 13:
        return None
    prog = (pmt[3] << 8) | pmt[4]
    pcr_pid = ((pmt[8] & 0x1F) << 8) | pmt[9]
    pil = ((pmt[10] & 0x0F) << 8) | pmt[11]
    i = 12 + pil
    streams = []
    while i + 4 < len(pmt):
        st = pmt[i]
        ep = ((pmt[i + 1] & 0x1F) << 8) | pmt[i + 2]
        esil = ((pmt[i + 3] & 0x0F) << 8) | pmt[i + 4]
        streams.append((st, ep))
        i += 5 + esil
        if st == 0x00:
            break
    return prog, pcr_pid, streams


def analyze(path):
    data = open(path, "rb").read()
    counts = {}
    for i in range(0, len(data) - 187, 188):
        pkt = data[i:i + 188]
        if pkt[0] != 0x47:
            continue
        pid = ((pkt[1] & 0x1F) << 8) | pkt[2]
        pusi = (pkt[1] & 0x40) >> 6
        afc = (pkt[3] >> 4) & 0x03
        if pusi and pid == 0 and afc in (1, 3):
            r = parse_pmt(pkt)
            if r:
                counts[pid] = r
        elif pusi and afc in (1, 3):
            counts.setdefault(pid, ("payload", pid, []))
    # contagem de pacotes por PID elemental
    pc = {}
    for i in range(0, len(data) - 187, 188):
        pkt = data[i:i + 188]
        if pkt[0] != 0x47:
            continue
        pid = ((pkt[1] & 0x1F) << 8) | pkt[2]
        pc[pid] = pc.get(pid, 0) + 1
    return counts, pc


for f in sorted(glob.glob("/tmp/opencode/seg/*.ts")):
    print("=" * 70)
    print(f)
    counts, pc = analyze(f)
    for pid, v in counts.items():
        if v[0] == "payload":
            continue
        prog, pcr_pid, streams = v
        print(f"  PMT programa={prog} pcr_pid=0x{pcr_pid:04X}")
        for st, ep in streams:
            print(f"    stream_type=0x{st:02X} {TYPES.get(st,'?'):14} pid=0x{ep:04X} pacotes={pc.get(ep,0)}")