import QuantLib as ql
import pandas as pd

from q1 import bond_characteristics
from q3 import build_curves
from q11 import shifted_curves, make_zero_curve, apply_parallel_shift, apply_slope_shift, apply_curvature_shift, df_prices


# =============================================================================
# 1. Set Evaluation Date
# =============================================================================

def set_evaluation_date():
    """
    Set the evaluation date using the trade date from bond_characteristics.
    """
    trade_date = ql.Date(
        bond_characteristics['Trade Date'].day,
        bond_characteristics['Trade Date'].month,
        bond_characteristics['Trade Date'].year
    )
    ql.Settings.instance().evaluationDate = trade_date


# =============================================================================
# 2. Build Shifted Curves
# =============================================================================

def build_shifted_curves_local():
    """
    Build shifted curves using a 1 bps shift for parallel, slope, and curvature adjustments.
    Returns a tuple: (shifted_curves_local, eval_date, day_counter_curve).
    """
    calendar = ql.TARGET()
    day_counter_curve = ql.Actual360()
    # day_counter_coupon is defined but not used in this function
    # day_counter_coupon = ql.Thirty360(ql.Thirty360.BondBasis)

    base_curve = build_curves()["Log-Cubic"]
    eval_date = ql.Date(18, 11, 2024)
    end_date = calendar.advance(eval_date, ql.Period(60, ql.Years))
    n_points = 100    # number of points on the curve

    # Generate evaluation dates along the curve
    dates = [eval_date + ql.Period(int(i * (end_date.serialNumber() - eval_date.serialNumber()) / n_points), ql.Days)
             for i in range(n_points + 1)]
    
    # Extract base rates from the base curve
    base_rates = [base_curve.zeroRate(d, day_counter_curve, ql.Continuous).rate() for d in dates]
    base_points = 1

    # Build shifted curves using the provided shift functions
    shifted_curves_local = {
        "Base": base_curve,
        "Parallel +1bps": make_zero_curve(dates, apply_parallel_shift(base_rates, base_points), calendar, day_counter_curve),
        "Parallel -1bps": make_zero_curve(dates, apply_parallel_shift(base_rates, -base_points), calendar, day_counter_curve),
        "Slope +1bps": make_zero_curve(dates, apply_slope_shift(base_rates, base_points), calendar, day_counter_curve),
        "Slope -1bps": make_zero_curve(dates, apply_slope_shift(base_rates, -base_points), calendar, day_counter_curve),
        "Curvature +1bps": make_zero_curve(dates, apply_curvature_shift(base_rates, 0.0001), calendar, day_counter_curve),
        "Curvature -1bps": make_zero_curve(dates, apply_curvature_shift(base_rates, -0.0001), calendar, day_counter_curve),
    }

    return shifted_curves_local, eval_date, day_counter_curve


# =============================================================================
# 3. Build Bond Schedule
# =============================================================================

def build_bond_schedule():
    """
    Construct a floating-rate bond schedule (Quarterly frequency) using the bond dates from bond_characteristics.
    """
    issue_date = ql.Date(
        bond_characteristics['Issue Date'].day,
        bond_characteristics['Issue Date'].month,
        bond_characteristics['Issue Date'].year
    )
    maturity_date_bond = ql.Date(
        bond_characteristics['Maturity Date'].day,
        bond_characteristics['Maturity Date'].month,
        bond_characteristics['Maturity Date'].year
    )
    # settlement_days is defined but not used here
    # settlement_days = bond_characteristics['Settlement Lag']

    bond_schedule = ql.Schedule(
        issue_date,
        maturity_date_bond,
        ql.Period(ql.Quarterly),
        ql.TARGET(),
        ql.ModifiedFollowing,
        ql.ModifiedFollowing,
        ql.DateGeneration.Forward,
        False
    )
    return bond_schedule


# =============================================================================
# 4. Compute DV01 and Swap Pricing
# =============================================================================

def compute_dv01(down_shift, up_shift):
    """
    Compute DV01 as the half difference between the down-shifted and up-shifted prices.
    """
    return (down_shift - up_shift) / 2


