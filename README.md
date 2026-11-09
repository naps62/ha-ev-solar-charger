# EV Solar Charger

A Home Assistant custom integration that dynamically sets your EV's charge current from solar surplus.

## Features

- Solar-tracking charge rate during the day, with a configurable "always make progress" SOC floor.
- Hard cap during dinner hours to avoid overloading your home during peak cooking loads.
- Full-speed top-up during cheap-tariff night windows, gated by a separate night SOC target.
- Two independent SOC targets so you can hold for tomorrow's solar or top up from grid.
- Force-min / force-max / off overrides for one-off situations.
- Safety fallback to a conservative 6 A if any required sensor goes stale.
- Optional grid-limit guard: pauses or reduces charging when the house nears its contracted power, in every mode including force-max.

## Installation

### Via HACS (custom repository)

1. HACS → ⋮ → Custom repositories
2. Add `https://github.com/naps62/ha-ev-solar-charger` as category "Integration"
3. Install "EV Solar Charger"
4. Restart Home Assistant
5. Settings → Devices & Services → Add Integration → "EV Solar Charger"

### Manual

Copy `custom_components/ev_solar_charger/` into your HA config's `custom_components/` directory. Restart HA. Add the integration via Settings → Devices & Services.

## Configuration

The config flow asks for:

- **Grid signal** — either a single signed sensor (positive = import) or a pair of `grid_import_w` + `grid_export_w` sensors.
- **EV consumption sensor** — W reading of the EV's actual draw (e.g. a Shelly EM on the EV circuit).
- **EV charge-current `number`** — the writable entity that sets the EV's charge amps.
- **EV charge `switch`** — the entity that starts/stops charging.
- **EV cable sensor** — binary sensor that reads `on` when plugged in.
- **EV battery SOC sensor** — percentage.
- **EV location tracker + home zone** — `device_tracker` and the zone name considered "home".
- **Solar production sensor** (optional) — for dashboard + install verification.

### Grid limit (optional)

Settings → Devices & Services → EV Solar Charger → Configure. All fields are optional; leave them empty to turn the guard off.

- **Near-limit binary sensor** — charging stops while it reads `on`. A `threshold` helper on a headroom sensor works well (e.g. on below 500 W headroom).
- **Grid usage sensor** — metered grid import in W or kW, including the EV's own draw. Needs a **contracted power**, either an entity (`input_number`, `number` or `sensor`) or a fixed value in W. Charging is reduced so usage stays under the limit minus the **safety margin** (default 500 W), and stops when less than the minimum current fits.
- **Resume delay** (default 300 s) — after the limit clears, charging stays paused (or capped) until it has been clear this long, so it doesn't flap around the threshold. A tighter limit always applies at once.

Both inputs can be used together. An unavailable grid-limit input counts as "no limit", so a broken helper never stops charging on its own. Saving the options reloads the integration.

While the guard is acting, `sensor.ev_solar_charger_sub_mode` reads `grid-limit` (when paused), the reason sensor starts with `grid limit:`, and `binary_sensor.ev_solar_charger_grid_limited` is on.

After setup, an "EV Solar Charger" device appears with these entities:

| Entity | Purpose |
|---|---|
| `number.ev_solar_charger_target_day_soc` | SOC to charge to during the day (solar-tracking) |
| `number.ev_solar_charger_target_night_soc` | SOC to charge to overnight (cheap tariff) |
| `select.ev_solar_charger_mode` | auto / force-min / force-max / off |
| `switch.ev_solar_charger_enabled` | master kill |
| `time.ev_solar_charger_dinner_start` | start of the dinner cap window |
| `time.ev_solar_charger_night_start` | start of the night cheap-tariff window |
| `sensor.ev_solar_charger_leftover_w` | current solar surplus available |
| `sensor.ev_solar_charger_desired_amps` | what the integration wants the EV to draw |
| `sensor.ev_solar_charger_actual_amps` | what the EV is actually set to |
| `sensor.ev_solar_charger_sub_mode` | solar / dinner / night / force-min / force-max / grid-limit / safety-fallback / disabled |
| `sensor.ev_solar_charger_last_decision_reason` | short human-readable trace |
| `binary_sensor.ev_solar_charger_healthy` | overall health |
| `binary_sensor.ev_solar_charger_grid_limited` | on while the grid limit pauses or reduces charging (attributes: `paused`, `cap_amps`, `held_cap_amps`) |

## Tuning

| Tomorrow's plan | day target | night target |
|---|--:|--:|
| Sunny forecast, no trip | 50 % | 50 % |
| Cloudy forecast, no trip | 50 % | 80 % |
| Big trip tomorrow | 80 % | 100 % |
| Departing now | (use force-max) | (use force-max) |

## License

MIT
