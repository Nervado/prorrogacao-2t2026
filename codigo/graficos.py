"""Resumo visual em PDF (formato retrato, para celular).

Uso: python graficos.py <dir_resultados> <saida.pdf>   (requer matplotlib e pandas)
"""
import json
import os
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages
import pandas as pd

D = 4430191
TINTA, TINTA2, MUDA, GRADE, FUNDO = "#0b0b0b", "#52514e", "#8a8984", "#e6e5e1", "#fcfcfb"
AZUL, LARANJA = "#2a78d6", "#eb6834"
W, H = 6.2, 10.0

plt.rcParams.update({
    "font.family": "DejaVu Sans", "font.size": 10, "text.color": TINTA,
    "axes.edgecolor": GRADE, "axes.labelcolor": TINTA2, "axes.facecolor": FUNDO,
    "figure.facecolor": FUNDO, "xtick.color": TINTA2, "ytick.color": TINTA2,
    "axes.spines.top": False, "axes.spines.right": False, "axes.grid": True,
    "grid.color": GRADE, "grid.linewidth": 0.8, "axes.axisbelow": True,
})


def br(n):
    return f"{int(round(n)):,}".replace(",", ".")


def mi(n):
    return f"{n/1e6:.2f}".replace(".", ",") + " mi"


def cabecalho(fig, titulo, sub=None):
    fig.text(0.07, 0.955, titulo, fontsize=15, weight="bold", va="top")
    if sub:
        fig.text(0.07, 0.918, sub, fontsize=9.5, color=TINTA2, va="top", wrap=True)


def rodape(fig, n):
    fig.text(0.07, 0.025, "Prorrogação do 2º turno 2026 · logs e BUs de 499.248 urnas (TSE, pleito 3221)",
             fontsize=7, color=MUDA)
    fig.text(0.93, 0.025, str(n), fontsize=7, color=MUDA, ha="right")


