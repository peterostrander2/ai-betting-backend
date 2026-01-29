"""
MATH GLITCH SIGNALS MODULE - Mathematical anomaly detection signals

This module provides mathematical anomaly detection for betting analysis.
Each function returns a score + explicit reason string.

SIGNALS:
1. Benford Anomaly - First digit distribution anomaly detection
2. Golden Ratio Alignment - Phi (1.618) alignment in lines
3. Prime Number Resonance - Prime number detection in key values
4. Numerical Symmetry - Pattern detection in numbers

ALL SIGNALS MUST RETURN:
- score: float (0-1 normalized)
- reason: str (explicit explanation or "NO_SIGNAL" reason)
- triggered: bool
"""

import os
import math
import logging
from typing import Dict, Any, List, Optional
from collections import Counter

logger = logging.getLogger("math_glitch")

# Feature flags
MATH_GLITCH_ENABLED = os.getenv("MATH_GLITCH_ENABLED", "true").lower() == "true"

# Constants
PHI = 1.6180339887  # Golden ratio
PRIMES_TO_100 = [2, 3, 5, 7, 11, 13, 17, 19, 23, 29, 31, 37, 41, 43, 47, 53, 59, 61, 67, 71, 73, 79, 83, 89, 97]


# =============================================================================
# BENFORD'S LAW ANOMALY DETECTION
# =============================================================================

def check_benford_anomaly(numbers: List[float]) -> Dict[str, Any]:
    """
    Check for Benford's Law anomalies in a set of numbers.

    Benford's Law states that in many naturally occurring datasets,
    the first digit is more likely to be small. Deviation from this
    pattern may indicate manipulation or unusual market conditions.

    Expected first-digit distribution:
    1: 30.1%, 2: 17.6%, 3: 12.5%, 4: 9.7%, 5: 7.9%
    6: 6.7%, 7: 5.8%, 8: 5.1%, 9: 4.6%

    Args:
        numbers: List of numbers to analyze

    Returns:
        Dict with score, reason, triggered, deviation, distribution
    """
    if not MATH_GLITCH_ENABLED:
        return {
            "score": 0.5,
            "reason": "MATH_GLITCH_DISABLED",
            "triggered": False,
            "deviation": None,
            "distribution": None
        }

    if not numbers or len(numbers) < 10:
        return {
            "score": 0.5,
            "reason": "INSUFFICIENT_DATA",
            "triggered": False,
            "deviation": None,
            "distribution": None
        }

    try:
        # Expected Benford distribution
        benford_expected = {
            1: 0.301, 2: 0.176, 3: 0.125, 4: 0.097, 5: 0.079,
            6: 0.067, 7: 0.058, 8: 0.051, 9: 0.046
        }

        # Extract first digits
        first_digits = []
        for n in numbers:
            if n == 0:
                continue
            abs_n = abs(n)
            while abs_n < 1:
                abs_n *= 10
            first_digit = int(str(abs_n)[0])
            if 1 <= first_digit <= 9:
                first_digits.append(first_digit)

        if not first_digits:
            return {
                "score": 0.5,
                "reason": "NO_VALID_DIGITS",
                "triggered": False,
                "deviation": None,
                "distribution": None
            }

        # Calculate observed distribution
        digit_counts = Counter(first_digits)
        total = len(first_digits)
        observed = {d: digit_counts.get(d, 0) / total for d in range(1, 10)}

        # Calculate chi-squared deviation
        chi_squared = 0
        for digit in range(1, 10):
            expected_count = benford_expected[digit] * total
            observed_count = digit_counts.get(digit, 0)
            if expected_count > 0:
                chi_squared += ((observed_count - expected_count) ** 2) / expected_count

        # Normalize deviation (0-1 scale)
        # Chi-squared critical value for df=8 at p=0.05 is ~15.5
        deviation = min(1.0, chi_squared / 30)

        if deviation >= 0.5:
            score = 0.8
            reason = f"BENFORD_ANOMALY_STRONG_dev={deviation:.2f}"
            triggered = True
        elif deviation >= 0.25:
            score = 0.65
            reason = f"BENFORD_ANOMALY_MODERATE_dev={deviation:.2f}"
            triggered = True
        else:
            score = 0.5
            reason = "BENFORD_NORMAL"
            triggered = False

        return {
            "score": score,
            "reason": reason,
            "triggered": triggered,
            "deviation": round(deviation, 3),
            "chi_squared": round(chi_squared, 2),
            "distribution": {str(k): round(v, 3) for k, v in observed.items()},
            "sample_size": total
        }

    except Exception as e:
        logger.warning("Benford analysis error: %s", e)
        return {
            "score": 0.5,
            "reason": f"CALCULATION_ERROR: {str(e)}",
            "triggered": False,
            "deviation": None,
            "distribution": None
        }


