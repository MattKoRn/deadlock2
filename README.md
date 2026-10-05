# Deadlock II: Shrine Wars — Eternal Chronicle

A Chronicle-first, text-based Python reinterpretation of **Deadlock II: Shrine Wars** built with `curses`.

## Eternal campaign rule

The campaign now has no final world.

Deadlock II canon defines a **Scenario** as a single map/game world that may be randomly generated, and a **Campaign** as scenarios chained so that completing one moves play to the next. This project extends that structure indefinitely:

- Completing a world generates a fresh seeded random scenario topology.
- The same race continues into the next world.
- Verified researched technologies remain permanently unlocked.
- Permanent empire power never resets.
- World count and completed-world count are arbitrary-precision integers.
- Enemy strategic scaling has no maximum tier.
- Number suffixes continue forever: K, M, B, T, aa, ab ... zz, aaa ...
- Exact large values are preserved in the save; suffixes are display-only.
- Each generated map uses only canon race names and canon shrine classifications as named game content.
- The Chronicle remains capped at the newest five actions and narrates every world transition.

## Generated worlds

Each world stores a random 63-bit seed and generates:

- a connected territory topology,
- additional random territory links,
- random placements using the canon Great Shrine, Hidden Shrine, and Underwater Shrine classifications,
- a random set of rival races chosen from the six canon races other than the player.

The curses view summarizes the generated map in text rather than drawing an ASCII map or adding a separate map panel.

## Uncapped progression and scaling

Permanent progression uses Python arbitrary-precision integers.

Enemy scale responds to:

- eternal world depth,
- total worlds completed,
- permanent player empire power.

There is deliberately no maximum enemy scale. Later combat/economy systems should consume this rating when assigning actual enemy production, forces, research, and decision quality.

## Existing rules retained

- Seven canon races: ChCh-t, Cyth, Human, Maug, Re'Lu, Tarth, Uva Mosk.
- Official Colony Assistant task-name list.
- Exactly one Colony Assistant decision per completed minute.
- Offline automation uses that same cadence.
- Silent autosave every second.
- Five-entry Chronicle cap.
- 12-hour timestamps with minutes and no seconds.
- One continuous text view: no tabs, dashboard panels, or ASCII art.
- Technology-gated advanced Colony Assistant tasks.
- Canon metal values: Iron 1, Steel 5, Endurium 5, Tridium 10.

## Run

```bash
python deadlock2.py
```

On Windows, install a curses-compatible package such as `windows-curses` if Python does not provide `curses`.

## Controls

- `1`-`7`: choose a canon race and generate the first eternal world
- `[` / `]`: select a Colony Assistant task
- `Enter`: set the selected task as assistant focus
- `A`: enable or disable the Colony Assistant
- `B`: issue a Build order
- `T`: issue a Trade order
- `R`: complete the next currently legal verified research field
- `X`: issue an Attack order
- `E`: end the current turn
- `V`: resolve the current prototype world as a victory, bank permanent progression, and generate the next random world
- `Q`: quit

`V` is the current development hook for world completion until full canon victory-condition resolution is implemented.

The save is stored at `~/.deadlock2_shrine_wars.json`.

## Tests

```bash
python -m unittest -v
```

The suite covers Chronicle limits, timestamp formatting, active/offline automation cadence, technology gating, prerequisite unlocks, legal automated decisions, canon metal values, deterministic seeded map generation, permanent world rollover, uncapped enemy scaling, unlimited suffix generation, and eternal save persistence.

## Canon boundary

Named factions, technologies, resources, Colony Assistant tasks, shrine classifications, and other exposed Deadlock II content remain canon-derived. The endless campaign, procedural topology algorithm, permanent-power score, suffix encoder, and uncapped scaling formula are explicit project systems rather than claims about the original 1998 rules.