def main():
    res, saida = sys.argv[1:]
    T = json.load(open(os.path.join(res, "tetos_por_corte.json")))
    S = pd.read_csv(os.path.join(res, "secoes.csv.gz"), dtype={"mun": str, "zona": str, "secao": str})
    A17 = int(S.A_1700.sum())
    curva = T["curva"]
    ts = sorted(curva)
    with PdfPages(saida) as pdf:
        # 1 ---------------------------------------------------------- veredito
        fig = plt.figure(figsize=(W, H))
        cabecalho(fig, "A prorrogação não poderia\nter mudado o vencedor")
        fig.text(0.07, 0.86, "Diferença oficial (D)", fontsize=10, color=TINTA2)
        fig.text(0.07, 0.835, br(D), fontsize=30, weight="bold", va="top")
        fig.text(0.07, 0.76, "Teto de votos registrados após 17h", fontsize=10, color=TINTA2)
        fig.text(0.07, 0.735, br(A17), fontsize=30, weight="bold", color=AZUL, va="top")
        fig.text(0.07, 0.665, f"= {A17 / D * 100:.1f}% de D".replace(".", ","), fontsize=11, color=TINTA2)
        fig.text(0.07, 0.635, "Mesmo que todos fossem para o vencedor, ele ainda\nvenceria por "
                 f"{mi(D - A17)} de votos.", fontsize=10, color=TINTA, va="top")

        ax = fig.add_axes([0.30, 0.19, 0.62, 0.34])
        a1645 = curva["16:45"]["A"] + (A17 - curva["17:00"]["A"])
        a1630 = curva["16:30"]["A"] + (A17 - curva["17:00"]["A"])
        itens = [("Diferença D", D, TINTA2), ("Votos após 17h", A17, AZUL),
                 ("Idem, relógio\n15 min adiantado", a1645, AZUL), ("Idem, relógio\n30 min adiantado", a1630, AZUL)]
        y = range(len(itens))[::-1]
        for yi, (nome, v, c) in zip(y, itens):
            ax.barh(yi, v, height=0.56, color=c, alpha=1 if nome != "Diferença D" else 0.55)
            ax.text(v + D * 0.02, yi, mi(v), va="center", fontsize=9.5, color=TINTA)
        ax.axvline(D, color=TINTA, lw=1.2, ls=(0, (3, 2)))
        ax.set_yticks(list(y), [i[0] for i in itens], fontsize=9)
        ax.set_xlim(0, D * 1.3)
        ax.xaxis.set_major_formatter(lambda v, _: f"{v/1e6:.0f} mi")
        ax.grid(axis="y", visible=False)
        ax.tick_params(length=0)
        fig.text(0.07, 0.11, "Linha tracejada = D. Todas as barras azuis ficam à esquerda dela:\n"
                 "nenhum cenário de relógio alcança a diferença.", fontsize=8.5, color=TINTA2, va="top")
        rodape(fig, 1)
        pdf.savefig(fig); plt.close(fig)

        # 2 ---------------------------------------------------------- curvas
        fig = plt.figure(figsize=(W, H))
        cabecalho(fig, "Os dois tetos ao longo do tempo",
                  "Para cada horário de corte t: quanto ainda poderia entrar depois de t.")
        mn = lambda t: int(t[:2]) * 60 + int(t[3:])
        x = [mn(t) for t in ts]
        marcos = {"17:00": "17h", "17:49": "ofício\nTSE", "19:00": "19h"}
        for i, (chave, cor, titulo, txt) in enumerate([
            ("R", LARANJA, "R(t) · eleitorado residual das urnas abertas",
             "Supõe que TODO eleitor que ainda não votou\ncompareceria. Às 17h não serve (inclui a\nabstenção). Fica abaixo de D a partir de 17h05."),
            ("A", AZUL, "A(t) · votos efetivamente registrados após t",
             "Conta voto a voto nos logs. Abaixo de D em\nqualquer corte. Antes das 17h, a curva equivale\na supor relógios de urna adiantados."),
        ]):
            ax = fig.add_axes([0.13, 0.555 - i * 0.43, 0.80, 0.27])
            v = [curva[t][chave] for t in ts]
            ax.plot(x, v, color=cor, lw=2)
            ax.axhline(D, color=TINTA, lw=1.1, ls=(0, (3, 2)))
            ax.text(x[-1], D, " D = 4,43 mi", va="bottom", ha="right", fontsize=8.5, color=TINTA)
            for t, lab in marcos.items():
                xi = mn(t)
                ax.axvline(xi, color=MUDA, lw=0.7)
                ax.text(xi + 2, ax.get_ylim()[1] * 0.97 if chave == "R" else D * 1.45, lab,
                        fontsize=7.5, color=TINTA2, va="top")
            ax.set_xticks(x[::6], [f"{t[:2]}h{t[3:]}" for t in ts[::6]], fontsize=8)
            ax.yaxis.set_major_formatter(lambda vv, _: f"{vv/1e6:.0f} mi" if vv >= 1e6 or vv == 0 else f"{vv/1e3:.0f} mil")
            if chave == "A":
                ax.set_ylim(0, D * 1.6)
            ax.set_title(titulo, loc="left", fontsize=10.5, weight="bold", pad=8)
            fig.text(0.13, 0.515 - i * 0.43, txt, fontsize=8.5, color=TINTA2, va="top")
            ax.tick_params(length=0)
        rodape(fig, 2)
        pdf.savefig(fig); plt.close(fig)

        # 3 ---------------------------------------------------------- composicao + encerramento
        fig = plt.figure(figsize=(W, H))
        cabecalho(fig, f"De onde vêm os {br(A17)}",
                  "O teto é inflado de propósito: tudo o que é incerto conta contra a hipótese.")
        br_ = S[S.uf != "zz"]; o = br_[br_.observada]
        comp = [
            ("Votos sem horário no log\n(1.432 urnas, quase todas substituídas)", o[o.n_log < o.K].A_1700.sum()),
            ("Exterior, no fuso mais\ndesfavorável possível", S[S.uf == "zz"].A_1700.sum()),
            ("Votos com horário após 17h\nno Brasil (fila)", o[o.n_log >= o.K].A_1700.sum()),
            ("2 urnas sem log legível\n(eleitorado inteiro)", br_[~br_.observada].A_1700.sum()),
        ]
        ax = fig.add_axes([0.42, 0.56, 0.50, 0.30])
        y = range(len(comp))[::-1]
        for yi, (nome, v) in zip(y, comp):
            ax.barh(yi, v, height=0.56, color=AZUL)
            ax.text(v + 3000, yi, br(v), va="center", fontsize=9)
        ax.set_yticks(list(y), [c[0] for c in comp], fontsize=8.2)
        ax.set_xlim(0, 200000)
        ax.xaxis.set_major_formatter(lambda vv, _: f"{vv/1e3:.0f} mil")
        ax.grid(axis="y", visible=False); ax.tick_params(length=0)

        fu = {}
        for u, c in T["fim_urna"].items():
            if u == "zz":
                continue
            for k, n in c.items():
                fu[k] = fu.get(k, 0) + n
        faixas = [k for k in sorted(fu) if "17:00" <= k <= "20:45"]
        ax = fig.add_axes([0.13, 0.12, 0.80, 0.30])
        xs = range(len(faixas))
        ax.bar(xs, [fu[k] for k in faixas], width=0.8, color=[LARANJA if k == "19:00" else AZUL for k in faixas])
        ax.set_yscale("log")
        ax.set_xticks(list(xs), faixas, rotation=90, fontsize=7.5)
        for xi, k in zip(xs, faixas):
            if k in ("17:00", "19:00"):
                ax.text(xi, fu[k] * 1.3, br(fu[k]), ha="center", fontsize=8.5)
        ax.yaxis.set_major_formatter(lambda vv, _: br(vv))
        ax.set_title("Urnas no Brasil por horário de encerramento (faixas de 15 min,\nescala log)",
                     loc="left", fontsize=10.5, weight="bold", pad=8)
        fig.text(0.13, 0.065, "Laranja: 6.316 urnas fecharam entre 19h00 e 19h15, as que usaram a prorrogação.",
                 fontsize=8.5, color=TINTA2)
        ax.tick_params(length=0)
        rodape(fig, 3)
        pdf.savefig(fig); plt.close(fig)

        # 4 ---------------------------------------------------------- por UF
        fig = plt.figure(figsize=(W, H))
        cabecalho(fig, "Teto A(17h) por UF",
                  "Votos registrados após 17h (com votos sem horário contados como posteriores).")
        g = S.groupby("uf").A_1700.sum().sort_values()
        ax = fig.add_axes([0.12, 0.08, 0.72, 0.80])
        ax.barh(range(len(g)), g.values, height=0.68, color=AZUL)
        for i, v in enumerate(g.values):
            ax.text(v + 600, i, br(v), va="center", fontsize=7.5)
        ax.set_yticks(range(len(g)), [u.upper() if u != "zz" else "Exterior" for u in g.index], fontsize=8)
        ax.xaxis.set_major_formatter(lambda vv, _: f"{vv/1e3:.0f} mil")
        ax.grid(axis="y", visible=False); ax.tick_params(length=0)
        rodape(fig, 4)
        pdf.savefig(fig); plt.close(fig)

        # 5 ---------------------------------------------------------- metodo
        fig = plt.figure(figsize=(W, H))
        cabecalho(fig, "Como foi feito")
        txt = [
            ("Dados", "BU + log de cada uma das 499.248 urnas do 2º turno, baixados um a um do site\n"
                      "Resultados do TSE (pleito 3221). Totais batem com o oficial (diferença: 70\n"
                      "urnas do exterior sem log, contadas pelo eleitorado inteiro)."),
            ("Conta", "Para cada urna, os eventos \"O voto do eleitor foi computado\" depois do\n"
                      "corte. A(t) = soma nacional. Voto que o log não mostra conta como posterior."),
            ("Fuso", "Urna grava hora local. Brasil: abertura às 8h de Brasília fixa o fuso de\n"
                     "cada município. Exterior: o fuso mais tardio compatível com o recebimento."),
            ("Cortes", "17h00 encerramento legal · 17h03 decisão divulgada · 17h49 ofício do TSE\n"
                       "· 18h21 nota TRE-RS · 18h44 nota TSE · 19h00 fim da prorrogação."),
            ("Conferência", "Dois cálculos independentes (script e dataframe pandas) dão o mesmo\n"
                            "número. SHA-256 de 998.412 arquivos no manifesto."),
            ("Limite", "Prova só o efeito direto dos votos acrescentados. Não avalia a\n"
                       "legalidade da medida nem efeitos indiretos sobre o eleitor."),
            ("Sigilo", "O log não registra o candidato; nenhum voto foi associado a ninguém."),
        ]
        yy = 0.86
        for k, v in txt:
            fig.text(0.07, yy, k, fontsize=10.5, weight="bold")
            fig.text(0.07, yy - 0.022, v, fontsize=8.6, color=TINTA2, va="top", linespacing=1.4)
            yy -= 0.022 + 0.022 * (v.count("\n") + 1) + 0.045
        rodape(fig, 5)
        pdf.savefig(fig); plt.close(fig)


if __name__ == "__main__":
    main()
