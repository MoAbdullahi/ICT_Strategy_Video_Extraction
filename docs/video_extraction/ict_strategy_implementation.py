import pandas as pd
import numpy as np

class ICTStrategy:
    def __init__(self, daily_data, hourly_data, fifteen_min_data):
        self.daily_df = daily_data
        self.hourly_df = hourly_data
        self.fifteen_min_df = fifteen_min_data

    def detect_fvgs(self, df):
        """Detect Fair Value Gaps (FVGs) in a given DataFrame."""
        fvgs = []
        for i in range(2, len(df)):
            # Bullish FVG
            if df['low'].iloc[i-2] > df['high'].iloc[i]:
                fvgs.append({
                    'type': 'bullish',
                    'start_idx': i-2,
                    'end_idx': i,
                    'range': (df['high'].iloc[i], df['low'].iloc[i-2])
                })
            # Bearish FVG
            elif df['high'].iloc[i-2] < df['low'].iloc[i]:
                fvgs.append({
                    'type': 'bearish',
                    'start_idx': i-2,
                    'end_idx': i,
                    'range': (df['low'].iloc[i-2], df['high'].iloc[i])
                })
        return fvgs

    def detect_bprs(self, df):
        """Detect Balanced Price Ranges (BPRs) by finding overlapping FVGs."""
        fvgs = self.detect_fvgs(df)
        bprs = []
        for i in range(len(fvgs)):
            for j in range(i + 1, len(fvgs)):
                fvg1 = fvgs[i]
                fvg2 = fvgs[j]
                
                # Check for overlap between fvg1 and fvg2
                low1, high1 = fvg1['range']
                low2, high2 = fvg2['range']
                
                overlap_low = max(low1, low2)
                overlap_high = min(high1, high2)
                
                if overlap_low < overlap_high:
                    bprs.append({
                        'range': (overlap_low, overlap_high),
                        'fvg1_idx': fvg1['start_idx'],
                        'fvg2_idx': fvg2['start_idx']
                    })
        return bprs

    def detect_swing_points(self, df, n=2):
        """Detect Swing Highs and Swing Lows."""
        swing_highs = []
        swing_lows = []
        for i in range(n, len(df) - n):
            # Swing High
            if all(df['high'].iloc[i] > df['high'].iloc[i-j] for j in range(1, n+1)) and \
               all(df['high'].iloc[i] > df['high'].iloc[i+j] for j in range(1, n+1)):
                swing_highs.append({'idx': i, 'price': df['high'].iloc[i]})
            # Swing Low
            if all(df['low'].iloc[i] < df['low'].iloc[i-j] for j in range(1, n+1)) and \
               all(df['low'].iloc[i] < df['low'].iloc[i+j] for j in range(1, n+1)):
                swing_lows.append({'idx': i, 'price': df['low'].iloc[i]})
        return swing_highs, swing_lows

    def check_cisd(self, df, swing_points, current_idx):
        """Check for Change in State of Delivery (CISD) / Market Structure Shift."""
        swing_highs, swing_lows = swing_points
        last_close = df['close'].iloc[current_idx]
        
        # Bearish CISD (Price closes below the most recent Swing Low)
        recent_swing_lows = [s for s in swing_lows if s['idx'] < current_idx]
        if recent_swing_lows:
            last_swing_low = recent_swing_lows[-1]
            if last_close < last_swing_low['price']:
                return 'bearish'
        
        # Bullish CISD (Price closes above the most recent Swing High)
        recent_swing_highs = [s for s in swing_highs if s['idx'] < current_idx]
        if recent_swing_highs:
            last_swing_high = recent_swing_highs[-1]
            if last_close > last_swing_high['price']:
                return 'bullish'
        
        return None

    def execute_strategy(self):
        """Main strategy execution logic following MTF alignment."""
        # 1. Higher Timeframe (Daily) Analysis
        daily_fvgs = self.detect_fvgs(self.daily_df)
        daily_bprs = self.detect_bprs(self.daily_df)
        
        # Example: Look for a Daily Bearish Bias
        bearish_bias_active = False
        current_daily_price = self.daily_df['close'].iloc[-1]
        
        # Check if price is within a Daily Bearish FVG or BPR
        for fvg in [f for f in daily_fvgs if f['type'] == 'bearish']:
            low, high = fvg['range']
            if low <= current_daily_price <= high:
                bearish_bias_active = True
                break
        
        if not bearish_bias_active:
            for bpr in daily_bprs:
                low, high = bpr['range']
                if low <= current_daily_price <= high:
                    bearish_bias_active = True
                    break
        
        if bearish_bias_active:
            print("Daily Bearish Bias Confirmed. Looking for Lower Timeframe Entry...")
            
            # 2. Lower Timeframe (Hourly) Confirmation
            hourly_swing_points = self.detect_swing_points(self.hourly_df)
            hourly_cisd = self.check_cisd(self.hourly_df, hourly_swing_points, len(self.hourly_df)-1)
            
            if hourly_cisd == 'bearish':
                print("Hourly Bearish CISD Confirmed. Seeking Entry...")
                
                # 3. Entry Logic (e.g., Hourly Inversion FVG)
                hourly_fvgs = self.detect_fvgs(self.hourly_df)
                # (Additional logic for FVG inversion and entry execution would go here)
                print("Strategy Signal: Potential Short Entry Identified.")
                return "Short Entry"
        
        return "No Signal"

# Example Usage (Placeholder Data)
if __name__ == "__main__":
    # In a real scenario, these would be populated with actual price data
    data = {'high': np.random.random(100), 'low': np.random.random(100), 'close': np.random.random(100)}
    df = pd.DataFrame(data)
    
    strategy = ICTStrategy(df, df, df) # Using same df for demonstration
    signal = strategy.execute_strategy()
    print(f"Current Signal: {signal}")
