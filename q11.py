#%%
import QuantLib as ql
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from q1 import bond_characteristics
from q3 import build_curves

# --- Shift Helpers ---
def apply_parallel_shift(rates, shift_bps=10):
    return [r + shift_bps / 10000 for r in rates]

def apply_slope_shift(rates, shift_bps=10):
    n = len(rates)
    return [r + (shift_bps / 10000 * (2 * i / n - 1)) for i, r in enumerate(rates)]

def apply_curvature_shift(rates, bump=0.001):
    n = len(rates)
    mid, width = n // 2, n // 4
    return [r + bump * np.exp(-((i - mid)**2) / (2 * width**2)) for i, r in enumerate(rates)]

def make_zero_curve(dates, shifted_rates, calendar, day_counter):
    curve = ql.ZeroCurve(dates, shifted_rates, day_counter, calendar)
    curve.enableExtrapolation()
    return curve

def compute_sensitivity():
    """Compute shifted curves and bond price sensitivity summary."""
    # --- Setup ---
    spot_date = ql.Date(26, 11, 2024)
    ql.Settings.instance().evaluationDate = spot_date
    calendar = ql.TARGET()
    day_counter_curve = ql.Actual360()
    day_counter_coupon = ql.Thirty360(ql.Thirty360.BondBasis)
    
    # Build base curve
    base_curve = build_curves()["Log-Cubic"]
    eval_date = ql.Date(18, 11, 2024)
    end_date = calendar.advance(eval_date, ql.Period(60, ql.Years))
    n_points = 100    # number of points on the curve
    dates = [eval_date + ql.Period(int(i * (end_date.serialNumber() - eval_date.serialNumber()) / n_points), ql.Days)
             for i in range(n_points + 1)]
    date_labels = [d.ISO() for d in dates]
    base_rates = [base_curve.zeroRate(d, day_counter_curve, ql.Continuous).rate() for d in dates]
    
    # Build shifted curves
    shifted_curves = {
        "Base": base_curve,
        "Parallel +10bps": make_zero_curve(dates, apply_parallel_shift(base_rates, 10), calendar, day_counter_curve),
        "Parallel -10bps": make_zero_curve(dates, apply_parallel_shift(base_rates, -10), calendar, day_counter_curve),
        "Slope +10bps": make_zero_curve(dates, apply_slope_shift(base_rates, 10), calendar, day_counter_curve),
        "Slope -10bps": make_zero_curve(dates, apply_slope_shift(base_rates, -10), calendar, day_counter_curve),
        "Curvature +10bps": make_zero_curve(dates, apply_curvature_shift(base_rates, 0.001), calendar, day_counter_curve),
        "Curvature -10bps": make_zero_curve(dates, apply_curvature_shift(base_rates, -0.001), calendar, day_counter_curve),
    }
    
    # --- Bond Characteristics ---
    frequency = ql.Quarterly
    notional = bond_characteristics["Nominal Value"]
    cap = bond_characteristics["Cap"]
    floor = bond_characteristics["Floor"]
    settlement_lag = bond_characteristics["Settlement Lag"]
    
    issue_date = ql.Date(bond_characteristics["Issue Date"].day,
                         bond_characteristics["Issue Date"].month,
                         bond_characteristics["Issue Date"].year)
    maturity_date = ql.Date(29, 7, 2027)
    
    schedule = ql.Schedule(
        issue_date, maturity_date,
        ql.Period(frequency),
        calendar,
        ql.ModifiedFollowing, ql.ModifiedFollowing,
        ql.DateGeneration.Forward, False
    )
    
    # --- Pricing Functions ---
    def get_forward_rate(start, end, curve):
        safe_start = max(start, spot_date)
        return curve.forwardRate(safe_start, end, day_counter_curve, ql.Simple).rate() if safe_start < end else 0.0
    
    def compute_gross_price(curve):
        cashflows = []
        for i in range(len(schedule) - 1):
            start = schedule[i]
            end = schedule[i + 1]
            if end <= spot_date:
                continue
            if start < spot_date:
                reset = calendar.advance(start, -settlement_lag, ql.Days)
                start_for_fwd = reset if spot_date >= reset else spot_date
            else:
                start_for_fwd = start
            fwd = get_forward_rate(start_for_fwd, end, curve)
            rate = min(max(fwd, floor), cap)
            yf = day_counter_coupon.yearFraction(start, end)
            coupon = notional * rate * yf
            df = curve.discount(end)
            cashflows.append(coupon * df)
        # Redemption
        cashflows.append(notional * curve.discount(maturity_date))
        return sum(cashflows)
    
    def compute_accrued(curve):
        for i in range(len(schedule) - 1):
            start = schedule[i]
            end = schedule[i + 1]
            if start < spot_date <= end:
                reset = calendar.advance(start, -settlement_lag, ql.Days)
                start_for_fwd = reset if spot_date >= reset else spot_date
                fwd = get_forward_rate(start_for_fwd, end, curve)
                rate = min(max(fwd, floor), cap)
                yf = day_counter_coupon.yearFraction(start, spot_date)
                return notional * rate * yf
        return 0.0
    
    price_summary = {}
    for label, curve in shifted_curves.items():
        gross = compute_gross_price(curve)
        accrued = compute_accrued(curve)
        clean = gross - accrued
        price_summary[label] = {
            "Gross Price": round(gross, 4),
            "Accrued Interest": round(accrued, 4),
            "Clean Price": round(clean, 4)
        }
    
    df_prices = pd.DataFrame(price_summary).T
    return shifted_curves, df_prices, dates, date_labels, base_rates, calendar, day_counter_curve

# Compute global variables for import
_shifted_curves, _df_prices, _dates, _date_labels, _base_rates, _calendar, _day_counter_curve = compute_sensitivity()
shifted_curves = _shifted_curves
df_prices = _df_prices

def main():
    # Retrieve computed values for plotting and output
    shifted_curves_local, df_prices_local, dates, date_labels, base_rates, calendar, day_counter_curve = compute_sensitivity()
    
    # Plot base curve
    plt.figure(figsize=(12, 6), dpi=250)
    plt.plot(date_labels, base_rates)
    plt.title("Base Zero Rate Curve")
    plt.xlabel("Maturity Date")
    plt.ylabel("Zero Rate")
    plt.xticks(rotation=45)
    plt.show()
    
    # Plot shifted curves for each shift type
    plot_groups = {
        "Parallel Shift": ["Base", "Parallel +10bps", "Parallel -10bps"],
        "Slope Shift": ["Base", "Slope +10bps", "Slope -10bps"],
        "Curvature Shift": ["Base", "Curvature +10bps", "Curvature -10bps"]
    }
    
    for title, group_labels in plot_groups.items():
        plt.figure(figsize=(10, 5), dpi=150)
        for name in group_labels:
            curve = shifted_curves_local[name]
            rates = [curve.zeroRate(d, day_counter_curve, ql.Continuous).rate() * 100 for d in dates]
            linestyle = '-' if name == "Base" else '--' if "+10bps" in name else '-.'
            plt.plot(date_labels, rates, label=name, linestyle=linestyle)
    
        plt.title(f"Spot Rate Curves – {title}")
        plt.ylabel("Zero Rate (%)")
        plt.xlabel("Maturity Date")
        plt.xticks(date_labels[::5], rotation=45)
        plt.grid(axis='y')
        plt.legend()
        plt.tight_layout()
        plt.show()
    

df_prices.to_csv("bond_sensitivity_prices.csv") # Output the results for Q16-18
#%%
