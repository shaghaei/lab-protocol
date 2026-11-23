"""Experiment definitions as data.

An experiment says what each group measures (quantities with units and
plausible ranges), which constants and which formula give the result, what
result is expected and which causes typically push it too low or too high.
Built-in experiments are defined here; experiments made in the builder are
stored as JSON in the database with the same structure.
"""
import re
from dataclasses import asdict, dataclass, field

from .formula import FormulaError, parse

SYMBOL = re.compile(r"^[A-Za-z][A-Za-z0-9_]{0,19}$")
CATEGORIES = ("Titration", "Gravimetry", "Calibration", "Gas laws", "Other")
UNITS = ("", "g", "mg", "kg", "mL", "L", "µL", "mol", "mmol", "mol/L", "g/L", "°C", "K",
         "hPa", "bar", "%", "s", "min")


@dataclass
class Quantity:
    key: str
    label: str
    unit: str
    min_value: float
    max_value: float
    decimals: int
    example: float
    help_text: str = ""


@dataclass
class Constant:
    key: str
    label: str
    value: float
    unit: str = ""


@dataclass
class Experiment:
    id: str
    title: str
    category: str
    summary: str
    quantities: list
    constants: list
    formula: str
    result_label: str
    result_symbol: str
    result_unit: str
    result_decimals: int
    expected: float
    tolerance_percent: float          # usual range: expected ± this many percent
    min_spread: float                 # smallest robust SD used for class comparison
    max_rsd_percent: float            # spread between runs of one group above this is flagged
    runs: int = 3
    stations: int = 6
    constraints: list = field(default_factory=list)   # [["V_end", "V_start"], ...] meaning a > b
    causes_low: list = field(default_factory=list)
    causes_high: list = field(default_factory=list)
    procedure: list = field(default_factory=list)
    sources: list = field(default_factory=list)       # [["title", "url"], ...]
    builtin: bool = False

    @property
    def station_numbers(self) -> tuple:
        return tuple(range(1, self.stations + 1))

    @property
    def symbols(self) -> set:
        return {q.key for q in self.quantities} | {c.key for c in self.constants}

    @property
    def expected_min(self) -> float:
        return self.expected * (1 - self.tolerance_percent / 100)

    @property
    def expected_max(self) -> float:
        return self.expected * (1 + self.tolerance_percent / 100)

    def quantity(self, key: str) -> Quantity:
        return next(q for q in self.quantities if q.key == key)

    def compiled_formula(self):
        return parse(self.formula, self.symbols)

    def to_dict(self) -> dict:
        return asdict(self)


def from_dict(d: dict) -> Experiment:
    d = dict(d)
    d["quantities"] = [Quantity(**q) for q in d["quantities"]]
    d["constants"] = [Constant(**c) for c in d["constants"]]
    return Experiment(**d)


def check_definition(exp: Experiment) -> list:
    """Return a list of problems that stop an experiment from being saved."""
    problems = []
    if not exp.title.strip():
        problems.append("Give the experiment a name.")
    if exp.category not in CATEGORIES:
        problems.append("Choose a category.")
    if not 1 <= exp.runs <= 6:
        problems.append("Runs per group must be between 1 and 6.")
    if not 1 <= exp.stations <= 20:
        problems.append("Number of lab stations must be between 1 and 20.")
    if not exp.quantities:
        problems.append("Add at least one measured quantity.")
    seen = set()
    for q in exp.quantities:
        if not SYMBOL.match(q.key):
            problems.append(f"Symbol '{q.key}': start with a letter, then letters, digits or _ "
                            "(max. 20 characters).")
        if q.key in seen:
            problems.append(f"Symbol '{q.key}' is used twice.")
        seen.add(q.key)
        if not q.label.strip():
            problems.append(f"Quantity '{q.key}' needs a name.")
        if q.min_value >= q.max_value:
            problems.append(f"Quantity '{q.key}': the minimum must be smaller than the maximum.")
        if not 0 <= q.decimals <= 6:
            problems.append(f"Quantity '{q.key}': decimals must be between 0 and 6.")
        if not q.min_value <= q.example <= q.max_value:
            problems.append(f"Quantity '{q.key}': the example value must lie within min and max.")
    for c in exp.constants:
        if not SYMBOL.match(c.key):
            problems.append(f"Constant symbol '{c.key}' is not valid.")
        if c.key in seen:
            problems.append(f"Symbol '{c.key}' is used twice.")
        seen.add(c.key)
    for pair in exp.constraints:
        for key in pair:
            if key not in {q.key for q in exp.quantities}:
                problems.append(f"Rule '{pair[0]} > {pair[1]}': '{key}' is not a measured quantity.")
    if exp.expected == 0:
        problems.append("The expected result must not be zero.")
    if not 0 < exp.tolerance_percent <= 100:
        problems.append("The usual range must be between 0 and 100 %.")
    if exp.min_spread <= 0:
        problems.append("The smallest spread must be larger than zero.")
    if exp.max_rsd_percent <= 0:
        problems.append("The allowed spread between runs must be larger than zero.")
    try:
        exp.compiled_formula()
    except FormulaError as e:
        problems.append(f"Formula: {e}")
    return problems


