"""Refina o exterior: fuso real de cada cidade em vez do maior deslocamento possivel.

Uso: python -I exterior_fuso_real.py <zz-p003221-cs.json> <fusos_exterior.csv> <secoes.csv.gz> <coleta.jsonl>
Requer tzdata atualizado (pip install tzdata; usado 2026e).

A urna no exterior grava hora local. Conversao: Brasilia = local - UTC(local) + UTC(-3),
com o deslocamento da cidade em 25/10/2026 (a Europa ja saiu do horario de verao
a 01h UTC desse dia, antes da abertura). Checagens por urna: abertura local perto
das 8h e ultimo evento convertido <= recebimento no TSE.
"""
import csv
import json
import sys
from datetime import datetime
from zoneinfo import ZoneInfo

import pandas as pd

D = 4430191
CORTES = {"1700": 1020, "1703": 1023, "1749": 1069, "1821": 1101, "1844": 1124, "1900": 1140}
BRT = -180


def hm(s):
    return int(s[:2]) * 60 + int(s[3:5])


def main():
    csz, fusos, secoes, *jsonls = sys.argv[1:]
    tz = {r["cidade"]: r["tz"] for r in csv.DictReader(open(fusos))}
    nome = {m["cd"]: m["nm"] for ab in json.load(open(csz))["abr"] for m in ab["mu"]}
    falta = sorted(set(nome.values()) - set(tz))
    assert not falta, f"cidades sem fuso: {falta}"

    S = pd.read_csv(secoes, dtype={"mun": str, "zona": str, "secao": str})
    zz = S[S.uf == "zz"].set_index(["mun", "zona", "secao"])
    soma = {c: 0 for c in CORTES}
    checagem = {"urnas": 0, "abertura_fora_7h30_8h30": 0, "fim_depois_do_recebimento": 0}
    por_cidade = {}
    vistos = set()
    regs = {}
    for p in jsonls:
        for l in open(p):
            r = json.loads(l)
            if r["uf"] == "zz":
                regs[(r["mun"], r["zona"], r["secao"])] = r
    for k, r in regs.items():
        row = zz.loc[k]
        if not row.observada:
            continue  # lacunas: ficam com o eleitorado inteiro (ja em secoes.csv)
        hs = [h for h in r["hashes"] if h.get("st") == "Totalizado" and "bu" in h] or \
             [h for h in r["hashes"] if h.get("st") == "Recebido" and "bu" in h]
        h = hs[0]
        z = ZoneInfo(tz[nome[k[0]]])
        off = BRT - datetime(2026, 10, 25, 12, tzinfo=z).utcoffset().total_seconds() / 60
        hist, K = h["log"]["votos_hist"], h["bu"]["comparecimento"]
        checagem["urnas"] += 1
        ab = h["bu"]["abertura"]
        if not (450 <= int(ab[9:11]) * 60 + int(ab[11:13]) <= 510):
            checagem["abertura_fora_7h30_8h30"] += 1
        receb = (datetime.strptime(h["dr"] + " " + h["hr"], "%d/%m/%Y %H:%M:%S") - datetime(2026, 10, 25)).total_seconds() / 60
        if row.fim_local + off > receb + 5:
            checagem["fim_depois_do_recebimento"] += 1
        cid = nome[k[0]]
        for c, t in CORTES.items():
            antes = sum(n for m, n in hist.items() if hm(m) + off < t)
            depois = sum(hist.values()) - antes
            A = max(depois, K - min(antes, K))
            soma[c] += A
            if c == "1700":
                por_cidade[cid] = por_cidade.get(cid, 0) + A
        vistos.add(k)
    lac = zz[~zz.observada]
    brasil = S[S.uf != "zz"]
    print("checagens:", checagem)
    print(f"lacunas no exterior (eleitorado inteiro): {len(lac)} urnas, {int(lac.E_teto.sum())} eleitores")
    print(f"\n{'corte':>6} {'ext. fuso max':>14} {'ext. fuso real':>15} {'Brasil':>9} {'A nacional':>11}")
    for c in CORTES:
        ext_real = soma[c] + int(lac[f"A_{c}"].sum())
        nac = int(brasil[f"A_{c}"].sum()) + ext_real
        print(f"{c:>6} {int(zz[f'A_{c}'].sum()):>14,} {ext_real:>15,} {int(brasil[f'A_{c}'].sum()):>9,} "
              f"{nac:>11,}  ({nac / D * 100:.1f}% de D)".replace(",", "."))
    print("\nCidades com votos apos 17h de Brasilia (fuso real):")
    for cid, v in sorted(por_cidade.items(), key=lambda x: -x[1]):
        if v:
            print(f"  {cid:<22} {tz[cid]:<28} {v:>6}")


if __name__ == "__main__":
    main()
