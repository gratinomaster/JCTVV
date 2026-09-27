#!/usr/bin/env python3
"""Gera EPGFULL.xml.gz contendo SOMENTE os canais do NEWSWORLDNOVOS.m3u.

Fontes: arquivos regionais do IPTV-EPG.org (uma fonte por pais presente no .m3u).
Janela: de HOJE-1 ate HOJE+7 dias, para o guia nao ficar maior do que o necessario.
O arquivo EPGFULL.xml.gz e sobrescrito (via temporario + os.replace).
"""
import gzip
import html
import os
import re
import sys
import tempfile
import unicodedata
import urllib.request
from collections import OrderedDict
from datetime import datetime, timedelta, timezone

M3U_URL = "https://github.com/gratinomaster/JCTV/raw/refs/heads/main/NEWSWORLDNOVOS.m3u"
M3U_LOCAL = "NEWSWORLDNOVOS.m3u"
OUTPUT = "EPGFULL.xml.gz"
SRC_DIR = "/tmp/opencode/epgsrc"

PAST_DAYS = 1
FUTURE_DAYS = 7

# paises do IPTV-EPG.org que cobrem os canais do .m3u
PAISES = ["cl", "ar", "mx", "ve", "us", "br", "il", "pt", "fr", "es", "co", "gb"]

PAIS_NOME = {
    "cl": "Chile", "ar": "Argentina", "mx": "Mexico", "ve": "Venezuela",
    "us": "USA", "br": "Brasil", "il": "Israel", "pt": "Portugal",
    "fr": "Franca", "es": "Espanha", "co": "Colombia", "gb": "Reino Unido",
}


def norm(s):
    """Normaliza mantendo letras unicode (ex.: hebraico) para evitar falsos casamentos."""
    s = unicodedata.normalize("NFKD", s)
    s = "".join(c for c in s if not unicodedata.combining(c))
    return re.sub(r"[\W_]+", "", s.lower(), flags=re.UNICODE)


def sem_sufixo(nome):
    """Nome do canal sem os sufixos entre parenteses/colchetes.

    Ex.: 'TVI (Portugal)' -> 'TVI', 'TV Chile [Geo-bloqueado]' -> 'TV Chile'.
    """
    limpo = re.sub(r"\s*[\(\[][^()\[\]]*[\)\]]", " ", nome)
    return re.sub(r"\s{2,}", " ", limpo).strip()


def pais_de(cid):
    return cid.rsplit(".", 1)[-1].lower() if "." in cid else ""


def barra(titulo):
    print("=" * 70)
    print(titulo)
    print("=" * 70)


def agora_utc():
    return datetime.now(timezone.utc).replace(tzinfo=None, microsecond=0)


def baixar(url, destino):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=120) as r:
        dados = r.read()
    with open(destino, "wb") as f:
        f.write(dados)
    return len(dados)


# ---------------------------------------------------------------- 1. M3U
barra("1. LISTA DE CANAIS (.m3u)")

conteudo = None
try:
    req = urllib.request.Request(M3U_URL, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=60) as r:
        conteudo = r.read().decode("utf-8", errors="replace")
    print(f"  baixado do GitHub: {len(conteudo):,} bytes")
except Exception as e:
    print(f"  GitHub indisponivel ({e}); usando arquivo local")
    if not os.path.exists(M3U_LOCAL):
        print("ERRO: sem .m3u local para usar")
        sys.exit(1)
    with open(M3U_LOCAL, encoding="utf-8", errors="replace") as f:
        conteudo = f.read()

# ordem dos canais conforme o .m3u, para saida estavel
canais = OrderedDict()
nome_para_id = {}
for linha in conteudo.splitlines():
    if not linha.startswith("#EXTINF"):
        continue
    mt = re.search(r'tvg-id="([^"]*)"', linha)
    tvg = mt.group(1).strip() if mt else ""
    nome = linha.split(",")[-1].strip()
    if not tvg:
        continue
    if tvg in canais:
        continue
    ml = re.search(r'tvg-logo="([^"]*)"', linha)
    canais[tvg] = {
        "tvg_id": tvg,
        "nome": nome,
        "logo": ml.group(1).strip() if ml else "",
        "display": "",
        "icone": "",
    }
    nome_para_id.setdefault(norm(nome), tvg)

print(f"  canais com tvg-id: {len(canais)}")

# ---------------------------------------------------------------- 2. FONTES
barra("2. FONTES EPG (IPTV-EPG.org)")

