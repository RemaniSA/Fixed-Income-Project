# TODO: Add df_worst to the CVA calculation and sensitivity analysis.
# Rerun with df_worst instead of df_best.
# TODO: Fix coupon exposure to be the variable coupon amount instead of the best case coupoons
# %%
import os
import pandas as pd
import numpy as np
import QuantLib as ql

from q3 import build_curves
from q4 import df_best  # best-case coupon cash flows from Q4
from q1 import bond_characteristics  # to get the 'Nominal Value'

# ----------------------------
# 0. set up inputs
# ----------------------------

# evaluation date and discount curve
log_cubic_curve = build_curves()["Log-Cubic"]
eval_date = ql.Settings.instance().evaluationDate
day_counter = ql.Actual360()

# BNP CDS data (as of 26 Nov 2024)
base_cds_spread = 0.004921  # 49.21 bps
base_recovery_rate = 0.40   # 40%

# retrieve nominal from bond_characteristics
notional = bond_characteristics["Nominal Value"]

# define maturity as per q4
maturity_date = ql.Date(29, 7, 2027)

# ----------------------------
# 1. survival probability function
# ----------------------------
def survival_prob(t, cds, R):
    """
    Calculate survival probability using the approximation:
    
      Q(t) = [exp(-cds * t) - R] / (1 - R)
    
    where:
      - cds: CDS spread in decimals,
      - t: time (in years) from evaluation date,
      - R: Recovery rate.
    """
    return (np.exp(-cds * t) - R) / (1 - R)

# ----------------------------
# 2. cva calculation function
# ----------------------------
def compute_cva(cds, R):
    """
    Compute Credit Valuation Adjustment (CVA) for the bond,
    incorporating both coupon cash flows (from df_best) and the
    principal redemption at maturity.
    
    Returns:
      total_cva: Total CVA value.
      rows: A list of dictionaries with a breakdown per cash flow.
    """
    total_cva = 0.0
    rows = []
    
    # loop over coupon cash flows (from best-case scenario in Q4)
    for _, row in df_best.iterrows():
        payment_date = row["End Date"]
        t = day_counter.yearFraction(eval_date, payment_date)
        if t <= 0:
            continue  # skip past historical cash flows
        df_val = log_cubic_curve.discount(payment_date)
        surv = survival_prob(t, cds, R)
        default_prob = 1 - surv
        exposure = row["Coupon Amount"]  # exposure is the coupon payment
        marginal = exposure * default_prob * df_val
        total_cva += marginal
        rows.append({
            "Payment Date": payment_date,
            "Year Fraction": round(t, 4),
            "Exposure": exposure,
            "Discount Factor": df_val,
            "Survival Prob": surv,
            "Default Prob": default_prob,
            "Marginal CVA": marginal
        })
    
    # Add notional redemption at maturity (exposure = notional)
    t_principal = day_counter.yearFraction(eval_date, maturity_date)
    if t_principal > 0:
        df_principal = log_cubic_curve.discount(maturity_date)
        surv_principal = survival_prob(t_principal, cds, R)
        default_prob_principal = 1 - surv_principal
        exposure_principal = notional
        marginal_principal = exposure_principal * default_prob_principal * df_principal
        total_cva += marginal_principal
        rows.append({
            "Payment Date": maturity_date,
            "Year Fraction": round(t_principal, 4),
            "Exposure": exposure_principal,
            "Discount Factor": df_principal,
            "Survival Prob": surv_principal,
            "Default Prob": default_prob_principal,
            "Marginal CVA": marginal_principal
        })
    
    return total_cva, rows

# ----------------------------
# 3. base case cva
# ----------------------------
base_cva, base_cva_rows = compute_cva(base_cds_spread, base_recovery_rate)

# for a full risk-free bond value, add discounted principal to the sum of coupon PVs
risk_free_npv = df_best["PV"].sum() + notional * log_cubic_curve.discount(maturity_date)
adjusted_npv = risk_free_npv - base_cva

print("\n=== Base Case ===")
print(f"Risk-free Value:      {risk_free_npv:.4f}")
print(f"Total CVA:            {base_cva:.4f}")
print(f"Credit-adjusted Value:{adjusted_npv:.4f}")

# ----------------------------
# 4. sensitivity analysis
# ----------------------------

# sensitivity to CDS Spread (varying from 20 bps to 70 bps)
cds_values = np.linspace(0.002, 0.007, 6)
sensitivity_cds = []

for cds in cds_values:
    cva_val, _ = compute_cva(cds, base_recovery_rate)
    adjusted_val = risk_free_npv - cva_val
    sensitivity_cds.append({
        "CDS Spread": cds,
        "CVA": cva_val,
        "Adjusted NPV": adjusted_val
    })

df_sens_cds = pd.DataFrame(sensitivity_cds)
print("\nSensitivity Analysis - CDS Spread:")
print(df_sens_cds)

# sensitivity to recovery rate (varying from 30% to 50%)
recov_values = np.linspace(0.30, 0.50, 5)
sensitivity_recov = []

for recov in recov_values:
    cva_val, _ = compute_cva(base_cds_spread, recov)
    adjusted_val = risk_free_npv - cva_val
    sensitivity_recov.append({
        "Recovery Rate": recov,
        "CVA": cva_val,
        "Adjusted NPV": adjusted_val
    })

df_sens_recov = pd.DataFrame(sensitivity_recov)
print("\nSensitivity Analysis - Recovery Rate:")
print(df_sens_recov)

# ----------------------------
# 5. detailed cva breakdown table
# ----------------------------
df_cva = pd.DataFrame(base_cva_rows)
print("\nDetailed CVA Breakdown:")
print(df_cva[["Payment Date", "Exposure", "Discount Factor", "Survival Prob", "Default Prob", "Marginal CVA"]])

# %%
