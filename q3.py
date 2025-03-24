# %%
import os
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import math
import re

# ========= Configuration and File Paths =========
ROOT_PATH = os.path.dirname(__file__)
market_data_file_path = os.path.join(ROOT_PATH, 'datasets', 'MarketData.xlsx')
bootstrap_method = "CFR"  # Set "LSR" for Linear Swap Rate or "CFR" for Constant Forward Rate

# ========= Read Data from Excel =========
# Read deposit and IRS sheets
deposits_df = pd.read_excel(market_data_file_path, sheet_name="Deposit Rates")
irs_df = pd.read_excel(market_data_file_path, sheet_name="IRS Rates")

# ========= Helper Functions for Maturities =========
def maturity_from_deposit(ric):
    """
    Map deposit RIC to maturity in years using ACT/360 assumptions:
      - EURSWD: ~7 days  -> 7/360 years,
      - EUR1MD: 30 days -> 30/360,
      - EUR3MD: 90 days -> 90/360,
      - EUR6MD: 180 days -> 180/360,
      - EUR9MD: 270 days -> 270/360,
      - EUR1YD: 360 days -> 1 year.
    """
    if "SWD" in ric:
        return 7/360
    elif "1MD" in ric:
        return 30/360
    elif "3MD" in ric:
        return 90/360
    elif "6MD" in ric:
        return 180/360
    elif "9MD" in ric:
        return 270/360
    elif "1YD" in ric:
        return 1.0
    else:
        return None

def maturity_from_irs(name):
    """
    Extract integer maturity (in years) from IRS instrument name,
    e.g., "EUR  5Y AB3E IRS" returns 5.
    """
    m = re.search(r'(\d+)(?=Y)', name)
    return int(m.group(1)) if m else None

# ========= Process Deposit Rates =========
# We ignore the first two rows (OND and TND) due to spot lag.
deposit_data = deposits_df.iloc[2:].copy()
deposit_data['T'] = deposit_data['RIC'].apply(maturity_from_deposit)
# Calculate discount factors using simple interest:
# P(0, T) = 1 / (1 + (rate/100) * T)
deposit_data['Discount_Factor'] = 1 / (1 + deposit_data['Last'] / 100 * deposit_data['T'])
# Save deposit discount factors (using T as key)
deposit_discount_factors = {}
for _, row in deposit_data.iterrows():
    T = row['T']
    if T is not None:
        deposit_discount_factors[T] = row['Discount_Factor']

# ========= Process IRS Swap Rates =========
irs_df['T'] = irs_df['Name'].apply(maturity_from_irs)
irs_df = irs_df.dropna(subset=['T'])
irs_df.sort_values(by='T', inplace=True)
# Save quoted IRS rates in dictionary (convert percentage to decimal)
irs_rates = {}
for _, row in irs_df.iterrows():
    T = int(row['T'])
    rate = row['Last'] / 100.0
    irs_rates[T] = rate

# ========= Bootstrapping Helper Functions =========
def bootstrap_discount_factor_IRS(S, T, previous_discount_factors, alpha=1.0):
    """
    Calculate discount factor P(0,T) using:
       1 = S * [sum_{i=1}^{T-1} (alpha * P(0,i)] + (1 + S * alpha) * P(0,T)
    Rearranged as:
       P(0,T) = (1 - S * sum_{i=1}^{T-1} (alpha * P(0,i))) / (1 + S * alpha)
    """
    annuity = sum(alpha * previous_discount_factors[t] for t in sorted(previous_discount_factors.keys()) if t < T)
    return (1 - S * annuity) / (1 + S * alpha)

def interpolate_LSR(S_a, S_b, T_a, T_b, T):
    """
    Linear Swap Rate (LSR) interpolation:
      S_T = ((T_b - T) / (T_b - T_a)) * S_a + ((T - T_a) / (T_b - T_a)) * S_b
    """
    return ((T_b - T) / (T_b - T_a)) * S_a + ((T - T_a) / (T_b - T_a)) * S_b

