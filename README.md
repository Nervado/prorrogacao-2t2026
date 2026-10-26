# A prorrogação de 25/10/2026 poderia ter mudado o vencedor?

**Conclusão: demonstrado.** O teto de votos efetivamente registrados após o corte das 17h (horário de Brasília), A(17h) = 239.078, é menor que a diferença oficial D = 4.430.191. Isso vale para todas as 499.248 urnas do 2º turno, inclusive as do exterior. Para qualquer corte a partir das 17h05, o teto de eleitorado residual também fica abaixo de D: R(17h05) = 4.300.560.

Mesmo admitindo que todos esses votos tenham ido para o vencedor, eles não alcançam a diferença. A diferença também não muda de lado se os relógios das urnas estiverem até 30 minutos adiantados: A(16h30) = 2.598.888 < D.

O cálculo cobre apenas o efeito direto dos votos acrescentados. Não trata de questões jurídicas nem de efeitos indiretos, como a mobilização causada pela notícia da prorrogação.

## Números

| | valor |
|---|---|
| D = Lula 64.256.232 − Flávio Bolsonaro 59.826.041 | **4.430.191** |
| Urnas cobertas (BU + log) | 499.178 de 499.248, e as 70 restantes entram com o eleitorado inteiro |
| Eleitorado nos BUs / oficial | 158.743.025 / 158.745.502 (a diferença são as 70 urnas do exterior) |
| Comparecimento nos BUs / oficial | 128.235.243 / 128.236.074 |
| Urnas abertas às 17h00 / 17h49 / 19h00 | 499.248 / 7.871 / 6.929 |

| corte (Brasília) | marco | R(t) | A(t) | A com relógio −15 min |
|---|---|---|---|---|
| 17h00 | encerramento legal | 30.746.702 (≥ D) | **239.078** | 961.513 |
| 17h03 | decisão divulgada | 9.122.244 (≥ D) | 211.737 | 734.750 |
| 17h49 | ofício-circular TSE assinado | 780.765 | 194.053 | 198.292 |
| 18h21 | nota do TRE-RS | 740.647 | 185.224 | 189.087 |
| 18h44 | nota do TSE | 729.520 | 179.441 | 182.975 |
| 19h00 | fim da prorrogação | 696.061 | 175.952 | 179.034 |

A coluna A(t) da tabela vem do `tabela.py`, que é o mais conservador dos dois cálculos. Ele conta pelo eleitorado inteiro duas urnas cujo BU está publicado mas cujo log não pôde ser lido; o `analise.py` conta essas duas pelo comparecimento. Com essa diferença de convenção, `analise.py` dá 158 votos a menos no teto. Nos demais casos os dois scripts batem exatamente. Os números por UF estão em `resultados/tabelas.txt`.

Do teto A(17h), 157.290 votos não têm horário no log. São urnas, a maioria substituídas, em que o log contém menos votos que o BU, e esses votos foram contados como posteriores ao corte. Do exterior vêm 47 mil votos, porque ali se usa o fuso mais desfavorável compatível com os dados. Os votos com horário registrado depois das 17h no Brasil são poucas dezenas de milhares, basicamente a fila.

Encerramento das urnas no Brasil: 488.793 fecharam entre 17h00 e 17h15, e 6.316 entre 19h00 e 19h15. Essas 6.316 são as que usaram a prorrogação.

## Método

