# %%
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from datetime import datetime

# -------------------
# bond characteristics
# -------------------
bond_characteristics = {
    'Issuer': 'BNP Paribas',
    'Bond Name': 'Variable Rate Bond 2033',
    'ISIN': 'XS2392609181',
    'Currency': 'EUR',
    'Nominal Value': 1000,
    'Issue Price': 1000,
    'Issue Date': pd.Timestamp('2022-07-29'), 
    'Maturity Date': pd.Timestamp('2027-07-29'),
    'Trade Date': pd.Timestamp('2024-11-24'), 
    'Coupon Rate': '3M Euribor',
    'Floor': 0.016,  
    'Cap': 0.037, 
    'Coupon Frequency': 4,
    'Interest Payment Dates': ['29/01', '29/04', '29/07', '29/10'],
    'Settlement Lag': 2,
    'Business Day Convention (Interest Payment)': 'Modified Following',
    'Business Day Convention (Maturity Date)': 'Modified Following',
    'Day Count Convention (Days in Month)': 30,
    'Day Count Convention (Days in Year)': 360,
    'Redemption Type': 'At Par',
    'Credit Rating': 'AA-',
    'Listing': 'EuroTLX Listing'
}

def get_next_payment_date(trade_date, payment_dates):
    """
    Given a trade date (datetime) and a list of interest payment dates (as 'DD/MM' strings),
    return the next interest payment date as a datetime object.
    """
    year = trade_date.year
    candidates = []
    for date_str in payment_dates:
        day, month = map(int, date_str.strip().split('/'))
        candidate = datetime(year, month, day)
        candidates.append(candidate)
    
    future_dates = [d for d in candidates if d > trade_date]
    
    if future_dates:
        return min(future_dates)
    else:
        day, month = map(int, payment_dates[0].strip().split('/'))
        return datetime(year + 1, month, day)

def coupon_payoff(r, floor, cap):
    return np.minimum(np.maximum(r, floor), cap)

def main():
    # -------------------
    # key dates
    # -------------------
    trade_date = bond_characteristics['Trade Date']
    spot_lag = 2
    value_date = trade_date + pd.Timedelta(days=spot_lag)

    # date of first interest payment
    first_interest_payment_date = get_next_payment_date(trade_date, bond_characteristics['Interest Payment Dates'])

    key_dates = {
        "Trade Date": trade_date,
        "Spot Lag (days)": spot_lag,
        "Value Date": value_date,
        "First Interest Payment Date": first_interest_payment_date
    }

    df_key_dates = pd.DataFrame(list(key_dates.items()), columns=["Key Date", "Value"])
    print(df_key_dates)

    # create dataframe of bond char.
    df_bond = pd.DataFrame(list(bond_characteristics.items()), columns=["Characteristic", "Value"])
    df_bond.set_index("Characteristic", inplace=True)

    # -------------------
    # cap and floor the ref. rate
    # -----------------
    floor = bond_characteristics['Floor']
    cap = bond_characteristics['Cap']
    euribor_range = np.arange(0, 0.0501, 0.001)

    coupon_values = coupon_payoff(euribor_range, floor, cap)

    df_coupon_payoff = pd.DataFrame({
        "Euribor Rate (%)": euribor_range * 100,
        "Coupon Payoff (%)": coupon_values * 100
    })

    print(df_coupon_payoff)

    # -------------------
    # plot coupon payoff vs 3M euribor rate
    # ----------------
    plt.figure(figsize=(10, 6))
    plt.axhline(y=cap * 100, color='red', linestyle='--', label='Cap (3.70%)')
    plt.axhline(y=floor * 100, color='green', linestyle='--', label='Floor (1.60%)')
    sns.lineplot(x="Euribor Rate (%)", y="Coupon Payoff (%)", data=df_coupon_payoff, label="Coupon Payoff", linewidth=2)
    plt.xlabel("3M Euribor Rate (%)")
    plt.ylabel("Coupon Payoff (%)")
    plt.title("Coupon Payoff vs 3M Euribor Rate (With Floor & Cap)")
    plt.legend()
    plt.tight_layout()
    plt.show()

if __name__ == "__main__":
    main()

# %%
