"""
analyze/ — Deterministic GSC analysis modules.

Each module exports a single `analyze(data_dir, **kwargs)` function that:
  1. Loads the relevant JSON files from the data directory.
  2. Computes findings deterministically (no LLM, no randomness).
  3. Returns a list of finding dicts, each with a human-readable "so_what" field.

The CTR benchmark curve is defined once here and imported by any module that needs it.
"""

# Standard position → CTR benchmark curve.
# Source: industry consensus from Sistrix, Backlinko, and Advanced Web Rankings studies.
# Intentionally conservative estimates to avoid over-promising click gains.
# Positions beyond 20 are treated as negligible (~0.3%).
CTR_BENCHMARK: dict[int, float] = {
    1:  0.284,
    2:  0.148,
    3:  0.103,
    4:  0.073,
    5:  0.053,
    6:  0.040,
    7:  0.031,
    8:  0.025,
    9:  0.021,
    10: 0.018,
    11: 0.015,
    12: 0.013,
    13: 0.012,
    14: 0.011,
    15: 0.010,
    16: 0.009,
    17: 0.008,
    18: 0.007,
    19: 0.007,
    20: 0.006,
}

# Default CTR for positions beyond 20.
CTR_BENCHMARK_FALLBACK = 0.003


def expected_ctr(position: float) -> float:
    """
    Return the expected CTR for a given (possibly fractional) position.

    Uses linear interpolation between the two nearest integer positions in
    CTR_BENCHMARK. Positions > 20 return CTR_BENCHMARK_FALLBACK.
    """
    if position <= 0:
        return CTR_BENCHMARK[1]
    pos_floor = int(position)
    pos_ceil = pos_floor + 1

    ctr_floor = CTR_BENCHMARK.get(pos_floor, CTR_BENCHMARK_FALLBACK)
    ctr_ceil = CTR_BENCHMARK.get(pos_ceil, CTR_BENCHMARK_FALLBACK)

    # Fractional interpolation.
    frac = position - pos_floor
    return ctr_floor + frac * (ctr_ceil - ctr_floor)
