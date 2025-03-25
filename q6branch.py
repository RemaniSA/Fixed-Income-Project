# %%
import QuantLib as ql
import numpy as np
import pandas as pd

from q1 import bond_characteristics
from q3 import build_curves

# ----------------------------
# 0. Setup
# ----------------------------

log_cubic_curve = build_curves()["Log-Cubic"]
spot_date = ql.Date(26, 11, 2024)
ql.Settings.instance().evaluationDate = spot_date
calendar = ql.TARGET()

# Bond details
notional = bond_characteristics["Nominal Value"]
cap = bond_characteristics["Cap"]
floor = bond_characteristics["Floor"]
settlement_lag = bond_characteristics["Settlement Lag"]
frequency = ql.Quarterly
convention = ql.ModifiedFollowing
issue_date = ql.Date(bond_characteristics["Issue Date"].day,
                     bond_characteristics["Issue Date"].month,
                     bond_characteristics["Issue Date"].year)
maturity_date = ql.Date(29, 7, 2027)

# Day counters
day_counter_curve = ql.Actual360()
day_counter_coupon = ql.Thirty360(ql.Thirty360.BondBasis)


# BNP CDS data (as of 26 Nov 2024)
base_cds_spread = 0.004921  # 49.21 bps
base_recovery_rate = 0.40   # 40%


# ----------------------------
# 1. Build coupon schedule
# ----------------------------

schedule = ql.Schedule(
    issue_date, maturity_date,
    ql.Period(frequency),
    calendar,
    convention, convention,
    ql.DateGeneration.Forward, False
)

# ----------------------------
# 2. Build variable exposure cashflows
# ----------------------------

def get_forward_rate_safe(start, end):
    safe_start = max(start, spot_date)
    if safe_start >= end:
        return 0.0
    return log_cubic_curve.forwardRate(safe_start, end, day_counter_curve, ql.Simple).rate()

exposure_rows = []

for i in range(len(schedule) - 1):
    start = schedule[i]
    end = schedule[i + 1]

    if end <= spot_date:
        continue

    if start < spot_date:
        reset_date = calendar.advance(start, -settlement_lag, ql.Days)
        start_for_fwd = reset_date if spot_date >= reset_date else spot_date
    else:
        start_for_fwd = start

    fwd_rate = get_forward_rate_safe(start_for_fwd, end)
    effective_rate = min(max(fwd_rate, floor), cap)
    yf = day_counter_coupon.yearFraction(start, end)
    coupon = notional * effective_rate * yf
    df = log_cubic_curve.discount(end)
    pv = coupon * df

    exposure_rows.append({
        "Payment Date": end,
        "Forward Rate (%)": fwd_rate * 100,
        "Effective Rate (%)": effective_rate * 100,
        "Coupon Amount": coupon,
        "Discount Factor": df,
        "Present Value": pv
    })

# Add redemption at maturity (only once)
df_redemption = log_cubic_curve.discount(maturity_date)
pv_redemption = notional * df_redemption
exposure_rows.append({
    "Payment Date": maturity_date,
    "Forward Rate (%)": None,
    "Effective Rate (%)": None,
    "Coupon Amount": notional,
    "Discount Factor": df_redemption,
    "Present Value": pv_redemption
})

df_variable_exposure = pd.DataFrame(exposure_rows)

# ----------------------------
# 3. Survival probability + CVA
# ----------------------------

def survival_prob(t, cds, R):
    return (np.exp(-cds * t) - R) / (1 - R)

def compute_cva(cds, R, df_exposure):
    cva = 0.0
    rows = []
    for _, row in df_exposure.iterrows():
        payment_date = row["Payment Date"]
        t = day_counter_curve.yearFraction(spot_date, payment_date)
        if t <= 0:
            continue
        exposure = row["Coupon Amount"]
        df = row["Discount Factor"]
        surv = survival_prob(t, cds, R)
        default_prob = 1 - surv
        marginal = exposure * default_prob * df
        cva += marginal
        rows.append({
            "Payment Date": payment_date,
            "Year Fraction": round(t, 4),
            "Exposure": exposure,
            "Discount Factor": df,
            "Survival Prob": surv,
            "Default Prob": default_prob,
            "Marginal CVA": marginal
        })
    return cva, rows



# Compute CVA using variable coupon exposures
base_cva, base_cva_rows = compute_cva(base_cds_spread, base_recovery_rate, df_variable_exposure)

# Compute risk-free and adjusted value
risk_free_npv = df_variable_exposure["Present Value"].sum()
adjusted_npv = risk_free_npv - base_cva

print("\n=== Base Case ===")
print(f"Risk-free Value:      {risk_free_npv:.4f}")
print(f"Total CVA:            {base_cva:.4f}")
print(f"Credit-adjusted Value:{adjusted_npv:.4f}")

# ----------------------------
# 4. Sensitivity Analysis
# ----------------------------

# CDS spread sensitivity
cds_values = np.linspace(0.002, 0.007, 6)
sensitivity_cds = []

for cds in cds_values:
    cva_val, _ = compute_cva(cds, base_recovery_rate, df_variable_exposure)
    adjusted_val = risk_free_npv - cva_val
    sensitivity_cds.append({
        "CDS Spread": cds,
        "CVA": cva_val,
        "Adjusted NPV": adjusted_val
    })

df_sens_cds = pd.DataFrame(sensitivity_cds)
print("\nSensitivity Analysis - CDS Spread:")
print(df_sens_cds)

# Recovery rate sensitivity
recov_values = np.linspace(0.30, 0.50, 5)
sensitivity_recov = []

for recov in recov_values:
    cva_val, _ = compute_cva(base_cds_spread, recov, df_variable_exposure)
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
# 5. CVA Breakdown Table
# ----------------------------

df_cva = pd.DataFrame(base_cva_rows)
print("\nDetailed CVA Breakdown:")
print(df_cva[["Payment Date", "Exposure", "Discount Factor", "Survival Prob", "Default Prob", "Marginal CVA"]])
# %%