Q = Quantity
C = Constant

NAOH_TITER = Experiment(
    id="naoh-titer",
    title="Titer of 0.1 mol/L sodium hydroxide",
    category="Titration",
    summary="Find the actual concentration of a NaOH solution by titrating a weighed primary "
            "standard, KHP. The result is the factor f that all later titrations with this "
            "solution use.",
    quantities=[
        Q("m_KHP", "Mass of KHP", "g", 0.05, 2.0, 4, 0.4100, "Analytical balance, 4 decimals."),
        Q("V_start", "Burette start reading", "mL", 0.0, 50.0, 2, 0.20, "Before the titration."),
        Q("V_end", "Burette end reading", "mL", 0.0, 50.0, 2, 20.54, "At the first lasting pink."),
    ],
    constants=[C("M_KHP", "Molar mass of KHP", 204.22, "g/mol"),
               C("c_nom", "Nominal concentration", 0.1, "mol/L")],
    formula="m_KHP / M_KHP / ((V_end - V_start) / 1000) / c_nom",
    result_label="Factor", result_symbol="f", result_unit="", result_decimals=4,
    expected=1.0, tolerance_percent=5, min_spread=0.003, max_rsd_percent=0.5, runs=3,
    constraints=[["V_end", "V_start"]],
    causes_low=[
        "Endpoint overshot: titrated past the first faint, lasting pink.",
        "Burette not rinsed with the NaOH solution, so the titrant was diluted by water.",
        "Air bubble in the burette tip that escaped during the titration.",
    ],
    causes_high=[
        "KHP not dried: the weighed mass contains moisture, so fewer moles were titrated.",
        "Endpoint taken too early: the pink faded within about 30 seconds.",
        "Part of the KHP stayed on the weighing boat and never reached the flask.",
    ],
    procedure=[
        "Weigh about 0.4 g of dried KHP on the analytical balance.",
        "Dissolve it in about 50 mL of water and add two drops of phenolphthalein.",
        "Read the burette, titrate to the first faint pink that lasts 30 seconds, read again.",
        "Repeat with two more portions of KHP.",
    ],
    sources=[["Wikibooks: Praktikum Anorganische Chemie / Titerbestimmung (CC BY-SA)",
              "https://de.wikibooks.org/wiki/Praktikum_Anorganische_Chemie/_Titerbestimmung"]],
    builtin=True,
)

