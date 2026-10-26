"""Coleta e resume, secao por secao, os arquivos de urna do 2o turno de 2026.

Fonte: site Resultados do TSE (arquivos individuais por secao).
  config : /oficial/ele2026/arquivo-urna/3221/config/<uf>/<uf>-p003221-cs.json
  aux    : /oficial/ele2026/arquivo-urna/3221/dados/<uf>/<mun>/<zona>/<secao>/p003221-<uf>-m<mun>-z<zona>-s<secao>-aux.json
  arqs   : .../<secao>/<hash>/<nome do arquivo>

Para cada secao grava uma linha JSON com: hashes do aux, SHA-256 de cada
arquivo baixado, eleitorado apto e comparecimento do BU (eleicao 6258,
Presidente), abertura/encerramento do BU e, do log, o horario (relogio da
urna) de cada evento "O voto do eleitor foi computado" de 25/10/2026,
agregado por minuto. Os arquivos de log nao sao guardados (so o hash).

Uso:  python3 -I coleta.py <dir_cs> <saida.jsonl> [uf ...] [--workers N]
Retoma de onde parou: secoes ja presentes em <saida.jsonl> sao puladas.
"""
import hashlib
import http.client
import json
import os
import subprocess
import sys
import tempfile
import threading
import time
from concurrent.futures import ThreadPoolExecutor

HOST = "resultados.tse.jus.br"
BASE = "/oficial/ele2026/arquivo-urna/3221"
PLEITO = "3221"
ELEICAO_PRES = 6258
DIA = "25/10/2026"
UA = {"User-Agent": "Mozilla/5.0 (auditoria-prorrogacao-2t2026)"}
SEVENZIP = os.environ.get("SEVENZIP", "7zz")

_tls = threading.local()

# O servidor devolve HTTP 429 acima de um limite por IP. Ritmo global fixo
# (--rps) e, a cada 429, pausa global crescente para todas as threads.
RPS = 30.0
_rl = threading.Lock()
_prox = [0.0]
_pausa = [0.0, 0]  # ate quando, quantos 429 seguidos
N429 = [0]


def _vez():
    with _rl:
        agora = time.time()
        t = max(agora, _prox[0], _pausa[0])
        _prox[0] = t + 1.0 / RPS
    if t > agora:
        time.sleep(t - agora)


def get(path, tries=40):
    for i in range(tries):
        _vez()
        try:
            c = getattr(_tls, "c", None)
            if c is None:
                c = _tls.c = http.client.HTTPSConnection(HOST, timeout=60)
            c.request("GET", path, headers=UA)
            r = c.getresponse()
            body = r.read()
            if r.status == 200:
                with _rl:
                    _pausa[1] = 0
                return body
            if r.status == 404:
                return None
            if r.status == 429:
                with _rl:
                    N429[0] += 1
                    _pausa[1] += 1
                    _pausa[0] = max(_pausa[0], time.time() + min(300, 15 * _pausa[1]))
                continue
            raise IOError(f"HTTP {r.status}")
        except Exception:
            try:
                _tls.c.close()
            except Exception:
                pass
            _tls.c = None
            time.sleep(min(30, 2 ** min(i, 5)))
    raise IOError(f"falhou {path}")


# ---------- BER minimo para o bu.dat ----------
def ber(buf, i=0, end=None):
    end = len(buf) if end is None else end
    out = []
    while i < end:
        tag = buf[i]; i += 1
        if tag & 0x1F == 0x1F:
            while buf[i] & 0x80:
                i += 1
            i += 1
        ln = buf[i]; i += 1
        if ln & 0x80:
            n = ln & 0x7F
            ln = int.from_bytes(buf[i:i + n], "big"); i += n
        val = buf[i:i + ln]
        node = {"tag": tag, "val": val}
        if tag & 0x20:
            node["kids"] = ber(buf, i, i + ln)
        out.append(node)
        i += ln
    return out


def as_int(n):
    return int.from_bytes(n["val"], "big", signed=True)