- **Unidade:** a urna que gerou o BU. As 17.931 seções agregadas já estão no BU da seção principal.
- **E_s:** eleitorado apto do BU (eleição 6258, Presidente). **K_s:** comparecimento do BU.
- **C_s(t):** eventos "O voto do eleitor foi computado" do log de 25/10/2026 com horário anterior a t, deduplicados e limitados a K_s.
- **A_s(t):** = max(votos do log em t ou depois, K_s − C_s(t)). Voto que não aparece no log conta como posterior ao corte.
- **R_s(t):** = E_s − C_s(t) se a urna ainda estava aberta em t. Considera-se fechada quando o último evento entre encerramento no BU, encerramento no log e último voto ocorreu antes de t.
- **Urna sem BU ou sem log:** R_s = A_s = eleitorado (do BU ou do 1º turno).
- **Fuso no Brasil:** a urna registra hora local, e a abertura é às 8h de Brasília (Res.-TSE 23.751/2026, art. 129). O deslocamento de cada município é 8 − moda da hora de abertura. Resultado: AC +2h; AM +1h, e +2h em 11 municípios; MS, MT, RO, RR +1h; Fernando de Noronha −1h; demais estados 0h.
- **Fuso no exterior:** a urna abre às 8h locais, então a abertura não revela o fuso. Usa-se o maior deslocamento compatível com os dados (recebimento no TSE − último evento do log), o que empurra todos os votos para o mais tarde possível.
- **Coerência dos relógios:** em nenhuma urna do Brasil o horário convertido do log ficou mais de 5 minutos depois do recebimento do arquivo pelo TSE.
- **Folga de relógio:** δ de 0, 5 e 15 minutos (o corte efetivo vira t − δ), além da curva completa de 16h30 a 21h00.
- Não se tenta saber em quem cada pessoa votou: o log não registra o candidato, e o RDV é embaralhado.

## Reproduzir

```
python3 -I codigo/coleta.py <dir_cs> coleta.jsonl [ufs] --workers 64 --rps 30   # ~1,5 mi de requisições; o servidor bloqueia acima de ~50 req/s por IP
python3 -I codigo/analise.py <dir_cs> aptos_1t_presidente.csv.gz parcial.json coleta.jsonl
python3 -I codigo/combinar.py final.json parcial*.json
python  -I codigo/tabela.py  <dir_cs> aptos_1t_presidente.csv.gz secoes.csv.gz coleta.jsonl   # pandas
```

Requisitos: Python 3.12+, `7zz` (7-Zip 24.09) e, para `tabela.py`, pandas.

`resultados/secoes.csv.gz` tem uma linha por urna (E, K, horários, fuso, A_t, R_t, aberta_t). Os tetos são somas dessas colunas.

O manifesto com o hash da pasta do TSE e o SHA-256 de cada BU e log baixado (998.412 arquivos, 91 MB) fica fora do git, como anexo da release `dados-2026-10-26`. `resultados/cs_sha256.txt` traz o SHA-256 dos 28 arquivos de configuração. Com eles, qualquer pessoa pode conferir que usou exatamente os mesmos arquivos.

## Fontes (consulta em 26/10/2026)

