#%%
import numpy as np
from scipy.optimize import brentq

from q1 import bond_characteristics
from q6 import compute_cva
from q8 import model_clean_price
from q6 import df_variable_exposure

# ----------------------------
# 1. Setup known values
# ----------------------------

market_price_per_100= 98.43
notional=bond_characteristics["Nominal Value"]

market_clean_price = market_price_per_100 * notional/100
recovery_rate = 0.40  # As per coursework

# ----------------------------
# 2. Define root-finding target
# ----------------------------

def price_difference(cds_spread):
    """
    Target: find CDS spread where model_clean_price - CVA(cds) ≈ market_clean_price
    """
    cva, _ = compute_cva(cds_spread, recovery_rate, df_variable_exposure)
    return model_clean_price - cva - market_clean_price

# ----------------------------
# 3. Run solver
# ----------------------------

cds_solution = brentq(price_difference, 0.001, 0.10)  # Search between 10 and 1000 bps
implied_cva, _ = compute_cva(cds_solution, recovery_rate,df_variable_exposure)
credit_adjusted_price = model_clean_price - implied_cva

# ----------------------------
# 4. Output result
# ----------------------------

print("\n=== Q10: Market-Implied CDS Spread ===")
print(f"Implied CDS Spread:       {cds_solution * 10000:.2f} bps")
print(f"Model Clean Price:        {model_clean_price:.4f}")
print(f"Market Clean Price:       {market_clean_price:.4f}")
print(f"Implied CVA:              {implied_cva:.4f}")
print(f"Credit-Adjusted Price:    {credit_adjusted_price:.4f}")
print(f"Pricing Error:            {credit_adjusted_price - market_clean_price:.6f}")

# %%
