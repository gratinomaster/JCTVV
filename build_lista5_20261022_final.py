#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Monta a lista5 final: EPG valido e atualizado, logos .jpg, streams testados.

Regras aplicadas (mesmas do build_lista5_epg_validado.py, atualizadas):
  - todo canal precisa de tvg-id presente no EPG com programacao de hoje, amanha e depois de amanha
  - tvg-logo obrigatoriamente .jpg (nunca imgur.com), verificado byte a byte (magic JPEG)
  - toda URL de stream precisa de uma linha #EXTINF imediatamente acima
  - URLs com token/sessao expirada (hdnea=exp=, dai.google.com) e hosts crus sao descartadas
  - todo canal passa pelo teste anti-virus (URLhaus + heuristicas locais)

O EPG publicado e regerado a partir de https://iptv-epg.org/files/epg-us.xml.gz
contendo apenas os canais da lista (janela de -1 a +7 dias) e a URL do EPG e
inserida no cabecalho da lista (x-tvg-url/url-tvg).

Uso: python3 build_lista5_20261022_final.py [--escrever] [--pular-teste]
"""
import argparse
import datetime
import gzip
import os
import re
import shutil
import sys
from urllib.parse import urlparse

import requests

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from testar_lista5_20261022 import test_url  # noqa: E402

PLAYLIST = "lista5.m3u"
EPG_XML = "lista5_epg.xml"
EPG_GZ = "lista5_epg.xml.gz"
EPG_FONTE = "https://iptv-epg.org/files/epg-us.xml.gz"
EPG_CACHE = "/tmp/opencode/epg_iptv_epg_us.xml.gz"
EPG_PUBLICO = "https://raw.githubusercontent.com/gratinomaster/JCTVV/main/lista5_epg.xml.gz"
RAW_LOGOS = "https://raw.githubusercontent.com/gratinomaster/JCTVV/main/logos"
DIAS_EPG = 8          # dias de programacao publicados (-1 .. +7)
JANELA_TESTE = 3      # dias exigidos com programacao (hoje, amanha, depois de amanha)

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
H = {"User-Agent": UA, "Accept": "*/*", "Accept-Language": "en-US,en;q=0.9"}

CHANNELS = [
    ("ABC News Live", "ABCNewsLive.us", "news world",
     "https://abcnews-livestreams.akamaized.net/out/v1/6a597119dbd5428a82dc11a2f514a1a2/"
     "abcn-live-10-cmaf-manifest/abcn-live-10-index.m3u8",
     "https://keyframe-cdn.abcnews.com/streamprovider10.jpg"),
    ("ABC News Live 2", "ABCNewsLive.us", "news world",
     "https://abcnews-livestreams.akamaized.net/out/v1/173a6e46d5c5423d9611bc7fb7899c73/"
     "abcn-live-05-cmaf-manifest/abcn-live-05-index.m3u8",
     "https://keyframe-cdn.abcnews.com/streamprovider5.jpg"),
    ("CBS News 24/7", "CBSNews.us", "news world",
     "https://cbsn-us.cbsnstream.cbsnews.com/out/v1/55a8648e8f134e82a470f83d562deeca/master.m3u8",
     "https://assets2.cbsnewsstatic.com/hub/i/r/2024/04/16/0fb75ad2-a909-44bb-87dc-86b9d51cbeb2/"
     "thumbnail/1280x720/949f3d3fef16f9c113e3048c6aef229f/247-key-channelthumbnail-1920x1080.jpg"),
    ("Fox News Channel", "FoxNewsChannel.us", "news world",
     "https://247preview.foxnews.com/hls/live/2020027/fncv3preview/primary.m3u8",
     "https://a57.foxnews.com/cf-images.us-east-1.prod.boltdns.net/v1/static/694940094001/"
     "15de0523-3be4-4a9a-8159-7020114e7036/b6ff623a-26d6-4fd9-8bb8-0856adbf38ce/"
     "1280x720/match/676/380/image.jpg?ve=1&tl=1"),
    ("Fox Business", "FoxBusiness.us", "news world",
     "https://247preview.foxbusiness.com/hls/live/2020026/fbnv3preview/primary.m3u8",
     "https://a57.foxnews.com/cf-images.us-east-1.prod.boltdns.net/v1/static/694940094001/"
     "c9b2e2eb-7b87-435c-9510-eab2650ff944/8b584585-acf2-4c37-aa07-aaf2d077bb20/"
     "1280x720/match/676/380/image.jpg?ve=1&tl=1"),
    ("CNN International", "CNNinternational.us", "news world",
     "https://d3bp6dwmpbdajl.cloudfront.net/v1/master/3722c60a815c199d9c0ef36c5b73da68a62b09d1/"
     "cc-ury0meh5m4nzm/index.m3u8",
     f"{RAW_LOGOS}/l5-cnn-international.jpg"),
    ("NBC News NOW", "NBCNewsNow.us", "news world",
     "https://d1si3n1st4nkgb.cloudfront.net/10502/88896001/hls/master.m3u8?ads.xumo_channelId=88896001",
     f"{RAW_LOGOS}/l5-nbc-news-now.jpg"),
    ("DW English", "DWEnglish.us", "news world",
     "https://dwamdstream102.akamaized.net/hls/live/2015525/dwstream102/master.m3u8",
     f"{RAW_LOGOS}/l5-dw-english.jpg"),
    ("Euronews", "Euronews.us", "news world",
     "https://cdn-euronews.akamaized.net/live/eds/euronews-en/25080/index.m3u8",
     f"{RAW_LOGOS}/l5-euronews.jpg"),
    ("i24 News", "i24News.us", "news world",
     "https://i24newsenglish-cdn.encoders.immergo.tv/master.m3u8",
     f"{RAW_LOGOS}/l5-i24-news.jpg"),
    ("NHK World", "NHKWorld.us", "news world",
     "https://masterpl.hls.nhkworld.jp/hls/w/live/smarttv.m3u8",
     f"{RAW_LOGOS}/l5-nhk-world.jpg"),
    ("France 24 en Espanol", "France24enEspanol.us", "news world",
     "https://live.france24.com/hls/live/2037220-b/F24_ES_HI_HLS/master_5000.m3u8",
     f"{RAW_LOGOS}/l5-france24-espanol.jpg"),
    ("Newsmax TV", "NewsmaxTV.us", "news world",
     "https://nmx1ota.akamaized.net/hls/live/2107010/Live_1/index.m3u8",
     f"{RAW_LOGOS}/l5-newsmax-tv.jpg"),
    ("Reuters TV", "ReutersTV.us", "news world",
     "https://amg00453-reuters-amg00453c1-rakuten-uk-2110.playouts.now.amagi.tv/playlist/"
     "amg00453-reuters-reuters-rakutenuk/playlist.m3u8",
     f"{RAW_LOGOS}/l5-reuters-tv.jpg"),
    ("Live NOW from FOX", "LiveNOWfromFOX.us", "news world",
     "https://fox-foxnewsnow-vizio.amagi.tv/playlist.m3u8",
     f"{RAW_LOGOS}/l5-live-now-from-fox.jpg"),
    ("Scripps News", "ScrippsNews.us", "news world",
     "https://aegis-cloudfront-1.tubi.video/7e1c26b7-7975-4240-9a4f-480eaa8f3ea4/playlist.m3u8",
     f"{RAW_LOGOS}/l5-scripps-news.jpg"),
    ("CGTN CCTV News", "CGTNCCTVNews.us", "news world",
     "https://amg00405-rakutentv-cgtn-rakuten-i9tar.amagi.tv/master.m3u8",
     f"{RAW_LOGOS}/l5-cgtn-cctv-news.jpg"),
    ("Al Jazeera", "AlJazeera.us", "news world",
     "https://live-hls-apps-aje-fa.getaj.net/AJE/index.m3u8",
     f"{RAW_LOGOS}/l5-al-jazeera.jpg"),
]

# hosts bloqueados (token expirado, aggregators com IP cru, etc.)
BLOQUEADOS = ("hdnea=", "dai.google.com", "dai.google", "jmp2.uk", "aynaott.com")


def log(msg):
    print(msg, flush=True)


def carregar_epg():
    if os.path.exists(EPG_CACHE) and os.path.getsize(EPG_CACHE) > 1_000_000:
        log(f"[EPG] cache local {EPG_CACHE}")
        bruto = gzip.decompress(open(EPG_CACHE, "rb").read())
    else:
        log(f"[EPG] baixando {EPG_FONTE}")
        bruto = requests.get(EPG_FONTE, headers=H, timeout=300).content
        if bruto[:2] == b"\x1f\x8b":
            bruto = gzip.decompress(bruto)
        os.makedirs(os.path.dirname(EPG_CACHE), exist_ok=True)
        with open(EPG_CACHE, "wb") as f:
            f.write(gzip.compress(bruto))
    return bruto.decode("utf-8", "replace")


def programmes_por_canal(epg):
    """{canal_id: [(start, stop, corpo_xml)]} com tempos ja em UTC."""
    out = {}
    for m in re.finditer(
        r'<programme start="(\d{14})([^"]*)" stop="(\d{14})([^"]*)" channel="([^"]+)">(.*?)</programme>',
        epg, re.S,
    ):
        cid = m.group(5)
        out.setdefault(cid, []).append(
            (m.group(1) + m.group(2), m.group(3) + m.group(4), m.group(6).strip())
        )
    return out


def construir_epg(epg, canais, hoje):
    canais_xml, programas_xml = [], []
    ini = hoje - datetime.timedelta(days=1)
    fim = hoje + datetime.timedelta(days=DIAS_EPG - 1)
    todos = programmes_por_canal(epg)
    contagem = {}
    for nome, cid, _grupo, _url, _logo in canais:
        if any(c[0] == cid for c in canais_xml):
            continue
        m = re.search(r'<channel id="%s">(.*?)</channel>' % re.escape(cid), epg, re.S)
        display = nome
        if m:
            dm = re.search(r"<display-name>([^<]*)</display-name>", m.group(1))
            if dm:
                display = dm.group(1).strip()
        canais_xml.append((cid, display, nome))
        por_dia, ultimo_stop = {}, ""
        programas = sorted(todos.get(cid, []), key=lambda p: p[0])
        for start, stop, corpo in programas:
            dia = start[:8]
            if not (ini.strftime("%Y%m%d") <= dia <= fim.strftime("%Y%m%d")):
                continue
            if ultimo_stop and start < ultimo_stop:
                continue
            ultimo_stop = stop
            por_dia[dia] = por_dia.get(dia, 0) + 1
            title = re.search(r"<title[^>]*>(.*?)</title>", corpo, re.S)
            desc = re.search(r"<desc[^>]*>(.*?)</desc>", corpo, re.S)
            cat = re.findall(r"<category[^>]*>(.*?)</category>", corpo, re.S)
            data = re.search(r"<date>(.*?)</date>", corpo, re.S)
            bloco = [f'  <programme start="{start}" stop="{stop}" channel="{cid}">']
            bloco.append(f"    <title lang=\"en\">{title.group(1).strip() if title else display}</title>")
            if desc:
                bloco.append(f"    <desc lang=\"en\">{desc.group(1).strip()}</desc>")
            for c in cat[:3]:
                bloco.append(f"    <category lang=\"en\">{c.strip()}</category>")
            if data:
                bloco.append(f"    <date>{data.group(1).strip()}</date>")
            bloco.append("  </programme>")
            programas_xml.append("\n".join(bloco))
        contagem[cid] = por_dia
    return canais_xml, programas_xml, contagem


def testar_logo(url):
    if "imgur.com" in url.lower():
        return False, "imgur.com nao permitido"
    if not url.lower().split("?")[0].endswith(".jpg"):
        return False, "nao termina em .jpg"
    try:
        r = requests.get(url, headers=H, timeout=30)
    except Exception as e:
        return False, f"erro {type(e).__name__}"
    if r.status_code != 200:
        return False, f"HTTP {r.status_code}"
    if not r.content.startswith(b"\xff\xd8\xff"):
        return False, "conteudo nao e JPEG"
    return True, f"JPEG {len(r.content)} bytes"


def checar_av(url, hosts, bad_urls):
    try:
        import av_check_20261022 as av
    except ImportError:
        import av_check_20261008 as av
    return av.check(url, hosts, bad_urls)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--escrever", action="store_true")
    ap.add_argument("--pular-teste", action="store_true", help="nao roda teste de stream (rapido)")
    args = ap.parse_args()

    hoje = datetime.datetime.now(datetime.timezone.utc).date()
    dias = [(hoje + datetime.timedelta(days=i)).strftime("%Y%m%d") for i in range(JANELA_TESTE)]
    log(f"[EPG] janela minima exigida: {dias}")

    epg = carregar_epg()
    canais_xml, programas_xml, contagem = construir_epg(epg, CHANNELS, hoje)

    try:
        import av_check_20261022 as av
    except ImportError:
        import av_check_20261008 as av
    csvpath = av.ensure_downloaded()
    hosts, bad_urls = av.load_hosts(), av.load_urls(csvpath)
    log(f"[AV] URLhaus: {len(hosts)} hosts, {len(bad_urls)} URLs maliciosas")

    aprovados, relatorio = [], []
    for nome, cid, grupo, url, logo in CHANNELS:
        por_dia = contagem.get(cid, {})
        epg_ok = cid in dict((c[0], c) for c in canais_xml) and all(por_dia.get(d, 0) > 0 for d in dias)
        log(f"[EPG] {'OK  ' if epg_ok else 'FALHA'} {cid:22} " +
            ", ".join(f"{d}:{por_dia.get(d, 0)}" for d in dias))

        probs = []
        host = (urlparse(url).hostname or "").lower()
        for b in BLOQUEADOS:
            if b in url.lower():
                probs.append(f"URL bloqueada ({b})")
        if host.replace(".", "").isdigit():
            probs.append("host IP cru")
        probs += checar_av(url, hosts, bad_urls)
        probs += checar_av(logo, hosts, bad_urls)

        stream_ok, stream_msg = False, "nao testado"
        if not args.pular_teste and not probs:
            _u, stream_ok, _a, stream_msg, _s = test_url(url)
        elif not args.pular_teste:
            stream_msg = "pulado (reprovado na triagem)"
        logo_ok, logo_msg = testar_logo(logo)

        log(f"[AV ] {'OK  ' if not probs else 'FALHA'} {nome:22} {url[:78]}")
        for p in probs:
            log(f"          -> {p}")
        log(f"[STR] {'OK  ' if stream_ok else 'FALHA'} {nome:22} {stream_msg}")
        log(f"[LOG] {'OK  ' if logo_ok else 'FALHA'} {nome:22} {logo_msg}")

        if epg_ok and stream_ok and logo_ok and not probs:
            aprovados.append((nome, cid, grupo, url, logo))
            relatorio.append(f"OK    {nome:22} {cid:22} {stream_msg} | {logo_msg}")
        else:
            log(f"[X  ] {nome} REMOVIDO")
            relatorio.append(
                f"FALHA {nome:22} {cid:22} epg={epg_ok} stream={stream_ok} logo={logo_ok} "
                f"av={probs or 'ok'} | {stream_msg}")

    if not aprovados:
        log("nenhum canal passou em todas as verificacoes")
        return 1

    cabecalho = f'#EXTM3U x-tvg-url="{EPG_PUBLICO},{EPG_FONTE}" url-tvg="{EPG_PUBLICO},{EPG_FONTE}"'
    linhas = [cabecalho]
    for nome, cid, grupo, url, logo in aprovados:
        linhas.append(f'#EXTINF:-1 tvg-id="{cid}" tvg-name="{nome}" tvg-logo="{logo}" group-title="{grupo}",{nome}')
        linhas.append(url)
    conteudo = "\n".join(linhas) + "\n"

    xml = ["<?xml version='1.0' encoding='utf-8'?>",
           '<tv generator-info-name="lista5 EPG (iptv-epg.org)" source-info-name="iptv-epg.org">']
    for cid, display, _nome in canais_xml:
        xml.append(f'  <channel id="{cid}">')
        xml.append(f"    <display-name>{display}</display-name>")
        xml.append("    <lang>en</lang>")
        xml.append("  </channel>")
    xml.extend(programas_xml)
    xml.append("</tv>")
    xml_texto = "\n".join(xml) + "\n"

    log("")
    log(f"[EPG] canais publicados: {len(canais_xml)} | programas: {len(programas_xml)}")
    log(conteudo)

    if args.escrever:
        stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        for alvo in (PLAYLIST, EPG_XML, EPG_GZ):
            if os.path.exists(alvo):
                shutil.copy2(alvo, f"{alvo}.bak.pre_tarefa_{stamp}")
                log(f"[BAK] {alvo}.bak.pre_tarefa_{stamp}")
        with open(PLAYLIST, "w", encoding="utf-8") as f:
            f.write(conteudo)
        with open(EPG_XML, "w", encoding="utf-8") as f:
            f.write(xml_texto)
        with gzip.open(EPG_GZ, "wb") as f:
            f.write(xml_texto.encode("utf-8"))
        with open(f"relatorio_lista5_{stamp}.txt", "w", encoding="utf-8") as f:
            f.write(f"lista5 final - {datetime.datetime.now().isoformat(timespec='seconds')}\n")
            f.write(f"canais: {len(aprovados)} | EPG: {len(canais_xml)} canais / "
                    f"{len(programas_xml)} programas\n\n")
            f.write("\n".join(relatorio) + "\n")
        log(f"[OK] {PLAYLIST}, {EPG_XML} e {EPG_GZ} gravados")
    return 0


if __name__ == "__main__":
    sys.exit(main())
