import pandas as pd
import numpy as np
from typing import Dict, Any, Optional

class Forecaster:
    def generate_forecast(self, metrics_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Generates a simple linear revenue forecast for the next 3 years.
        Returns None if insufficient data.
        """
        if "history" not in metrics_data or not metrics_data["history"]:
            return None

        try:
            df = pd.DataFrame(metrics_data["history"])
            
            # Identify Revenue column
            cols = [c for c in df.columns if "Revenue" in c]
            if not cols:
                return None
            rev_col = cols[0]
            
            # Need at least 2 points for linear regression
            if len(df) < 2:
                return None

            # Simple Linear Regression (Year vs Revenue)
            # Assuming 'Year' exists, otherwise use index 0,1,2...
            if 'Year' in df.columns:
                X = df['Year'].values
            else:
                X = np.arange(len(df))
            
            y = df[rev_col].values
            
            # Simple fit
            slope, intercept = np.polyfit(X, y, 1)
            
            # Next 3 years
            last_x = X[-1]
            future_X = [last_x + 1, last_x + 2, last_x + 3]
            future_y = [slope * x + intercept for x in future_X]
            
            return {
                "method": "linear_regression",
                "forecast_years": [int(x) for x in future_X],
                "forecast_revenue": [float(val) for val in future_y],
                "slope": float(slope)
            }
            
        except Exception:
            # Never raise, just return None
            return None
