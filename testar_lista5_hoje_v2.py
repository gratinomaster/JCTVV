#!/usr/bin/env python3
"""Testa todos os canais do lista5.m3u e remove os que nao funcionam."""

import json
import shutil
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from urllib.parse import urljoin, urlparse, urlunparse

import requests

ARQUIVO = "lista5.m3u"
STAMP = datetime.now().strftime("%Y%m%d_%H%M%S")
BACKUP = f"lista5.m3u.bak.pre_teste_{STAMP}"
RELATORIO = f"relatorio_lista5_teste_{STAMP}.txt"
RESULTADOS = f"l5_teste_results_{STAMP}.json"

UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)
HEADERS = {
    "User-Agent": UA,
    "Accept": "*/*",
    "Accept-Language": "en-US,en;q=0.9",
    "Connection": "close",
}

TIMEOUT = 15
SEGUIR_QUERY = True


def parse_m3u(caminho):
    with open(caminho, encoding="utf-8", errors="replace") as fh:
        linhas = fh.read().splitlines()

    cabecalho, blocos, extras, extinf = [], [], [], None
    i = 0
    while i < len(linhas):
        linha = linhas[i].strip()
        if linha.startswith("#EXTM3U"):
            cabecalho.append(linha)
        elif linha.startswith("#EXTINF"):
            extinf, extras = linha, []
            i += 1
            while i < len(linhas) and linhas[i].strip().startswith("#"):
                extras.append(linhas[i].strip())
                i += 1
            if i < len(linhas):
                url = linhas[i].strip()
                if url and not url.startswith("#"):
                    blocos.append({"extinf": extinf, "extras": extras, "url": url})
                    extinf = None
        i += 1
    return cabecalho, blocos


def carregar(url, token=None, profundidade=0, vistos=None):
    """Baixa um manifest e devolve (texto, url_final). Herda token de query."""
    if vistos is None:
        vistos = set()
    if url in vistos or profundidade > 3:
        return None, None
    vistos.add(url)

    if SEGUIR_QUERY and token and urlparse(url).query != token:
        novo = urlunparse(urlparse(url)._replace(query=token))
        if novo != url:
            return carregar(novo, token, profundidade + 1, vistos)

    try:
        resp = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
    except Exception:  # noqa: BLE001
        return None, None
    if resp.status_code != 200:
        return None, None
    if SEGUIR_QUERY and token and urlparse(resp.url).query != token:
        resp.close()
        return None, None
    try:
        texto = resp.text
        final = resp.url
    except Exception:  # noqa: BLE001
        return None, None
    resp.close()
    return texto, final


def linhas_uri(texto):
    return [
        l.strip()
        for l in texto.splitlines()
        if l.strip() and not l.strip().startswith("#")
    ]


MANIFESTOS = (".m3u8", ".m3u", ".mpd", ".ism", ".isml")


def eh_media(uri):
    caminho = urlparse(uri).path.lower()
    return not any(caminho.endswith(m) for m in MANIFESTOS)


def achar_segmentos(texto, base, token, prof=0, vistos=None):
    """Resolve manifest -> variante -> segmentos (ate 3 niveis)."""
    if vistos is None:
        vistos = set()
    for uri in linhas_uri(texto):
        if eh_media(uri):
            return [urljoin(base, uri)]
    # nenhum segmento direto: e' master/variante, desce
    for uri in linhas_uri(texto):
        if prof > 2:
            break
        abs_uri = urljoin(base, uri)
        if abs_uri in vistos:
            continue
        sub, sub_url = carregar(abs_uri, token, prof + 1, vistos)
        if not sub or "#EXTM3U" not in sub:
            continue
        segs = achar_segmentos(sub, sub_url or abs_uri, token, prof + 1, vistos)
        if segs:
            return segs
    return []


def byte_ts(buf):
    return buf[0:1] == b"\x47" and buf[188:189] == b"\x47"


def media_valida(buf):
    """True se o buffer parece video/audio real: MPEG-TS ou CMAF/MP4."""
    if len(buf) < 1000:
        return False
    if byte_ts(buf):
        return True
    amostra = buf[:8192]
    for caixa in (b"ftyp", b"moof", b"mdat", b"sidx"):
        if caixa in amostra:
            return True
    return False