# =============================================================================
# GOLDEN RATIO ALIGNMENT
# =============================================================================

def check_golden_ratio(value: float, reference: float = None) -> Dict[str, Any]:
    """
    Check for golden ratio (phi = 1.618) alignment.

    The golden ratio appears frequently in nature and may have
    psychological significance in betting markets.

    Args:
        value: Value to check
        reference: Reference value for ratio calculation

    Returns:
        Dict with score, reason, triggered, ratio, phi_proximity
    """
    if not MATH_GLITCH_ENABLED:
        return {
            "score": 0.5,
            "reason": "MATH_GLITCH_DISABLED",
            "triggered": False,
            "ratio": None,
            "phi_proximity": None
        }

    if value == 0:
        return {
            "score": 0.5,
            "reason": "ZERO_VALUE",
            "triggered": False,
            "ratio": None,
            "phi_proximity": None
        }

    try:
        # Check various phi alignments
        alignments = []

        # Direct phi check
        if reference and reference != 0:
            ratio = max(value, reference) / min(value, reference)
            phi_diff = abs(ratio - PHI)

            if phi_diff < 0.02:
                alignments.append(("EXACT_PHI_RATIO", phi_diff))
            elif phi_diff < 0.1:
                alignments.append(("NEAR_PHI_RATIO", phi_diff))

        # Check if value is near phi multiple
        for mult in [1, 2, 5, 10]:
            target = PHI * mult
            diff = abs(value - target) / target
            if diff < 0.02:
                alignments.append((f"PHI_MULTIPLE_{mult}x", diff))

        # Check if value/10 or value/100 is near phi
        for divisor in [10, 100]:
            normalized = value / divisor
            diff = abs(normalized - PHI) / PHI
            if diff < 0.05:
                alignments.append((f"PHI_SCALED_{divisor}", diff))

        if alignments:
            best_alignment = min(alignments, key=lambda x: x[1])
            score = 0.8 if best_alignment[1] < 0.02 else 0.65
            reason = f"GOLDEN_RATIO_{best_alignment[0]}"
            triggered = True
            phi_proximity = 1 - best_alignment[1]
        else:
            score = 0.5
            reason = "NO_PHI_ALIGNMENT"
            triggered = False
            phi_proximity = None

        return {
            "score": score,
            "reason": reason,
            "triggered": triggered,
            "ratio": round(ratio, 4) if reference else None,
            "phi_proximity": round(phi_proximity, 3) if phi_proximity else None,
            "alignments_found": len(alignments)
        }

    except Exception as e:
        logger.warning("Golden ratio check error: %s", e)
        return {
            "score": 0.5,
            "reason": f"CALCULATION_ERROR: {str(e)}",
            "triggered": False,
            "ratio": None,
            "phi_proximity": None
        }


# =============================================================================
# PRIME NUMBER RESONANCE
# =============================================================================

def check_prime_resonance(value: float) -> Dict[str, Any]:
    """
    Check for prime number resonance in betting values.

    Prime numbers have special mathematical properties and may
    appear at significant market turning points.

    Args:
        value: Value to check for prime properties

    Returns:
        Dict with score, reason, triggered, prime_found, closest_prime
    """
    if not MATH_GLITCH_ENABLED:
        return {
            "score": 0.5,
            "reason": "MATH_GLITCH_DISABLED",
            "triggered": False,
            "prime_found": None,
            "closest_prime": None
        }

    try:
        # Work with integer part and common half-point values
        int_val = int(abs(value))
        half_val = int(abs(value) * 2)  # Convert half-points to integers

        resonances = []

        # Check if integer value is prime
        if int_val in PRIMES_TO_100:
            resonances.append(("DIRECT_PRIME", int_val))

        # Check if doubled value (for half-points) is prime
        if half_val in PRIMES_TO_100:
            resonances.append(("HALF_POINT_PRIME", half_val / 2))

        # Check digit sum
        digit_sum = sum(int(d) for d in str(int_val) if d.isdigit())
        if digit_sum in PRIMES_TO_100[:10]:  # First 10 primes
            resonances.append(("DIGIT_SUM_PRIME", digit_sum))

        # Find closest prime
        closest_prime = min(PRIMES_TO_100, key=lambda p: abs(p - int_val))
        distance = abs(closest_prime - int_val)

        if resonances:
            score = 0.75 if len(resonances) >= 2 else 0.65
            reason = f"PRIME_RESONANCE_{'+'.join(r[0] for r in resonances)}"
            triggered = True
        elif distance <= 1:
            score = 0.55
            reason = f"NEAR_PRIME_{closest_prime}"
            triggered = False
        else:
            score = 0.5
            reason = "NO_PRIME_RESONANCE"
            triggered = False

        return {
            "score": score,
            "reason": reason,
            "triggered": triggered,
            "prime_found": [r[1] for r in resonances] if resonances else None,
            "closest_prime": closest_prime,
            "distance_to_prime": distance
        }

    except Exception as e:
        logger.warning("Prime resonance check error: %s", e)
        return {
            "score": 0.5,
            "reason": f"CALCULATION_ERROR: {str(e)}",
            "triggered": False,
            "prime_found": None,
            "closest_prime": None
        }