def solve_constant_forward(x_low, x_high, f, tol=1e-8, max_iter=100):
    """
    Bisection solver to find x in [x_low, x_high] such that f(x) = 0.
    """
    for _ in range(max_iter):
        x_mid = (x_low + x_high) / 2.0
        f_mid = f(x_mid)
        if abs(f_mid) < tol:
            return x_mid
        if f(x_low) * f_mid < 0:
            x_high = x_mid
        else:
            x_low = x_mid
    return x_mid

def solve_cfr(P_a, ann_a, S_target, delta):
    """
    Solve for constant forward rate F (and corresponding x = 1/(1+F)) over an interval of delta years.
    Given:
       P_a   : discount factor at T_a,
       ann_a : annuity (cumulative discount factors) up to T_a,
       S_target : quoted swap rate for T_b (in decimal),
       delta : T_b - T_a.
       
    We solve for x in:
       f(x) = S_target*(ann_a + P_a*(x*(1 - x**delta))/(1 - x)) - (1 - P_a*x**delta) = 0.
       
    Returns:
       F : constant forward rate (F = 1/x - 1),
       xs: list of discount factors for each year in the interval.
    """
    def f(x):
        if abs(1 - x) < 1e-8:
            summation = delta * x
        else:
            summation = x * (1 - x**delta) / (1 - x)
        return S_target * (ann_a + P_a * summation) - (1 - P_a * x**delta)
    
    # x is expected to lie in (0,1). We bracket the solution:
    x_low, x_high = 0.8, 1.0
    x_solution = solve_constant_forward(x_low, x_high, f)
    F = 1 / x_solution - 1
    # Compute discount factors for each missing year in the interval:
    xs = [P_a * (x_solution ** i) for i in range(1, delta + 1)]
    return F, xs

# ========= Bootstrapping Procedure =========
# We maintain two dictionaries:
#   bootstrapped_discount_factors: discount factor for each maturity T (integer years)
#   annuity: cumulative sum of discount factors up to T
bootstrapped_discount_factors = {}
annuity = {}

# Use deposit discount factor for T = 1.0 (assumed available)
if 1.0 in deposit_discount_factors:
    bootstrapped_discount_factors[1] = deposit_discount_factors[1.0]
    annuity[1] = deposit_discount_factors[1.0]
else:
    raise ValueError("1-year deposit rate is required for bootstrapping.")

max_maturity = 60
for T in range(2, max_maturity + 1):
    if T in irs_rates:
        # When a quoted IRS rate is available:
        S = irs_rates[T]
        P_T = bootstrap_discount_factor_IRS(S, T, bootstrapped_discount_factors, alpha=1.0)
        bootstrapped_discount_factors[T] = P_T
        annuity[T] = annuity.get(T-1, 0) + P_T
    else:
        # For missing IRS quotes, identify the surrounding maturities with quotes.
        quoted_maturities = sorted(irs_rates.keys())
        lower_candidates = [m for m in quoted_maturities if m < T]
        upper_candidates = [m for m in quoted_maturities if m > T]
        if lower_candidates and upper_candidates:
            T_prev = max(lower_candidates)
            T_next = min(upper_candidates)
        else:
            # Fallback: use previous discount factor if no proper interval is found.
            bootstrapped_discount_factors[T] = bootstrapped_discount_factors[T - 1]
            annuity[T] = annuity.get(T-1, 0) + bootstrapped_discount_factors[T]
            continue

        # If using LSR or if required data for CFR is missing, fallback to LSR:
        if bootstrap_method.upper() == "LSR" or T_prev not in bootstrapped_discount_factors:
            S_prev = irs_rates[T_prev]
            S_next = irs_rates[T_next]
            S_interpolated = interpolate_LSR(S_prev, S_next, T_prev, T_next, T)
            P_T = bootstrap_discount_factor_IRS(S_interpolated, T, bootstrapped_discount_factors, alpha=1.0)
            bootstrapped_discount_factors[T] = P_T
            annuity[T] = annuity.get(T-1, 0) + P_T
        elif bootstrap_method.upper() == "CFR":
            # Use CFR interpolation over the interval [T_prev, T_next].
            delta = T_next - T_prev
            P_a = bootstrapped_discount_factors[T_prev]
            ann_a = annuity[T_prev]
            S_target = irs_rates[T_next]
            F_const, interp_DFs = solve_cfr(P_a, ann_a, S_target, delta)
            # Fill in all missing maturities in [T_prev+1, T_next]:
            for i, T_missing in enumerate(range(T_prev + 1, T_next + 1)):
                bootstrapped_discount_factors[T_missing] = interp_DFs[i]
                annuity[T_missing] = annuity.get(T_missing - 1, 0) + interp_DFs[i]
        else:
            raise ValueError("Invalid bootstrap_method specified. Use 'LSR' or 'CFR'.")

