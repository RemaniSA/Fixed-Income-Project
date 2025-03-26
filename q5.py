# %%
import os
import pandas as pd
import numpy as np
import QuantLib as ql

from q1 import bond_characteristics
from q3 import build_curves

# ----------------------------
# 0. setup and load curve
# ----------------------------

ROOT_PATH = os.path.dirname(__file__)
vol_path = os.path.join(ROOT_PATH, 'datasets', 'shifted_black_vols.csv')

log_cubic_curve = build_curves()["Log-Cubic"]
eval_date = ql.Settings.instance().evaluationDate
calendar = ql.TARGET()

cap_rate = bond_characteristics["Cap"]
floor_rate = bond_characteristics["Floor"]
notional = bond_characteristics["Nominal Value"]
settlement_lag = bond_characteristics["Settlement Lag"]
issue_date = ql.Date(bond_characteristics["Issue Date"].day,
                     bond_characteristics["Issue Date"].month,
                     bond_characteristics["Issue Date"].year)
maturity_date = ql.Date(29, 7, 2027)  # from coursework
frequency = ql.Quarterly
day_counter = ql.Actual360()
shift = 0.03

# ----------------------------
# 1. load and process vol surface
# ----------------------------

def load_shifted_vol_surface(filepath):
    """
    Loads a shifted volatility surface from a CSV file, processes the data, and returns it as a DataFrame.

    The function reads a CSV file containing a volatility surface, removes unnecessary columns 
    ("STK" and "ATM" if they exist), converts the "Maturity" column to float, and sets it as the 
    index of the DataFrame. The column names are also converted to floats, and the values are 
    scaled from basis points (bps) to decimals.

    Args:
        filepath (str): The file path to the CSV file containing the shifted volatility surface.

    Returns:
        pandas.DataFrame: A DataFrame containing the processed volatility surface, with maturities 
        as the index and scaled volatilities as the values.
    """
    df = pd.read_csv(filepath)
    df = df.drop(columns=["STK", "ATM"], errors="ignore")
    df["Maturity"] = df["Maturity"].astype(float)
    df.set_index("Maturity", inplace=True)
    df.columns = df.columns.astype(float)
    return df / 100  # convert bps to decimals

vol_surface = load_shifted_vol_surface(vol_path)

def interpolate_vol(maturity, strike_percent):
    """
    Interpolates the implied volatility for a given option maturity and strike percentage
    using a volatility surface.

    Parameters:
        maturity (float): The maturity of the option in years. If the exact maturity
                          is not available in the volatility surface, the closest
                          available maturity will be used.
        strike_percent (float): The strike price as a percentage of the underlying asset's
                                current price.

    Returns:
        float: The interpolated implied volatility corresponding to the given maturity
               and strike percentage.

    Notes:
        - The function assumes the existence of a global variable `vol_surface`, which
          is a pandas DataFrame where the rows represent maturities, the columns represent
          strike percentages, and the values represent implied volatilities.
        - If the exact maturity is not found in the volatility surface, the closest
          maturity is selected based on the absolute difference.
        - Linear interpolation is performed using numpy's `interp` function to estimate
          the implied volatility for the given strike percentage.
    """
    if maturity not in vol_surface.index:
        maturity = min(vol_surface.index, key=lambda x: abs(x - maturity))
    row = vol_surface.loc[maturity]
    strikes = row.index.to_numpy()
    vols = row.values
    return np.interp(strike_percent, strikes, vols)

# ----------------------------
# 2. build cap/floor schedule and leg
# ----------------------------

schedule = ql.Schedule(
    max(eval_date, issue_date), maturity_date,
    ql.Period(frequency),
    calendar,
    ql.ModifiedFollowing, ql.ModifiedFollowing,
    ql.DateGeneration.Forward, False
)

index = ql.Euribor3M(ql.YieldTermStructureHandle(log_cubic_curve))
float_leg = ql.IborLeg([notional], schedule, index)

# ----------------------------
# 3. create cap and floor instruments
# ----------------------------

cap = ql.Cap(float_leg, [cap_rate])
floor = ql.Floor(float_leg, [floor_rate])

# determine maturity for vol interpolation
maturity = round(day_counter.yearFraction(eval_date, maturity_date))
vol_cap = interpolate_vol(maturity, cap_rate * 100)
vol_floor = interpolate_vol(maturity, floor_rate * 100)

# ----------------------------
# 4. assign BlackCapFloorEngine
# ----------------------------

def make_engine(vol):
    """
    Creates a BlackCapFloorEngine with the specified volatility.
    
    Parameters:
        vol (float): The volatility to use in the BlackCapFloorEngine.

    Returns:
        ql.BlackCapFloorEngine: The BlackCapFloorEngine object with the specified
        volatility and other parameters set.    
    """
    return ql.BlackCapFloorEngine(
        ql.YieldTermStructureHandle(log_cubic_curve),
        ql.QuoteHandle(ql.SimpleQuote(vol)),
        day_counter,
        shift
    )

fixing_date = eval_date  # since our data is our Eval Date
index.addFixing(fixing_date, cap_rate)

cap.setPricingEngine(make_engine(vol_cap))
floor.setPricingEngine(make_engine(vol_floor))

npv_cap = cap.NPV()
npv_floor = floor.NPV()

# ----------------------------
# 5. results
# ----------------------------

print(f"cap leg NPV (short):  {-npv_cap:.4f}")
print(f"floor leg NPV (long): {npv_floor:.4f}")
print(f"net option value (floor - cap): {npv_floor - npv_cap:.4f}")

# %%
