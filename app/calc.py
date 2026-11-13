"""Validation and calculation for one group's titrations (pure functions)."""
from dataclasses import dataclass
from statistics import mean, stdev

from .experiments import Experiment


@dataclass
class Titration:
    mass_g: float
    start_ml: float
    end_ml: float

    @property
    def volume_ml(self) -> float:
        return round(self.end_ml - self.start_ml, 2)


@dataclass
class TitrationResult:
    index: int
    titration: Titration
    volume_ml: float
    conc_mol_l: float
    factor: float


@dataclass
class GroupResult:
    titrations: list
    mean_factor: float
    sd_factor: float | None
    rsd_percent: float | None
    mean_conc_mol_l: float


def validate_titration(t: Titration, exp: Experiment, index: int) -> tuple[list, list]:
    """Return (errors, warnings) for one titration. Errors block saving."""
    errors, warnings = [], []
    label = f"Titration {index}"

    if t.mass_g > 2.0 and t.mass_g < 2000:
        errors.append(f"{label}: mass {t.mass_g} g is too large for this titration. "
                      "Was it entered in milligrams? Enter grams, e.g. 0.4123.")
    elif not exp.quantities[0].min_value <= t.mass_g <= exp.quantities[0].max_value:
        errors.append(f"{label}: mass must be between 0.05 and 2.0 g.")

    for name, value in (("start", t.start_ml), ("end", t.end_ml)):
        if not 0.0 <= value <= exp.burette_capacity_ml:
            errors.append(f"{label}: {name} reading must be between 0 and "
                          f"{exp.burette_capacity_ml:g} mL.")

    if t.end_ml <= t.start_ml:
        errors.append(f"{label}: end reading must be larger than start reading. "
                      "Were the two readings swapped?")
    elif t.volume_ml < 5.0:
        warnings.append(f"{label}: only {t.volume_ml:.2f} mL used. Small volumes "
                        "make the reading error relatively large.")

    if not errors:
        expected_ml = expected_volume_ml(t.mass_g, exp)
        if t.volume_ml > 1.5 * expected_ml or t.volume_ml < 0.5 * expected_ml:
            warnings.append(f"{label}: {t.volume_ml:.2f} mL is far from the "
                            f"~{expected_ml:.1f} mL expected for {t.mass_g:.4f} g KHP.")
    return errors, warnings


def expected_volume_ml(mass_g: float, exp: Experiment) -> float:
    """Volume a solution with f = 1 would need for this mass."""
    moles = mass_g / exp.standard_molar_mass_g_mol
    return moles / exp.nominal_conc_mol_l * 1000


def concentration_mol_l(mass_g: float, volume_ml: float, exp: Experiment) -> float:
    """c(NaOH) = m(KHP) / (M(KHP) * V(NaOH)); KHP and NaOH react 1:1."""
    moles = mass_g / exp.standard_molar_mass_g_mol
    return moles / (volume_ml / 1000)


def factor(conc: float, exp: Experiment) -> float:
    return conc / exp.nominal_conc_mol_l


def titration_factor(t: Titration, exp: Experiment) -> float:
    return factor(concentration_mol_l(t.mass_g, t.volume_ml, exp), exp)


def evaluate_group(titrations: list, exp: Experiment) -> GroupResult:
    results = []
    for i, t in enumerate(titrations, start=1):
        c = concentration_mol_l(t.mass_g, t.volume_ml, exp)
        results.append(TitrationResult(i, t, t.volume_ml, c, factor(c, exp)))

    factors = [r.factor for r in results]
    mean_f = mean(factors)
    sd_f = stdev(factors) if len(factors) > 1 else None
    rsd = sd_f / mean_f * 100 if sd_f is not None else None
    return GroupResult(
        titrations=results,
        mean_factor=mean_f,
        sd_factor=sd_f,
        rsd_percent=rsd,
        mean_conc_mol_l=mean_f * exp.nominal_conc_mol_l,
    )
