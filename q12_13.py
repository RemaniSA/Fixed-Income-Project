import QuantLib as ql

from q1 import bond_characteristics
from q3 import build_curves

# =============================================================================
# 1. Set Evaluation Date Based on Trade Date
# =============================================================================
trade_date = ql.Date(bond_characteristics['Trade Date'].day,
                     bond_characteristics['Trade Date'].month,
                     bond_characteristics['Trade Date'].year)
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



# Parameters for the FloatingRateBond:
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
    original_price = bond.cleanPrice()
    bumped_rates = [original_curve.zeroRate(date, ql.Actual365Fixed(), ql.Continuous).rate() + bump
                    for date in original_curve.dates()]
    bumped_curve = ql.ZeroCurve(original_curve.dates(), bumped_rates, ql.Actual365Fixed())
    bumped_handle = ql.YieldTermStructureHandle(bumped_curve)
    bond.setPricingEngine(ql.DiscountingBondEngine(bumped_handle))
    bumped_price = bond.cleanPrice()
    dv01 = (bumped_price - original_price) / bump
    return dv01

# =============================================================================
# Swap Setup: Define a plain vanilla swap to be priced using each yield curve.
# =============================================================================

nominal = bond_characteristics['Nominal Value']  # Notional amount
fixed_rate = 0.02202 # Fixed rate payment

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

for curve_name, forward_curve in curves.items():
    # Create a handle for the forward curve
    forward_handle = ql.YieldTermStructureHandle(forward_curve)
    
    # -------------------------------------------------------------------------
    # 1. Build a discount curve from the forward curve
    # -------------------------------------------------------------------------
    # Retrieve the dates from the forward curve (these should cover the maturities of interest)
    dates = forward_curve.dates()
    # Get the day counter from the forward curve; if not available, you can default to Actual365Fixed
    try:
        day_counter = forward_curve.dayCounter()
    except AttributeError:
        day_counter = ql.Actual365Fixed()
    # Compute discount factors at each date from the forward curve
    discount_factors = [forward_curve.discount(date) for date in dates]
    # Build a discount curve using these dates and discount factors
    discount_curve = ql.DiscountCurve(dates, discount_factors, day_counter)
    discount_handle = ql.YieldTermStructureHandle(discount_curve)
    
    # -------------------------------------------------------------------------
    # 2. Build the floating index using the forward curve (for projecting coupons)
    # -------------------------------------------------------------------------
    euribor3m = ql.Euribor3M(forward_handle)
    
    # Re-create the bond for this curve iteration with the new index.
    # (Reinstantiating the bond is safest because the index is set at construction.)
    bond = ql.FloatingRateBond(
        settlementDays=settlement_days,
        faceAmount=bond_characteristics['Nominal Value'],
        schedule=bond_schedule,
        index=euribor3m,  # Use forward curve for forecasting
        paymentDayCounter=ql.Thirty360(ql.Thirty360.BondBasis),
        paymentConvention=ql.ModifiedFollowing,
        fixingDays=2,
        gearings=[1.0],
        spreads=[0.0],
        caps=[bond_characteristics['Cap']],
        floors=[bond_characteristics['Floor']],
        inArrears=False,
        redemption=100.0,
        issueDate=issue_date
    )
    pricer = ql.BlackIborCouponPricer()
    ql.setCouponPricer(bond.cashflows(), pricer)
    
    # Use the discount curve for pricing
    bond.setPricingEngine(ql.DiscountingBondEngine(discount_handle))
    bond_price = bond.cleanPrice()
    # Compute bond DV01 using the discount curve
    bond_dv01 = compute_bond_dv01(bond, discount_curve)
    
    # -------------------------------------------------------------------------
    # 3. Construct the Swap using the forward curve for the floating leg and the discount curve for discounting
    # -------------------------------------------------------------------------
    # Determine swap type based on bond DV01
    if bond_dv01 < 0:
        swap_type = ql.VanillaSwap.Payer
    else:
        swap_type = ql.VanillaSwap.Receiver
    
    # Rebuild the floating leg index (using the forward curve)
    euribor_index = ql.Euribor6M(forward_handle)
    swap = ql.VanillaSwap(
        swap_type,
        bond_characteristics['Nominal Value'],  # Notional amount
        fixed_schedule, fixed_rate, ql.Thirty360(ql.Thirty360.BondBasis),
        floating_schedule, euribor_index, 0.0, ql.Actual360()
    )
    # Use the discount curve for discounting the swap cash flows
    swap_engine = ql.DiscountingSwapEngine(discount_handle)
    swap.setPricingEngine(swap_engine)
    
    swap_npv = swap.NPV()
    swap_dv01 = compute_dv01(swap, discount_curve)
    
    # Calculate hedge notional as the ratio of DV01s (absolute values)
    hedge_notional = abs(bond_dv01) / abs(swap_dv01) if swap_dv01 != 0 else float('inf')
    
    # Print the results for this curve
    print("{:<25} {:>12.2f} {:>15.2f} {:>15.2f} {:>20.0f}".format(curve_name, bond_price, bond_dv01, swap_dv01, hedge_notional))
