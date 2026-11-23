# Built-in experiments

Written in our own words from general chemistry practice. The full definitions (ranges, decimals,
constants, causes) are in `app/experiments.py`; this page explains the chemistry and how errors move
each result.

## 1. Titer of 0.1 mol/L sodium hydroxide

NaOH solutions lose strength over time because they absorb CO₂. Each group weighs KHP (potassium
hydrogen phthalate, M = 204.22 g/mol), titrates it to the phenolphthalein endpoint and reports the
factor f = c(actual) / 0.1 mol/L.

`f = m_KHP / M_KHP / ((V_end - V_start) / 1000) / c_nom`

| Error | Effect on f |
| --- | --- |
| Endpoint overshot | lower |
| Burette not rinsed with NaOH (titrant diluted) | lower |
| Air bubble in the burette tip escapes | lower |
| KHP not dried | higher |
| Endpoint taken too early | higher |
| KHP lost during transfer | higher |
| Balance reads too high (station) | higher |

## 2. Acetic acid in vinegar

10.00 mL vinegar are diluted to 100.0 mL; a 20.00 mL aliquot is titrated with the NaOH of known factor.

`β = f_NaOH * c_nom * (V_end - V_start) / V_sample * dilution * M_HAc` (g/L, M_HAc = 60.05 g/mol)

| Error | Effect on β |
| --- | --- |
| Endpoint taken too early | lower |
| Pipette rinsed with water, aliquot diluted | lower |
| Pipette at a station delivers less than noted | lower |
| Endpoint overshot | higher |
| Nominal concentration used instead of the factor | higher (if f < 1) |

## 3. Calibration of a 10 mL volumetric pipette

The delivered water is weighed; the water temperature gives the density.

`V = (m_full - m_empty) / ρ(T)` with ρ(T) = 1 − (T − 3.98)² (T + 283) / (503570 (T + 67.26)) g/mL,
a standard approximation for the density of water (0.99820 g/mL at 20 °C).

| Error | Effect on V |
| --- | --- |
| Drain time too short | lower |
| Meniscus below the mark | lower |
| Drop on the outside of the tip not wiped | higher |
| Last drop blown out | higher |

A balance offset cancels out here, because both masses are read on the same balance.

## 4. Water of crystallization in copper sulfate

CuSO₄·5H₂O is heated to constant mass; the mass lost is water.

`x = ((m_before - m_after) / M_H2O) / ((m_after - m_crucible) / M_CuSO4)`, expected x = 5.

| Error | Effect on x |
| --- | --- |
| Not heated to constant mass | lower |
| Salt took up moisture while cooling outside the desiccator | lower |
| Overheated, partial decomposition | higher |
| Salt spattered out of the crucible | higher |

## 5. Molar volume of hydrogen

Mg + 2 HCl → MgCl₂ + H₂. The gas is collected in a gas syringe and converted to 0 °C and 1013.25 hPa
(dry gas assumed, no water vapour correction).

`Vm = (V_gas / 1000) * (p_air / p0) * (T0 / (T_room + T0)) / (m_Mg / M_Mg)`, expected 22.41 L/mol.

| Error | Effect on Vm |
| --- | --- |
| Leak at the syringe or tubing | lower |
| Magnesium surface oxidised | lower |
| Volume read before the reaction finished | lower |
| Gas still warm when read | higher |
| Syringe did not start at zero | higher |

## Sources

- Wikibooks, *Praktikum Anorganische Chemie* (CC BY-SA): https://de.wikibooks.org/wiki/Praktikum_Anorganische_Chemie
- LibreTexts, *Acid/base titration lab*: https://chem.libretexts.org/Courses/Westfield_State_University/General_Chemistry_Labs_Westfield_State/Lab_6:_Acid_base_titration
