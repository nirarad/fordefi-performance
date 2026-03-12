from dataclasses import dataclass


@dataclass(frozen=True)
class RegressionThresholds:
    warning_pct: float = 10.0
    critical_pct: float = 20.0


DEFAULT_THRESHOLDS = RegressionThresholds()
