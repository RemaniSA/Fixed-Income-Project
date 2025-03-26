import QuantLib as ql
import pandas as pd

from q1 import bond_characteristics
from q3 import build_curves
from q11 import shifted_curves, make_zero_curve, apply_parallel_shift, apply_slope_shift, apply_curvature_shift, df_prices

# =============================================================================
# 1. Set Evaluation Date Based on Trade Date
# =============================================================================
trade_date = ql.Date(bond_characteristics['Trade Date'].day,
                     bond_characteristics['Trade Date'].month,
                     bond_characteristics['Trade Date'].year)
ql.Settings.instance().evaluationDate = trade_date

# =============================================================================
# 2. Get shifted curves (already discount curves from question 11)
# =============================================================================
calendar = ql.TARGET()
day_counter_curve = ql.Actual360()
day_counter_coupon = ql.Thirty360(ql.Thirty360.BondBasis)
base_curve = build_curves()["Log-Cubic"]
eval_date = ql.Date(18, 11, 2024)
end_date = calendar.advance(eval_date, ql.Period(60, ql.Years))
n_points = 100    # number of points on the curve
dates = [eval_date + ql.Period(int(i * (end_date.serialNumber() - eval_date.serialNumber()) / n_points), ql.Days)
         for i in range(n_points + 1)] # evaluation dates
base_rates = [base_curve.zeroRate(d, day_counter_curve, ql.Continuous).rate() for d in dates]
base_points = 1

# Build shifted curves
shifted_curves = {
    "Base": base_curve,
    "Parallel +10bps": make_zero_curve(dates, apply_parallel_shift(base_rates, base_points), calendar, day_counter_curve),
    "Parallel -10bps": make_zero_curve(dates, apply_parallel_shift(base_rates, -base_points), calendar, day_counter_curve),
    "Slope +10bps": make_zero_curve(dates, apply_slope_shift(base_rates, base_points), calendar, day_counter_curve),
    "Slope -10bps": make_zero_curve(dates, apply_slope_shift(base_rates, -base_points), calendar, day_counter_curve),
    "Curvature +10bps": make_zero_curve(dates, apply_curvature_shift(base_rates, 0.0001), calendar, day_counter_curve),
    "Curvature -10bps": make_zero_curve(dates, apply_curvature_shift(base_rates, -0.0001), calendar, day_counter_curve),
}

# =============================================================================
# 3. Bond Setup: Construct a Floating-Rate Bond with Cap and Floor
# =============================================================================
# Extract bond dates from bond_characteristics
issue_date = ql.Date(bond_characteristics['Issue Date'].day,
                     bond_characteristics['Issue Date'].month,
                     bond_characteristics['Issue Date'].year)
maturity_date_bond = ql.Date(bond_characteristics['Maturity Date'].day,
                             bond_characteristics['Maturity Date'].month,
                             bond_characteristics['Maturity Date'].year)
settlement_days = bond_characteristics['Settlement Lag']

# Create a coupon schedule for the floating rate bond (Quarterly frequency)
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

# =============================================================================
# 5. Functions to Compute DV01 for a Swap and a Bond (using finite differences)
# =============================================================================
def compute_dv01(down_shift, up_shift):
    dv01 = (down_shift - up_shift) / 2
    return dv01

