#!/usr/bin/env python3
"""
AdiOS Standard C Library: Mathematical Subsystem (math.py)
Implements C99 standard mathematical functions (sin, cos, tan, sqrt, pow, exp, log)
from first principles using Taylor series expansions and Newton-Raphson approximations.
Zero external dependencies.
"""

PI = 3.14159265358979323846
TWO_PI = 2.0 * PI
HALF_PI = PI / 2.0
E = 2.71828182845904523536

def fabs(x: float) -> float:
    return -x if x < 0.0 else x

def floor(x: float) -> int:
    i = int(x)
    return i if x >= 0 or x == float(i) else i - 1

def ceil(x: float) -> int:
    i = int(x)
    return i if x <= 0 or x == float(i) else i + 1

def round(x: float) -> int:
    return int(x + 0.5) if x >= 0 else int(x - 0.5)

def sqrt(x: float) -> float:
    """Computes square root using Newton-Raphson iteration."""
    if x < 0:
        raise ValueError("Domain error in sqrt: negative number")
    if x == 0.0:
        return 0.0

    guess = x / 2.0 if x > 1.0 else 1.0
    for _ in range(20):
        guess = 0.5 * (guess + x / guess)
    return guess

def _reduce_angle(x: float) -> float:
    """Reduces angle x to range [-PI, PI]."""
    x = x % TWO_PI
    if x > PI:
        x -= TWO_PI
    elif x < -PI:
        x += TWO_PI
    return x

def sin(x: float) -> float:
    """Computes sine using 10-term Taylor series expansion."""
    x = _reduce_angle(x)
    term = x
    res = x
    x2 = x * x
    for n in range(1, 10):
        term = -term * x2 / ((2 * n) * (2 * n + 1))
        res += term
    return res

def cos(x: float) -> float:
    """Computes cosine using 10-term Taylor series expansion."""
    x = _reduce_angle(x)
    term = 1.0
    res = 1.0
    x2 = x * x
    for n in range(1, 10):
        term = -term * x2 / ((2 * n - 1) * (2 * n))
        res += term
    return res

def tan(x: float) -> float:
    c = cos(x)
    if fabs(c) < 1e-12:
        raise ZeroDivisionError("Division by zero in tan (cosine is zero)")
    return sin(x) / c

def exp(x: float) -> float:
    """Computes e^x using Taylor series."""
    # Split into integer and fractional parts
    n = int(x)
    f = x - n
    
    # Compute e^n
    e_int = 1.0
    if n > 0:
        for _ in range(n):
            e_int *= E
    elif n < 0:
        for _ in range(-n):
            e_int /= E

    # Compute e^f
    term = 1.0
    e_frac = 1.0
    for i in range(1, 15):
        term = term * f / i
        e_frac += term

    return e_int * e_frac

def log(x: float) -> float:
    """Computes natural logarithm ln(x) using area hyperbolic tangent series."""
    if x <= 0:
        raise ValueError("Domain error in log: non-positive number")

    # Range reduction: x = m * 2^k where 0.5 <= m < 1.0
    k = 0
    while x > 1.5:
        x /= 2.0
        k += 1
    while x < 0.75:
        x *= 2.0
        k -= 1

    # y = (x - 1) / (x + 1)
    y = (x - 1.0) / (x + 1.0)
    y2 = y * y
    term = y
    res = y
    for n in range(1, 15):
        term *= y2
        res += term / (2 * n + 1)

    return 2.0 * res + (k * 0.6931471805599453)

def pow(base: float, exp_val: float) -> float:
    if exp_val == 0.0:
        return 1.0
    if base == 0.0:
        return 0.0
    if exp_val == int(exp_val) and exp_val > 0:
        res = 1.0
        for _ in range(int(exp_val)):
            res *= base
        return res
    return exp(exp_val * log(base))

if __name__ == "__main__":
    assert fabs(sin(0.0)) < 1e-6
    assert fabs(sin(PI / 2.0) - 1.0) < 1e-6
    assert fabs(cos(0.0) - 1.0) < 1e-6
    assert fabs(sqrt(16.0) - 4.0) < 1e-6
    assert fabs(exp(1.0) - E) < 1e-4
    assert fabs(pow(2.0, 10.0) - 1024.0) < 1e-4
    print("LibC math functions verified.")
