# %%
import os
import pandas as pd
import matplotlib.pyplot as plt
import numpy as np
import QuantLib as ql

from q1 import bond_characteristics
from q3 import build_curves

# -----------------
# 0. setup paths and curve
# ------------------

ROOT_PATH = os.path.dirname(__file__).replace('code','')
df_curve = build_curves()["Log-Cubic"]

# -----------------
# 1. bond settings
# ----------------

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
day_counter = ql.Thirty360(ql.Thirty360.BondBasis)
eval_date = ql.Settings.instance().evaluationDate
# coupon_date = ql.Date(29, 1, 2025)

# -----------------
# 2. build schedule (patched)
# ------------------

schedule = ql.Schedule(
    issue_date, maturity_date,
    ql.Period(frequency),
    calendar,
    convention, convention,
    ql.DateGeneration.Forward, False
)


# -----------------
# 3. helper to build cash flows
# ------------------

def generate_cashflows(rate):
    """
    Generates a DataFrame of cashflows for a given coupon rate,
    including final coupon and notional repayment at maturity.
    """
    cashflows = []

    for i in range(len(schedule) - 1):
        start = schedule[i]
        end = schedule[i + 1]

        if end < eval_date:
            continue  # skip past cash flows

        yf = day_counter.yearFraction(start, end)
        cpn = notional * rate * yf
        discount = df_curve.discount(end)

        cashflows.append({
            "Start Date": start,
            "End Date": end,
            "Year Fraction": yf,
            "Coupon Rate (%)": rate * 100,
            "Coupon Amount": cpn,
            "Discount Factor": discount,
            "PV": cpn * discount
    })


    # # Add notional redemption at maturity
    # discount_redemption = df_curve.discount(maturity_date)
    # cashflows.append({
    #     "Start Date": maturity_date,
    #     "End Date": maturity_date,
    #     "Year Fraction": 0.0,
    #     "Coupon Rate (%)": None,
    #     "Coupon Amount": notional,
    #     "Discount Factor": discount_redemption,
    #     "PV": notional * discount_redemption
    # })

    return pd.DataFrame(cashflows)

# ------------------
# 4. expose values for import
# ------------------

df_best = generate_cashflows(cap)
df_worst = generate_cashflows(floor)

# ------------------
# 5. main script block
# ------------------


if __name__=='__main__':
    def filter_coupon_only(df):
        return df[df["Coupon Amount"] < bond_characteristics["Nominal Value"]].copy()

    df_best_coupons = filter_coupon_only(df_best)
    df_worst_coupons = filter_coupon_only(df_worst)


    npv_best = df_best["PV"].sum()
    npv_worst = df_worst["PV"].sum()

    print("best case NPV (cap rate):", round(npv_best, 4))
    print("worst case NPV (floor rate):", round(npv_worst, 4))

    # plot coupon comparison
    labels = [end.to_date() for end in df_best["End Date"]]
    x = np.arange(len(labels))
    width = 0.4

    plt.figure(figsize=(10, 5))
    plt.bar(x - width/2, df_best["Coupon Amount"], width=width, label="Best Case (Cap)", alpha=0.7)
    plt.bar(x + width/2, df_worst["Coupon Amount"], width=width, label="Worst Case (Floor)", alpha=0.7)
    plt.xticks(x, [d.strftime('%Y-%m-%d') for d in labels], rotation=45)
    plt.ylabel("Coupon Amount")
    plt.xlabel("Payment Date")
    plt.title("Future Coupon Comparison: Cap vs Floor Scenarios")
    plt.legend()
    plt.grid(True)
    plt.tight_layout()
    plt.show()

    # show tables
    print("\nBest Case cash flows (cap rate):")
    print(df_best[["Start Date", "End Date", "Coupon Rate (%)", "Coupon Amount", "Discount Factor", "PV"]])

    print("\nWorst Case cash flows (floor rate):")
    print(df_worst[["Start Date", "End Date", "Coupon Rate (%)", "Coupon Amount", "Discount Factor", "PV"]])


# %%
