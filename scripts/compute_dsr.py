#!/usr/bin/env python3
"""Compute the Deflated Sharpe Ratio (DSR) for the EURUSD walk-forward results.

Based on Bailey & Lopez de Prado (2014): "The Deflated Sharpe Ratio:
Correcting for Selection Bias, Backtest Overfitting, and Non-Normality".

The DSR adjusts the observed Sharpe ratio for the implicit multiple-testing
bias that arises from testing N strategy configurations and selecting the
best. Even though we report the "best" strategy (daily_swing_framework),
the search space includes multiple instruments, cost scenarios, and rule
variants.

Usage:
    python scripts/compute_dsr.py
"""

from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np
from scipy import stats


def load_oos_sharpes(wf_path: Path) -> list[float]:
    """Extract OOS Sharpe ratios from a walk-forward JSON file."""
    with open(wf_path) as f:
        data = json.load(f)
    windows = data["walk_forward"]["windows"]
    return [w["test_report"]["sharpe"] for w in windows]


def compute_dsr(
    observed_sharpe: float,
    n_obs: int,
    skew: float,
    kurtosis_excess: float,
    n_trials: int,
    avg_n_trades: int,
) -> dict[str, float]:
    """Compute the Deflated Sharpe Ratio.

    Parameters
    ----------
    observed_sharpe : float
        The observed (or estimated) Sharpe ratio of the strategy.
    n_obs : int
        Number of independent observations (e.g., number of WF windows).
    skew : float
        Skewness of the return distribution.
    kurtosis_excess : float
        Excess kurtosis (kurtosis - 3) of the return distribution.
    n_trials : int
        Number of strategy configurations tested (the implicit search space).
    avg_n_trades : int
        Average number of trades per observation window.

    Returns
    -------
    dict with keys: dsr, e_max_sr, observed_sharpe, threshold
    """
    # E[max(SR_N)] under the null (all strategies have zero true Sharpe)
    # Approximation from Bailey & Lopez de Prado eq. (17):
    # E[max(SR_0)] ≈ (1-γ)*Φ^{-1}(1-1/N) + γ*Φ^{-1}(1-1/(N*e))
    # where γ ≈ Euler-Mascheroni constant ≈ 0.5772
    gamma = 0.5772156649015329  # Euler-Mascheroni

    # For n_trials = 1, E[max] = 0 (no multiple testing)
    if n_trials <= 1:
        e_max_sr = 0.0
    else:
        e_max_sr = (1 - gamma) * stats.norm.ppf(1 - 1.0 / n_trials) + \
                   gamma * stats.norm.ppf(1 - 1.0 / (n_trials * math.e))

    # DSR formula (Bailey & Lopez de Prado, eq. 14):
    # DSR = Φ((SR - E[max(SR_N)]) * sqrt(n-1) / sqrt(1 - γ₃*SR + (γ₄-1)/4 * SR²))
    # where γ₃ = skewness, γ₄ = kurtosis (not excess)
    #
    # Here we use the per-window Sharpe values, so n = n_obs (number of windows)
    # and SR = observed_sharpe

    numerator = (observed_sharpe - e_max_sr) * math.sqrt(n_obs - 1)
    denominator = math.sqrt(
        max(1e-12, 1 - skew * observed_sharpe + (kurtosis_excess) / 4.0 * observed_sharpe ** 2)
    )

    z = numerator / denominator
    dsr = stats.norm.cdf(z)

    return {
        "dsr": dsr,
        "e_max_sr": e_max_sr,
        "observed_sharpe": observed_sharpe,
        "z_score": z,
        "n_trials": n_trials,
        "n_windows": n_obs,
    }


