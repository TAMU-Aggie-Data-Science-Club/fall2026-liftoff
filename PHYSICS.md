# Physics Overview

## 1. Coordinate Frame and State Vector

**Frame:** flat-Earth model that doesn't rotate. The plane of motion is the launch azimuth plane.
-  $x$: downrange distance from the pad, horizontal (m)
- $h$: geometric altitude above mean sea level, positive up (m). Initial value is $h_0 =$ site_altitude
- Origin: the launch pad. $x_0 = 0$ and $h_0 = h_{site}$

**State Vector:** 

$$
\mathbf{y} = \begin{bmatrix} x & h & v_x & v_y & m \end{bmatrix}^T

\quad [\text{m},\ \text{m},\ \text{m/s},\ \text{m/s},\ \text{kg}]
$$

---

## 2. Equations of Motion

Newton's second law of motion for a variable-mass point. Thrust is equal to exhaust momentum flux.

$$
\dot x = v_x \\
\dot h = v_y \\
\dot v_x = \frac{T(h)\cos\theta\ - \ D(h, V)\frac{v_x}{V}}{m} \\
\dot v_y = \frac{T(h)\sin\theta \ - \ D(h, V)\frac{v_y}{V}}{m} \ - \ g(h) \\
\dot m = -\dot m_p \quad (\text{while } m > m_{\text{dry}}),\qquad 0 \text{ after burnout}
$$

**Drag Note.** The drag vector is computed as $\mathbf{D} = -\tfrac12 \rho C_D A\, V\,\mathbf{v}$. This form avoids dividing by $V$, which is zero on the pad at $t = 0$.

**Pad Hold.** At $t=0$, if $T(h_0) \le m_0 g$, the vehicle cannot lift off. `simulate_trajectory` raises `ValueError` for $T/W \le 1$ rather than integrating a rocket that sinks into the ground.

---

## 3. Force Models

### 3.1 Gravity

| Model | Equation | Notes |
|---|---|---|
| `constant` (default) | $g = g_0 = 9.80665\ \text{m/s}^2$ | Matches flat-Earth frame |
| `inverse_square` (v2) | $g(h) = g_0 \left(\dfrac{R_E}{R_E + h}\right)^2$ | About 3% lower at 100 km. Only meaningful together with round Earth. |

### 3.2 Thrust (altitude-dependent)

Thrust is altitude dependent because it depends on ambient pressure (which changes with altitude). Exit pressure is fixed.

$$
T(h) = T_{\text{vac}} - p(h)\,A_e, \qquad A_e = \frac{T_{\text{vac}} - T_{\text{SL}}}{p_0}
$$
Equivalently, $T(h) = T_{\text{SL}} + (T_{\text{vac}} - T_{\text{SL}})\left(1 - \dfrac{p(h)}{p_0}\right)$.

| Symbol | Meaning | Units |
|---|---|---|
| $T_{\text{SL}},\ T_{\text{vac}}$ | Sea-level and vacuum thrust | N |
| $A_e$ | Effective nozzle exit area (derived, not input) | m² |
| $p(h)$ | Ambient static pressure (§4.5) | Pa |
| $p_0$ | 101 325 | Pa |
 
After burnout, $T = 0$.

### 3.3 Mass Flow
 
Mass flow is set by the engine and does not depend on altitude. Only thrust and Isp vary with altitude.
 
$$
\dot m_p = \frac{T_{\text{vac}}}{g_0\, I_{sp,\text{vac}}} \;\; [\text{kg/s}], \qquad
t_{\text{burn}} = \frac{m_{\text{prop}}}{\dot m_p} \;\; [\text{s}]
$$
 
**Consistency check (input validation).** $T_{\text{SL}}/(g_0 I_{sp,\text{SL}})$ must equal $\dot m_p$ within 2%. If it does not, the vehicle inputs contradict each other. Warn the user, and use the vacuum pair to compute $\dot m_p$.
 
**Invariant:** $m(t) \ge m_{\text{dry}}$ for all $t$. The burnout event (§7) stops the powered phase exactly at $m = m_{\text{dry}}$.

### 3.4 Aerodynamic Drag
 
$$
D = q\,C_D\,A_{\text{ref}}, \qquad q = \tfrac12 \rho(h)\, V^2, \qquad M = \frac{V}{a(h)}
$$
 
