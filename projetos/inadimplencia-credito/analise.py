# -*- coding: utf-8 -*-
"""
Inadimplência de crédito no Brasil (2011–2026)
==============================================
Extração, limpeza e análise das séries públicas do Banco Central (API SGS):
  - 21082: Inadimplência da carteira de crédito — Total (%)
  - 21084: Inadimplência da carteira de crédito — Pessoas Físicas (%)

Saídas:
  - data/sgs_21082_inadimplencia_total.csv
  - data/sgs_21084_inadimplencia_pf.csv
  - grafico_inadimplencia.png
  - resumo.json (estatísticas usadas na página do case)

Uso:
  python analise.py            # tenta API; se offline, usa os CSVs locais
  python analise.py --offline  # força uso dos CSVs locais

Autor: João Talma · joaotalmaj@gmail.com
"""

import json
import sys
from pathlib import Path

import pandas as pd
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.ticker import FuncFormatter, MultipleLocator

# ----------------------------------------------------------------------------
# Configuração
# ----------------------------------------------------------------------------
SERIES = {
    "21082": {"nome": "Total", "arquivo": "sgs_21082_inadimplencia_total.csv"},
    "21084": {"nome": "Pessoa Física", "arquivo": "sgs_21084_inadimplencia_pf.csv"},
}
API_URL = "https://api.bcb.gov.br/dados/serie/bcdata.sgs.{codigo}/dados?formato=json"
BASE = Path(__file__).resolve().parent
DATA_DIR = BASE / "data"

# Identidade visual (mesma paleta do site)
COR_FUNDO = "#FFF8F0"
COR_TOTAL = "#E85D04"   # laranja principal
COR_PF = "#1F2937"      # grafite
COR_GRADE = "#E8DDD0"
COR_TEXTO = "#44403C"


# ----------------------------------------------------------------------------
# Extração
# ----------------------------------------------------------------------------
def baixar_serie(codigo: str) -> pd.DataFrame:
    """Baixa uma série da API SGS do Banco Central e devolve DataFrame limpo."""
    import urllib.request

    url = API_URL.format(codigo=codigo)
    with urllib.request.urlopen(url, timeout=30) as resp:
        bruto = json.loads(resp.read().decode("utf-8"))
    df = pd.DataFrame(bruto)
    df["data"] = pd.to_datetime(df["data"], format="%d/%m/%Y").dt.strftime("%Y-%m")
    df["valor"] = pd.to_numeric(df["valor"], errors="coerce")
    return df.dropna().reset_index(drop=True)


def carregar_local(arquivo: str) -> pd.DataFrame:
    df = pd.read_csv(DATA_DIR / arquivo)
    df["valor"] = pd.to_numeric(df["valor"], errors="coerce")
    return df.dropna().reset_index(drop=True)


def obter_dados(offline: bool) -> dict:
    """Tenta API; em falha (ou --offline), usa snapshot local versionado no repo."""
    dados = {}
    for codigo, cfg in SERIES.items():
        if not offline:
            try:
                df = baixar_serie(codigo)
                DATA_DIR.mkdir(exist_ok=True)
                df.to_csv(DATA_DIR / cfg["arquivo"], index=False)
                dados[codigo] = df
                print(f"[API] série {codigo} ({cfg['nome']}): {len(df)} observações")
                continue
            except Exception as exc:  # noqa: BLE001
                print(f"[aviso] API indisponível p/ {codigo} ({exc}); usando CSV local")
        dados[codigo] = carregar_local(cfg["arquivo"])
        print(f"[CSV] série {codigo} ({cfg['nome']}): {len(dados[codigo])} observações")
    return dados


# ----------------------------------------------------------------------------
# Análise
# ----------------------------------------------------------------------------
def estatisticas(df: pd.DataFrame) -> dict:
    """Últimos valores, variação 12m, pico e piso históricos."""
    atual = df.iloc[-1]
    idx_12m = len(df) - 13
    var_12m = round(atual["valor"] - df.iloc[idx_12m]["valor"], 2) if idx_12m >= 0 else None
    pico = df.loc[df["valor"].idxmax()]
    piso = df.loc[df["valor"].idxmin()]
    pre_2020 = df[df["data"] < "2020-01"]
    pico_pre = pre_2020.loc[pre_2020["valor"].idxmax()] if len(pre_2020) else None
    return {
        "valor_atual": float(atual["valor"]),
        "mes_atual": atual["data"],
        "variacao_12m_pp": var_12m,
        "pico_historico": {"valor": float(pico["valor"]), "mes": pico["data"]},
        "piso_historico": {"valor": float(piso["valor"]), "mes": piso["data"]},
        "pico_pre_pandemia": (
            {"valor": float(pico_pre["valor"]), "mes": pico_pre["data"]}
            if pico_pre is not None
            else None
        ),
    }