# =============================================================================
# NUMERICAL SYMMETRY
# =============================================================================

def check_numerical_symmetry(value: float) -> Dict[str, Any]:
    """
    Check for numerical symmetry and palindrome patterns.

    Symmetric numbers (121, 252, 333) may have psychological
    significance in betting markets.

    Args:
        value: Value to check for symmetry

    Returns:
        Dict with score, reason, triggered, symmetry_type
    """
    if not MATH_GLITCH_ENABLED:
        return {
            "score": 0.5,
            "reason": "MATH_GLITCH_DISABLED",
            "triggered": False,
            "symmetry_type": None
        }

    try:
        # Convert to string for pattern analysis
        str_val = str(abs(value)).replace(".", "").replace("-", "")

        symmetries = []

        # Check palindrome
        if str_val == str_val[::-1] and len(str_val) >= 2:
            symmetries.append("PALINDROME")

        # Check repeating digits (111, 222, 333)
        if len(set(str_val)) == 1 and len(str_val) >= 2:
            symmetries.append("REPEATING")

        # Check mirror pattern (12.21, 34.43)
        if len(str_val) >= 4:
            mid = len(str_val) // 2
            if str_val[:mid] == str_val[mid:][::-1]:
                symmetries.append("MIRROR")

        # Check sequential (123, 234, 321)
        if len(str_val) >= 3:
            digits = [int(d) for d in str_val]
            diffs = [digits[i+1] - digits[i] for i in range(len(digits)-1)]
            if all(d == 1 for d in diffs):
                symmetries.append("ASCENDING")
            elif all(d == -1 for d in diffs):
                symmetries.append("DESCENDING")

        if symmetries:
            score = 0.75 if len(symmetries) >= 2 else 0.65
            reason = f"SYMMETRY_{'+'.join(symmetries)}"
            triggered = True
        else:
            score = 0.5
            reason = "NO_SYMMETRY"
            triggered = False

        return {
            "score": score,
            "reason": reason,
            "triggered": triggered,
            "symmetry_type": symmetries if symmetries else None,
            "analyzed_value": str_val
        }

    except Exception as e:
        logger.warning("Symmetry check error: %s", e)
        return {
            "score": 0.5,
            "reason": f"CALCULATION_ERROR: {str(e)}",
            "triggered": False,
            "symmetry_type": None
        }


# =============================================================================
# AGGREGATE MATH GLITCH SCORE
# =============================================================================

def get_math_glitch_score(
    primary_value: float = None,
    secondary_value: float = None,
    value_series: List[float] = None
) -> Dict[str, Any]:
    """
    Calculate aggregate math glitch score from all signals.

    Returns:
        Dict with overall score, all signal breakdowns, and reasons
    """
    results = {}

    if primary_value is not None:
        results["golden_ratio"] = check_golden_ratio(primary_value, secondary_value)
        results["prime"] = check_prime_resonance(primary_value)
        results["symmetry"] = check_numerical_symmetry(primary_value)

    if value_series:
        results["benford"] = check_benford_anomaly(value_series)

    if not results:
        return {
            "math_glitch_score": 0.5,
            "triggered_count": 0,
            "triggered_signals": [],
            "reasons": ["NO_INPUT_DATA"],
            "breakdown": {},
            "enabled": MATH_GLITCH_ENABLED
        }

    # Equal weights for each signal
    weights = {key: 1.0 / len(results) for key in results}

    # Calculate weighted score
    total_score = sum(
        results[key]["score"] * weights[key]
        for key in results
    )

    # Collect triggered signals
    triggered_signals = [
        key for key, result in results.items()
        if result.get("triggered", False)
    ]

    # Collect reasons
    reasons = [
        f"{key.upper()}: {results[key]['reason']}"
        for key in results
    ]

    return {
        "math_glitch_score": round(total_score, 3),
        "triggered_count": len(triggered_signals),
        "triggered_signals": triggered_signals,
        "reasons": reasons,
        "breakdown": results,
        "enabled": MATH_GLITCH_ENABLED
    }


# =============================================================================
# EXPORTS
# =============================================================================

__all__ = [
    "check_benford_anomaly",
    "check_golden_ratio",
    "check_prime_resonance",
    "check_numerical_symmetry",
    "get_math_glitch_score",
    "PHI",
    "PRIMES_TO_100",
    "MATH_GLITCH_ENABLED",
]
