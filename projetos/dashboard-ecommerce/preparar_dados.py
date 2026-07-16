# -*- coding: utf-8 -*-
"""
Dashboard de vendas e-commerce — preparação dos dados
=====================================================
Lê o dataset público Olist (Brazilian E-Commerce, ~100 mil pedidos reais
de 2016–2018) e gera o JSON agregado que alimenta o dashboard (index.html).

Como obter o dataset (não versionado aqui por tamanho, ~120 MB):
  https://www.kaggle.com/datasets/olistbr/brazilian-ecommerce

Uso:
  python preparar_dados.py --src /caminho/para/csvs

Saída:
  data/dados.json  (agregados: KPIs, série mensal, categorias, estados, pagamentos)

Autor: João Talma · joaotalmaj@gmail.com
"""

import argparse
import json
from pathlib import Path

import pandas as pd

BASE = Path(__file__).resolve().parent


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", required=True, help="pasta com os CSVs do Olist")
    src = Path(ap.parse_args().src)

    orders = pd.read_csv(src / "olist_orders_dataset.csv",
                         parse_dates=["order_purchase_timestamp",
                                      "order_delivered_customer_date"])
    items = pd.read_csv(src / "olist_order_items_dataset.csv")
    products = pd.read_csv(src / "olist_products_dataset.csv")
    customers = pd.read_csv(src / "olist_customers_dataset.csv")
    payments = pd.read_csv(src / "olist_order_payments_dataset.csv")
    reviews = pd.read_csv(src / "olist_order_reviews_dataset.csv")
    traducao = pd.read_csv(src / "product_category_name_translation.csv")

    # Base: pedidos entregues (análise de vendas concretizadas)
    entregues = orders[orders["order_status"] == "delivered"].copy()
    entregues["mes"] = entregues["order_purchase_timestamp"].dt.strftime("%Y-%m")
    entregues["ano"] = entregues["order_purchase_timestamp"].dt.year

    # Receita por item (preço + frete)
    it = items.merge(entregues[["order_id", "mes", "ano", "customer_id"]], on="order_id")
    it["receita"] = it["price"] + it["freight_value"]

    # Categorias (top 10 por receita)
    it_cat = it.merge(products[["product_id", "product_category_name"]], on="product_id")
    cat = (it_cat.groupby("product_category_name")["receita"].sum()
           .sort_values(ascending=False).head(10))

    # Estados (top 10 por receita)
    it_uf = it.merge(customers[["customer_id", "customer_state"]], on="customer_id")
    uf = (it_uf.groupby("customer_state")["receita"].sum()
          .sort_values(ascending=False).head(10))

    # Série mensal (receita e nº de pedidos)
    mensal_receita = it.groupby("mes")["receita"].sum().round(2)
    mensal_pedidos = entregues.groupby("mes")["order_id"].nunique()

    # Pagamentos (participação por tipo)
    pay = payments[payments["order_id"].isin(entregues["order_id"])]
    pagamento = pay.groupby("payment_type")["payment_value"].sum().sort_values(ascending=False)

    # Tempo de entrega e avaliação média
    ent = entregues.dropna(subset=["order_delivered_customer_date"])
    dias_entrega = (ent["order_delivered_customer_date"]
                    - ent["order_purchase_timestamp"]).dt.days
    rev = reviews[reviews["order_id"].isin(entregues["order_id"])]

    # KPIs por ano (para o filtro do dashboard) + total
    kpis = {}
    for chave, grupo_o, grupo_i in [("total", entregues, it)] + [
        (str(a), entregues[entregues["ano"] == a], it[it["ano"] == a])
        for a in sorted(entregues["ano"].unique())
    ]:
        ids = grupo_o["order_id"]
        rev_g = reviews[reviews["order_id"].isin(ids)]
        ent_g = grupo_o.dropna(subset=["order_delivered_customer_date"])
        dias_g = (ent_g["order_delivered_customer_date"]
                  - ent_g["order_purchase_timestamp"]).dt.days
        kpis[chave] = {
            "receita": round(float(grupo_i["receita"].sum()), 2),
            "pedidos": int(ids.nunique()),
            "ticket_medio": round(float(grupo_i.groupby("order_id")["receita"].sum().mean()), 2),
            "avaliacao_media": round(float(rev_g["review_score"].mean()), 2),
            "dias_entrega_mediana": float(dias_g.median()),
        }

    # Série mensal por ano (para o filtro)
    mensal = [
        {"mes": m,
         "receita": float(mensal_receita.get(m, 0)),
         "pedidos": int(mensal_pedidos.get(m, 0))}
        for m in sorted(mensal_receita.index)
    ]

    saida = {
        "fonte": "Olist Brazilian E-Commerce Public Dataset (Kaggle) — pedidos entregues, 2016–2018",
        "kpis": kpis,
        "mensal": mensal,
        "categorias": [{"nome": k, "receita": round(float(v), 2)} for k, v in cat.items()],
        "estados": [{"uf": k, "receita": round(float(v), 2)} for k, v in uf.items()],
        "pagamentos": [{"tipo": k, "valor": round(float(v), 2)} for k, v in pagamento.items()],
    }

    destino = BASE / "data" / "dados.json"
    destino.parent.mkdir(exist_ok=True)
    destino.write_text(json.dumps(saida, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"OK: {destino} ({destino.stat().st_size/1024:.1f} KB)")
    print(json.dumps(kpis["total"], indent=2))


if __name__ == "__main__":
    main()
