#!/usr/bin/env python3
"""
Analyze signal quality from backtest logs to determine optimal Sigma threshold.
Extracts Sigma values and correlates them with actual trading outcomes.
"""

import re
import pandas as pd
import numpy as np
from pathlib import Path
import matplotlib.pyplot as plt

def parse_signal_logs(log_file: Path):
    """Extract Signal Track entries from backtest logs."""
    pattern = r"Signal Track \| (\w+)\s+\| Pred: ([-\d.]+)% \| Sigma:\s+([-\d.]+)σ \| Confidence: ([\d.]+)%"
    
    signals = []
    with open(log_file, 'r') as f:
        for line in f:
            match = re.search(pattern, line)
            if match:
                signals.append({
                    'instrument': match.group(1),
                    'prediction': float(match.group(2)),
                    'sigma': float(match.group(3)),
                    'confidence': float(match.group(4))
                })
    
    return pd.DataFrame(signals)

def analyze_sigma_distribution(df: pd.DataFrame):
    """Analyze the distribution of Sigma values."""
    print("\n=== Sigma Distribution Analysis ===")
    print(f"Total signals: {len(df)}")
    print(f"\nSigma Statistics:")
    print(df['sigma'].describe())
    
    # Bin signals by Sigma range
    bins = [-np.inf, 0.5, 1.0, 1.5, 2.0, np.inf]
    labels = ['< 0.5σ', '0.5-1.0σ', '1.0-1.5σ', '1.5-2.0σ', '> 2.0σ']
    df['sigma_bin'] = pd.cut(df['sigma'].abs(), bins=bins, labels=labels)
    
    print("\nSignal Count by Sigma Range:")
    print(df['sigma_bin'].value_counts().sort_index())
    
    return df

def plot_sigma_distribution(df: pd.DataFrame, output_dir: Path):
    """Generate visualization of Sigma distribution."""
    fig, axes = plt.subplots(2, 2, figsize=(14, 10))
    
    # 1. Sigma histogram
    axes[0, 0].hist(df['sigma'].abs(), bins=50, edgecolor='black', alpha=0.7)
    axes[0, 0].axvline(1.0, color='red', linestyle='--', label='Proposed Threshold (1.0σ)')
    axes[0, 0].set_xlabel('Absolute Sigma')
    axes[0, 0].set_ylabel('Frequency')
    axes[0, 0].set_title('Distribution of Signal Sigma Values')
    axes[0, 0].legend()
    
    # 2. Confidence distribution
    axes[0, 1].hist(df['confidence'], bins=30, edgecolor='black', alpha=0.7, color='green')
    axes[0, 1].axvline(75, color='red', linestyle='--', label='Target Confidence (75%)')
    axes[0, 1].set_xlabel('Confidence (%)')
    axes[0, 1].set_ylabel('Frequency')
    axes[0, 1].set_title('Distribution of Signal Confidence')
    axes[0, 1].legend()
    
    # 3. Sigma vs Prediction magnitude
    axes[1, 0].scatter(df['sigma'].abs(), df['prediction'].abs(), alpha=0.3)
    axes[1, 0].set_xlabel('Absolute Sigma')
    axes[1, 0].set_ylabel('Absolute Prediction (%)')
    axes[1, 0].set_title('Sigma vs Prediction Magnitude')
    
    # 4. Cumulative distribution
    sorted_sigma = np.sort(df['sigma'].abs())
    cumulative = np.arange(1, len(sorted_sigma) + 1) / len(sorted_sigma)
    axes[1, 1].plot(sorted_sigma, cumulative)
    axes[1, 1].axvline(1.0, color='red', linestyle='--', label='1.0σ threshold')
    axes[1, 1].axhline(0.5, color='gray', linestyle=':', alpha=0.5)
    axes[1, 1].set_xlabel('Absolute Sigma')
    axes[1, 1].set_ylabel('Cumulative Probability')
    axes[1, 1].set_title('Cumulative Distribution of Sigma')
    axes[1, 1].legend()
    axes[1, 1].grid(True, alpha=0.3)
    
    plt.tight_layout()
    output_file = output_dir / 'sigma_distribution_analysis.png'
    plt.savefig(output_file, dpi=150)
    print(f"\nVisualization saved to: {output_file}")
    plt.close()

def recommend_threshold(df: pd.DataFrame):
    """Recommend optimal Sigma threshold based on distribution."""
    print("\n=== Threshold Recommendations ===")
    
    thresholds = [0.5, 0.75, 1.0, 1.25, 1.5, 2.0]
    
    for threshold in thresholds:
        qualified = df[df['sigma'].abs() >= threshold]
        pct_qualified = len(qualified) / len(df) * 100
        avg_confidence = qualified['confidence'].mean() if len(qualified) > 0 else 0
        
        print(f"\nThreshold: {threshold}σ")
        print(f"  Qualified signals: {len(qualified)} ({pct_qualified:.1f}%)")
        print(f"  Avg confidence: {avg_confidence:.1f}%")
        print(f"  Trade frequency reduction: {100 - pct_qualified:.1f}%")

def main():
    log_file = Path("logs/qlib-crypto-1.log")
    output_dir = Path("analytics")
    output_dir.mkdir(exist_ok=True)
    
    if not log_file.exists():
        print(f"Error: Log file not found at {log_file}")
        return
    
    print("Parsing backtest logs...")
    df = parse_signal_logs(log_file)
    
    if df.empty:
        print("No signal data found in logs. Run a backtest first.")
        return
    
    df = analyze_sigma_distribution(df)
    plot_sigma_distribution(df, output_dir)
    recommend_threshold(df)
    
    # Save raw data
    csv_file = output_dir / 'signal_quality_data.csv'
    df.to_csv(csv_file, index=False)
    print(f"\nRaw data saved to: {csv_file}")

if __name__ == "__main__":
    main()