os.makedirs(SRC_DIR, exist_ok=True)
fontes = []
for cc in PAISES:
    nome_arq = f"epg-{cc}.xml.gz"
    caminho = os.path.join(SRC_DIR, nome_arq)
    if not os.path.exists(caminho) or os.path.getsize(caminho) < 1024:
        url = f"https://iptv-epg.org/files/{nome_arq}"
        try:
            n = baixar(url, caminho)
            print(f"  {PAIS_NOME.get(cc, cc):<12} baixado {n:,} bytes")
        except Exception as e:
            print(f"  {PAIS_NOME.get(cc, cc):<12} FALHOU ({e})")
            continue
    else:
        print(f"  {PAIS_NOME.get(cc, cc):<12} cache {os.path.getsize(caminho):,} bytes")
    fontes.append((cc, caminho))

if not fontes:
    print("ERRO: nenhuma fonte disponivel")
    sys.exit(1)

# ---------------------------------------------------------------- 3. JANELA
agora = agora_utc()
inicio = (agora - timedelta(days=PAST_DAYS)).strftime("%Y%m%d000000")
fim = (agora + timedelta(days=FUTURE_DAYS + 1)).strftime("%Y%m%d000000")
hoje = agora.strftime("%Y%m%d")
amanha = (agora + timedelta(days=1)).strftime("%Y%m%d")

barra("3. JANELA DE PROGRAMACAO")
print(f"  agora (UTC)  : {agora:%Y-%m-%d %H:%M}")
print(f"  janela       : {inicio[:8]} -> {fim[:8]}  (-{PAST_DAYS} / +{FUTURE_DAYS} dias)")

def esc(s):
    return (s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
             .replace('"', "&quot;"))


# ---------------------------------------------------------------- 4. FILTRAGEM
barra("4. FILTRAGEM DOS PROGRAMAS")

re_chan = re.compile(r'<channel\s+id="([^"]*)"')
re_disp = re.compile(r"<display-name[^>]*>(.*?)</display-name>", re.S)
re_icon = re.compile(r'<icon\s+src="([^"]*)"')
re_atr = re.compile(r'(\w[\w-]*)="([^"]*)"')
NOME_MIN = 4
# o indice guarda tambem nomes de 3 letras (ex.: TVI); o casamento entre paises
# continua exigindo NOME_MIN, o curto so passa no proprio pais
INDICE_MIN = 3

# --- PASSO A: indexa os canais de todas as fontes -------------------------
print("  passo A: indexando canais das fontes...")
fonte = {}                 # cid da fonte -> dict(pais, display, icone)
nome_indice = {}           # (pais, norm(display)) -> [cid]
for cc, caminho in fontes:
    n = 0
    with gzip.open(caminho, "rt", encoding="utf-8", errors="replace") as f:
        bloco = None
        for linha in f:
            s = linha.strip()
            if bloco is None:
                if s.startswith("<channel "):
                    bloco = [s]
                continue
            if s.startswith("<icon ") or s.startswith("<display-name"):
                bloco.append(s)
            elif s.startswith("</channel>"):
                cid = html.unescape(re_chan.search(bloco[0]).group(1)).strip()
                dm = re_disp.search("\n".join(bloco))
                im = re_icon.search("\n".join(bloco))
                disp = html.unescape(dm.group(1)).strip() if dm else cid
                icone = im.group(1).strip() if im else ""
                if cid not in fonte:
                    fonte[cid] = {"pais": pais_de(cid), "display": disp, "icone": icone}
                    rot = norm(disp.split(" - ")[-1])
                    if len(rot) >= INDICE_MIN:
                        nome_indice.setdefault((pais_de(cid), rot), []).append(cid)
                    n += 1
                bloco = None
    print(f"  {PAIS_NOME.get(cc, cc):<12} {n:>6} canais")

# --- resolve o casamento fonte -> tvg-id ----------------------------------
mapeia = {}                # cid da fonte -> tvg-id do .m3u
usados = set()
origem = {}

for tvg in canais:                                   # 1) tvg-id exato
    if tvg in fonte and tvg not in usados:
        mapeia[tvg] = tvg
        usados.add(tvg)
        origem[tvg] = "id"

# 2) por nome. Ordem de preferencia: pais proprio, nome completo, sem sufixo e
# por fim qualquer pais. Exatamente um candidato, para nunca casar por
# semelhanca parcial (T13 nao pode cair em Canal13).
for rotulo, restricao in (("mesmo pais", True), ("qualquer pais", False)):
    for modo in ("completo", "sem sufixo"):
        for tvg in canais:
            if tvg in usados:
                continue
            nome = canais[tvg]["nome"]
            if modo == "sem sufixo":
                nome = sem_sufixo(nome)
            nn = norm(nome)
            # nome curto so passa no casamento exato dentro do proprio pais
            # (ex.: 'TVI (Portugal)' -> TVI.pt); entre paises exige 4+ caracteres
            if len(nn) < (INDICE_MIN if restricao else NOME_MIN):
                continue
            chaves = [(pais_de(tvg), nn)] if restricao else [
                k for k in nome_indice if k[1] == nn
            ]
            for k in chaves:
                cands = nome_indice.get(k, [])
                if len(cands) == 1 and cands[0] not in mapeia.values():
                    mapeia[cands[0]] = tvg
                    usados.add(tvg)
                    origem[tvg] = f"nome/{modo}/{rotulo}"
                    break

