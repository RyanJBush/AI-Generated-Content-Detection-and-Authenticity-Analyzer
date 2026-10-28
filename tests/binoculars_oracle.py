"""Independent scalar oracle for Addendum A4 (pure Python, float64, no torch).

Written directly from the A4 formulas:
    O[t] = log_softmax(observer_logits[t]),  P[t] = log_softmax(performer_logits[t])
    NLL_perf = (1/(T-1)) * sum_{t=0}^{T-2} -P[t][ids[t+1]]
    XENT     = (1/T)     * sum_{t=0}^{T-1} sum_v exp(O[t][v]) * (-P[t][v])
    B        = NLL_perf / XENT
"""
import math


def log_softmax(row):
    m = max(row)
    total = 0.0
    for x in row:
        total += math.exp(x - m)
    log_z = m + math.log(total)
    return [x - log_z for x in row]


def oracle(observer_logits, performer_logits, ids):
    """observer_logits, performer_logits: T lists of V floats; ids: T ints."""
    T = len(ids)
    obs_lp = [log_softmax(row) for row in observer_logits]  # O[t]
    perf_lp = [log_softmax(row) for row in performer_logits]  # P[t]

    nll = 0.0
    for t in range(T - 1):
        nll += -perf_lp[t][ids[t + 1]]
    nll /= T - 1

    xent = 0.0
    for t in range(T):
        for v in range(len(perf_lp[t])):
            xent += math.exp(obs_lp[t][v]) * (-perf_lp[t][v])
    xent /= T

    return {"nll_performer": nll, "xent": xent, "score": nll / xent}
