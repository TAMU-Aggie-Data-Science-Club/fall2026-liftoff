# Physics Tests

These are the sample-value checks for the physics module. They make sure the force and atmosphere functions give the right numbers before anything gets plugged into `solve_ivp`.

## 1. How to Run

Run everything from the **repo root** (the `fall2026-liftoff` folder), not from inside `tests/`. Otherwise the `src.physics` imports won't resolve.

**Without pytest (default):**
```sh
python -m tests.test_forces
python -m tests.test_atmosphere
```
Each one prints `PASS` for every check and ends with `All N checks passed.` If a check fails, it stops and shows an `AssertionError` with the values that didn't match.

**With pytest (if installed):**
```sh
python -m pytest tests/
```

The only dependency is numpy.

---

## 2. `test_forces.py` — Forces (17 checks)

Checks `src/physics/forces.py`. The sample vehicle is roughly a Falcon 9 first stage: $T_{\text{SL}} = 7.607$ MN, $T_{\text{vac}} = 8.227$ MN, $d = 3.66$ m.

| Area | What it checks |
|---|---|
| Gravity | Constant model always gives $g_0 = 9.80665$. Inverse-square gives $g_0$ at sea level and about 9.506 m/s² at 100 km. Unknown model name raises `ValueError`. |
| Thrust | $T = T_{\text{SL}}$ at $p_0$ and $T = T_{\text{vac}}$ in vacuum. Half of $p_0$ gives 7.917 MN. Exit area comes out to about 6.119 m². $T_{\text{vac}} < T_{\text{SL}}$ raises `ValueError`. |
| Mass flow | $\dot m = T_{\text{vac}} / (g_0 I_{sp})$ |
| Drag | Reference area ≈ 10.521 m². $q = 6125$ Pa at 100 m/s at sea level. Vertical drag ≈ −32 220 N. Drag is exactly (0, 0) at V = 0 (no NaN on the pad), always opposes velocity, scales with $V^2$, and its magnitude equals $q C_D A$. |
| $C_D(M)$ | Linear interpolation inside the table and clamping at both ends |
| Arrays | Functions take numpy arrays and return arrays of the same shape |

---

## 3. `test_atmosphere.py` — US76 Atmosphere (15 checks)

Checks `src/physics/atmosphere.py` against published US Standard Atmosphere 1976 values. It also checks that the atmosphere and the forces work together.

| Area | What it checks |
|---|---|
| Sea level | $T = 288.15$ K, $p = 101\,325$ Pa, $\rho = 1.225$ kg/m³, $a \approx 340.3$ m/s |
| US76 tables | T, p, and ρ at 10, 30, 50, and 80 km match the published tables within 0.1% |
| Layer bases | T and p at each layer base match the table in PHYSICS.md §3.5 |
| Continuity | No jumps in T or p across any layer boundary (matters for `solve_ivp`) |
| Above 84.852 km | T stays at 186.946 K and p, ρ stay positive (so `thrust()` never gets a negative pressure) |
| Trends | p and ρ always decrease with altitude from 0 to 150 km |
| Consistency | $p = \rho R T$ and $a = \sqrt{\gamma R T}$ hold everywhere |
| Misc. | Geopotential conversion, below-sea-level altitudes, exponential model, bad model name raises `ValueError`, scalars return floats and arrays return arrays |
| With forces.py | Thrust at sea level is exactly $T_{\text{SL}}$. Thrust at 100 km is basically $T_{\text{vac}}$. At 10 km and 400 m/s the Mach → $C_D$ → drag chain works and gives $q C_D A$. |

---

## 4. Notes

- The Falcon 9 numbers are approximate public values used as sample inputs. They are not validation against a real launch. That is a separate deliverable.
- If you change a constant in `constants.py` (like `P0` or `R_AIR`), rerun both files. A lot of the expected values depend on them.
- When you add a new physics function, add its checks to the matching test file in the same style: a `test_` function with plain `assert`s. The runner at the bottom of each file picks it up automatically.
