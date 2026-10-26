"""Soma as saidas parciais de analise.py (UFs disjuntas) e imprime as tabelas.

Uso: python3 -I combinar.py <saida_final.json> <parcial1.json> [parcial2.json ...]
"""
import collections
import json
import sys

D = 64256232 - 59826041
OFICIAL = {"E": 158745502, "K": 128236074, "urnas": 499248}


def br(n):
    return f"{n:,}".replace(",", ".")


def main():
    saida, *parts = sys.argv[1:]
    P = [json.load(open(p)) for p in parts]
    cob = {}
    for p in P:
        for u, c in p["cobertura"].items():
            assert u not in cob, f"UF {u} em duas parciais"
            cob[u] = c
    res = collections.defaultdict(lambda: collections.defaultdict(collections.Counter))
    curva = collections.defaultdict(lambda: collections.defaultdict(collections.Counter))
    fim = collections.defaultdict(collections.Counter)
    ultv = collections.defaultdict(collections.Counter)
    fusos = {}
    for p in P:
        fusos.update(p["fuso_por_uf"])
        for key, v in p["resultados"].items():
            for u, x in v["por_uf"].items():
                res[key][u].update(x)
        for t, v in p["curva"].items():
            for u, x in v.items():
                curva[t][u].update(x)
        for u, c in p["fim_urna_por_15min"].items():
            fim[u].update(c)
        for u, c in p["ultimo_voto_por_15min"].items():
            ultv[u].update(c)

    tot = lambda d, k: sum(x.get(k, 0) for x in d.values())
    E = sum(c.get("E", 0) for c in cob.values())
    K = sum(c.get("K", 0) for c in cob.values())
    U = sum(c.get("urnas", 0) for c in cob.values())
    print(f"D oficial = {br(D)}")
    print(f"Cobertura: urnas {br(U)} (oficial {br(OFICIAL['urnas'])}); "
          f"E(BU) {br(E)} (oficial {br(OFICIAL['E'])}); K(BU) {br(K)} (oficial {br(OFICIAL['K'])})")
    print(f"\n{'UF':>3} {'urnas':>7} {'c/BU':>7} {'c/log':>7} {'log=BU':>7} {'log<BU':>6} {'sem hora':>8} {'incoer.':>7}")
    for u in sorted(cob):
        c = cob[u]
        print(f"{u:>3} {c.get('urnas',0):>7} {c.get('com_bu',0):>7} {c.get('com_log',0):>7} "
              f"{c.get('log_igual_bu',0):>7} {c.get('log_menor_bu',0):>6} {c.get('votos_sem_horario',0):>8} "
              f"{c.get('relogio_incoerente',0):>7}")

    print(f"\n{'corte':>6} {'delta':>5} {'abertas':>8} {'R(t)':>12} {'R<D':>4} {'A(t)':>11} {'A<D':>4} {'D-A':>11} {'lacunas':>7}")
    tab = {}
    for key in sorted(res, key=lambda k: (k.split('|')[0], int(k.split('|')[1]))):
        d = res[key]
        R, A, ab, lac = tot(d, "R"), tot(d, "A"), tot(d, "abertas"), tot(d, "lacuna_secoes")
        c, dl = key.split("|")
        tab[key] = {"R": R, "A": A, "abertas": ab, "lacunas": lac, "R<D": R < D, "A<D": A < D}
        print(f"{c:>6} {dl:>5} {ab:>8} {br(R):>12} {'sim' if R < D else 'nao':>4} {br(A):>11} "
              f"{'sim' if A < D else 'nao':>4} {br(D - A):>11} {lac:>7}")

    print("\nPor UF, corte 17:00 (delta 0 e 15 min):")
    print(f"{'UF':>3} {'abertas':>8} {'R(17h)':>11} {'A(17h)':>10} {'A(17h-15)':>10} {'A(17:49)':>9}")
    for u in sorted(cob):
        a0, a15, a49 = res["17:00|0"][u], res["17:00|15"][u], res["17:49|0"][u]
        print(f"{u:>3} {a0.get('abertas',0):>8} {br(a0.get('R',0)):>11} {br(a0.get('A',0)):>10} "
              f"{br(a15.get('A',0)):>10} {br(a49.get('A',0)):>9}")

    print("\nCurva nacional (delta 0):")
    cv = {}
    for t in sorted(curva):
        d = curva[t]
        cv[t] = {"R": tot(d, "R"), "A": tot(d, "A"), "abertas": tot(d, "abertas")}
        print(f"  {t}  abertas {cv[t]['abertas']:>7}  R {br(cv[t]['R']):>12}  A {br(cv[t]['A']):>11}")

    fimn = collections.Counter(); [fimn.update(c) for u, c in fim.items() if u != "zz"]
    print("\nEncerramento das urnas no Brasil (hora de Brasilia, faixas de 15 min):")
    for t in sorted(fimn):
        if fimn[t] >= 1:
            print(f"  {t} {fimn[t]}")
    json.dump({"D": D, "cobertura": cob, "fusos": fusos, "tabela": tab,
               "por_uf": {k: {u: dict(x) for u, x in v.items()} for k, v in res.items()},
               "curva": cv, "fim_urna": {u: dict(c) for u, c in fim.items()},
               "ultimo_voto": {u: dict(c) for u, c in ultv.items()}},
              open(saida, "w"), ensure_ascii=False, indent=1)


if __name__ == "__main__":
    main()
