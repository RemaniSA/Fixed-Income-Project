import QuantLib as ql
import numpy as np

# Set the evaluation date
today = ql.Date(24, 11, 2024)
ql.Settings.instance().evaluationDate = today

# ---------------------------
# Build a simple yield curve
# ---------------------------
# Create deposit rate helpers from sample quotes
depo_quotes = [(ql.Period(1, ql.Months), 0.01),
               (ql.Period(3, ql.Months), 0.012),
               (ql.Period(6, ql.Months), 0.015)]
depo_helpers = [ql.DepositRateHelper(
                    ql.QuoteHandle(ql.SimpleQuote(rate)),
                    period,
                    2,                  # settlement days
                    ql.TARGET(),
                    ql.ModifiedFollowing,
                    False,
                    ql.Actual360())
                for period, rate in depo_quotes]

# Create swap rate helpers from sample swap quotes
swap_quotes = [(ql.Period(2, ql.Years), 0.017),
               (ql.Period(5, ql.Years), 0.025),
               (ql.Period(10, ql.Years), 0.03)]
swap_helpers = [ql.SwapRateHelper(
                    ql.QuoteHandle(ql.SimpleQuote(rate)),
                    tenor,
                    ql.TARGET(),
                    ql.Annual,
                    ql.Thirty360(),
                    ql.Euribor6M())
                for tenor, rate in swap_quotes]

# Combine deposit and swap helpers
rate_helpers = depo_helpers + swap_helpers
yield_curve = ql.PiecewiseFlatForward(today, rate_helpers, ql.Actual365Fixed())
yc_handle = ql.YieldTermStructureHandle(yield_curve)

# ---------------------------
# Price a vanilla interest rate swap
# ---------------------------
nominal = 1000000  # Notional amount
fixed_rate = 0.025
start_date = today
maturity_date = ql.TARGET().advance(today, ql.Period(5, ql.Years))

# Build schedules for fixed and floating legs
fixed_schedule = ql.Schedule(start_date, maturity_date, ql.Period(ql.Annual),
                             ql.TARGET(), ql.ModifiedFollowing, ql.ModifiedFollowing,
                             ql.DateGeneration.Forward, False)
floating_schedule = ql.Schedule(start_date, maturity_date, ql.Period(ql.Semiannual),
                                ql.TARGET(), ql.ModifiedFollowing, ql.ModifiedFollowing,
                                ql.DateGeneration.Forward, False)

# Create a payer swap: pays fixed, receives floating
swap = ql.VanillaSwap(ql.VanillaSwap.Payer, nominal,
                      fixed_schedule, fixed_rate, ql.Thirty360(),
                      floating_schedule, ql.Euribor6M(yc_handle), 0.0, ql.Actual360())

# Price the swap using a discounting engine
swap_engine = ql.DiscountingSwapEngine(yc_handle)
swap.setPricingEngine(swap_engine)
swap_npv = swap.NPV()
print("Swap NPV: {:.2f}".format(swap_npv))

# ---------------------------
# Compute DV01 for the swap (using a finite difference approximation)
# ---------------------------
def compute_dv01(swap, yc_handle, bump=1e-4):
    original_npv = swap.NPV()
    
    # Create a bumped yield curve (flat bump of 1 bp)
    bumped_curve = ql.ZeroCurve(
        yield_curve.dates(),
        [yield_curve.zeroRate(date, ql.Actual365Fixed(), ql.Continuous).rate() + bump for date in yield_curve.dates()],
        ql.Actual365Fixed())
    bumped_handle = ql.YieldTermStructureHandle(bumped_curve)
    
    # Rebuild the pricing engine with the bumped curve
    swap.setPricingEngine(ql.DiscountingSwapEngine(bumped_handle))
    bumped_npv = swap.NPV()
    
    # DV01: Change in NPV per basis point
    dv01 = (bumped_npv - original_npv) / bump
    return dv01

swap_dv01 = compute_dv01(swap, yc_handle)
print("Swap DV01 (per 1 bp): {:.2f}".format(swap_dv01))

# ---------------------------
# Determine the Hedge Ratio
# ---------------------------
# Assume your structured bond portfolio has been computed to have a DV01 of -5000 (i.e., it loses €5,000 per 1 bp increase)
bond_dv01 = -5000.0
hedge_notional = abs(bond_dv01) / abs(swap_dv01)
print("Required hedge notional (approx): {:.0f}".format(hedge_notional))

# ---------------------------
# Note:
# In a full implementation, you would compute key rate durations across multiple maturities,
# and optimize hedge ratios (e.g., via least squares) to address non-parallel shifts.
# This example illustrates the fundamental QuantLib workflow for yield curve construction,
# swap pricing, and sensitivity calculation.