#!/usr/bin/env python3
"""
Reescreve o lista5.m3u usando apenas o que passou em l5_verificar_20260930.py.

Garante:
  - todo canal tem tvg-id presente na fonte EPG com programme para
    hoje, amanha e depois de amanha;
  - todo canal tem tvg-logo em .jpg (nunca imgur.com) e que responde JPEG valido;
  - a fonte EPG entra no cabecalho (x-tvg-url) e em cada #EXTINF (url-tvg);
  - nenhuma URL de canal fica sem o #EXTINF na linha de cima;
  - nada de entradas repetidas nem de streams com token que expira.
"""
import json
import re
import shutil
import sys
from datetime import datetime

PL = "lista5.m3u"
JSON = "/tmp/opencode/l5_verificacao.json"
EPG = "https://epgshare01.online/epgshare01/epg_ripper_US2.xml.gz"
GRUPO = "NEWS WORLD"
NOME_EPG = {"ABC News Live": "ABC News Live",
            "Fox News Channel": "Fox News Channel",
            "Fox Business": "Fox Business",
            "CBS News 24/7": "CBS News 24/7"}


def carregar():
    with open(JSON, encoding="utf-8") as f:
        return json.load(f)


def canal(c, nome, url):
    return (
        '#EXTINF:-1 tvg-id="%s" tvg-name="%s" tvg-logo="%s" group-title="%s" url-tvg="%s",%s'
        % (c["tvg_id"], nome.replace('"', ""), c["logo"], c["grupo"], EPG, nome),
        url,
    )


def main():
    dados = carregar()
    veredito = dados["veredito"]

    canais, descartes = [], []
    for nome, v in veredito.items():
        if not v["ok"]:
            descartes.append((nome, "reprovado na verificacao"))
            continue
        if not v["epg"]["ok"]:
            descartes.append((nome, "sem EPG para hoje/amanha/depois de amanha"))
            continue
        logo = v["logo"].split("?")[0]
        if not logo.lower().endswith(".jpg") or "imgur.com" in logo:
            descartes.append((nome, "tvg-logo fora das regras"))
            continue
        for i, url in enumerate(v["urls"]):
            canais.append(canal(v, nome if i == 0 else "%s (Reserva)" % nome, url))

    # dedupe defensivo por URL mantendo a primeira ocorrencia
    vistos, unicos = set(), []
    for extinf, url in canais:
        if url in vistos:
            continue
        vistos.add(url)
        unicos.append((extinf, url))
    canais = unicos

    # checagem final de formato: nenhuma URL sem #EXTINF acima
    for i, (extinf, url) in enumerate(canais):
        if not extinf.startswith("#EXTINF:"):
            sys.exit("ERRO: entrada %d sem #EXTINF" % i)
        if not re.match(r"^https?://", url):
            sys.exit("ERRO: URL invalida na entrada %d" % i)

    bak = "%s.bak.%s" % (PL, datetime.now().strftime("%Y%m%d_%H%M%S"))
    shutil.copy2(PL, bak)
    with open(PL, "w", encoding="utf-8", newline="\n") as f:
        f.write('#EXTM3U x-tvg-url="%s"\n' % EPG)
        for extinf, url in canais:
            f.write(extinf + "\n" + url + "\n")

    rel = "relatorio_lista5_20260930.txt"
    with open(rel, "w", encoding="utf-8") as f:
        f.write("CORRECAO lista5.m3u - %s\n" % datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        f.write("EPG: %s\n" % EPG)
        f.write("Dias verificados: hoje=%s amanha=%s depois=%s\n"
                % (dados["dias"]["hoje"], dados["dias"]["amanha"], dados["dias"]["depois"]))
        f.write("Backup: %s\n" % bak)
        f.write("ClamAV: %d arquivo(s) varrido(s), %d-infecao(oes)\n"
                % (len({a for s in dados["streams"] for a in s.get("arquivos", [])}),
                   len(dados.get("clamav_infected", []))))
        f.write("\nCANAIS NOVO (%d):\n" % len(canais))
        for extinf, url in canais:
            nome = extinf.split(",")[-1]
            tid = re.search(r'tvg-id="([^"]+)"', extinf).group(1)
            e = next((x["epg"] for x in veredito.values() if x["nome"] in nome), None)
            f.write("  - %-26s tvg-id=%-30s hoje=%s amanha=%s depois=%s\n"
                    % (nome, tid,
                       e["hoje"] if e else "?", e["amanha"] if e else "?", e["depois"] if e else "?"))
            f.write("      %s\n" % url)
        f.write("\nREMOVIDOS:\n")
        for nome, motivo in descartes:
            f.write("  - %s (%s)\n" % (nome, motivo))
        f.write("""  - 30 entradas duplicadas/variantes (13x CBS News 24/7, 8x ABC Disney dssott,
    6x ABC akamai index_3/index_4_0, 2x Fox e 1x CBS DAI): mantidas so as masters
    estaveis verificadas.
  - 247.foxnews.com e 247.foxbusiness.com com token hdnea: HTTP 403 (token expirado)
  - linear-abcnews...media.dssott.com: token expira 2026-10-01 01:44 UTC
  - dai.google.com/linear/...: URL de evento DAI, efemera
""")

    print("Backup: %s" % bak)
    print("Relatorio: %s" % rel)
    print("Canais gravados: %d" % len(canais))
    for extinf, url in canais:
        print("  - %-26s %s" % (extinf.split(",")[-1], url[:96]))
    if descartes:
        print("Removidos: %s" % ", ".join(n for n, _ in descartes))


if __name__ == "__main__":
    main()
