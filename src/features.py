# src/features.py
import pandas as pd
import numpy as np

BASIC_COLS = ["company","fiscal_year","revenue","net_income","gross_profit",
              "operating_income","total_assets","total_liabilities","shareholders_equity",
              "operating_cash_flow","capex"]

def standardize_columns(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df.columns = [c.strip().lower().replace(" ", "_") for c in df.columns]
    # 最低限
    need = {"company","fiscal_year","revenue","net_income"}
    if not need.issubset(df.columns):
        raise KeyError(f"必須列が不足: {need - set(df.columns)}")
    df["fiscal_year"] = pd.to_numeric(df["fiscal_year"], errors="coerce").astype("Int64")
    df = df.dropna(subset=["fiscal_year"]).copy()
    df["fiscal_year"] = df["fiscal_year"].astype(int)
    return df.sort_values(["company","fiscal_year"])

def add_ratios(df: pd.DataFrame) -> pd.DataFrame:
    d = df.copy()
    if "gross_profit" in d and "revenue" in d:
        d["gross_margin"] = d["gross_profit"] / d["revenue"]
    if "operating_income" in d and "revenue" in d:
        d["operating_margin"] = d["operating_income"] / d["revenue"]
    d["profit_margin"] = d["net_income"] / d["revenue"]
    if "total_assets" in d:
        d["roa"] = d["net_income"] / d["total_assets"]
        d["asset_turnover"] = d["revenue"] / d["total_assets"]
    if "shareholders_equity" in d:
        d["roe"] = d["net_income"] / d["shareholders_equity"]
        if "total_assets" in d:
            d["equity_multiplier"] = d["total_assets"] / d["shareholders_equity"]
            d["roe_dupont"] = d["profit_margin"] * d["asset_turnover"] * d["equity_multiplier"]
    if "operating_cash_flow" in d and "capex" in d:
        d["free_cash_flow"] = d["operating_cash_flow"] - d["capex"]
    return d

def add_lags_growth(df: pd.DataFrame, cols=None, lags=(1,2,3)) -> pd.DataFrame:
    if cols is None:
        cols = ["revenue","net_income","gross_margin","operating_margin","profit_margin","roa","roe","free_cash_flow"]
    d = df.copy()
    for c in cols:
        if c not in d.columns: 
            continue
        d[c] = pd.to_numeric(d[c], errors="coerce")
        for L in lags:
            d[f"{c}_lag{L}"] = d.groupby("company")[c].shift(L)
        d[f"{c}_yoy"] = d.groupby("company")[c].pct_change()
        d[f"{c}_cagr3y"] = (d.groupby("company")[c].apply(lambda s: s/ s.shift(3)) ** (1/3) - 1).reset_index(level=0, drop=True)
    return d

def train_test_by_year(df: pd.DataFrame, cutoff_year: int):
    train = df[df["fiscal_year"] <= cutoff_year].copy()
    test  = df[df["fiscal_year"] >  cutoff_year].copy()
    return train, test