| Symbol | Meaning | Units |
|---|---|---|
| $q$ | Dynamic pressure | Pa |
| $\rho$ | Air density (§4.5) | kg/m³ |
| $C_D$ | Drag coefficient. Either a constant, or $C_D(M)$ by linear interpolation of a table, clamped at the table ends | – |
| $A_{\text{ref}}$ | Reference area $= \pi d^2/4$ | m² |
| $a$ | Speed of sound $= \sqrt{\gamma_{\text{air}} R\, T_{\text{atm}}(h)}$ | m/s |
| $M$ | Mach number | – |
 
Drag acts along $-\hat{\mathbf v}$. There is no wind (air at rest in the flat-Earth frame) and no lift, because angle of attack is assumed zero.

### 3.5 Atmosphere — US Standard Atmosphere 1976 (default)
 
We use US76 rather than a pure exponential model. The exponential model gives $\rho$ but no temperature. Without temperature there is no speed of sound, so neither Mach nor $C_D(M)$ can be computed.
 
Layers are defined in **geopotential** altitude $z = \dfrac{r_0 h}{r_0 + h}$, with $r_0 = 6\,356\,766$ m:
 
| Base $z$ [km] | $T_b$ [K] | Lapse $L$ [K/m] | $p_b$ [Pa] |
|---|---|---|---|
| 0 | 288.15 | −0.0065 | 101 325 |
| 11 | 216.65 | 0.0 | 22 632.06 |
| 20 | 216.65 | +0.0010 | 5 474.889 |
| 32 | 228.65 | +0.0028 | 868.0187 |
| 47 | 270.65 | 0.0 | 110.9063 |
| 51 | 270.65 | −0.0028 | 66.93887 |
| 71 | 214.65 | −0.0020 | 3.956420 |
| 84.852 (top) | 186.946 | – | – |
 
Within each layer, $T = T_b + L(z - z_b)$, and pressure follows
 
$$
p = \begin{cases}
p_b \left(\dfrac{T}{T_b}\right)^{-g_0/(R L)} & L \ne 0 \\[2ex]
p_b \exp\!\left(-\dfrac{g_0 (z - z_b)}{R\,T_b}\right) & L = 0
\end{cases}
\qquad \rho = \frac{p}{R\,T}
$$
 
Constants: $R = 287.05287\ \text{J/(kg·K)}$ and $\gamma_{\text{air}} = 1.4$.
 
**Above 84.852 km**, temperature is held at 186.946 K and pressure decays isothermally ($L = 0$ formula). The resulting drag is negligible.
 
**Alternative (`atmosphere="exponential"`).** $\rho = \rho_0 e^{-h/H}$ with $\rho_0 = 1.225\ \text{kg/m}^3$ and $H \approx 8\,500$ m. This is kept for hand-calculation checks. In this mode temperature is fixed at 288.15 K for Mach, so $C_D(M)$ results are wrong at altitude. Use it only for teaching or tests.

---

## 4. Guidance (Thrust Direction θ)
 
| Mode | Phase | θ(t) |
|---|---|---|
| `ballistic` | Powered | $\theta = \theta_0$ (launch elevation, constant) |
| `gravity_turn` | Vertical rise, $0 \le t < t_k$ | $\theta = 90°$ |
| | Pitch kick, $t_k \le t < t_k + \Delta t_k$ | $\theta$ ramps linearly from $90°$ to $90° - \delta_k$ |
| | Gravity turn, $t \ge t_k + \Delta t_k$ | $\theta = \gamma = \operatorname{atan2}(v_y, v_x)$ |
| Any | Coast | $T = 0$, θ unused |
 
During the kick, the tilted thrust gives the vehicle a small horizontal velocity, so $\gamma$ drops slightly below 90°. Gravity then turns the velocity vector the rest of the way. The final trajectory is **very sensitive** to $\delta_k$ and $t_k$. These are the main tuning parameters when matching a real launch, and they should be reported as fitted values, not as physics.

---

## 5. Assumptions
 