# =============================================================================
# 3. Manual Swap Pricing Function
# =============================================================================
def compute_swap_prices(curve, fixed_schedule, notional, fixed_rate, day_counter, eval_date):
    """
    Computes the swap price manually using discount factors from the provided curve.
    
    The method is as follows:
      - Fixed leg PV is calculated by summing the discounted fixed coupon payments
        for all payment dates after the evaluation date.
      - Floating leg PV is approximated by: Notional * (1 - DF(final_payment_date))
      - Swap NPV = Floating PV - Fixed PV.
      - Gross Price is defined as: Notional + Swap NPV.
      - Accrued Interest on the fixed leg is computed as the fraction of the fixed coupon
        accrued from the last payment date to the evaluation date.
      - Clean Price = Gross Price - Accrued Interest.
    
    Returns a tuple (gross_price, accrued_interest, clean_price).
    """
    # Convert the fixed schedule into a list of dates.
    fixed_dates = list(fixed_schedule)

    # ----- Fixed Leg PV Calculation -----
    fixed_leg_PV = 0.0
    for i in range(1, len(fixed_dates)):
        payment_date = fixed_dates[i]
        if payment_date > eval_date:
            # The accrual factor for the coupon period:
            period = day_counter.yearFraction(fixed_dates[i-1], payment_date)
            payment = notional * fixed_rate * period
            # Discount the payment using the provided curve:
            df = curve.discount(payment_date)
            fixed_leg_PV += payment * df

    # ----- Floating Leg PV Calculation -----
    # Under the assumption of a par-reset swap:
    final_date = fixed_dates[-1]
    PV_floating = notional * (1 - curve.discount(final_date))

    # ----- Swap NPV & Gross Price -----
    swap_NPV = PV_floating - fixed_leg_PV
    gross_price = notional + swap_NPV

    # ----- Accrued Interest Calculation on Fixed Leg -----
    # Find the last coupon date that is on or before eval_date.
    last_coupon_date = None
    for d in fixed_dates:
        if d <= eval_date:
            last_coupon_date = d
        else:
            break
    accrued = 0.0
    if last_coupon_date is not None and last_coupon_date != fixed_dates[-1]:
        # Compute fraction of the period elapsed:
        fraction = day_counter.yearFraction(last_coupon_date, eval_date)
        accrued = notional * fixed_rate * fraction

    # ----- Clean Price -----
    clean_price = gross_price - accrued
    return gross_price, accrued, clean_price

# =============================================================================
# 4. Loop Over Shifted Curves to Build the Swap Price Table
# =============================================================================
nominal = bond_characteristics['Nominal Value']  # Notional amount
fixed_rate = 0.02202  # Fixed rate payment
day_counter_fixed = ql.Actual360()

rows = []
for scenario, curve in shifted_curves.items():
    gross, accrued, clean = compute_swap_prices(curve, bond_schedule, nominal, fixed_rate, day_counter_fixed, eval_date)
    rows.append({
        "Interpolation Method": scenario,
        "Gross Price": round(gross, 4),
        "Accrued Interest": round(accrued, 4),
        "Clean Price": round(clean, 4)
    })

df_swap_prices = pd.DataFrame(rows)
df_swap_prices.set_index("Interpolation Method", inplace=True)
print(df_prices)
print(df_swap_prices)

# =============================================================================
# 6. Loop Over Each Yield Curve: Price the Bond & Swap, Compute DV01s, and Determine Hedge Ratio
# =============================================================================

print("Comparison of Bond and Swap DV01s Using Different Yield Curves:")
print("----------------------------------------------------------------------------------------------")
print("{:<25} {:>15} {:>15} {:>20}".format("Interpolation Method", "Bond DV01", "Swap DV01", "Hedge Ratio"))
print("----------------------------------------------------------------------------------------------")

for i in range(1, 6, 2):
    bond_dv01 = compute_dv01(df_prices.iloc[i+1]['Gross Price'], df_prices.iloc[i]['Gross Price'])
    swap_dv01 = compute_dv01(df_swap_prices.iloc[i+1]['Gross Price'], df_swap_prices.iloc[i]['Gross Price'])

    if swap_dv01 != 0:
        hedge_ratio = abs(bond_dv01) / abs(swap_dv01)
    else:    
        hedge_ratio = float('inf')

    print("{:<25} {:>15.6f} {:>15.6f} {:>20.6f}".format(df_prices.index[i], bond_dv01, swap_dv01, hedge_ratio))

# to use DV01 we can only use a shift of 1bps by definition
# dv01 = (down - up / 2)
