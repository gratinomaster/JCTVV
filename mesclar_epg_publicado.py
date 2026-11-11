#!/usr/bin/env python3
"""Repara o EPGFULL.xml.gz recem-gerado usando o EPG publicado no GitHub.

Duas situacoes sao corrigidas, sempre respeitando a mesma janela de
retencao do gerar_epgfull.py (-1 dia / +7 dias):

  1. canais que ficaram sem NENHUM programa nas fontes frescas (ex.: canais
     venezuelanos, que o iptv-epg.org nao publica mais) recebem a grade
     publicada;
  2. canais cuja unica grade fresca e preenchimento "No Data" (o iptv-epg.org
     publica blocos vazios quando nao tem programacao real) tem o filler
     descartado e recebem a grade real publicada no lugar.

Canais que ja tem programacao real das fontes frescas nao sao tocados. O
display-name de canais substituidos cujo prefixo de pais diverge do sufixo
do tvg-id (ex.: "CO - Globovision" para Globovision.ve) e refeito a partir
do proprio .m3u (nome + logo).

Uso:
    python3 mesclar_epg_publicado.py   (rodar DEPOIS do gerar_epgfull.py)
"""
import copy
import gzip
import os
import re
import sys
import tempfile
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone

EPG_LOCAL = "EPGFULL.xml.gz"
M3U_LOCAL = "NEWSWORLDNOVOS.m3u"
M3U_URL = "https://github.com/gratinomaster/JCTV/raw/refs/heads/main/NEWSWORLDNOVOS.m3u"
EPG_PUBLISHED_URL = "https://github.com/gratinomaster/JCTV/raw/refs/heads/main/EPGFULL.xml.gz"

PAST_DAYS = 1
FUTURE_DAYS = 7

FILLER = {"no data", "no-data", "nodata", "sin datos", "sem dados"}


def barra(titulo):
    print("=" * 70)
    print(titulo)
    print("=" * 70)


def baixar(url):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=120) as r:
        return r.read()


def utc_stamp(valor):
    """Converte 'YYYYMMDDHHMMSS +HHMM' para o mesmo instante em UTC (+0000)."""
    m = re.match(r"^(\d{14})\s*([+-])(\d{2})(\d{2})$", (valor or "").strip())
    if not m:
        return (valor or "").strip()
    base, sinal, hh, mm = m.groups()
    dt = datetime.strptime(base, "%Y%m%d%H%M%S")
    desloc = timedelta(hours=int(hh), minutes=int(mm))
    dt = dt - desloc if sinal == "+" else dt + desloc
    return dt.strftime("%Y%m%d%H%M%S") + " +0000"


def titulos_canal(raiz, cid):
    return [(p.findtext("title") or "").strip().lower()
            for p in raiz.findall("programme") if p.get("channel") == cid]


def e_filler(raiz, cid):
    titulos = [t for t in titulos_canal(raiz, cid) if t]
    return bool(titulos) and all(t in FILLER for t in titulos)


def tem_real(raiz, cid):
    return any(t and t not in FILLER for t in titulos_canal(raiz, cid))


def ler_m3u():
    if os.path.exists(M3U_LOCAL):
        with open(M3U_LOCAL, encoding="utf-8", errors="replace") as f:
            return f.read()
    return baixar(M3U_URL).decode("utf-8", errors="replace")


def info_m3u(texto):
    infos = {}
    for linha in texto.splitlines():
        if not linha.startswith("#EXTINF"):
            continue
        m = re.search(r'tvg-id="([^"]*)"', linha)
        if not m:
            continue
        tid = m.group(1).strip()
        if not tid or tid in ("0", "(no tvg-id)") or tid in infos:
            continue
        ml = re.search(r'tvg-logo="([^"]*)"', linha)
        nome = linha.rsplit(",", 1)[-1].strip() if "," in linha else tid
        infos[tid] = {"nome": nome or tid,
                      "logo": (ml.group(1).strip() if ml else "")}
    return infos


