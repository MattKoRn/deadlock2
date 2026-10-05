# Deadlock II: Shrine Wars — Chronicle Command

A Chronicle-first, text-based Python reinterpretation of **Deadlock II: Shrine Wars** built with `curses`.

## Current playable foundation

- Uses the seven canon races: ChCh-t, Cyth, Human, Maug, Re'Lu, Tarth, and Uva Mosk.
- Uses the complete official Colony Assistant task-name list.
- Makes exactly one Colony Assistant strategic decision per completed minute.
- Applies the same decision cadence during offline time and shows an in-game offline-progress popup on return.
- Silently autosaves every second.
- Caps the Chronicle at the newest five actions.
- Uses 12-hour Chronicle timestamps with minutes and no seconds.
- Keeps one continuous text view: no tabs, dashboard panels, or ASCII art.
- Records game state changes as detailed Chronicle sentences.

## Canon rules now enforced

Advanced Colony Assistant tasks are locked behind their verified technologies:

- **Electronic Parts** requires **Electronics**.
- **Iron to Steel** requires **Metallurgy**.
- **Mine Endurium** requires **Endurium Mining**.
- **Endurium to Triidium** requires **Tridium Processing**.
- **Anti-Matter Pods** requires **Anti-Matter Containment**.

The current verified research subset also models canon prerequisite chains and effects for Nuclear Fusion, Electronics, Metallurgy, Chaos Computer, Molecular Bonding, Synthetic Fertilizer, Anti-Matter Containment, Endurium Mining, Tridium Processing, and Food Replication.

Canon metal values are enforced as rule data:

- Iron = 1 metal value
- Steel = 5
- Endurium = 5
- Tridium = 10

Research speed remains deliberately abstract for now rather than inventing production rates that have not yet been imported and verified.

## Run

```bash
python deadlock2.py
```

On Windows, install a curses-compatible package such as `windows-curses` if Python does not provide `curses`.

## Controls

- `1`-`7`: choose a canon race on first launch
- `[` / `]`: select a Colony Assistant task
- `Enter`: set the selected task as assistant focus; blocked tasks explain their missing technology in the Chronicle
- `A`: enable or disable the Colony Assistant
- `B`: issue a Build order
- `T`: issue a Trade order
- `R`: complete the next currently legal verified research field
- `X`: issue an Attack order
- `E`: end the current turn
- `Q`: quit

The save is stored at `~/.deadlock2_shrine_wars.json`.

## Tests

```bash
python -m unittest -v
```

The suite currently checks Chronicle limits, timestamp formatting, active/offline minute cadence, save persistence, technology gating, prerequisite unlocks, legal automated decisions, and canon metal values.

## Canon boundary

The project only exposes names and rule facts that have been verified against Deadlock II material. New factions, units, buildings, technologies, resource names, combat statistics, and lore are not invented to fill gaps.
