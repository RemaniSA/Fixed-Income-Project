#%%
import QuantLib as ql
import pandas as pd
from q1 import bond_characteristics
from q3 import build_curves

# --- Setup ---
log_cubic_curve = build_curves()["Log-Cubic"]
eval_date = ql.Date(18, 11, 2024)  # same as eval_date
ql.Settings.instance().evaluationDate = eval_date
calendar = ql.TARGET()
convention = ql.ModifiedFollowing
frequency = ql.Quarterly
settlement_lag = bond_characteristics["Settlement Lag"]
notional = bond_characteristics["Nominal Value"]
cap = bond_characteristics["Cap"]
floor = bond_characteristics["Floor"]

issue_date = ql.Date(bond_characteristics["Issue Date"].day,
                     bond_characteristics["Issue Date"].month,
                     bond_characteristics["Issue Date"].year)
maturity_date = ql.Date(29, 7, 2027)

schedule = ql.Schedule(
    issue_date, maturity_date,
    ql.Period(frequency),
    calendar,
    convention, convention,
    ql.DateGeneration.Forward, False
)

day_counter_curve = ql.Actual360()
day_counter_coupon = ql.Thirty360(ql.Thirty360.BondBasis)

# --- Safe forward rate helper ---
def get_forward_rate(start, end):
    # Ensure we're not asking for forward rates before the curve starts
    safe_start = max(start, eval_date)
    if safe_start >= end:
        return 0.0
    return log_cubic_curve.forwardRate(safe_start, end, day_counter_curve, ql.Simple).rate()

# --- Cash flow calculation ---
cf_rows = []

for i in range(len(schedule) - 1):
    start = schedule[i]
    end = schedule[i + 1]

    if end <= eval_date:
        continue

    # Use reset date if we're in the current coupon period
    if start < eval_date:
        reset_date = calendar.advance(start, -settlement_lag, ql.Days)
        start_for_fwd = reset_date if eval_date >= reset_date else eval_date
    else:
        start_for_fwd = start

    fwd_rate = get_forward_rate(start_for_fwd, end)
    effective_rate = min(max(fwd_rate, floor), cap)
    yf = day_counter_coupon.yearFraction(start, end)
    coupon = notional * effective_rate * yf
    df = log_cubic_curve.discount(end)
    pv = coupon * df

    cf_rows.append({
        "Payment Date": end,
        "Forward Rate (%)": round(fwd_rate * 100, 4),
        "Effective Rate (%)": round(effective_rate * 100, 4),
        "Coupon Amount": round(coupon, 4),
        "Discount Factor": round(df, 6),
        "Present Value": round(pv, 4)
    })

# --- Redemption at Maturity ---
df_redemption = log_cubic_curve.discount(maturity_date)
pv_redemption = notional * df_redemption
cf_rows.append({
    "Payment Date": maturity_date,
    "Forward Rate (%)": None,
    "Effective Rate (%)": None,
    "Coupon Amount": notional,
    "Discount Factor": round(df_redemption, 6),
    "Present Value": round(pv_redemption, 4)
})

coupon_table = pd.DataFrame(cf_rows)

# --- Accrued Interest ---
accrued = 0.0
for i in range(len(schedule) - 1):
    start = schedule[i]
    end = schedule[i + 1]
    if start < eval_date <= end:
        reset_date = calendar.advance(start, -settlement_lag, ql.Days)
        start_for_fwd = reset_date if eval_date >= reset_date else eval_date
        fwd_rate = get_forward_rate(start_for_fwd, end)
        effective_rate = min(max(fwd_rate, floor), cap)
        yf_accrued = day_counter_coupon.yearFraction(start, eval_date)
        accrued = notional * effective_rate * yf_accrued
        break

# --- Prices ---
model_gross_price = coupon_table["Present Value"].sum()
model_clean_price = model_gross_price - accrued

def main():
    # --- Output ---
    print("\nQ8: Forward Rate-Based Coupon Table (Including Redemption)")
    print(coupon_table)

    print("\nBond Pricing Summary:")
    print(f"Gross Price (Dirty): {round(model_gross_price, 4)}")
    print(f"Accrued Interest:    {round(accrued, 4)}")
    print(f"Clean Price:         {round(model_clean_price, 4)}")

if __name__ == "__main__":
    main()

# %%