VINEGAR = Experiment(
    id="vinegar-acetic-acid",
    title="Acetic acid in vinegar",
    category="Titration",
    summary="Determine how much acetic acid a vinegar contains by titrating a diluted sample "
            "with the NaOH solution of known factor.",
    quantities=[
        Q("V_sample", "Aliquot of diluted vinegar", "mL", 1.0, 50.0, 2, 20.00,
          "Volume pipetted from the 1:10 dilution."),
        Q("f_NaOH", "Factor of the NaOH solution", "", 0.8, 1.2, 4, 0.9870,
          "From the titer experiment."),
        Q("V_start", "Burette start reading", "mL", 0.0, 50.0, 2, 0.30, ""),
        Q("V_end", "Burette end reading", "mL", 0.0, 50.0, 2, 17.17, ""),
    ],
    constants=[C("c_nom", "Nominal NaOH concentration", 0.1, "mol/L"),
               C("M_HAc", "Molar mass of acetic acid", 60.05, "g/mol"),
               C("dilution", "Dilution factor", 10, "")],
    formula="f_NaOH * c_nom * (V_end - V_start) / V_sample * dilution * M_HAc",
    result_label="Acetic acid content", result_symbol="β", result_unit="g/L", result_decimals=2,
    expected=50.0, tolerance_percent=10, min_spread=0.15, max_rsd_percent=1.0, runs=3,
    constraints=[["V_end", "V_start"]],
    causes_low=[
        "Endpoint taken too early: the pink faded again.",
        "Pipette rinsed with water instead of sample, so the aliquot was diluted.",
        "Pipette filled below the mark: less sample than noted.",
    ],
    causes_high=[
        "Endpoint overshot: titrated past the first faint, lasting pink.",
        "Nominal concentration used instead of the measured factor (f = 1).",
        "Pipette filled above the mark: more sample than noted.",
    ],
    procedure=[
        "Dilute 10.00 mL of vinegar to 100.0 mL in a volumetric flask.",
        "Pipette 20.00 mL of the dilution into a flask and add phenolphthalein.",
        "Titrate with the NaOH solution to the first lasting pink. Repeat twice.",
    ],
    sources=[["Wikibooks: Praktikum Anorganische Chemie / Säure-Base-Titrationen (CC BY-SA)",
              "https://de.wikibooks.org/wiki/Praktikum_Anorganische_Chemie"]],
    builtin=True,
)

PIPETTE = Experiment(
    id="pipette-calibration",
    title="Calibration of a 10 mL volumetric pipette",
    category="Calibration",
    summary="Check how much water a 10 mL pipette really delivers by weighing it. The water "
            "temperature gives the density, and mass divided by density gives the volume.",
    quantities=[
        Q("m_empty", "Mass of the empty beaker", "g", 10.0, 200.0, 4, 49.8123, ""),
        Q("m_full", "Mass of beaker with water", "g", 10.0, 200.0, 4, 59.7856, ""),
        Q("T_water", "Water temperature", "°C", 15.0, 30.0, 1, 21.0, ""),
    ],
    constants=[],
    formula="(m_full - m_empty) / (1 - (T_water - 3.98)^2 * (T_water + 283) / "
            "(503570 * (T_water + 67.26)))",
    result_label="Delivered volume", result_symbol="V", result_unit="mL", result_decimals=3,
    expected=10.0, tolerance_percent=0.5, min_spread=0.005, max_rsd_percent=0.3, runs=5,
    constraints=[["m_full", "m_empty"]],
    causes_low=[
        "Waiting time after draining too short: liquid still ran down the inner wall.",
        "Meniscus set below the mark.",
        "Air bubble in the pipette while filling.",
    ],
    causes_high=[
        "Drops on the outside of the tip were not wiped off.",
        "The last drop in the tip was blown out, which this pipette type does not need.",
        "Meniscus set above the mark.",
    ],
    procedure=[
        "Weigh a dry beaker, note the mass.",
        "Fill the pipette with water above the mark and set the meniscus exactly on the mark.",
        "Let the water run into the beaker, touch the tip to the wall, wait the drain time.",
        "Weigh again, note the water temperature. Repeat four more times.",
    ],
    sources=[],
    builtin=True,
)

