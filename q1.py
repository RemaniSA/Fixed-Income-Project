# %%
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from datetime import datetime

# %%
# -------------------
# Key Dates
# -------------------

trade_date = pd.to_datetime("24/11/2024", dayfirst=True)  # pandas Timestamp
spot_lag = 2
value_date = trade_date + pd.Timedelta(days=spot_lag)

# %%
# -------------------------------
# Bond Characteristics DataFrame
# -------------------------------
bond_characteristics = {
    'Issuer': 'BNP Paribas',
    'Bond Name': 'Variable Rate Bond 2033',
    'ISIN': 'XS2392609181',
    'Currency': 'EUR',
    'Nominal Value': 1000,
    'Issue Price': 1000,
    'Issue Date': pd.Timestamp('2022-07-29'), 
    'Maturity Date': pd.Timestamp('2027-07-29'), 
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

# Convert to DataFrame
df_bond = pd.DataFrame(list(bond_characteristics.items()), columns=["Characteristic", "Value"])
df_bond.set_index("Characteristic", inplace=True)

# %%

def get_next_payment_date(trade_date: datetime, payment_dates: list[str]) -> datetime:
    """
    Given a trade date (datetime) and a list of interest payment dates (as 'DD/MM' strings),
    return the next interest payment date as a datetime object.
    """
    year = trade_date.year

    # Generate datetime objects for this year
    candidates = []
    for date_str in payment_dates:
        day, month = map(int, date_str.strip().split('/'))
        candidate = datetime(year, month, day)
        candidates.append(candidate)
    
    # Filter future ones
    future_dates = [d for d in candidates if d > trade_date]
    
    if future_dates:
        return min(future_dates)
    else:
        # Roll over to next year using the first date in list
        day, month = map(int, payment_dates[0].strip().split('/'))
        return datetime(year + 1, month, day)


# %%
# Calculate the first interest payment date
first_interest_payment_date = get_next_payment_date(trade_date, bond_characteristics['Interest Payment Dates'])

key_dates = {
    "Trade Date": trade_date,
    "Spot Lag (days)": spot_lag,
    "Value Date": value_date,
    "First Interest Payment Date": first_interest_payment_date
}

# Display as DataFrame
df_key_dates = pd.DataFrame(list(key_dates.items()), columns=["Key Date", "Value"])
print(df_key_dates)

# %%
# Replicating Coupon Payoffs
# Long a Floating Rate Note (FRN) -> pays the Euribor rate
# Long a Floor -> ensures the coupon doesn’t go below 1.60%
# Short a Cap -> limits the coupon from exceeding 3.70%

# %%
# -------------------
# Visualise Coupon Payoff
# -------------------

# Floor and Cap are already defined
floor = bond_characteristics['Floor']
cap = bond_characteristics['Cap']

# Euribor range (0% to 5%)
euribor_range = np.arange(0, 0.0501, 0.001)

# Coupon payoff function
def coupon_payoff(r, floor, cap):
    return np.min(np.max(r, floor), cap)

coupon_values = coupon_payoff(euribor_range, floor, cap)

# Combine into DataFrame for table view
df_coupon_payoff = pd.DataFrame({
    "Euribor Rate (%)": euribor_range * 100,
    "Coupon Payoff (%)": coupon_values * 100
})

# Display as DataFrame
print(df_coupon_payoff)

# Visualise coupon payoff

sns.set(style="whitegrid", context="notebook")
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
# %%