- **Arquivos de urna, 2º turno (pleito 3221):** `https://resultados.tse.jus.br/oficial/ele2026/arquivo-urna/3221/config/<uf>/<uf>-p003221-cs.json` e `.../dados/<uf>/<mun>/<zona>/<secao>/p003221-<uf>-m<mun>-z<zona>-s<secao>-aux.json`. Os arquivos de configuração foram gerados em 25/10 às 23:22:31. O pacote em lote do Portal de Dados Abertos ainda tem só o 1º turno: `bu_imgbu_logjez_rdv_vscmr_2026_2t_*.zip` dá 404.
- **Resultado oficial:** `https://resultados.tse.jus.br/oficial/ele2026/6258/dados/br/br-c0001-e006258-u.json`, gerado em 25/10 às 23:27:02.
- **Eleitorado do 1º turno, usado só como reserva:** `https://cdn.tse.jus.br/estatistica/sead/odsele/detalhe_votacao_secao/detalhe_votacao_secao_2026.zip` (SHA-256 11a62c3a…512f573).
- **STF, Rcl 101.673/BA:** decisão de Zanin e decisão de esclarecimento ("nos locais onde as urnas não foram fechadas"). Cópias das decisões em `fontes/`, obtidas pelo Poder360. Nenhuma das duas tem hora de assinatura.
- **TSE:** Ofício-Circular GAB-PRES nº 354/2026, assinado às 17:49, e a nota "Esclarecimento sobre prorrogação da votação", publicada às 18:44.
- **TRE-RS:** nota oficial publicada às 18:21 (urna encerrada não é reaberta).
- **Imprensa, para os horários:** [cronologia do Poder360](https://www.poder360.com.br/poder-eleicoes/leia-a-cronologia-da-ampliacao-do-horario-de-votacao-no-2o-turno/), [Poder360 sobre a decisão](https://www.poder360.com.br/poder-eleicoes-2026/zanin-prorroga-votacao-do-2o-turno-ate-19h/), [Agência Brasil](https://agenciabrasil.ebc.com.br/politica/noticia/2026-10/tse-diz-que-contagem-dos-votos-sera-retomada-19h).
- **Fila:** Res.-TSE 23.751/2026, art. 160 e art. 118, VI. Quem está na fila às 17h recebe senha e vota.

## Limitações

- **70 urnas do exterior** entram pelo eleitorado inteiro, por serem conservadoras: 41 não foram instaladas (423 eleitores, sem votos) e 29 votaram pelo sistema de apuração, sem log de urna.
- **Horários sem documento:** não há hora documentada de quando cada mesa recebeu a ordem. Por isso o corte principal é 17h, antes de qualquer comunicação, e esse corte inclui também a fila, que votaria de qualquer forma.
- **Relógio das urnas:** é o relógio interno de cada urna. O teste de sensibilidade mostra que um erro de até 30 minutos não altera a conclusão.
- **Exterior:** o fuso não é medido diretamente; usa-se o limite superior compatível com os dados, como descrito no método.
- **Escopo:** o cálculo não avalia a legalidade da medida nem efeitos indiretos sobre o comportamento dos eleitores.

## Em linguagem simples

O vencedor teve 4,43 milhões de votos a mais. Os logs de todas as urnas do país registram, voto a voto, o horário de cada votação. Somando tudo o que foi votado depois das 17h, inclusive a fila e com folgas a favor da dúvida, chega-se a no máximo 239 mil votos, menos de 6% da diferença. Mesmo que todos esses votos tivessem ido para o vencedor, sem a prorrogação ele ainda teria vencido por mais de 4,19 milhões de votos. Por isso a prorrogação não pode ter decidido a eleição pelo efeito direto dos votos que acrescentou.

## Refinamento: exterior com o fuso real de cada cidade

`codigo/exterior_fuso_real.py` + `codigo/fusos_exterior.csv` (186 cidades → fuso IANA, tzdata 2026e). Saída em `resultados/exterior_fuso_real.txt`.

| corte | exterior, fuso máximo | exterior, fuso real | A nacional refinado |
|---|---|---|---|
| 17h00 | 47.229 | 13.730 | **205.579** (4,6% de D) |
| 17h49 | 34.086 | 7.491 | 167.458 |
| 19h00 | 18.422 | 4.639 | 162.169 |

Checagens: nas 1.281 urnas do exterior com log, nenhuma termina depois do recebimento no TSE. Quatro abriram fora da janela de 7h30 a 8h30 no horário local.

Dos 13.730 votos do exterior:
- cerca de 10,9 mil são votos com horário depois das 17h de Brasília, quase todos na América do Norte (Vancouver, Los Angeles, Boston, São Francisco etc.), que votam no horário local normal e não têm relação com a prorrogação;
- 2.476 vêm das 70 urnas sem log, contadas pelo eleitorado inteiro;
- 383 são votos sem horário no log.

Votos com horário registrado depois das 17h, sem nenhuma folga: 34.330 no Brasil e cerca de 10,9 mil no exterior.

## Conferência com uma análise independente

O repositório [apolinario/urnas-tardias](https://github.com/apolinario/urnas-tardias) leu os mesmos logs com código próprio. Cruzando urna por urna o `secoes.csv` de lá com o `resultados/secoes.csv.gz` daqui:

- as 497.882 urnas do Brasil batem no total de votos do log (127.696.482), nos votos a partir das 17h (34.330) e no fuso de cada município, sem diferença em nenhuma urna;
- o número de destaque de lá, 5.052 votos (0,11% de D), conta só os votos depois das 17h nas 7.352 urnas que fecharam depois das 17h45. Para essas urnas o cálculo daqui dá os mesmos 5.052;
- nessas 7.352 urnas há ainda 8.128 votos sem horário no log, que lá não entram. Com eles, 13.180 (0,30% de D).

As duas análises e a reportagem do G1 (35.521) ficam abaixo de D.
