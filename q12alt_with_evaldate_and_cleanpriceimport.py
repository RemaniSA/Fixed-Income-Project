#%%
import QuantLib as ql
import numpy as np
import pandas as pd

from q1 import bond_characteristics
from q3 import build_curves
from q8 import model_clean_price

# =============================================================================
# 1. Set Evaluation Date Based on Trade Date
# =============================================================================
trade_date = ql.Date(18,11,2024)
ql.Settings.instance().evaluationDate = trade_date

# =============================================================================
# 2. Construct Multiple Yield Curves Using Different Interpolation Methods
# =============================================================================
curves = build_curves()

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

# For a floating rate bond, we need a schedule.
# Since the bond pays 4 times per year, we use Quarterly frequency.
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

# Create the index for the floating rate coupon.
# Since the coupon is "3M Euribor", we use Euribor3M.
# We'll create a dummy yield curve here; later, when pricing the bond, we attach the current yield curve.
dummy_curve = ql.FlatForward(trade_date, 0.02, ql.Actual365Fixed())  # Dummy 2% flat curve
dummy_handle = ql.YieldTermStructureHandle(dummy_curve)
euribor3m = ql.Euribor3M(dummy_handle)

# Set parameters for the FloatingRateBond:
# - settlementDays: from bond_characteristics
# - faceAmount: Nominal Value
# - schedule: bond_schedule
# - index: euribor3m
# - paymentDayCounter: Using Thirty360 based on the bond's conventions (Days in Month=30, Days in Year=360)
# - paymentConvention: Modified Following
# - fixingDays: We'll assume 2 (typical for Euribor)
# - gearings: [1.0] (no gearing)
# - spreads: [0.0] (no spread)
# - caps: [bond_characteristics['Cap']]
# - floors: [bond_characteristics['Floor']]
# - inArrears: False
# - redemption: 100 (since the nominal is 1000 and redemption "At Par", we use 100% of par)
# - issueDate: issue_date

bond = ql.FloatingRateBond(
    settlementDays=settlement_days,
    faceAmount=bond_characteristics['Nominal Value'],
    schedule=bond_schedule,
    index=euribor3m,
    paymentDayCounter=ql.Thirty360(ql.Thirty360.BondBasis),
    paymentConvention=ql.ModifiedFollowing,
    fixingDays=2,
    gearings=[1.0],
    spreads=[0.0],
    caps=[bond_characteristics['Cap']],
    floors=[bond_characteristics['Floor']],
    inArrears=False,
    redemption=100.0,   # 100% of par
    issueDate=issue_date
)

pricer = ql.BlackIborCouponPricer()
# 💡 Add this line to set the pricer for the floating coupons
ql.setCouponPricer(bond.cashflows(), pricer)

# =============================================================================
# 5. Functions to Compute DV01 for a Swap and a Bond (using finite differences)
# =============================================================================
def compute_dv01(swap, original_curve, bump=1e-4):
    """Compute DV01 for a swap by bumping the yield curve by 1 basis point."""
    original_npv = swap.NPV()
    bumped_rates = [original_curve.zeroRate(date, ql.Actual365Fixed(), ql.Continuous).rate() + bump
                    for date in original_curve.dates()]
    bumped_curve = ql.ZeroCurve(original_curve.dates(), bumped_rates, ql.Actual365Fixed())
    bumped_handle = ql.YieldTermStructureHandle(bumped_curve)
    swap.setPricingEngine(ql.DiscountingSwapEngine(bumped_handle))
    bumped_npv = swap.NPV()
    dv01 = (bumped_npv - original_npv) / bump
    return dv01

def compute_bond_dv01(bond, original_curve, bump=1e-4):
    """Compute DV01 for a bond by bumping the yield curve by 1 basis point."""
    yc_handle = ql.YieldTermStructureHandle(original_curve)
    bond.setPricingEngine(ql.DiscountingBondEngine(yc_handle))
    original_price = model_clean_price
    bumped_rates = [original_curve.zeroRate(date, ql.Actual365Fixed(), ql.Continuous).rate() + bump
                    for date in original_curve.dates()]
    bumped_curve = ql.ZeroCurve(original_curve.dates(), bumped_rates, ql.Actual365Fixed())
    bumped_handle = ql.YieldTermStructureHandle(bumped_curve)
    bond.setPricingEngine(ql.DiscountingBondEngine(bumped_handle))
    bumped_price = model_clean_price
    dv01 = (bumped_price - original_price) / bump
    return dv01

