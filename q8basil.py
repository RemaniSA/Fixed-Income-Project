# %%

import os
import pandas as pd
import numpy as np
import QuantLib as ql

from q1 import bond_characteristics, get_next_payment_date
from q3 import build_curves
from q5 import interpolate_vol

# ----------------------------
# 1. Setup Evaluation Date and Bond Data (from Q1)
# ----------------------------
trade_date = bond_characteristics["Trade Date"]
# Use the settlement lag from Q1
spot_lag = bond_characteristics["Settlement Lag"]
ql.Settings.instance().evaluationDate = ql.Date(trade_date.day, trade_date.month, trade_date.year)
# Define day counter for discounting and accruals (using Actual360 as in Q5)
day_counter = ql.Actual360()
day_counter_coupon = ql.Thirty360(ql.Thirty360.BondBasis)
spot_date = ql.Date(26, 11, 2024)

# Build coupon schedule using Q1 data.
# For this example, we assume quarterly coupons.
frequency = ql.Quarterly
calendar = ql.TARGET()
# Convert Q1 dates to QuantLib Dates:
issue_date = ql.Date(bond_characteristics["Issue Date"].day,
                     bond_characteristics["Issue Date"].month,
                     bond_characteristics["Issue Date"].year)
maturity_date = ql.Date(bond_characteristics["Maturity Date"].day,
                        bond_characteristics["Maturity Date"].month,
                        bond_characteristics["Maturity Date"].year)
schedule = ql.Schedule(issue_date, maturity_date,
                       ql.Period(frequency),
                       calendar,
                       ql.ModifiedFollowing, ql.ModifiedFollowing,
                       ql.DateGeneration.Forward, False)

# Extract floor and cap rates and notional from bond characteristics
floor_rate = bond_characteristics["Floor"]
cap_rate = bond_characteristics["Cap"]
notional = bond_characteristics["Nominal Value"]

# ----------------------------
# 2. Build the Yield (Discount) Curve from Q3
# ----------------------------
yield_curve = build_curves()["Log-Cubic"] # Use the Log-Cubic curve (as used in Q5)
discount_curve_handle = ql.YieldTermStructureHandle(yield_curve)

# Create the 3M Euribor index based on the discount curve
index = ql.Euribor3M(discount_curve_handle)

# ----------------------------
# 3. Loop Over Coupon Periods to Decompose Coupon Components
# ----------------------------
coupon_details = []   # list to store detailed info for each period
total_coupon_pv = 0.0
shift = 0.03

