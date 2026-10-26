"""Dataframe por urna e tetos R(t), A(t) em pandas (conferencia independente de analise.py).

Uso: python -I tabela.py <dir_cs> <aptos_1t.csv.gz> <saida.csv.gz> <coleta.jsonl> [...]
Gera uma linha por urna; R(t) e A(t) sao somas de colunas dessa tabela.
"""
import json
import os
import sys

import numpy as np
import pandas as pd

CORTES = {"1700": 17 * 60, "1703": 17 * 60 + 3, "1749": 17 * 60 + 49, "1821": 18 * 60 + 21,
          "1844": 18 * 60 + 44, "1900": 19 * 60}
DIA = pd.Timestamp("2026-10-25")


def minutos(s, fmt):
    return (pd.to_datetime(s, format=fmt, errors="coerce") - DIA).dt.total_seconds() / 60


def main():
    csdir, apt1t, saida, *paths = sys.argv[1:]
    exp = []
    for f in sorted(os.listdir(csdir)):
        if f.endswith("-cs.json"):
            for ab in json.load(open(os.path.join(csdir, f)))["abr"]:
                for m in ab["mu"]:
                    for z in m["zon"]:
                        exp += [(f[:2], m["cd"], z["cd"], s["ns"]) for s in z["sec"] if "nsp" not in s]
    chave = ["uf", "mun", "zona", "secao"]
    df = pd.DataFrame(exp, columns=chave)

    linhas = {}
    for p in paths:
        for l in open(p):
            r = json.loads(l)
            linhas[(r["uf"], r["mun"], r["zona"], r["secao"])] = r
    df = df[df.uf.isin({k[0] for k in linhas})].reset_index(drop=True)

    reg = []
    for k, r in linhas.items():
        hs = [h for h in r.get("hashes", []) if h.get("st") == "Totalizado" and "bu" in h] or \
             [h for h in r.get("hashes", []) if h.get("st") == "Recebido" and "bu" in h]
        h = hs[0] if hs else None
        bu = h["bu"] if h else {}
        lg = h.get("log") if h else None
        hist = lg["votos_hist"] if lg else {}
        ev = (lg["enc_confirmado"] + lg["sel_encerrar"]) if lg else []
        reg.append({**dict(zip(chave, k)),
                    "E": bu.get("aptos"), "K": bu.get("comparecimento"),
                    "abertura": bu.get("abertura"), "encerramento": bu.get("encerramento"),
                    "n_log": lg["votos_25"] if lg else None,
                    "receb": f"{h['dr']} {h['hr']}" if h else None,
                    "ult_ev_local": max([int(m[:2]) * 60 + int(m[3:]) for m in hist] +
                                        [int(x[:2]) * 60 + int(x[3:5]) for x in ev] + [0]) if lg else None,
                    "st": h.get("st") if h else r.get("aux_st"), "hist": hist})
    R = pd.DataFrame(reg)
    df = df.merge(R, on=chave, how="left")

    ap = pd.read_csv(apt1t, dtype=str)
    ap["aptos_1t"] = ap.aptos_1t.astype(int)
    df = df.merge(ap, on=chave, how="left")

    df["abertura_min"] = minutos(df.abertura, "%Y%m%dT%H%M%S")
    df["enc_min"] = minutos(df.encerramento, "%Y%m%dT%H%M%S")
    df["receb_min"] = minutos(df.receb, "%d/%m/%Y %H:%M:%S")
    df["fim_local"] = np.fmax(df.ult_ev_local, df.enc_min)

    # fuso: Brasil pela moda da abertura no municipio (abre as 8h de Brasilia);
    # exterior pelo maior deslocamento compativel com o recebimento no TSE
    moda = (df[df.uf != "zz"].assign(h=(df.abertura_min / 60).round())
            .groupby(["uf", "mun"]).h.agg(lambda s: s.mode().iloc[0] if len(s.dropna()) else np.nan))
    df = df.merge((8 - moda).rename("desl_h").reset_index(), on=["uf", "mun"], how="left")
    df["off_min"] = np.where(df.uf == "zz", df.receb_min - df.fim_local, df.desl_h * 60)

    df["observada"] = df.E.notna() & df.n_log.notna() & df.off_min.notna()
    df["E_teto"] = df.E.fillna(df.aptos_1t)

    for nome, t in CORTES.items():
        antes = np.array([sum(n for m, n in h.items() if int(m[:2]) * 60 + int(m[3:]) + o < t)
                          if isinstance(h, dict) and o == o else 0
                          for h, o in zip(df["hist"], df.off_min)])
        depois = df.n_log.fillna(0).to_numpy() - antes
        antes = np.minimum(antes, df.K.fillna(0).to_numpy())
        A = np.maximum(depois, df.K.fillna(0).to_numpy() - antes)
        aberta = (df.fim_local + df.off_min) >= t
        Rv = np.where(aberta, df.E.fillna(0) - antes, 0)
        # nao observada: eleitorado inteiro nos dois tetos
        df[f"A_{nome}"] = np.where(df.observada, A, df.E_teto)
        df[f"R_{nome}"] = np.where(df.observada, Rv, df.E_teto)
        df[f"aberta_{nome}"] = np.where(df.observada, aberta, True)

    df.drop(columns=["hist"]).to_csv(saida, index=False, compression="gzip")

    D = 64256232 - 59826041
    print(f"urnas {len(df)}  observadas {int(df.observada.sum())}  "
          f"E={int(df.E.sum()):,}  K={int(df.K.sum()):,}  log==BU: {int((df.n_log == df.K).sum())}")
    for nome in CORTES:
        a, r = int(df[f"A_{nome}"].sum()), int(df[f"R_{nome}"].sum())
        print(f"t={nome}  abertas={int(df[f'aberta_{nome}'].sum()):>7}  R={r:>12,} ({'<' if r < D else '>='}D)  "
              f"A={a:>10,} ({'<' if a < D else '>='}D)")


if __name__ == "__main__":
    main()
