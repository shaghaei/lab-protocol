"""Seeded synthetic classes for the built-in experiments.

Each class has 30 groups at 6 stations. Most groups work cleanly; some carry an
injected error with a known effect on the result, and one station has faulty
equipment. The labels are ground truth for evaluating the checks and are never
shown in the student view.
"""
import random

N_GROUPS = 30
N_STATIONS = 6
SEED = 42


def station_of(n: int) -> int:
    return (n - 1) % N_STATIONS + 1


def _rho_water(t: float) -> float:
    return 1 - (t - 3.98) ** 2 * (t + 283) / (503570 * (t + 67.26))


def _burette(rng, volume):
    start = rng.uniform(0.0, 0.6)
    return round(start + rng.gauss(0, 0.015), 2), round(start + volume + rng.gauss(0, 0.015), 2)


def sim_naoh(rng, mech):
    m = round(rng.uniform(0.38, 0.46), 4)
    n = m / 204.22 * (0.98 if mech == "wet_standard" else 1)
    v = n / (0.987 * 0.1) * 1000 + rng.gauss(0, 0.03)
    if mech == "overshoot":
        v += rng.uniform(0.25, 0.45)
    if mech == "not_rinsed":
        v *= 1.012
    shown = m + (0.0050 if mech == "station" else 0)    # balance reads 5 mg high
    start, end = _burette(rng, v)
    return {"m_KHP": round(shown, 4), "V_start": start, "V_end": end}


def sim_vinegar(rng, mech):
    aliquot = 19.85 if mech == "station" else 20.00       # pipette at the station delivers less
    n = aliquot / 1000 * (50.2 / 60.05 / 10)
    v = n / (0.987 * 0.1) * 1000 + rng.gauss(0, 0.03)
    if mech == "early_endpoint":
        v -= rng.uniform(0.2, 0.35)
    if mech == "overshoot":
        v += rng.uniform(0.25, 0.4)
    start, end = _burette(rng, v)
    f = 1.0 if mech == "wrong_factor" else 0.987
    return {"V_sample": 20.00, "f_NaOH": f, "V_start": start, "V_end": end}


def sim_pipette(rng, mech):
    t = round(rng.uniform(19.5, 22.5), 1)
    volume = 9.992 + rng.gauss(0, 0.004)
    volume += {"drain_time": -rng.uniform(0.02, 0.035), "outer_drop": rng.uniform(0.02, 0.03),
               "station": -0.04}.get(mech, 0)
    m_empty = round(rng.uniform(40, 60), 4)
    m_full = round(m_empty + volume * _rho_water(t) + rng.gauss(0, 0.0002), 4)
    return {"m_empty": m_empty, "m_full": m_full, "T_water": t}


def sim_hydrate(rng, mech):
    c = round(rng.uniform(18, 25), 4)
    mh = rng.uniform(0.9, 1.2)
    n = mh / 249.685
    x = 4.97 + rng.gauss(0, 0.02)
    x += {"incomplete": -rng.uniform(0.2, 0.3), "overheated": rng.uniform(0.15, 0.25),
          "station": -0.12}.get(mech, 0)
    m_before = c + mh
    m_after = c + n * 159.61 + n * (5 - x) * 18.015
    return {"m_crucible": c, "m_before": round(m_before + rng.gauss(0, 0.0001), 4),
            "m_after": round(m_after + rng.gauss(0, 0.0001), 4)}


def sim_hydrogen(rng, mech):
    m = round(rng.uniform(0.030, 0.045), 4)
    t = round(rng.uniform(20, 23), 1)
    p = round(rng.uniform(1005, 1020))
    vm = 22.30 * (1 + rng.gauss(0, 0.004))
    vm *= {"leak": 0.96, "warm_gas": 1.03, "station": 0.97}.get(mech, 1)
    v = vm * (m / 24.305) * ((t + 273.15) / 273.15) * (1013.25 / p) * 1000 + rng.gauss(0, 0.15)
    return {"m_Mg": m, "V_gas": round(v, 1), "T_room": t, "p_air": float(p)}


# experiment id -> (simulator, faulty station, direction of the station fault,
#                   key to corrupt for the typo case, {group: (label, mechanism)})
CLASSES = {
    "naoh-titer": (sim_naoh, 4, "high", "V_end", {
        "G03": ("low", "overshoot"), "G11": ("low", "overshoot"), "G19": ("low", "overshoot"),
        "G14": ("low", "not_rinsed"), "G08": ("high", "wet_standard"),
        "G23": ("high", "wet_standard"), "G26": ("swap", None)}),
    "vinegar-acetic-acid": (sim_vinegar, 3, "low", "V_end", {
        "G02": ("low", "early_endpoint"), "G13": ("low", "early_endpoint"),
        "G05": ("high", "overshoot"), "G18": ("high", "overshoot"),
        "G10": ("high", "wrong_factor"), "G29": ("swap", None)}),
    "pipette-calibration": (sim_pipette, 5, "low", "m_full", {
        "G01": ("low", "drain_time"), "G14": ("low", "drain_time"),
        "G06": ("high", "outer_drop"), "G20": ("high", "outer_drop"), "G27": ("swap", None)}),
    "hydrate-water": (sim_hydrate, 2, "low", None, {
        "G03": ("low", "incomplete"), "G16": ("low", "incomplete"),
        "G07": ("high", "overheated"), "G24": ("high", "overheated")}),
    "molar-volume-h2": (sim_hydrogen, 6, "low", "V_gas", {
        "G04": ("low", "leak"), "G15": ("low", "leak"), "G09": ("high", "warm_gas"),
        "G25": ("high", "warm_gas"), "G20": ("swap", None)}),
}


def swap_digits(value: float, decimals: int) -> float:
    """Swap the ones digit with the first decimal (or tens and ones), e.g. 21.24 -> 22.14."""
    text = f"{value:.{decimals}f}"
    chars = list(text)
    dot = text.find(".")
    i, j = (dot - 1, dot + 1) if dot > 0 else (len(text) - 2, len(text) - 1)
    if chars[i] == chars[j] and dot > 1:
        i, j = dot - 2, dot - 1
    chars[i], chars[j] = chars[j], chars[i]
    return float("".join(chars))


def generate(exp, seed: int = SEED) -> list:
    """Groups for a built-in experiment: dict(code, station, label, mechanism, runs=[{...}])."""
    if exp.id not in CLASSES:
        return []
    sim, faulty, _, swap_key, injected = CLASSES[exp.id]
    rng = random.Random(f"{seed}-{exp.id}")
    groups = []
    for n in range(1, N_GROUPS + 1):
        code = f"G{n:02d}"
        station = station_of(n)
        label, mech = injected.get(code, ("none", None))
        if station == faulty:
            label, mech = "station", "station"
        runs = [sim(rng, mech) for _ in range(exp.runs)]
        if label == "swap" and swap_key:
            q = exp.quantity(swap_key)
            runs[1][swap_key] = swap_digits(runs[1][swap_key], q.decimals)
        groups.append({"code": code, "station": station, "label": label, "mechanism": mech,
                       "runs": runs})
    return groups
