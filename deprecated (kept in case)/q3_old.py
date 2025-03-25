#%%
import os
import sys
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import re

ROOT_PATH = os.path.dirname(__file__)
market_data_file_path = os.path.join(ROOT_PATH, 'datasets', 'MarketData.xlsx')

def bootstrap_deposits(df_deposits):
    """
    Bootstraps discount factors from deposit rates.
    df_deposits is expected to have columns: "RIC" and "Last".
    Uses a mapping from deposit RIC to maturity (in years).
    Ignores OND and TND deposits as spot lag is 2 days.
    """
    deposit_maturities_map = {
        "EURSWD=": 7/360,   # EURIBOR uses ACT/360 DCC
        "EUR1MD=": 1/12,    # 1 Month deposit
        "EUR3MD=": 3/12,    # 3 Month deposit
        "EUR6MD=": 6/12,    # 6 Month deposit
        "EUR9MD=": 9/12,    # 9 Month deposit
        "EUR1YD=": 1        # 1 Year deposit
    }
    
    deposit_dfs = {}
    for idx, row in df_deposits.iterrows():
        ric = row["RIC"]
        if ric in deposit_maturities_map:
            T = deposit_maturities_map[ric]
            r = row["Last"] / 100.0  # Convert percentage to decimal
            DF = 1.0 / (1 + r * T)
            deposit_dfs[T] = DF
        else:
            print(f"Warning: RIC {ric} not found in deposit maturities mapping.")
    return deposit_dfs

def extract_swap_maturity(ric):
    """
    Extracts the maturity in years from the swap RIC.
    e.g.: "EURAB3E1Y=TWEB" returns 1, "EURAB3E10Y=TWEB" returns 10.
    """
    match = re.search(r'(\d+)Y', ric)
    if match:
        return float(match.group(1))
    else:
        raise ValueError(f"Could not extract maturity from RIC: {ric}")

def interpolate_df(known_dfs, t):
    """
    Interpolates (or extrapolates) a discount factor for time t using continuously compounded zero rates.
    known_dfs: dictionary of known discount factors {maturity: DF}
    If t exceeds the maximum known maturity, perform constant extrapolation using the last known zero rate.
    """
    maturities = sorted(known_dfs.keys())
    # if t > maturities[-1]:
    #     t_low = maturities[-1]
    #     DF_low = known_dfs[t_low]
    #     r_low = -np.log(DF_low) / t_low
    #     DF_t = np.exp(-r_low * t)
    #     return DF_t
    else:
        t_low = max([m for m in maturities if m < t], default=None)
        t_high = min([m for m in maturities if m > t], default=None)
        if t_low is None or t_high is None:
            raise ValueError(f"Cannot interpolate discount factor for t = {t}.")
        DF_low = known_dfs[t_low]
        DF_high = known_dfs[t_high]
        r_low = -np.log(DF_low) / t_low
        r_high = -np.log(DF_high) / t_high
        r_t = r_low + (r_high - r_low) * ((t - t_low) / (t_high - t_low))
        DF_t = np.exp(-r_t * t)
        return DF_t

def bootstrap_swaps(df_swaps, known_dfs, frequency=1):
    """
    Bootstraps discount factors from IRS rates.
    df_swaps has columns: "RIC", "Name", "Last".
    known_dfs is a dictionary containing discount factors from deposits.
    frequency is the number of payments per year.
    """
    swap_dfs = {}
    for idx, row in df_swaps.iterrows():
        ric = row["RIC"]
        T = extract_swap_maturity(ric)
        S = row["Last"] / 100.0  # Convert percentage to decimal
        N = int(T * frequency)  # Number of coupon payments
        delta = 1.0 / frequency
        
        sum_df = 0.0
        for i in range(1, N):
            t_i = i * delta
            if t_i in known_dfs:
                DF_i = known_dfs[t_i]
            else:
                DF_i = interpolate_df(known_dfs, t_i)
            sum_df += DF_i * delta
        
        DF_T = (1 - S * sum_df) / (1 + S * delta)
        swap_dfs[T] = DF_T
        # Update the known discount factors with the newly computed DF for maturity T
        known_dfs[T] = DF_T
        
    return swap_dfs

