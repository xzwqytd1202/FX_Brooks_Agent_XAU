import os
import sys
import datetime
import platform

# Add the current directory to sys.path to import app
sys.path.append(os.getcwd())

try:
    from app import config
    from app.services.global_risk import GlobalRiskService
except ImportError as e:
    print(f"Error importing app: {e}")
    sys.exit(1)

def run_diagnostic():
    print("="*50)
    print("FX_Brooks_Agent Diagnostic Tool")
    print("="*50)
    
    # 1. System Info
    print(f"OS: {platform.system()} {platform.release()}")
    print(f"Python: {sys.version}")
    print(f"Current Directory: {os.getcwd()}")
    
    # 2. Time Info
    now = datetime.datetime.now()
    utc_now = datetime.datetime.utcnow()
    print(f"Local Time: {now.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"UTC Time: {utc_now.strftime('%Y-%m-%d %H:%M:%S')}")
    
    # 3. Beijing Time Calculation (Logic from global_risk.py)
    # Note: global_risk.py uses data.server_time_hour. 
    # Here we assume local machine time is either Server time or similar for testing.
    hour_diff = 6 if config.IS_WINTER_TIME else 5
    bj_h = (now.hour + hour_diff) % 24
    print(f"Config Winter Time: {config.IS_WINTER_TIME}")
    print(f"Hour Diff (Server to BJ): {hour_diff}")
    print(f"If Local==Server, Estimated BJ Time: {bj_h:02d}:{now.minute:02d}")
    
    # 4. Config Constants
    print("-" * 30)
    print("Trading Hours (BJ):")
    print(f"  No Trade: {config.NO_TRADE_START_H_BJ} - {config.NO_TRADE_END_H_BJ}")
    print(f"  Rollover: {config.ROLLOVER_START_H_BJ} - {config.ROLLOVER_END_H_BJ}")
    
    print("-" * 30)
    print("Spread Limits:")
    print(f"  Max Spread ATR Ratio: {config.MAX_SPREAD_ATR_RATIO}")
    print(f"  Spread Floor Points: {config.SPREAD_FLOOR_POINTS}")
    
    print("-" * 30)
    print("Risk Settings:")
    print(f"  Max Positions: {config.MAX_POSITIONS_COUNT}")
    print(f"  Risk Per Trade: ${config.RISK_PER_TRADE_USD}")
    print(f"  Min Margin Level: {config.MIN_MARGIN_LEVEL}%")
    
    print("="*50)
    print("Diagnosis Suggestions:")
    if config.SPREAD_FLOOR_POINTS >= 400:
        print("* SPREAD_FLOOR_POINTS is set to 400. If EBC spreads are often > 40 pips, trades will be filtered.")
    
    # Check if we are in trading hours
    bj_decimal = bj_h + (now.minute / 60.0)
    is_no_trade = config.NO_TRADE_START_H_BJ <= bj_decimal < config.NO_TRADE_END_H_BJ
    if is_no_trade:
        print(f"* CURRENTLY IN NO_TRADE_HOURS (BJ {bj_decimal:.2f})")
    
    print("Finished.")

if __name__ == "__main__":
    run_diagnostic()