def testar(url):
    token = urlparse(url).query or None
    texto, base = carregar(url, token)
    if not texto:
        return False, "manifest_sem_resposta"
    if "#EXTM3U" not in texto:
        return False, "nao_e_manifest"
    low = texto.lower()
    if "not found" in low[:400] or "error" in low[:200]:
        return False, "manifest_erro"

    segs = achar_segmentos(texto, base or url, token)
    if not segs:
        return False, "manifest_sem_segmentos"

    for seg in segs[:2]:
        alvo = seg
        if SEGUIR_QUERY and token:
            p = urlparse(alvo)
            if p.query != token:
                alvo = urlunparse(p._replace(query=token))
        try:
            r = requests.get(alvo, headers=HEADERS, timeout=TIMEOUT, stream=True)
        except Exception as exc:  # noqa: BLE001
            return False, f"segmento_erro:{type(exc).__name__}"
        if r.status_code != 200:
            r.close()
            return False, f"segmento_http_{r.status_code}"
        dados = b""
        try:
            for pedaco in r.iter_content(65536):
                dados += pedaco
                if len(dados) >= 300_000:
                    break
        except Exception as exc:  # noqa: BLE001
            r.close()
            return False, f"segmento_leitura:{type(exc).__name__}"
        r.close()
        if "#EXTM3U" in dados[:300].decode("utf-8", errors="ignore"):
            return False, "loop_manifest"
        if not media_valida(dados):
            return False, "segmento_invalido"
    return True, f"OK manifest+segmento ({len(segs)} disp.)"


def main():
    cabecalho, blocos = parse_m3u(ARQUIVO)
    print(f"Total de canais: {len(blocos)}")
    shutil.copy2(ARQUIVO, BACKUP)
    print(f"Backup: {BACKUP}")

    resultados = []
    with ThreadPoolExecutor(max_workers=6) as pool:
        futuros = {pool.submit(testar, b["url"]): i for i, b in enumerate(blocos)}
        for fut in as_completed(futuros):
            i = futuros[fut]
            try:
                ok, motivo = fut.result()
            except Exception as exc:  # noqa: BLE001
                ok, motivo = False, f"excecao:{type(exc).__name__}"
            nome = blocos[i]["extinf"].split(",", 1)[-1][:55]
            resultados.append(
                {"idx": i, "url": blocos[i]["url"], "ok": ok, "motivo": motivo, "nome": nome}
            )
            print(f"[{'OK  ' if ok else 'FAIL'}] {i:3d} {motivo:32s} {nome}")

    resultados.sort(key=lambda r: r["idx"])
    with open(RESULTADOS, "w", encoding="utf-8") as fh:
        json.dump(resultados, fh, ensure_ascii=False, indent=2)

    ok_idx = {r["idx"] for r in resultados if r["ok"]}
    falhos = [r for r in resultados if not r["ok"]]
    mantidos = [b for i, b in enumerate(blocos) if i in ok_idx]

    with open(ARQUIVO, "w", encoding="utf-8") as fh:
        for linha in cabecalho:
            fh.write(linha + "\n")
        for b in mantidos:
            fh.write(b["extinf"] + "\n")
            for extra in b.get("extras", []):
                fh.write(extra + "\n")
            fh.write(b["url"] + "\n")

    with open(RELATORIO, "w", encoding="utf-8") as fh:
        fh.write(f"Teste: {datetime.now()}\nArquivo: {ARQUIVO}\nBackup: {BACKUP}\n")
        fh.write(
            f"Total: {len(blocos)} | Funcionando: {len(mantidos)} | Removidos: {len(falhos)}\n\n"
        )
        fh.write("=== REMOVIDOS ===\n")
        for r in falhos:
            fh.write(f"[{r['idx']}] {r['motivo']}\n  {r['url']}\n\n")
        fh.write("=== MANTIDOS ===\n")
        for r in resultados:
            if r["ok"]:
                fh.write(f"[{r['idx']}] {r['motivo']}\n  {r['url']}\n\n")

    print(f"\nTotal: {len(blocos)} | Funcionando: {len(mantidos)} | Removidos: {len(falhos)}")
    print(f"Relatorio: {RELATORIO} | JSON: {RESULTADOS}")
    return 0


if __name__ == "__main__":
    sys.exit(main())