HYDRATE = Experiment(
    id="hydrate-water",
    title="Water of crystallization in copper sulfate",
    category="Gravimetry",
    summary="Heat blue copper sulfate hydrate until it turns white and weigh the water that "
            "left. The ratio of water to anhydrous salt gives the number of water molecules "
            "per formula unit.",
    quantities=[
        Q("m_crucible", "Mass of the empty crucible", "g", 5.0, 100.0, 4, 21.4530, ""),
        Q("m_before", "Crucible with hydrate", "g", 5.0, 100.0, 4, 22.5012, "Before heating."),
        Q("m_after", "Crucible after heating", "g", 5.0, 100.0, 4, 22.1230,
          "After cooling in the desiccator, constant mass."),
    ],
    constants=[C("M_H2O", "Molar mass of water", 18.015, "g/mol"),
               C("M_CuSO4", "Molar mass of CuSO4", 159.61, "g/mol")],
    formula="((m_before - m_after) / M_H2O) / ((m_after - m_crucible) / M_CuSO4)",
    result_label="Water of crystallization", result_symbol="x", result_unit="mol/mol",
    result_decimals=2,
    expected=5.0, tolerance_percent=4, min_spread=0.03, max_rsd_percent=2.0, runs=2,
    constraints=[["m_before", "m_after"], ["m_after", "m_crucible"]],
    causes_low=[
        "Not heated to constant mass: some water is still in the salt.",
        "The salt took up moisture while cooling outside the desiccator.",
    ],
    causes_high=[
        "Overheated: copper sulfate began to decompose and lost more than water.",
        "Salt spattered out of the crucible during heating.",
        "Crucible not dried beforehand, so it lost mass itself.",
    ],
    procedure=[
        "Heat the empty crucible, cool it in the desiccator and weigh it.",
        "Add about 1 g of copper sulfate pentahydrate and weigh again.",
        "Heat gently until the salt is white, cool in the desiccator, weigh.",
        "Repeat heating and weighing until the mass stays constant. Do a second sample.",
    ],
    sources=[],
    builtin=True,
)

HYDROGEN = Experiment(
    id="molar-volume-h2",
    title="Molar volume of hydrogen",
    category="Gas laws",
    summary="React a weighed piece of magnesium with hydrochloric acid, collect the hydrogen in "
            "a gas syringe and convert its volume to standard conditions.",
    quantities=[
        Q("m_Mg", "Mass of magnesium", "g", 0.005, 0.2, 4, 0.0380, ""),
        Q("V_gas", "Volume of hydrogen", "mL", 1.0, 100.0, 1, 37.8, "Read after cooling."),
        Q("T_room", "Room temperature", "°C", 10.0, 35.0, 1, 21.5, ""),
        Q("p_air", "Air pressure", "hPa", 900.0, 1100.0, 0, 1012, ""),
    ],
    constants=[C("M_Mg", "Molar mass of magnesium", 24.305, "g/mol"),
               C("T0", "Standard temperature", 273.15, "K"),
               C("p0", "Standard pressure", 1013.25, "hPa")],
    formula="(V_gas / 1000) * (p_air / p0) * (T0 / (T_room + T0)) / (m_Mg / M_Mg)",
    result_label="Molar volume at 0 °C and 1013 hPa", result_symbol="Vm", result_unit="L/mol",
    result_decimals=2,
    expected=22.41, tolerance_percent=5, min_spread=0.1, max_rsd_percent=2.0, runs=3,
    constraints=[],
    causes_low=[
        "Leak at the gas syringe or the tubing.",
        "Magnesium surface oxidised, so less metal reacted.",
        "Volume read before the reaction was complete.",
    ],
    causes_high=[
        "Volume read while the gas was still warm from the reaction.",
        "The syringe did not start at zero.",
        "Part of the weighed magnesium was lost before the reaction.",
    ],
    procedure=[
        "Weigh a short piece of clean magnesium ribbon.",
        "Connect the flask with hydrochloric acid to the gas syringe, set the syringe to zero.",
        "Add the magnesium, wait until the reaction stops and the gas has cooled, read the volume.",
        "Note room temperature and air pressure. Repeat twice.",
    ],
    sources=[],
    builtin=True,
)

BUILTINS = [NAOH_TITER, VINEGAR, PIPETTE, HYDRATE, HYDROGEN]

# Builder templates: a starting point per experiment type
TEMPLATES = {
    "titration": ("Titration: content of a sample", VINEGAR),
    "standardise": ("Titration: factor of a solution", NAOH_TITER),
    "gravimetry": ("Gravimetry: mass difference", HYDRATE),
    "calibration": ("Calibration by weighing", PIPETTE),
    "gas": ("Gas volume", HYDROGEN),
}
