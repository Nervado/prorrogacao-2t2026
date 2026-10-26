"""Tetos R(t) e A(t) para os votos possibilitados pela prorrogacao (2o turno 2026).

Entrada: o(s) .jsonl gerado(s) por coleta.py e o diretorio com os *-cs.json.
Saida  : tabelas em texto e um JSON com todos os numeros.

Uso: python3 -I analise.py <dir_cs> <aptos_1t.csv.gz> <saida.json> <coleta.jsonl> [mais.jsonl ...]
Cada maquina roda sobre as UFs que coletou (UFs inteiras); combinar.py soma.

Definicoes (por secao s = urna que gerou BU; agregadas vem no BU da principal):
  E_s        eleitorado apto do BU, eleicao 6258 (Presidente)
  K_s        comparecimento do BU (Presidente)
  antes_s(t) votos do log ("O voto do eleitor foi computado", deduplicados)
             com horario de Brasilia < t - delta, limitado a K_s
  A_s(t)     = max(votos do log em >= t - delta,  K_s - antes_s(t))
             (voto que o log nao mostra e tratado como posterior ao corte)
  aberta(t)  = encerramento (o mais tardio entre BU e ultimo evento de
               encerramento/voto do log) >= t - delta
  R_s(t)     = E_s - antes_s(t)  se aberta(t), senao 0
Secao sem BU ou sem log legivel: R_s = A_s = E_s (eleitorado do BU se houver,
senao o maior eleitorado do 1o turno disponivel; sem nada, entra como lacuna).

Fuso: horario da urna e local. No Brasil, a abertura e as 8h de Brasilia em
todo o pais (Res.-TSE 23.751/2026, art. 129); o deslocamento de cada municipio
e 8 - moda(hora arredondada da abertura no BU). No exterior a urna abre as 8h
locais e nao ha como deduzir o fuso pela abertura; usa-se o MAIOR deslocamento
compativel com os dados: horario de recebimento do arquivo pelo TSE (aux, em
Brasilia) menos o ultimo evento do log (local). Isso empurra os votos para o
mais tarde possivel e por isso so pode aumentar A(t) e R(t).
"""
import bisect
import collections
import csv
import itertools
import gzip
import json
import os
import sys
from datetime import datetime, timedelta

D_OFICIAL = 64256232 - 59826041
CORTES = ["17:00", "17:03", "17:49", "18:21", "18:44", "19:00"]
DELTAS_MIN = [0, 5, 15]
DIA = datetime(2026, 10, 25)


def hm(s):
    h, m = map(int, s.split(":")[:2])
    return h * 60 + m


def bu_ts(s):  # 20261025T150152 -> minutos desde 00:00 de 25/10 (local)
    d = datetime.strptime(s, "%Y%m%dT%H%M%S")
    return (d - DIA).total_seconds() / 60


def carregar(paths):
    ult = {}
    for p in paths:
        for l in open(p):
            r = json.loads(l)
            ult[(r["uf"], r["mun"], r["zona"], r["secao"])] = r
    return ult


def esperado(csdir):
    exp, agreg, nomes = {}, 0, {}
    for f in sorted(os.listdir(csdir)):
        if not f.endswith("-cs.json"):
            continue
        uf = f[:2]
        cs = json.load(open(os.path.join(csdir, f)))
        for ab in cs["abr"]:
            for m in ab["mu"]:
                nomes[(uf, m["cd"])] = m["nm"]
                for z in m["zon"]:
                    for s in z["sec"]:
                        if "nsp" in s:
                            agreg += 1
                        else:
                            exp[(uf, m["cd"], z["cd"], s["ns"])] = s
    return exp, agreg, nomes


def escolher(r):
    """Hash totalizado (ou recebido) com BU; devolve (bu, log, hr_recebimento)."""
    hs = [h for h in r.get("hashes", []) if h.get("st") == "Totalizado"] or \
         [h for h in r.get("hashes", []) if h.get("st") == "Recebido"]
    for h in hs:
        if "bu" in h:
            return h["bu"], h.get("log"), h, len(r.get("hashes", []))
    return None, None, (hs[0] if hs else None), len(r.get("hashes", []))


def receb_min(h):
    """Horario (Brasilia) em que o TSE recebeu o arquivo, em min desde 25/10 00:00."""
    if not h or not h.get("dr") or not h.get("hr"):
        return None
    d = datetime.strptime(h["dr"] + " " + h["hr"], "%d/%m/%Y %H:%M:%S")
    return (d - DIA).total_seconds() / 60