def compute_zero_rates(discount_factors):
    """
    Computes continuously compounded zero rates from discount factors.
    discount_factors: dictionary {maturity (years): DF}
    """
    zero_rates = {}
    for T, DF in discount_factors.items():
        r = -np.log(DF) / T
        zero_rates[T] = r
    return zero_rates

def compute_forward_rates(discount_factors):
    """
    Computes forward rates for each interval between consecutive maturities.
    Assumes the discount factor at time 0 is 1.
    For each interval [T_{i-1}, T_i], the forward rate is computed as:
        F = (P(0, T_{i-1}) / P(0, T_i) - 1) / (T_i - T_{i-1}).
    Returns a dictionary mapping the interval end (T_i) to the forward rate.
    """
    if 0.0 not in discount_factors:
        discount_factors[0.0] = 1.0
    sorted_maturities = sorted(discount_factors.keys())
    forward_rates = {}
    for i in range(1, len(sorted_maturities)):
        T_prev = sorted_maturities[i-1]
        T_curr = sorted_maturities[i]
        dt = T_curr - T_prev
        F = (discount_factors[T_prev] / discount_factors[T_curr] - 1) / dt
        forward_rates[T_curr] = F
    return forward_rates

def main():
    market_data = pd.ExcelFile(market_data_file_path)
    df_deposits = market_data.parse("Deposit Rates")
    df_swaps = market_data.parse("IRS Rates")
    
    df_swaps["Maturity"] = df_swaps["RIC"].apply(extract_swap_maturity)
    df_swaps = df_swaps.sort_values("Maturity")
    
    # Compute deposit discount factors
    deposit_dfs = bootstrap_deposits(df_deposits)
    
    # Compute swap discount factors (using a copy of deposit_dfs as starting point)
    swap_dfs = bootstrap_swaps(df_swaps, deposit_dfs.copy(), frequency=1)
    
    # Merge the two sets explicitly
    discount_factors = deposit_dfs.copy()
    discount_factors.update(swap_dfs)
    
    # Compute zero rates from the merged discount factors
    zero_rates = compute_zero_rates(discount_factors)
    
    # Prepare DataFrame for zero curve plot
    maturities = sorted(zero_rates.keys())
    df_zero = pd.DataFrame({
        "Maturity (Years)": maturities,
        "Zero Rate (%)": [zero_rates[t] * 100 for t in maturities]
    })
    
    print("Bootstrapped Zero Rates:")
    print(df_zero)
    
    plt.figure(figsize=(10, 6))
    plt.plot(df_zero["Maturity (Years)"], df_zero["Zero Rate (%)"], marker='o', linestyle='-')
    plt.xlabel("Maturity (Years)")
    plt.ylabel("Zero Rate (%)")
    plt.title("Bootstrapped Zero Curve")
    plt.grid(True)
    plt.show()
    
    # Prepare DataFrame for discount factors curve plot
    df_discount = pd.DataFrame({
        "Maturity (Years)": sorted(discount_factors.keys()),
        "Discount Factor": [discount_factors[t] for t in sorted(discount_factors.keys())]
    })
    
    print("Bootstrapped Discount Factors:")
    print(df_discount)
    
    plt.figure(figsize=(10, 6))
    plt.plot(df_discount["Maturity (Years)"], df_discount["Discount Factor"], marker='o', linestyle='-')
    plt.xlabel("Maturity (Years)")
    plt.ylabel("Discount Factor")
    plt.title("Bootstrapped Discount Factor Curve")
    plt.grid(True)
    plt.show()
    
    # Compute and plot the forward curve

    forward_rates = compute_forward_rates(discount_factors)
    sorted_forward = sorted(forward_rates.items())
    df_forward = pd.DataFrame(sorted_forward, columns=["Maturity (Years)", "Forward Rate"])
    df_forward["Forward Rate (%)"] = df_forward["Forward Rate"] * 100
    
    print("Bootstrapped Forward Rates:")
    print(df_forward)
    
    plt.figure(figsize=(10, 6))
    plt.plot(df_forward["Maturity (Years)"], df_forward["Forward Rate (%)"], marker='o', linestyle='-')
    plt.xlabel("Maturity (Years)")
    plt.ylabel("Forward Rate (%)")
    plt.title("Bootstrapped Forward Rate Curve")
    plt.grid(True)
    plt.show()

if __name__ == "__main__":
    main()
# %%