# =============================================================================
# Swap Setup: Define a plain vanilla swap to be priced using each yield curve.
# =============================================================================

nominal = bond_characteristics['Nominal Value']  # Notional amount
fixed_rate = 0.025 # Fixed rate payment

# Define swap start and maturity dates (5-year swap)
start_date = issue_date
maturity_date = maturity_date_bond

# Build schedules for the fixed and floating legs.
fixed_schedule = ql.Schedule(
    start_date, maturity_date, ql.Period(ql.Annual),
    ql.TARGET(), ql.ModifiedFollowing, ql.ModifiedFollowing,
    ql.DateGeneration.Forward, False
)
floating_schedule = ql.Schedule(
    start_date, maturity_date, ql.Period(ql.Semiannual),
    ql.TARGET(), ql.ModifiedFollowing, ql.ModifiedFollowing,
    ql.DateGeneration.Forward, False
)


# =============================================================================
# 6. Loop Over Each Yield Curve: Price the Bond & Swap, Compute DV01s, and Determine Hedge Ratio
# =============================================================================

print("Comparison of Bond and Swap DV01s Using Different Yield Curves:")
print("----------------------------------------------------------------------------------------------")
print("{:<25} {:>12} {:>15} {:>15} {:>20}".format("Interpolation Method", "Bond Price", "Bond DV01", "Swap DV01", "Hedge Notional"))
print("----------------------------------------------------------------------------------------------")

for curve_name, curve in curves.items():
    # Create a YieldTermStructureHandle for the current curve.
    yc_handle = ql.YieldTermStructureHandle(curve)
    
    # ---------------------------
    # 6.1 Bond Pricing & DV01 Computation
    # ---------------------------
    # Rebuild the bond pricing engine with the current yield curve.
    bond.setPricingEngine(ql.DiscountingBondEngine(yc_handle))
    bond_price = model_clean_price
    bond_dv01 = compute_bond_dv01(bond, curve)
    
    # ---------------------------
    # 6.2 Determine Swap Type Based on Bond DV01
    # ---------------------------
    # If the bond DV01 is negative (i.e., bond loses when rates rise), we need an instrument with positive DV01.
    # Use a Payer swap. Otherwise, if bond DV01 is positive, use a Receiver swap.
    if bond_dv01 < 0:
        swap_type = ql.VanillaSwap.Payer
    else:
        swap_type = ql.VanillaSwap.Receiver

    # ---------------------------
    # 6.3 Swap Setup: Create a Vanilla Swap Using the Current Yield Curve
    # ---------------------------
    # Rebuild the Euribor6M index using the current yield curve.
    euribor_index = ql.Euribor6M(yc_handle)
    swap = ql.VanillaSwap(
        swap_type,    # chosen dynamically based on bond DV01
        bond_characteristics['Nominal Value'],      # Notional
        fixed_schedule, fixed_rate, ql.Thirty360(ql.Thirty360.BondBasis),
        floating_schedule, euribor_index, 0.0, ql.Actual360()
    )
    swap_engine = ql.DiscountingSwapEngine(yc_handle)
    swap.setPricingEngine(swap_engine)
    
    swap_npv = swap.NPV()
    swap_dv01 = compute_dv01(swap, curve)
    
    # ---------------------------
    # 7.4 Calculate Hedge Notional
    # ---------------------------
    # Hedge notional = |bond DV01| / |swap DV01|
    hedge_notional = abs(bond_dv01) / abs(swap_dv01) if swap_dv01 != 0 else float('inf')
    
    # Print results.
    print("{:<25} {:>12.2f} {:>15.2f} {:>15.2f} {:>20.0f}".format(curve_name, bond_price, bond_dv01, swap_dv01, hedge_notional))
# %%
