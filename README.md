# Fixed Income Project (2024/25)

This project was developed as part of the MSc Mathematical Trading and Finance programme at Bayes Business School (formerly Cass). The work values a 5-year capped/floored Floating Rate Note (FRN) issued by BNP Paribas using market data from 2024. The analysis applies curve-building, derivative pricing, and risk management techniques in Python using QuantLib.

## Overview

The bond is decomposed into two parts:  
- A **Floating Rate Note (FRN)** valued using projected 3M Euribor rates  
- A **Cap/Floor Structure** valued as a portfolio of options under the Black model

The fair value is then adjusted for credit risk using a simplified **Credit Valuation Adjustment (CVA)** based on CDS spreads and bootstrapped survival probabilities. Finally, the project assesses **hedging strategies** (via swaps and CDS) and quantifies **risk exposures** using a Monte Carlo framework.

## Methodology Summary

- **Curve Building**: Construct the historical coupon schedule and interpolate a log-cubic discount curve from market data.
- **Price bond**: Forecast forward rates and price the bond as the present value of floating coupons.
- **Price replicating portfolio**:Price the cap/floor option strip using the Black model and implied volatility surface.
- **Adjust for default possibility**: Apply CVA to adjust for credit risk using a simplified hazard rate model.
- **Adjust for interest rate risk**: Hedge the bond’s interest rate and credit exposure using swaps and CDS contracts.
- **Stress-test performance**: Simulate bond value under market factor shocks (rate shifts, volatility shifts, CDS spread movements) to compute VaR and Expected Shortfall.

> See `code/` for full implementation, organized by question (Q1 to Q13).

## Figures

Key figures from the analysis are embedded below. All output charts are located in the `/figures` directory.

### Coupon Payoff Structure
![Coupon Payoff Structure](figures/couponpayoffstructure.png)

### Interpolated Log-Cubic Curve
![Log Cubic Curve](figures/logcubiccurve.png)

### Implied Volatility Surface
![Volatility Surface](figures/impvolsurface.png)

---

## Project Structure

```
Fixed-Income-Project/
├── code/                        # Full implementation for Q1–Q13
├── figures/                     # Output charts and plots
├── datasets/                    # Market data: interest rates, volatilities, CDS
├── Report.pdf                   # Final client-facing report
├── Task.pdf                     # Coursework brief
├── requirements.txt             # Required Python packages
└── README.md
```

## Requirements

Before running, install required Python libraries:

```bash
pip install -r requirements.txt
```

> Note: This project requires the `QuantLib` Python package. Refer to the [QuantLib installation guide](https://www.quantlib.org/install.shtml) if needed.

Ensure that all market data files (`MarketData.xlsx`, `shifted_black_vols.csv`, etc.) are placed in the `datasets/` folder.

## How to Run

Open the relevant script in the `code/` folder (e.g., `Q1.py`) and run via your preferred Python IDE.

## Authors

- Shaan Ali Remani  
- Basil Ibrahim  
- José Santos  
- Wincy So  

# Fixed Income Coursework
 
![Final Cousework for Fixed Income - Page 1](https://github.com/RemaniSA/Fixed-Income-Coursework/blob/main/images/Final_Coursework_FI_Page_1.jpg)

![Final Cousework for Fixed Income - Page 2](https://github.com/RemaniSA/Fixed-Income-Coursework/blob/main/images/Final_Coursework_FI_Page_2.jpg)

![Final Cousework for Fixed Income - Page 3](https://github.com/RemaniSA/Fixed-Income-Coursework/blob/main/images/Final_Coursework_FI_Page_3.jpg)

![Final Cousework for Fixed Income - Page 4](https://github.com/RemaniSA/Fixed-Income-Coursework/blob/main/images/Final_Coursework_FI_Page_4.jpg)

![Final Cousework for Fixed Income - Page 5](https://github.com/RemaniSA/Fixed-Income-Coursework/blob/main/images/Final_Coursework_FI_Page_5.jpg)

![Final Cousework for Fixed Income - Page 6](https://github.com/RemaniSA/Fixed-Income-Coursework/blob/main/images/Final_Coursework_FI_Page_6.jpg)

![Final Cousework for Fixed Income - Page 7](https://github.com/RemaniSA/Fixed-Income-Coursework/blob/main/images/Final_Coursework_FI_Page_7.jpg)

![Final Cousework for Fixed Income - Page 8](https://github.com/RemaniSA/Fixed-Income-Coursework/blob/main/images/Final_Coursework_FI_Page_8.jpg)

![Final Cousework for Fixed Income - Page 9](https://github.com/RemaniSA/Fixed-Income-Coursework/blob/main/images/Final_Coursework_FI_Page_9.jpg)

![Final Cousework for Fixed Income - Page 10](https://github.com/RemaniSA/Fixed-Income-Coursework/blob/main/images/Final_Coursework_FI_Page_10.jpg)