# ----------------------------------------------------------------------------
# Visualização
# ----------------------------------------------------------------------------
def gerar_grafico(dados: dict, resumo: dict) -> Path:
    fig, ax = plt.subplots(figsize=(11, 5.8), dpi=150)
    fig.patch.set_facecolor(COR_FUNDO)
    ax.set_facecolor(COR_FUNDO)

    for codigo, cor, largura in (("21084", COR_PF, 1.8), ("21082", COR_TOTAL, 2.6)):
        df = dados[codigo]
        x = pd.to_datetime(df["data"], format="%Y-%m")
        ax.plot(x, df["valor"], color=cor, linewidth=largura,
                label=f"{SERIES[codigo]['nome']} — {df['valor'].iloc[-1]:.2f}%".replace(".", ","))

    # Destaque no recorde atual da série Total
    df_t = dados["21082"]
    x_fim = pd.to_datetime(df_t["data"].iloc[-1], format="%Y-%m")
    y_fim = df_t["valor"].iloc[-1]
    ax.scatter([x_fim], [y_fim], s=70, zorder=5, color=COR_TOTAL, edgecolor="white", linewidth=1.5)
    ax.annotate(
        f"Recorde: {y_fim:.2f}%".replace(".", ","),
        xy=(x_fim, y_fim), xytext=(-118, -26), textcoords="offset points",
        fontsize=11, fontweight="bold", color=COR_TOTAL,
    )

    ax.set_title(
        "Inadimplência da carteira de crédito no Brasil (2011–2026)",
        fontsize=14, fontweight="bold", color=COR_TEXTO, pad=30, loc="left",
    )
    ax.text(
        0.0, 1.03, "Atrasos acima de 90 dias · % da carteira · Fonte: Banco Central (SGS 21082 e 21084)",
        transform=ax.transAxes, fontsize=9, color="#78716C",
    )
    ax.yaxis.set_major_locator(MultipleLocator(1))
    ax.yaxis.set_major_formatter(FuncFormatter(lambda v, _: f"{v:.0f}%"))
    ax.grid(axis="y", color=COR_GRADE, linewidth=0.8)
    for spine in ("top", "right", "left"):
        ax.spines[spine].set_visible(False)
    ax.spines["bottom"].set_color(COR_GRADE)
    ax.tick_params(colors=COR_TEXTO, labelsize=9)
    ax.legend(loc="upper center", frameon=False, ncol=2, fontsize=10)

    destino = BASE / "grafico_inadimplencia.png"
    fig.tight_layout()
    fig.savefig(destino, facecolor=COR_FUNDO, bbox_inches="tight")
    plt.close(fig)
    return destino


# ----------------------------------------------------------------------------
# Execução
# ----------------------------------------------------------------------------
def main() -> None:
    offline = "--offline" in sys.argv
    dados = obter_dados(offline)

    resumo = {
        "fonte": "Banco Central do Brasil — API SGS (séries 21082 e 21084)",
        "series": {
            codigo: {"nome": cfg["nome"], **estatisticas(dados[codigo])}
            for codigo, cfg in SERIES.items()
        },
    }
    (BASE / "resumo.json").write_text(
        json.dumps(resumo, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    grafico = gerar_grafico(dados, resumo)

    print("\n--- Resumo ---")
    for codigo, est in resumo["series"].items():
        print(
            f"{est['nome']}: {est['valor_atual']}% em {est['mes_atual']} "
            f"({est['variacao_12m_pp']:+.2f} p.p. em 12m) · "
            f"pico {est['pico_historico']['valor']}% em {est['pico_historico']['mes']}"
        )
    print(f"\nGrafico salvo em {grafico}")


if __name__ == "__main__":
    main()