def walk(nodes):
    for n in nodes:
        yield n
        if "kids" in n:
            yield from walk(n["kids"])


def parse_bu(raw):
    env = ber(raw)[0]["kids"]
    inner = None
    for n in env:
        if n["tag"] == 0x04:  # OCTET STRING com a EntidadeBoletimUrna
            inner = ber(n["val"])[0]["kids"]
    if inner is None:
        raise ValueError("BU sem conteudo")
    res = {}
    for n in inner:
        # dadosSecao: [0] { dataHoraAbertura, dataHoraEncerramento }
        if n["tag"] == 0xA0 and all(k["tag"] == 0x1B for k in n.get("kids", [])) and len(n["kids"]) >= 2:
            res["abertura"] = n["kids"][0]["val"].decode()
            res["encerramento"] = n["kids"][1]["val"].decode()
        if n["tag"] == 0x1B and len(n["val"]) == 15 and "emissao" not in res:
            res["emissao"] = n["val"].decode()
    for n in walk(inner):
        k = n.get("kids")
        if n["tag"] == 0x30 and k and k[0]["tag"] == 0x02 and as_int(k[0]) == ELEICAO_PRES:
            res["aptos"] = as_int(k[1])
            # primeiro ResultadoVotacao: ENUMERATED tipo, INTEGER comparecimento
            for m in walk(k[2:]):
                mk = m.get("kids")
                if m["tag"] == 0x30 and mk and len(mk) >= 2 and mk[0]["tag"] == 0x0A and mk[1]["tag"] == 0x02:
                    res["comparecimento"] = as_int(mk[1])
                    break
            break
    return res


# ---------- log.jez ----------
EVT_VOTO = "O voto do eleitor foi computado"


def parse_log(raw):
    with tempfile.TemporaryDirectory() as d:
        p = os.path.join(d, "log.jez")
        with open(p, "wb") as f:
            f.write(raw)
        lst = subprocess.run([SEVENZIP, "l", "-slt", p], capture_output=True, text=True).stdout
        names = [l[7:] for l in lst.splitlines() if l.startswith("Path = ") and l[7:] != p]
        txt = subprocess.run([SEVENZIP, "e", "-so", p], capture_output=True).stdout
    txt = txt.decode("latin-1")
    seen = set()
    hist = {}
    outras_datas = 0
    dup = 0
    pronta, encerrar, conf, ini_enc = [], [], [], []
    for line in txt.splitlines():
        f = line.split("\t")
        if len(f) < 5:
            continue
        dt = f[0]
        msg = f[4]
        if msg == EVT_VOTO:
            key = (dt, f[2], f[5] if len(f) > 5 else "")
            if key in seen:
                dup += 1
                continue
            seen.add(key)
            if dt[:10] != DIA:
                outras_datas += 1
                continue
            m = dt[11:16]
            hist[m] = hist.get(m, 0) + 1
        elif dt[:10] == DIA:
            if msg == "Urna pronta para receber votos":
                pronta.append(dt[11:])
            elif msg.startswith("Operador selecionou: Encerrar"):
                encerrar.append(dt[11:])
            elif msg == "Procedimento de encerramento confirmado":
                conf.append(dt[11:])
            elif msg.startswith("Inicio do Encerramento"):
                ini_enc.append(dt[11:])
    return {"arquivos": names, "votos_hist": hist, "votos_25": sum(hist.values()),
            "votos_outras_datas": outras_datas, "dup": dup, "pronta": pronta,
            "sel_encerrar": encerrar, "enc_confirmado": conf, "ini_encerramento": ini_enc,
            "1o_evento": next((l[:19] for l in txt.splitlines() if l.startswith(DIA)), None)}


def sha(b):
    return hashlib.sha256(b).hexdigest()


