#%%
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from scipy.stats import norm

# CDS sensitivity from q6
q6data = [
    {"CDS Spread": 0.002, "Adjusted NPV": 991.779335},
    {"CDS Spread": 0.003, "Adjusted NPV": 987.382883},
    {"CDS Spread": 0.004, "Adjusted NPV": 982.998305},
    {"CDS Spread": 0.005, "Adjusted NPV": 978.625570},
    {"CDS Spread": 0.006, "Adjusted NPV": 974.264644},
    {"CDS Spread": 0.007, "Adjusted NPV": 969.915497}
]

CDSsens = pd.DataFrame(q6data)

# Calculate price sensitivity (first-order forward difference)
CDSsens["Sensitivity"] = CDSsens["Adjusted NPV"].diff() / CDSsens["CDS Spread"].diff()

# Sensitivity per basis point
CDSsens["Sensitivity (per bps)"] = CDSsens["Sensitivity"] / 10000

beta_cds = CDSsens["Sensitivity (per bps)"].mean()

# import q11 output
shiftsens = pd.read_csv("bond_sensitivity_prices.csv", index_col=0)
base_price = shiftsens.loc["Base", "Clean Price"]
parallel_up = shiftsens.loc["Parallel +10bps", "Clean Price"]
parallel_dn = shiftsens.loc["Parallel -10bps", "Clean Price"]

# DV01 (symmetric approx): average price change per 1bp
dv01 = (parallel_dn - parallel_up) / 2 / 10
# Slope and Curvature change per 1 bp
slope_sens = (shiftsens.loc["Slope -10bps", "Clean Price"] - shiftsens.loc["Slope +10bps", "Clean Price"]) / 2 / 10
curv_sens = (shiftsens.loc["Curvature -10bps", "Clean Price"] - shiftsens.loc["Curvature +10bps", "Clean Price"]) / 2 / 10

print(f"Parallel DV01: {dv01:.6f}")
print(f"Slope Sensitivity:     {slope_sens:.6f} per 1bp")
print(f"Curvature Sensitivity: {curv_sens:.6f} per 1bp")
print(f"CDS Sensitivity {beta_cds:.6f} per 1bp")

# Given variances
var_l = 0.022
var_s = 0.003
var_c = 0.001
var_cds = 0.002

# Standard deviations
std_l = np.sqrt(var_l)
std_s = np.sqrt(var_s)
std_c = np.sqrt(var_c)
std_cds = np.sqrt(var_cds)

# Betas (from above)
beta_l = dv01
beta_s = slope_sens
beta_c = curv_sens
beta_cds = beta_cds 

# Monte Carlo simulation
n_simulations = 1000000
np.random.seed(42)

delta_l = np.random.normal(0, std_l, n_simulations)
delta_s = np.random.normal(0, std_s, n_simulations)
delta_c = np.random.normal(0, std_c, n_simulations)
delta_cds = np.random.normal(0, std_cds, n_simulations)

# Change in bond price
delta_GP = beta_l * delta_l + beta_s * delta_s + beta_c * delta_c + beta_cds * delta_cds
PnL = -delta_GP  # Loss

# Monte Carlo VaR & ES (99%)
VaR_mc = -np.percentile(PnL, 1)
ES_mc = PnL[PnL >= VaR_mc].mean()


# === QUESTION 17 ===
# Analytical (exact) VaR & ES using normal distribution
# Total variance of delta_GP
total_var = (beta_l**2 * var_l +
             beta_s**2 * var_s +
             beta_c**2 * var_c +
             beta_cds**2 * var_cds)
std_total = np.sqrt(total_var)

# Normal 99% quantile
z_99 = norm.ppf(0.01)
VaR_exact = -z_99 * std_total
ES_exact = std_total * norm.pdf(z_99) / 0.01


# === QUESTION 18 ===
# Marginal VaR is proportional to beta_i * std_i / std_total
# Component VaR = Marginal VaR * Beta_i
marginal_VaRs = {
    'l': beta_l * np.sqrt(var_l) / std_total,
    's': beta_s * np.sqrt(var_s) / std_total,
    'c': beta_c * np.sqrt(var_c) / std_total,
    'cds': beta_cds * np.sqrt(var_cds) / std_total
}

component_VaRs = {k: v * VaR_exact for k, v in marginal_VaRs.items()}


# === OUTPUT ===
print(f"\nMonte Carlo 99% VaR: {VaR_mc:.4f}")
print(f"Exact (Analytical) 99% VaR: {VaR_exact:.4f}")
print(f"Monte Carlo 99% ES: {ES_mc:.4f}")
print(f"Exact (Analytical) 99% ES: {ES_exact:.4f}")

print("\nMarginal VaR contributions:")
for factor in marginal_VaRs:
    print(f"  {factor}: {marginal_VaRs[factor]:.6f}")

print("\nComponent VaR contributions:")
for factor in component_VaRs:
    print(f"  {factor}: {component_VaRs[factor]:.6f}")
    
print(f"Sum of component VaRs: {-sum(component_VaRs.values()):.6f}")
print(f"Exact Total VaR:       {VaR_exact:.6f}")

# Plot
plt.hist(PnL, bins=100, alpha=0.7, edgecolor='k')
plt.axvline(-VaR_mc, color='red', linestyle='--', linewidth=2, label=f'MC VaR = {VaR_mc:.4f}')
plt.axvline(-VaR_exact, color='blue', linestyle='--', linewidth=2, label=f'Exact VaR = {VaR_exact:.4f}')
plt.title('Profit and Loss Distribution')
plt.xlabel('Loss')
plt.ylabel('Frequency')
plt.legend()
plt.grid()
plt.show()
# %%
