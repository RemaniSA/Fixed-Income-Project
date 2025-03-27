#%%

# %%
import matplotlib.pyplot as plt
import pandas as pd

from q1 import bond_characteristics
from q4 import df_best, df_worst  
from q6_14_15 import df_variable_exposure

# Prepare coupon-only data (exclude redemption)
def filter_coupon_only(df):
    return df[df["Coupon Amount"] < bond_characteristics["Nominal Value"]].copy()

df_best_coupons = filter_coupon_only(df_best)
df_worst_coupons = filter_coupon_only(df_worst)
df_realistic_coupons = df_variable_exposure[df_variable_exposure["Coupon Amount"] < bond_characteristics["Nominal Value"]].copy()
# df_realistic_coupons = df_realistic_coupons.iloc[:-1]

# Ensure Payment Date is datetime for sorting and plotting
df_best_coupons["Payment Date"] = df_best_coupons["End Date"].apply(lambda d: d.to_date())
df_worst_coupons["Payment Date"] = df_worst_coupons["End Date"].apply(lambda d: d.to_date())
df_realistic_coupons["Payment Date"] = df_realistic_coupons["Payment Date"].apply(lambda d: d.to_date())

# Merge into single DataFrame
df_q9 = pd.DataFrame({
    "Payment Date": df_best_coupons["Payment Date"],
    "Cap (Best Case)": df_best_coupons["Coupon Amount"].values,
    "Floor (Worst Case)": df_worst_coupons["Coupon Amount"].values,
    "Forward (Realistic)": df_realistic_coupons["Coupon Amount"].values
})

# Plot grouped bar chart
plt.figure(figsize=(12, 6))
bar_width = 0.25
x = range(len(df_q9))

plt.bar([p - bar_width for p in x], df_q9["Cap (Best Case)"], width=bar_width, label="Cap (Best Case)")
plt.bar(x, df_q9["Forward (Realistic)"], width=bar_width, label="Forward (Realistic)")
plt.bar([p + bar_width for p in x], df_q9["Floor (Worst Case)"], width=bar_width, label="Floor (Worst Case)")

plt.xticks(ticks=x, labels=[d.strftime("%b %Y") for d in df_q9["Payment Date"]], rotation=45)
plt.ylabel("Coupon Amount (€)")
plt.title("Q9: Expected Coupon Cash Flows (Cap vs Floor vs Forward)")
plt.legend()
plt.grid(axis='y')
plt.tight_layout()
plt.show()
# %%
