"""Experiment definitions.

Each experiment describes what is measured, in which unit, which values are
plausible and which constants the calculation needs. Text is our own wording;
sources are listed in docs/experiment-naoh.md.
"""
from dataclasses import dataclass, field


@dataclass(frozen=True)
class Quantity:
    key: str
    label: str
    unit: str
    min_value: float
    max_value: float
    decimals: int
    help_text: str


@dataclass(frozen=True)
class Experiment:
    id: str
    title: str
    summary: str
    standard_name: str
    standard_molar_mass_g_mol: float
    nominal_conc_mol_l: float
    burette_capacity_ml: float
    n_titrations: int
    quantities: tuple
    # Factor range that a well-prepared ~0.1 mol/L NaOH usually shows.
    expected_f_min: float = 0.95
    expected_f_max: float = 1.05
    # Relative standard deviation (%) above which titrations count as inconsistent.
    max_rsd_percent: float = 0.5
    # Smallest robust spread (in f units) used for outlier tests, so a very
    # tight class does not flag every tiny difference.
    min_spread_f: float = 0.003
    stations: tuple = field(default_factory=lambda: (1, 2, 3, 4, 5, 6))


NAOH_TITER = Experiment(
    id="naoh-titer",
    title="Titer determination of 0.1 mol/L NaOH",
    summary=(
        "Each group weighs a primary standard (potassium hydrogen phthalate, KHP), "
        "dissolves it and titrates it with the NaOH solution to the phenolphthalein "
        "endpoint. From the mass and the volume used, the group calculates the actual "
        "concentration and the factor f = c(actual) / c(nominal)."
    ),
    standard_name="KHP (potassium hydrogen phthalate)",
    standard_molar_mass_g_mol=204.22,
    nominal_conc_mol_l=0.1,
    burette_capacity_ml=50.0,
    n_titrations=3,
    quantities=(
        Quantity("mass_g", "Mass of KHP", "g", 0.05, 2.0, 4,
                 "Read from the analytical balance, 4 decimals."),
        Quantity("start_ml", "Burette start reading", "mL", 0.0, 50.0, 2,
                 "Reading before the titration, 2 decimals."),
        Quantity("end_ml", "Burette end reading", "mL", 0.0, 50.0, 2,
                 "Reading at the endpoint, 2 decimals."),
    ),
)

EXPERIMENTS = {NAOH_TITER.id: NAOH_TITER}