def compute_swap_prices(curve, fixed_schedule, notional, fixed_rate, day_counter, eval_date):
    """
    Compute the swap price manually using discount factors from the provided curve.
    
    The pricing method is:
      - Fixed Leg PV: Sum of discounted fixed coupon payments for all payment dates > eval_date.
      - Floating Leg PV (approx.): Notional * (1 - DF(final_payment_date)) assuming a par-reset swap.
      - Swap NPV = Floating PV - Fixed PV.
      - Gross Price = Notional + Swap NPV.
      - Accrued Interest: Fraction of the fixed coupon accrued from the last coupon date up to eval_date.
      - Clean Price = Gross Price - Accrued Interest.
    
    Returns a tuple: (gross_price, accrued_interest, clean_price).
    """
    fixed_dates = list(fixed_schedule)

    # ----- Fixed Leg PV Calculation -----
    fixed_leg_PV = 0.0
    for i in range(1, len(fixed_dates)):
        payment_date = fixed_dates[i]
        if payment_date > eval_date:
            period = day_counter.yearFraction(fixed_dates[i-1], payment_date)
            payment = notional * fixed_rate * period
            df = curve.discount(payment_date)
            fixed_leg_PV += payment * df

    # ----- Floating Leg PV Calculation -----
    final_date = fixed_dates[-1]
    PV_floating = notional * (1 - curve.discount(final_date))

    # ----- Swap NPV & Gross Price -----
    swap_NPV = PV_floating - fixed_leg_PV
    gross_price = notional + swap_NPV

    # ----- Accrued Interest Calculation -----
    last_coupon_date = None
    for d in fixed_dates:
        if d <= eval_date:
            last_coupon_date = d
        else:
            break
    accrued = 0.0
    if last_coupon_date is not None and last_coupon_date != fixed_dates[-1]:
        fraction = day_counter.yearFraction(last_coupon_date, eval_date)
        accrued = notional * fixed_rate * fraction

    clean_price = gross_price - accrued
    return gross_price, accrued, clean_price


# =============================================================================
# 5. Build Swap Price Table
# =============================================================================

def build_swap_price_table(shifted_curves_local, bond_schedule, eval_date, day_counter_fixed):
    """
    Loop over each shifted curve to compute swap prices and build a price table.
    Returns a pandas DataFrame with index as the Interpolation Method and columns:
    [Gross Price, Accrued Interest, Clean Price].
    """
    nominal = bond_characteristics['Nominal Value']
    fixed_rate = 0.02202  # Fixed rate payment
    rows = []
    for scenario, curve in shifted_curves_local.items():
        gross, accrued, clean = compute_swap_prices(curve, bond_schedule, nominal, fixed_rate, day_counter_fixed, eval_date)
        rows.append({
            "Interpolation Method": scenario,
            "Gross Price": round(gross, 4),
            "Accrued Interest": round(accrued, 4),
            "Clean Price": round(clean, 4)
        })
    
    df_swap_prices = pd.DataFrame(rows)
    df_swap_prices.set_index("Interpolation Method", inplace=True)
    return df_swap_prices


# =============================================================================
# 6. Print Hedge Ratios
# =============================================================================

def print_hedge_ratios(bond_df, swap_df):
    """
    Compute and print the DV01 for bond and swap as well as the hedge ratio.
    DV01 is computed as half the difference between the down-shifted and up-shifted prices.
    Hedge Ratio = |Bond DV01| / |Swap DV01|.
    """
    print("Comparison of Bond and Swap DV01s Using Different Yield Curves:")
    print("----------------------------------------------------------------------------------------------")
    print("{:<25} {:>15} {:>15} {:>20}".format("Interpolation Method", "Bond DV01", "Swap DV01", "Hedge Ratio"))
    print("----------------------------------------------------------------------------------------------")
    
    # Loop over DV01 pairs. Assumes DataFrame order: index 0 = Base, then pairs (1,2), (3,4), (5,6)
    for i in range(1, 6, 2):
        bond_dv01 = compute_dv01(bond_df.iloc[i+1]['Gross Price'], bond_df.iloc[i]['Gross Price'])
        swap_dv01 = compute_dv01(swap_df.iloc[i+1]['Gross Price'], swap_df.iloc[i]['Gross Price'])
        
        if swap_dv01 != 0:
            hedge_ratio = abs(bond_dv01) / abs(swap_dv01)
        else:
            hedge_ratio = float('inf')

        print("{:<25} {:>15.6f} {:>15.6f} {:>20.6f}".format(bond_df.index[i], bond_dv01, swap_dv01, hedge_ratio))


# =============================================================================
# 7. Main Execution Function
# =============================================================================

def main():
    # 1. Set the evaluation date from trade date
    set_evaluation_date()

    # 2. Build shifted curves and obtain evaluation date and day counter
    shifted_curves_local, eval_date, day_counter_curve = build_shifted_curves_local()

    # 3. Build the bond schedule for the floating rate bond
    bond_schedule = build_bond_schedule()

    # 4. Set day counter for fixed leg pricing
    day_counter_fixed = ql.Actual360()

    # 5. Build the swap price table for shifted curves
    df_swap_prices = build_swap_price_table(shifted_curves_local, bond_schedule, eval_date, day_counter_fixed)

    # 6. Print the Bond Price Table imported from q11 and the Swap Price Table
    print("Bond Price Table (from q11):")
    print(df_prices)
    print("\nSwap Price Table:")
    print(df_swap_prices)

    # 7. Compute and print DV01 and Hedge Ratios
    print_hedge_ratios(df_prices, df_swap_prices)


if __name__ == "__main__":
    main()