for cid_fonte, tvg in mapeia.items():
    c = canais[tvg]
    c["display"] = c["display"] or fonte[cid_fonte]["display"]
    c["icone"] = c["icone"] or fonte[cid_fonte]["icone"]

por_id = {t for t, o in origem.items() if o == "id"}
por_nome = {t for t, o in origem.items() if o != "id"}
print(f"  casamento por tvg-id: {len(por_id)} | por nome: {len(por_nome)}")

# --- PASSO B: coleta os programas na janela -------------------------------
print("  passo B: coletando programas na janela...")
programas = OrderedDict()   # (tvg, start, stop) -> xml
datas = set()
re_chan_attr = re.compile(r'(channel=")[^"]*(")')

for cc, caminho in fontes:
    n_prog = 0
    with gzip.open(caminho, "rt", encoding="utf-8", errors="replace") as f:
        segs = []
        dentro = False
        for linha in f:
            s = linha.strip()
            if not dentro:
                if s.startswith("<programme "):
                    dentro = True
                    segs = [s]
                continue
            segs.append(s)
            if not s.startswith("</programme>"):
                continue
            dentro = False
            at = dict(re_atr.findall(segs[0]))
            tvg = mapeia.get(html.unescape(at.get("channel", "")).strip())
            st = at.get("start", "")
            if not tvg or not st or not (inicio <= st < fim):
                continue
            chave = (tvg, st, at.get("stop", ""))
            if chave in programas:
                continue
            segs[0] = re_chan_attr.sub(lambda m: m.group(1) + esc(tvg) + m.group(2), segs[0], count=1)
            programas[chave] = "\n".join(segs)
            datas.add(st[:8])
            n_prog += 1
    print(f"  {PAIS_NOME.get(cc, cc):<12} {n_prog:>6} programas aceitos (total {len(programas):,})")

# ---------------------------------------------------------------- 5. SAIDA
barra("5. GRAVANDO EPGFULL.xml.gz")

saida = ["<?xml version='1.0' encoding='utf-8'?>", "<tv>"]
for tvg, c in canais.items():
    disp = c["display"] or c["nome"]
    icone = c["icone"] or c["logo"]
    saida.append(f'  <channel id="{esc(tvg)}">')
    saida.append(f'    <display-name lang="pt">{esc(disp)}</display-name>')
    saida.append(f'    <icon src="{esc(icone)}" />')
    saida.append("  </channel>")
for (tvg, st, sp), bloco in sorted(programas.items(), key=lambda kv: (kv[0][0], kv[0][1])):
    saida.append("  " + bloco.replace("\n", "\n  "))
saida.append("</tv>")
xml = "\n".join(saida) + "\n"

tmp = tempfile.NamedTemporaryFile(
    mode="wb", suffix=".xml.gz", delete=False, dir=os.path.dirname(os.path.abspath(OUTPUT))
)
try:
    with gzip.GzipFile(fileobj=tmp, mode="wb", compresslevel=9, mtime=0) as gz:
        gz.write(xml.encode("utf-8"))
    tmp.close()
    os.chmod(tmp.name, 0o644)      # tempfile cria com 600; o guia precisa ser legivel
    os.replace(tmp.name, OUTPUT)
except Exception:
    tmp.close()
    if os.path.exists(tmp.name):
        os.unlink(tmp.name)
    raise

# ---------------------------------------------------------------- 6. RELATORIO
barra("6. RELATORIO")
sem_epg = sorted(set(canais) - set(usados))
contagem = {}
for (tvg, st, _), _b in programas.items():
    contagem[tvg] = contagem.get(tvg, 0) + 1

print(f"  canais no .m3u ............. {len(canais)}")
print(f"  com <programme> ............ {len(contagem)}")
print(f"  sem <programme> ............ {len(sem_epg)}")
print(f"  casados por tvg-id ......... {len(por_id)}")
print(f"  casados por nome ........... {len(por_nome)}")
print(f"  total de programas ......... {len(programas):,}")
print(f"  cobertura de datas ......... {min(datas)} -> {max(datas)}" if datas else "  sem datas")
print(f"  HOJE  ({hoje}) ... {sum(1 for k in programas if k[1][:8] == hoje):,} programas")
print(f"  AMANHA ({amanha}) .. {sum(1 for k in programas if k[1][:8] == amanha):,} programas")
print()
print(f"  {OUTPUT}: {os.path.getsize(OUTPUT):,} bytes gzip "
      f"({len(xml.encode('utf-8')):,} bytes xml)")

if sem_epg:
    print()
    print("  canais do .m3u sem programa na fonte:")
    for t in sem_epg:
        print(f"    - {canais[t]['nome']} ({t})")
