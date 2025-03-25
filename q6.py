# %%
import os
import pandas as pd
import numpy as np
import QuantLib as ql

from q3 import build_curves
from q4 import df_best  # best-case cash flows from Q4

# ----------------------------
# 0. setup inputs
# ----------------------------

# evaluation date and curve
log_cubic_curve = build_curves()["Log-Cubic"]
eval_date = ql.Settings.instance().evaluationDate
day_counter = ql.Actual360()

# issuer-specific CDS data as of 26 Nov 2024
cds_spread = 0.004921  # 49.21 bps
recovery_rate = 0.40   # as given

# ----------------------------
# 1. define survival probability function
# ----------------------------

def survival_prob(t, cds, R):
    return (np.exp(-cds * t) - R) / (1 - R)

# ----------------------------
# 2. compute CVA
# ----------------------------

cva = 0.0
cashflow_rows = []

for _, row in df_best.iterrows():
    payment_date = row["End Date"]
    t = day_counter.yearFraction(eval_date, payment_date)

    if t <= 0:
        continue  # skip past cash flows

    df = log_cubic_curve.discount(payment_date)
    surv = survival_prob(t, cds_spread, recovery_rate)
    default_prob = 1 - surv

    exposure = row["Coupon Amount"]
    marginal_cva = exposure * default_prob * df
    cva += marginal_cva

    cashflow_rows.append({
        "Payment Date": row["End Date"],
        "Year Fraction": round(t, 4),
        "Exposure": exposure,
        "Discount Factor": df,
        "Survival Prob": surv,
        "Default Prob": default_prob,
        "Marginal CVA": marginal_cva
    })

# ----------------------------
# 3. results
# ----------------------------

df_cva = pd.DataFrame(cashflow_rows)

print("\nCredit Valuation Adjustment (CVA):")
print(f"Total CVA: {cva:.4f}")

# optional: adjusted bond value
risk_free_npv = df_best["PV"].sum()
adjusted_npv = risk_free_npv - cva

print(f"Risk-free value (from Q4): {risk_free_npv:.4f}")
print(f"Credit-adjusted value:     {adjusted_npv:.4f}")

# ----------------------------
# 4. show table
# ----------------------------

print("\nCash Flow CVA Breakdown:")
print(df_cva[["Payment Date", "Exposure", "Discount Factor", "Survival Prob", "Default Prob", "Marginal CVA"]])

# %%