| #   | Assumption                                        | Realistic for Liftoff?                                  | Effect on predicted vs. real path                                                                                                                                                                  |
| --- | ------------------------------------------------- | ------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| A1  | Point mass, no attitude dynamics                  | **Yes** for trajectory shape                            | No angle of attack, lift, or steering losses. Real vehicles fly small α.                                                                                                                           |
| A2  | 2D planar motion                                  | **Yes**                                                 | Crossrange and dogleg maneuvers are ignored. Compare downrange only.                                                                                                                               |
| A3  | Flat Earth                                        | **OK to roughly 100–200 km downrange**                  | Earth's surface falls away by $d^2/2R_E$: about 0.8 km at 100 km downrange, 7 km at 300 km, 28 km at 600 km. Altitude is under-predicted late in the flight, and orbit is impossible to represent. |
| A4  | Constant $g$                                      | **Yes** for first-stage ascent                          | About 3% too strong at 100 km, so apogee is slightly low.                                                                                                                                          |
| A5  | Non-rotating Earth, inertial pad                  | **Oversimplified** for velocity comparisons             | Cape Canaveral at 28.5° N has a free eastward speed of about 408 m/s. Webcast speed readouts are Earth-relative, so compare like with like.                                                        |
| A6  | US76 standard atmosphere, no wind                 | **Reasonable**                                          | Real day-of-launch density is within a few percent. Winds are ignored. Open-Meteo weather feeds the ML model, not the physics.                                                                     |
| A7  | Full thrust for the whole burn, constant $\dot m$ | **Oversimplified**                                      | Falcon 9 and the Shuttle throttle down through max-Q. Our `max_q` will over-predict and burnout velocity may be high.                                                                              |
| A8  | Constant $C_D$ (v1 default)                       | **Oversimplified** in the transonic range               | $C_D$ peaks near Mach 1, where it can be about twice the subsonic value. Use the $C_D(M)$ table when available.                                                                                    |
| A9  | Single stage                                      | **OK** if we validate first-stage-only events (see §10) | Full-mission values (orbit insertion) are out of scope until multi-stage plus round Earth exist.                                                                                                   |
| A10 | Exponential atmosphere                            | Hand-check mode only                                    | See §3.5.                                                                                                                                                                                          |

---

## 6. Numerical Integration (solve_ivp)

### 6.1 Inputs
```python
sol = solve_ivp(f, (t0, t_end), y0, events=[burnout, apogee, ground_impact],
                rtol=1e-8, max_step=1.0)
```
 
| Input | Meaning |
|---|---|
| `f(t, y) -> dy/dt` | The equations of motion from §3, with `y = [x, h, vx, vy, m]` |
| `(t0, t_end)` | Integration time window [s] |
| `y0` | Initial state, `[0, h_site, 0, 0, m_dry + m_prop]` |
| `events` | Functions `g(t, y)`. The solver stops or records the time where `g` crosses zero. |
 
### 6.2 Outputs
 
| Output | Meaning |
|---|---|
| `sol.t` | Time points, shape `(n,)` |
| `sol.y` | State at each time, shape `(5, n)` |
| `sol.t_events` | Time of each event |
| `sol.y_events` | State at each event |
 
`traj_df` is built from `sol.t` and `sol.y`. `events` is built from `sol.t_events` and `sol.y_events`.

### 6.3 Events
 
| Event           | `g(t, y)`                                 | Stops integration?                                       |
| --------------- | ----------------------------------------- | -------------------------------------------------------- |
| `burnout`       | $m - m_{\text{dry}}$                      | Yes. Restart the integration with $T = 0$ for the coast. |
| `apogee`        | $v_y$ (crossing downward)                 | No, only recorded                                        |
| `ground_impact` | $h - h_{\text{site}}$ (crossing downward) | Yes                                                      |
 
**Implementation note.** Run one `solve_ivp` call for the powered flight and a second for the coast. Thrust switches off at burnout, and the solver handles that jump in the equations more cleanly as two calls than as one.

---

## 7. Constants
 
| Name | Value | Units |
|---|---|---|
| $g_0$ | 9.80665 | m/s² |
| $R$ (air) | 287.05287 | J/(kg·K) |
| $\gamma_{\text{air}}$ | 1.4 | – |
| $p_0$, $T_0$, $\rho_0$ | 101 325, 288.15, 1.225 | Pa, K, kg/m³ |
| $r_0$ (US76 geopotential) | 6 356 766 | m |
| $R_E$ (mean, v2 gravity) | 6 371 000 | m |
| $\omega_E$ (v2 rotation) | 7.2921159e-5 | rad/s |