def main():
    csdir, apt1t, saida, *paths = sys.argv[1:]
    exp, n_agreg, nomes = esperado(csdir)
    ult = carregar(paths)
    ufs_coletadas = {k[0] for k in ult}
    exp = {k: v for k, v in exp.items() if k[0] in ufs_coletadas}
    e1t = {}
    with gzip.open(apt1t, "rt") as f:
        for row in csv.DictReader(f):
            e1t[(row["uf"], row["mun"], row["zona"], row["secao"])] = int(row["aptos_1t"])

    # 1a passada: deslocamento de fuso por municipio (Brasil)
    aber = collections.defaultdict(collections.Counter)
    for k, r in ult.items():
        if k not in exp or k[0] == "zz":
            continue
        bu, *_ = escolher(r)
        if bu and bu.get("abertura"):
            aber[(k[0], k[1])][round(bu_ts(bu["abertura"]) / 60)] += 1
    desloc = {}
    for mk, c in aber.items():
        desloc[mk] = 8 - c.most_common(1)[0][0]
    resumo_fuso = collections.Counter((mk[0], v) for mk, v in desloc.items())

    secs = []
    cobert = collections.defaultdict(collections.Counter)
    for k, s in exp.items():
        uf = k[0]
        cobert[uf]["urnas"] += 1
        r = ult.get(k)
        if r is None:
            cobert[uf]["nao_coletada"] += 1
            secs.append({"k": k, "obs": False, "E1t": e1t.get(k)})
            continue
        if "erro" in r:
            cobert[uf]["erro_" + r["erro"][:20]] += 1
            secs.append({"k": k, "obs": False, "motivo": r["erro"], "E1t": e1t.get(k)})
            continue
        bu, log, h, nh = escolher(r)
        if nh > 1:
            cobert[uf]["varios_hashes"] += 1
        if bu is None or "aptos" not in bu:
            cobert[uf]["sem_bu"] += 1
            secs.append({"k": k, "obs": False, "motivo": "sem BU", "st": r.get("aux_st"), "E1t": e1t.get(k)})
            cobert[uf]["sem_bu_st_" + str(r.get("aux_st"))] += 1
            continue
        cobert[uf]["com_bu"] += 1
        E, K = bu["aptos"], bu.get("comparecimento", 0)
        cobert[uf]["E"] += E
        cobert[uf]["K"] += K
        rec = {"k": k, "obs": True, "E": E, "K": K}
        if log is None:
            cobert[uf]["sem_log"] += 1
            rec["sem_log"] = True
            secs.append(rec)
            continue
        cobert[uf]["com_log"] += 1
        hist = log["votos_hist"]
        nlog = log["votos_25"]
        if nlog == K:
            cobert[uf]["log_igual_bu"] += 1
        elif nlog < K:
            cobert[uf]["log_menor_bu"] += 1
            cobert[uf]["votos_sem_horario"] += K - nlog
        else:
            cobert[uf]["log_maior_bu"] += 1
        # fuso
        ult_ev = max([hm(x) for x in hist] + [hm(x) for x in log["enc_confirmado"] + log["sel_encerrar"]] +
                     [bu_ts(bu["encerramento"]) if bu.get("encerramento") else 0])
        rm = receb_min(h)
        if uf == "zz":
            # ultimo registro do log (geracao do log.jez) <= recebimento
            rec["off_min"] = (rm - ult_ev) if rm is not None else None
        else:
            rec["off_min"] = 60 * desloc.get((uf, k[1]), 0)
            if rm is not None:
                folga = rm - (ult_ev + rec["off_min"])
                rec["folga_receb_min"] = folga
                if folga < -5:
                    cobert[uf]["relogio_incoerente"] += 1
        rec["hist"] = hist
        rec["fim_local"] = ult_ev
        secs.append(rec)

    E_tot = sum(c["E"] for c in cobert.values())
    K_tot = sum(c["K"] for c in cobert.values())

    def calc(t_min, delta):
        tc = t_min - delta
        por_uf = collections.defaultdict(lambda: collections.Counter())
        for rec in secs:
            uf = rec["k"][0]
            P = por_uf[uf]
            if not rec["obs"]:
                # nao observada: entra inteira nos dois tetos
                P["lacuna_secoes"] += 1
                if rec.get("E1t") is None:
                    P["lacuna_sem_eleitorado"] += 1
                else:
                    P["R"] += rec["E1t"]; P["A"] += rec["E1t"]; P["abertas"] += 1
                    P["lacuna_E"] += rec["E1t"]
                continue
            E, K = rec["E"], rec["K"]
            if rec.get("sem_log") or rec.get("off_min") is None:
                P["R"] += E; P["A"] += K; P["abertas"] += 1; P["teto_sem_log"] += 1
                continue
            off = rec["off_min"]
            if "_ts" not in rec:  # minutos (Brasilia) ordenados e soma acumulada
                ms = sorted((hm(m) + off, n) for m, n in rec["hist"].items())
                rec["_ts"] = [m for m, _ in ms]
                rec["_cum"] = list(itertools.accumulate(n for _, n in ms))
            i = bisect.bisect_left(rec["_ts"], tc)
            antes = rec["_cum"][i - 1] if i else 0
            depois = (rec["_cum"][-1] if rec["_cum"] else 0) - antes
            antes = min(antes, K)
            A = max(depois, K - antes)
            aberta = rec["fim_local"] + off >= tc
            P["A"] += A
            if aberta:
                P["abertas"] += 1
                P["R"] += E - antes
            if A > 0:
                P["secoes_com_voto_pos"] += 1
        return por_uf

    resultados = {}
    for c in CORTES:
        for d in DELTAS_MIN:
            pu = calc(hm(c), d)
            tot = collections.Counter()
            for v in pu.values():
                tot.update(v)
            resultados[f"{c}|{d}"] = {"total": dict(tot), "por_uf": {u: dict(v) for u, v in pu.items()}}

    # curva de 5 em 5 minutos, delta 0
    curva = {}
    for m in range(hm("16:30"), hm("21:00") + 1, 5):
        pu = calc(m, 0)
        curva[f"{m//60:02d}:{m%60:02d}"] = {u: {k: v[k] for k in ("R", "A", "abertas")} for u, v in pu.items()}

    # ultimo voto e ultima urna encerrada (Brasilia), excluindo exterior
    ult_voto = collections.defaultdict(collections.Counter)
    fim_urna = collections.defaultdict(collections.Counter)
    for rec in secs:
        if rec.get("hist") and rec.get("off_min") is not None:
            mx = max(hm(m) for m in rec["hist"]) + rec["off_min"]
            ult_voto[rec["k"][0]][f"{int(mx // 15) * 15 // 60:02d}:{int(mx // 15) * 15 % 60:02d}"] += 1
            fe = rec["fim_local"] + rec["off_min"]
            fim_urna[rec["k"][0]][f"{int(fe // 15) * 15 // 60:02d}:{int(fe // 15) * 15 % 60:02d}"] += 1

    out = {
        "D_oficial": D_OFICIAL, "E_total_bu": E_tot, "K_total_bu": K_tot,
        "urnas_esperadas": len(exp), "secoes_agregadas": n_agreg,
        "cobertura": {u: dict(c) for u, c in sorted(cobert.items())},
        "fuso_por_uf": {f"{u}:{v:+d}h": n for (u, v), n in sorted(resumo_fuso.items())},
        "resultados": resultados, "curva": curva,
        "ultimo_voto_por_15min": {u: dict(sorted(c.items())) for u, c in ult_voto.items()},
        "fim_urna_por_15min": {u: dict(sorted(c.items())) for u, c in fim_urna.items()},
    }
    json.dump(out, open(saida, "w"), ensure_ascii=False, indent=1)

    print(f"D oficial = {D_OFICIAL:,}".replace(",", "."))
    print(f"urnas esperadas {len(exp)}  agregadas {n_agreg}  E(BU) {E_tot:,}  K(BU) {K_tot:,}")
    print("fusos:", out["fuso_por_uf"])
    print(f"\n{'corte':>6} {'delta':>5} {'abertas':>8} {'R(t)':>12} {'A(t)':>11} {'A<D':>4} {'R<D':>4} lacunas")
    for key, v in resultados.items():
        c, d = key.split("|")
        T = v["total"]
        print(f"{c:>6} {d:>5} {T.get('abertas',0):>8} {T.get('R',0):>12,} {T.get('A',0):>11,} "
              f"{'sim' if T.get('A',0) < D_OFICIAL else 'nao':>4} {'sim' if T.get('R',0) < D_OFICIAL else 'nao':>4} "
              f"{T.get('lacuna_secoes',0)}")


if __name__ == "__main__":
    main()
