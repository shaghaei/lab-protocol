"""Seeded synthetic class for the NaOH titer experiment.

The class has 30 groups at 6 stations. Most groups work cleanly; some carry an
injected error with a known effect on f. The labels are ground truth for
evaluating the checks and are never shown in the student view.
"""
import random

from .experiments import NAOH_TITER as EXP

TRUE_FACTOR = 0.987          # the shared NaOH stock is slightly weaker than nominal
N_GROUPS = 30
SEED = 42

# group code -> injected error (station 4 is handled separately)
INJECTED = {
    "G03": "endpoint_overshoot",
    "G11": "endpoint_overshoot",
    "G19": "endpoint_overshoot",
    "G08": "wet_standard",
    "G23": "wet_standard",
    "G14": "burette_not_rinsed",
    "G26": "digit_swap",
}
FAULTY_STATION = 4
BALANCE_OFFSET_G = 0.0050    # balance at station 4 shows 5 mg too much


def _reading(value: float, rng: random.Random) -> float:
    """A burette reading: true level plus reading noise, rounded to 0.01 mL."""
    return round(value + rng.gauss(0, 0.015), 2)


def _swap_digits(value: float) -> float:
    """Swap the ones digit with the first decimal, e.g. 21.24 -> 22.14."""
    text = f"{value:.2f}"
    dot = text.index(".")
    chars = list(text)
    chars[dot - 1], chars[dot + 1] = chars[dot + 1], chars[dot - 1]
    return float("".join(chars))


def generate(seed: int = SEED) -> list:
    """Return a list of groups: dict(code, station, label, titrations=[(mass, start, end)])."""
    rng = random.Random(seed)
    groups = []
    for i in range(N_GROUPS):
        code = f"G{i + 1:02d}"
        station = EXP.stations[i % len(EXP.stations)]
        label = INJECTED.get(code, "none")
        if station == FAULTY_STATION:
            label = "balance_offset"
        overshoot = rng.uniform(0.25, 0.45)

        titrations = []
        for k in range(EXP.n_titrations):
            true_mass = round(rng.uniform(0.38, 0.46), 4)
            moles = true_mass / EXP.standard_molar_mass_g_mol
            if label == "wet_standard":
                moles *= 0.98                      # 2 % of the weighed mass is water
            volume = moles / (TRUE_FACTOR * EXP.nominal_conc_mol_l) * 1000
            volume += rng.gauss(0, 0.03)           # endpoint judgement
            if label == "endpoint_overshoot":
                volume += overshoot
            if label == "burette_not_rinsed":
                volume *= 1.012                    # titrant diluted by about 1.2 %

            shown_mass = true_mass + (BALANCE_OFFSET_G if label == "balance_offset" else 0.0)
            start_level = rng.uniform(0.0, 0.6)
            start = _reading(start_level, rng)
            end = _reading(start_level + volume, rng)
            if label == "digit_swap" and k == 1:
                end = _swap_digits(end)
            titrations.append((round(shown_mass, 4), start, end))
        groups.append({"code": code, "station": station, "label": label, "titrations": titrations})
    return groups