def prefixo_divergente(nome_exibido, cid):
    """True quando o display-name traz prefixo de pais (ex.: 'CO - ...')
    diferente do sufixo do tvg-id."""
    m = re.match(r"^([A-Z]{2})\s*-\s*", (nome_exibido or "").strip())
    if not m:
        return False
    sufixo = cid.rsplit(".", 1)[-1].upper()
    return m.group(1) != sufixo


def main():
    if not os.path.exists(EPG_LOCAL):
        print(f"ERRO: {EPG_LOCAL} nao existe; rode o gerar_epgfull.py primeiro")
        return 1

    agora = datetime.now(timezone.utc).replace(tzinfo=None)
    inicio = (agora - timedelta(days=PAST_DAYS)).strftime("%Y%m%d") + "000000"
    fim = (agora + timedelta(days=FUTURE_DAYS + 1)).strftime("%Y%m%d") + "000000"
    hoje = agora.strftime("%Y%m%d")
    amanha = (agora + timedelta(days=1)).strftime("%Y%m%d")

    barra("1. EPG PUBLICADO NO GITHUB (fonte legada)")
    try:
        legado = ET.fromstring(gzip.decompress(baixar(EPG_PUBLISHED_URL)))
    except Exception as e:
        print(f"  indisponivel ({e}); nada a reparar")
        return 0
    print(f"  baixado: {len(legado.findall('channel'))} canais, "
          f"{len(legado.findall('programme'))} programas")

    barra("2. EPG NOVO (fontes frescas)")
    with gzip.open(EPG_LOCAL, "rb") as f:
        novo = ET.fromstring(f.read())
    canais_novo = novo.findall("channel")
    ids_novo = [c.get("id") for c in canais_novo]
    com_real = {cid for cid in ids_novo if tem_real(novo, cid)}
    com_prog = {cid for cid in ids_novo if titulos_canal(novo, cid)}
    filler = {cid for cid in ids_novo if e_filler(novo, cid)}
    vazios = set(ids_novo) - com_prog
    print(f"  {len(ids_novo)} canais | com grade real: {len(com_real)} | "
          f"so filler \"No Data\": {len(filler)} | sem programas: {len(vazios)}")

    barra("3. REPARO (janela {} -> {})".format(inicio[:8], fim[:8]))
    legado_reais = {cid for cid in ids_novo if tem_real(legado, cid)}
    legado_prog_cids = {p.get("channel") for p in legado.findall("programme")}
    alvo_substituir = filler & legado_reais     # filler "No Data" -> grade real publicada
    alvo_completar = vazios & legado_prog_cids  # sem programas -> grade publicada

    trocar = alvo_substituir | alvo_completar
    if not trocar:
        print("  nenhum canal precisou de reparo")
    else:
        if alvo_substituir:
            print(f"  substituindo filler \"No Data\" pela grade real ({len(alvo_substituir)} canais):")
            for cid in sorted(alvo_substituir):
                print(f"    {cid}")
        if alvo_completar - alvo_substituir:
            print(f"  completando canais sem programas ({len(alvo_completar - alvo_substituir)} canais):")
            for cid in sorted(alvo_completar - alvo_substituir):
                print(f"    {cid}")

    # remove os programas atuais dos canais que trocarao de grade
    programas = [p for p in novo.findall("programme") if p.get("channel") not in trocar]

    vistos = {(p.get("channel"), p.get("start"), p.get("stop")) for p in programas}
    adicionados = {}
    for prog in legado.findall("programme"):
        cid = prog.get("channel", "")
        if cid not in trocar:
            continue
        st = utc_stamp(prog.get("start", ""))
        sp = utc_stamp(prog.get("stop", ""))
        if not re.match(r"^\d{14}", st):
            continue
        if not (inicio <= st < fim):
            continue
        chave = (cid, st, sp)
        if chave in vistos:
            continue
        vistos.add(chave)
        bloco = copy.deepcopy(prog)
        bloco.set("start", st)
        bloco.set("stop", sp)
        programas.append(bloco)
        adicionados[cid] = adicionados.get(cid, 0) + 1

    removidos = {cid: 0 for cid in trocar}
    for p in novo.findall("programme"):
        cid = p.get("channel")
        if cid in trocar:
            removidos[cid] = removidos.get(cid, 0) + 1

    barra("4. CANAIS: NOMES E LOGOS")
    infos = info_m3u(ler_m3u())
    corrigidos = []
    for canal in canais_novo:
        cid = canal.get("id")
        if cid not in trocar:
            continue
        dn = canal.find("display-name")
        exibido = (dn.text or "").strip() if dn is not None else ""
        if cid in infos and (not exibido or prefixo_divergente(exibido, cid)):
            if dn is None:
                dn = ET.SubElement(canal, "display-name")
            dn.text = infos[cid]["nome"]
            dn.set("lang", "pt")
            if infos[cid]["logo"]:
                icone = canal.find("icon")
                if icone is None:
                    icone = ET.SubElement(canal, "icon")
                icone.set("src", infos[cid]["logo"])
            corrigidos.append(f"{cid} -> \"{infos[cid]['nome']}\"")
    if corrigidos:
        for c in corrigidos:
            print(f"    display-name corrigido: {c}")
    else:
        print("    nenhum display-name divergente")

    barra("5. GRAVACAO DE EPGFULL.xml.gz")
    programas.sort(key=lambda p: (p.get("channel") or "", p.get("start") or ""))
    raiz = ET.Element("tv", novo.attrib)
    for canal in canais_novo:
        raiz.append(canal)
    for prog in programas:
        raiz.append(prog)
    corpo = ET.tostring(raiz, encoding="utf-8", xml_declaration=True)

    tmp = tempfile.NamedTemporaryFile(
        mode="wb", suffix=".xml.gz", delete=False, dir=os.path.dirname(os.path.abspath(EPG_LOCAL))
    )
    try:
        with gzip.GzipFile(fileobj=tmp, mode="wb", compresslevel=9, mtime=0) as gz:
            gz.write(corpo)
        tmp.close()
        os.chmod(tmp.name, 0o644)
        os.replace(tmp.name, EPG_LOCAL)
    except Exception:
        tmp.close()
        if os.path.exists(tmp.name):
            os.unlink(tmp.name)
        raise
    print(f"  gravado: {os.path.getsize(EPG_LOCAL):,} bytes gzip ({len(corpo):,} bytes xml)")
    if adicionados:
        print(f"  programas: -{sum(removidos.values())} filler/removidos, "
              f"+{sum(adicionados.values())} da grade publicada")

    barra("6. RESUMO")
    with gzip.open(EPG_LOCAL, "rb") as f:
        conferir = ET.fromstring(f.read())
    progs = conferir.findall("programme")
    ids = [c.get("id") for c in conferir.findall("channel")]
    n_hoje = sum(1 for p in progs if (p.get("start") or "")[:8] == hoje)
    n_amanha = sum(1 for p in progs if (p.get("start") or "")[:8] == amanha)
    c_hoje = {p.get("channel") for p in progs if (p.get("start") or "")[:8] == hoje}
    c_amanha = {p.get("channel") for p in progs if (p.get("start") or "")[:8] == amanha}
    c_real = {cid for cid in ids if tem_real(conferir, cid)}
    print(f"  canais ........ {len(ids)}")
    print(f"  com grade real  {len(c_real)}")
    print(f"  programas ..... {len(progs)}")
    print(f"  HOJE  {hoje} ... {n_hoje} programas em {len(c_hoje)} canais")
    print(f"  AMANHA {amanha} .. {n_amanha} programas em {len(c_amanha)} canais")
    print("=" * 70)
    return 0


if __name__ == "__main__":
    sys.exit(main())