# ========= Calculate Spot Rates =========
# Continuously compounded spot rates: r(0,T) = -ln(P(0,T)) / T
spot_rates = {}
for T, P in bootstrapped_discount_factors.items():
    if P > 0:
        spot_rates[T] = -math.log(P) / T
    else:
        spot_rates[T] = np.nan

# ========= Calculate Forward Rates =========
# Compute forward rates between consecutive maturities:
# f(T, T+1) = -ln(P(0,T+1)/P(0,T))
forward_rates = {}
sorted_maturities = sorted(bootstrapped_discount_factors.keys())
for i in range(len(sorted_maturities) - 1):
    T = sorted_maturities[i]
    T_next = sorted_maturities[i + 1]
    P_T = bootstrapped_discount_factors[T]
    P_T_next = bootstrapped_discount_factors[T_next]
    if P_T > 0 and P_T_next > 0:
        fwd_rate = -math.log(P_T_next / P_T) / (T_next - T)
    else:
        fwd_rate = np.nan
    forward_rates[(T, T_next)] = fwd_rate

# ========= Output the Results =========
print("\nSpot Rates and Discount Factors:")
print("Maturity (Years) | Spot Rate (%) | Discount Factor")
for T in sorted(spot_rates.keys()):
    print(f"{T:>16} | {spot_rates[T]*100:>13.3f} | {bootstrapped_discount_factors[T]:>16.6f}")

print("\nForward Rates (Continuously Compounded):")
print("From (Years) | To (Years) | Forward Rate (%)")
for (T, T_next), rate in sorted(forward_rates.items()):
    print(f"{T:>12} | {T_next:>9} | {rate*100:>14.3f}")

# ======= Plot the Results =======

# Plot the discount factors
plt.figure(figsize=(10, 6))
plt.plot(list(bootstrapped_discount_factors.keys()), list(bootstrapped_discount_factors.values()), 'bo-')
plt.title("Bootstrapped Discount Factors")
plt.xlabel("Maturity (Years)")
plt.ylabel("Discount Factor")
plt.grid(True)
plt.show()

# Plot the spot rates
plt.figure(figsize=(10, 6))
plt.plot(list(spot_rates.keys()), [r * 100 for r in spot_rates.values()], 'ro-')
plt.title("Bootstrapped Spot Rates")
plt.xlabel("Maturity (Years)")
plt.ylabel("Spot Rate (%)")
plt.grid(True)
plt.show()

# Plot the forward rates

# Extract only the start of each forward rate interval
start_years = [start for (start, end) in forward_rates.keys()]
rates = [r * 100 for r in forward_rates.values()]  # Convert to percentage

# Plot
plt.figure(figsize=(10, 6))
plt.plot(start_years, rates, 'go-')
plt.title("Bootstrapped Forward Rates")
plt.xlabel("Start of Forward Period (Years)")
plt.ylabel("Forward Rate (%)")
plt.grid(True)
plt.show()

#%%

df