# Loop from the second date onward (each coupon period is between consecutive schedule dates)
for i in range(1, len(schedule)):
    start_date = schedule[i-1]
    end_date = schedule[i] 
    if start_date < ql.Settings.instance().evaluationDate:
        continue
    accrual = day_counter.yearFraction(start_date, end_date)
    
    # Compute the forward rate for this period using the discount curve handle
    fwd_rate = discount_curve_handle.forwardRate(start_date, end_date, day_counter, ql.Simple).rate()
    
    # Determine the coupon rate using floor and cap rules:
    # Replication: coupon = fwd_rate + max(floor_rate - fwd_rate, 0) capped at cap_rate.
    # For decomposition we treat the floating part as: notional * fwd_rate * accrual,
    # and the option (floorlet) component as replicating max(floor_rate - fwd_rate, 0).
    coupon_rate = min(max(fwd_rate, floor_rate), cap_rate)
    
    # Floating Component PV: using the forward rate cash flow discounted to evaluation date
    floating_cash = notional * fwd_rate * accrual
    discount_factor = discount_curve_handle.discount(end_date)
    pv_floating = floating_cash * discount_factor
    
    # Floor Option Component:
    # Price a floorlet using QuantLib's Floorlet engine if fwd_rate is below the floor.
    # For each period, determine a volatility for the floorlet based on its time-to-expiry.
    # Use the year fraction from evaluation date to the coupon end_date as maturity for vol interpolation.
    T_expiry = day_counter.yearFraction(ql.Settings.instance().evaluationDate, end_date)
    # Strike in percent (e.g. 1.60% becomes 1.60)
    vol = interpolate_vol(T_expiry, floor_rate * 100)

    # Create a schedule for just one coupon period
    floor_schedule = ql.Schedule(
        start_date, end_date,
        ql.Period(frequency),  # frequency should match your coupon frequency
        calendar,
        ql.ModifiedFollowing, ql.ModifiedFollowing,
        ql.DateGeneration.Forward, False
    )

    black_engine = ql.BlackCapFloorEngine(
        discount_curve_handle,
        ql.QuoteHandle(ql.SimpleQuote(vol)),
        day_counter,
        shift
    )
    # Build a leg for the floorlet cash flow
    floor_leg = ql.IborLeg([notional], floor_schedule, index)

    # Create a Floor instrument with a single cashflow using the floor rate
    floor_instrument = ql.Floor(floor_leg, [floor_rate])

    # Set the pricing engine (using the same Black engine as before)
    floor_instrument.setPricingEngine(black_engine)

    # Get the NPV, which is the price of the floorlet
    pv_floor = floor_instrument.NPV()
    
    # The replicated coupon PV is the sum of the floating PV and the floor option PV.
    coupon_pv = pv_floating + pv_floor
    total_coupon_pv += coupon_pv

    # Record details for this coupon period
    coupon_details.append({
        "Period": f"{start_date.ISO()} to {end_date.ISO()}",
        "Accrual": round(accrual, 4),
        "Forward Rate (%)": round(fwd_rate * 100, 2),
        "Coupon Rate (%)": round(coupon_rate * 100, 2),
        "Floating Component PV": round(pv_floating, 4),
        "Floorlet PV": round(pv_floor, 4),
        "Total Coupon PV": round(coupon_pv, 4)
    })

# ----------------------------
# 4. PV of Notional Redemption at Maturity
# ----------------------------

# PV of the notional repayment at maturity
pv_notional = notional * discount_curve_handle.discount(maturity_date)

# Gross Price is the sum of all coupon PVs and the PV of the notional
gross_price = total_coupon_pv + pv_notional

# ----------------------------
# 5. Calculate Accrued Interest
# ----------------------------

# --- Safe forward rate helper ---
def get_forward_rate(start, end):
    # Ensure we're not asking for forward rates before the curve starts
    safe_start = max(start, spot_date)
    if safe_start >= end:
        return 0.0
    return yield_curve.forwardRate(safe_start, end, day_counter, ql.Simple).rate()


# --- Accrued Interest ---
accrued = 0.0
for i in range(len(schedule) - 1):
    start = schedule[i]
    end = schedule[i + 1]
    if start < spot_date <= end:
        # Calculate a reset date adjusted by the settlement lag
        reset_date = calendar.advance(start, -spot_lag, ql.Days)
        # Use reset_date if it's before spot_date; otherwise use spot_date directly
        start_for_fwd = reset_date if spot_date >= reset_date else spot_date
        # Obtain the forward rate for the period starting at start_for_fwd and ending at 'end'
        fwd_rate = get_forward_rate(start_for_fwd, end)
        # Apply floor and cap rules to get the effective coupon rate
        effective_rate = min(max(fwd_rate, floor_rate), cap_rate)
        # Compute the year fraction for accrued interest from the start of the period to spot_date
        yf_accrued = day_counter_coupon.yearFraction(start, spot_date)
        accrued = notional * effective_rate * yf_accrued
        break

clean_price = gross_price - accrued


# ----------------------------
# 6. Present the Results in Tables
# ----------------------------
df_coupon = pd.DataFrame(coupon_details)
summary_data = {
    "Description": ["Total Coupon PV", "PV of Notional", "Gross Price", "Accrued Interest", "Clean Price"],
    "Value": [round(total_coupon_pv, 4),
              round(pv_notional, 4),
              round(gross_price, 4),
              round(accrued, 4),
              round(clean_price, 4)]
}
df_summary = pd.DataFrame(summary_data)

print("Coupon Component Details:")
print(df_coupon.to_string(index=False))
print("\nSummary:")
print(df_summary.to_string(index=False))



# %%