def secao(uf, mun, zon, sec):
    d = f"{BASE}/dados/{uf}/{mun}/{zon}/{sec}"
    rec = {"uf": uf, "mun": mun, "zona": zon, "secao": sec}
    aux = get(f"{d}/p00{PLEITO}-{uf}-m{mun}-z{zon}-s{sec}-aux.json")
    if aux is None:
        rec["erro"] = "aux 404"
        return rec
    a = json.loads(aux)
    rec["aux_st"] = a.get("st")
    rec["aux_sha256"] = sha(aux)
    rec["hashes"] = []
    for h in a.get("hashes", []):
        hh = {"hash": h["hash"], "st": h.get("st"), "dr": h.get("dr"), "hr": h.get("hr"), "arq": {}}
        usar = h.get("st") in ("Totalizado", "Recebido")
        for arq in h.get("arq", []):
            hh["arq"][arq["nm"]] = arq["tp"]
            if not usar or arq["tp"] not in ("bu", "log", "busa", "logsa"):
                continue
            raw = get(f"{d}/{h['hash']}/{arq['nm']}")
            if raw is None:
                hh.setdefault("faltando", []).append(arq["nm"])
                continue
            hh.setdefault("sha256", {})[arq["nm"]] = sha(raw)
            try:
                if arq["tp"] == "bu":
                    hh["bu"] = parse_bu(raw)
                elif arq["tp"] == "log":
                    hh["log"] = parse_log(raw)
            except Exception as e:  # registra e segue; tratado como nao observado
                hh.setdefault("erros", []).append(f"{arq['nm']}: {e!r}")
        rec["hashes"].append(hh)
    return rec


def completo(r):
    """Registro sem erro e com BU e log de todo hash usado (refaz se faltar)."""
    if "erro" in r:
        return False
    for h in r.get("hashes", []):
        if h.get("st") in ("Totalizado", "Recebido"):
            if h.get("erros") or h.get("faltando"):
                return False
            tps = set(h["arq"].values())
            if "bu" in tps and "bu" not in h:
                return False
            if "log" in tps and "log" not in h:
                return False
    return True


def main():
    args = [a for a in sys.argv[1:]]
    global RPS
    workers = 48
    if "--workers" in args:
        i = args.index("--workers"); workers = int(args[i + 1]); del args[i:i + 2]
    if "--rps" in args:
        i = args.index("--rps"); RPS = float(args[i + 1]); del args[i:i + 2]
    csdir, out = args[0], args[1]
    ufs = args[2:] or sorted(f[:2] for f in os.listdir(csdir) if f.endswith("-cs.json"))
    feitos = set()
    if os.path.exists(out):
        for l in open(out):
            try:
                r = json.loads(l)
                k = (r["uf"], r["mun"], r["zona"], r["secao"])
                if completo(r):
                    feitos.add(k)
                else:
                    feitos.discard(k)
            except Exception:
                pass
    tarefas = []
    for uf in ufs:
        cs = json.load(open(os.path.join(csdir, f"{uf}-p00{PLEITO}-cs.json")))
        for ab in cs["abr"]:
            for m in ab["mu"]:
                for z in m["zon"]:
                    for s in z["sec"]:
                        if "nsp" in s:  # secao agregada: votos e eleitorado vem no BU da principal
                            continue
                        k = (uf, m["cd"], z["cd"], s["ns"])
                        if k not in feitos:
                            tarefas.append(k)
    print(f"{len(feitos)} ja feitas, {len(tarefas)} a fazer", flush=True)
    lock = threading.Lock()
    t0 = time.time(); n = 0
    with open(out, "a") as fo, ThreadPoolExecutor(workers) as ex:
        def job(k):
            try:
                return secao(*k)
            except Exception as e:
                return {"uf": k[0], "mun": k[1], "zona": k[2], "secao": k[3], "erro": repr(e)}
        for rec in ex.map(job, tarefas):
            with lock:
                fo.write(json.dumps(rec, ensure_ascii=False, separators=(",", ":")) + "\n")
                n += 1
                if n % 500 == 0:
                    fo.flush()
                    el = time.time() - t0
                    print(f"{n}/{len(tarefas)} {n/el:.1f} sec/s eta {(len(tarefas)-n)/(n/el)/3600:.2f} h 429s={N429[0]}", flush=True)


if __name__ == "__main__":
    main()