def main() -> None:
    repo = Path(__file__).resolve().parent.parent

    # Load walk-forward OOS Sharpe values for all symbols
    wf_paths = {
        "EURUSD": repo / "results" / "walk_forward.json",
        "GBPUSD": repo / "results" / "multi_asset" / "GBPUSD" / "walk_forward.json",
        "USDJPY": repo / "results" / "multi_asset" / "USDJPY" / "walk_forward.json",
        "XAUUSD": repo / "results" / "multi_asset" / "XAUUSD" / "walk_forward.json",
        "USA500": repo / "results" / "multi_asset" / "USA500IDXUSD" / "walk_forward.json",
        "USATECH": repo / "results" / "multi_asset" / "USATECHIDXUSD" / "walk_forward.json",
    }

    # Conservative estimate of the implicit search space:
    # 6 instruments × 2 strategy types (daily_swing, composite) ×
    # 3 cost scenarios × ~2 parameter variants (risk, partial_exit) = ~72
    # But we're computing DSR for the "selected best" daily_swing on each
    # instrument, so N_trials should reflect how many configs we tested
    # before settling on daily_swing.
    # Conservative: 6 instruments × 3 cost scenarios = 18
    # More conservative: include composite + benchmarks = ~36
    n_trials = 36  # conservative estimate

    print("=" * 70)
    print("DEFLATED SHARPE RATIO (Bailey & Lopez de Prado 2014)")
    print(f"Assumed search space (N_trials): {n_trials}")
    print("=" * 70)
    print()

    # LaTeX table rows
    latex_rows = []

    for symbol, path in wf_paths.items():
        if not path.exists():
            print(f"{symbol}: walk-forward data not found at {path}")
            continue

        oos_sharpes = load_oos_sharpes(path)
        n_obs = len(oos_sharpes)

        if n_obs < 3:
            print(f"{symbol}: too few windows ({n_obs}) for DSR computation")
            continue

        arr = np.array(oos_sharpes)
        mean_sr = float(np.mean(arr))
        std_sr = float(np.std(arr, ddof=1))
        skew_val = float(stats.skew(arr))
        kurt_val = float(stats.kurtosis(arr))  # excess kurtosis

        # The observed Sharpe for DSR is the average OOS Sharpe across windows
        # (this is what the WF pipeline reports as avg_oos_sharpe)
        result = compute_dsr(
            observed_sharpe=mean_sr,
            n_obs=n_obs,
            skew=skew_val,
            kurtosis_excess=kurt_val,
            n_trials=n_trials,
            avg_n_trades=int(np.mean([20] * n_obs)),  # approximate
        )

        print(f"{symbol}:")
        print(f"  OOS Sharpes:       {[f'{s:.3f}' for s in oos_sharpes]}")
        print(f"  Mean OOS Sharpe:   {mean_sr:.3f}")
        print(f"  Std OOS Sharpe:    {std_sr:.3f}")
        print(f"  Skewness:          {skew_val:.3f}")
        print(f"  Excess Kurtosis:   {kurt_val:.3f}")
        print(f"  E[max(SR_{n_trials})]:  {result['e_max_sr']:.3f}")
        print(f"  DSR z-score:       {result['z_score']:.3f}")
        print(f"  DSR (Φ(z)):        {result['dsr']:.4f}")
        print()

        latex_rows.append(
            f"    {symbol:<8} & ${mean_sr:+.3f}$ & {std_sr:.3f} & "
            f"{skew_val:+.3f} & {kurt_val:+.3f} & ${result['dsr']:.4f}$ \\\\"
        )

    # Print LaTeX table
    print()
    print("% LaTeX table snippet:")
    print("\\begin{table}[htbp]")
    print("  \\centering")
    print("  \\caption{Deflated Sharpe Ratio estimate, daily-swing framework, all instruments. "
          "DSR adjusts the average OOS Sharpe for the implicit search-space size ($N=36$).}")
    print("  \\label{tab:dsr}")
    print("  \\begin{tabular}{lrrrrr}")
    print("    \\toprule")
    print("    Instrument & Avg OOS-Sharpe & $\\sigma$ & Skew & Excess $\\kappa$ & DSR \\\\")
    print("    \\midrule")
    for row in latex_rows:
        print(row)
    print("    \\bottomrule")
    print("  \\end{tabular}")
    print("\\end{table}")

    # Also print a short paragraph for the paper
    print()
    print("% Suggested paragraph for the DSR subsection:")
    print("%")
    eur_dsr = compute_dsr(
        observed_sharpe=-3.223,
        n_obs=7,
        skew=0.0,  # placeholder
        kurtosis_excess=-1.5,  # placeholder
        n_trials=n_trials,
        avg_n_trades=22,
    )
    print(f"% For EURUSD with N=36 trials, E[max(SR)] = {eur_dsr['e_max_sr']:.3f}.")
    print(f"% Since the observed OOS Sharpe ({eur_dsr['observed_sharpe']:.3f}) is far below")
    print(f"% E[max(SR)], the DSR = {eur_dsr['dsr']:.4f} — essentially zero probability")
    print(f"% that this Sharpe represents a true positive edge corrected for multiple testing.")


if __name__ == "__main__":
    main()
