# Experiment specification: titer of 0.1 mol/L NaOH

Written in our own words from general chemistry practice. Sources are listed at the end.

## Purpose

Sodium hydroxide solutions change concentration over time, mainly because they absorb CO₂ from the air.
Before a NaOH solution is used for analyses, its actual concentration is determined against a primary
standard. The result is reported as the factor f = c(actual) / c(nominal).

## Procedure in brief

1. Weigh about 0.4 g of dried KHP (potassium hydrogen phthalate) on the analytical balance.
2. Dissolve it in water and add a few drops of phenolphthalein.
3. Read the burette, titrate with the NaOH solution to the first faint pink that lasts about 30 s,
   read the burette again.
4. Repeat three times with fresh portions of KHP.

## Data model

| Quantity | Key | Unit | Resolution | Hard limits | Notes |
| --- | --- | --- | --- | --- | --- |
| Mass of KHP | `mass_g` | g | 0.0001 | 0.05–2.0 | Values 2–2000 are treated as a likely mg entry |
| Burette start reading | `start_ml` | mL | 0.01 | 0–50 | |
| Burette end reading | `end_ml` | mL | 0.01 | 0–50 | Must be larger than the start reading |

Warnings (do not block saving): volume under 5 mL; volume more than 50% away from the volume expected
for the weighed mass.

## Calculation

KHP and NaOH react 1:1.

```
n(KHP)   = m(KHP) / M(KHP)            M(KHP) = 204.22 g/mol
c(NaOH)  = n(KHP) / V(NaOH)
f        = c(NaOH) / 0.1 mol/L
```

Per group: mean f, standard deviation and relative standard deviation (RSD) of the three titrations.

## Error catalog

How common errors move the factor. This catalog is the basis of the "likely causes" in the app.

| Error | Effect on V | Effect on f | Check that catches it |
| --- | --- | --- | --- |
| Endpoint overshot | larger | lower | Class outlier, low |
| Burette not rinsed with NaOH (titrant diluted) | larger | lower | Class outlier, low |
| Air bubble in the burette tip escapes | larger reading | lower | Class outlier, low |
| KHP lost during transfer | smaller | higher | Class outlier, high |
| KHP not dried (moisture weighed as KHP) | smaller | higher | Class outlier, high |
| Endpoint taken too early (pink fades) | smaller | higher | Class outlier, high |
| Balance reads too high | — (mass too high) | higher | Station check |
| NaOH stock absorbed CO₂ | larger | lower for all groups | Class median far from 1 (stock, not group) |
| Swapped digits when writing a reading | one titration far off | spread | Typo check, RSD |
| Mass entered in mg instead of g | — | — | Blocked at entry |
| Start and end reading swapped | negative | — | Blocked at entry |

## Sources

- Wikibooks, *Praktikum Anorganische Chemie / Titerbestimmung*, CC BY-SA:
  https://de.wikibooks.org/wiki/Praktikum_Anorganische_Chemie/_Titerbestimmung
- LibreTexts, *Acid/base titration lab* (NaOH standardisation with KHP):
  https://chem.libretexts.org/Courses/Westfield_State_University/General_Chemistry_Labs_Westfield_State/Lab_6:_Acid_base_titration
