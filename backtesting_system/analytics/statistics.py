from __future__ import annotations

from typing import Iterable, Tuple


try:
    from scipy import stats
except Exception:  # pragma: no cover - optional dependency
    stats = None


def t_test_independent(a: Iterable[float], b: Iterable[float]) -> Tuple[float, float]:
    if stats is None:
        raise ImportError("scipy is required for t-tests. Install with: pip install scipy")
    a_list = [x for x in a if x is not None]
    b_list = [x for x in b if x is not None]
    if len(a_list) < 2 or len(b_list) < 2:
        return 0.0, 1.0
    t_stat, p_value = stats.ttest_ind(a_list, b_list, equal_var=False, nan_policy="omit")
    return float(t_stat), float(p_value)


def binomial_test(successes: int, trials: int, p: float = 0.5) -> float:
    if stats is None:
        raise ImportError("scipy is required for binomial tests. Install with: pip install scipy")
    if trials == 0:
        return 1.0
    try:
        return float(stats.binom_test(successes, trials, p, alternative="greater"))
    except AttributeError:
        return float(stats.binomtest(successes, trials, p, alternative="greater").pvalue)


def anova_oneway(*groups: Iterable[float]) -> Tuple[float, float]:
    if stats is None:
        raise ImportError("scipy is required for ANOVA. Install with: pip install scipy")
    cleaned = [list(g) for g in groups if len(list(g)) > 1]
    if len(cleaned) < 2:
        return 0.0, 1.0
    f_stat, p_value = stats.f_oneway(*cleaned)
    return float(f_stat), float(p_value)


def pearson_correlation(a: Iterable[float], b: Iterable[float]) -> Tuple[float, float]:
    if stats is None:
        raise ImportError("scipy is required for Pearson correlation. Install with: pip install scipy")
    a_list = [x for x in a if x is not None]
    b_list = [x for x in b if x is not None]
    if len(a_list) < 2 or len(b_list) < 2:
        return 0.0, 1.0
    r_val, p_value = stats.pearsonr(a_list, b_list)
    return float(r_val), float(p_value)
