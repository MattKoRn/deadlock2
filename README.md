# Deadlock II: Shrine Wars — Autonomous Eternal Chronicle

A Chronicle-first, race-selectable and otherwise fully autonomous text-based Python reinterpretation of **Deadlock II: Shrine Wars** built with `curses`.

## Manual race selection, autonomous strategy

Race selection is the one manual gameplay choice. On a new save, the opening screen lets the player choose one of the seven canon races with Up/Down + Enter or the `1`-`7` keys. That race is permanent for the save.

After race selection, the AI owns the entire strategy loop. There is no manual task selection, Colony Assistant toggle, Build command, Trade command, Research command, Attack command, End Turn command, or World Victory command.

Once the campaign has started, the only accepted keyboard command is `Q`, which exits the program and does not alter strategy.

## Full automation

Exactly once per completed minute, one autonomous decision now:

1. chooses one of Deadlock II's canon strategic verbs: Build, Trade, Research, or Attack;
2. chooses a currently legal Colony Assistant task;
3. executes the abstract strategic operation without inventing unverified costs, yields, or combat statistics;
4. advances the turn;
5. advances autonomous scenario progress;
6. writes one highly detailed explanation into the Chronicle.

Research decisions automatically complete the next eligible verified technology and keep the unlock permanently.

Advanced Colony Assistant tasks remain technology-gated.

## Automatic endless worlds

World transitions no longer require the old development-only `V` command.

Every generated world has an autonomous scenario-operation goal derived from its generated territory count, rival count, and shrine-site count. When the AI reaches that goal, the game automatically:

- completes the current Eternal World;
- banks permanent empire power;
- retains verified research;
- creates a fresh random scenario seed;
- generates a new connected map;
- increases uncapped enemy scaling;
- resets only local world progress and the turn counter;
- records the complete transition in the Chronicle.

This scenario-operation threshold is an explicit project pacing rule, not a claim about Deadlock II's original victory conditions. Canon victory-condition resolution can replace it once fully imported.

## Canon foundation

The autonomous design continues to use:

- the seven canon races: ChCh-t, Cyth, Human, Maug, Re'Lu, Tarth, and Uva Mosk;
- the official Colony Assistant task names;
- Deadlock II's Build / Trade / Research / Attack strategic loop;
- Great Shrine, Hidden Shrine, and Underwater Shrine classifications;
- verified technology prerequisites and effects;
- canon metal values: Iron 1, Steel 5, Endurium 5, Tridium 10.

Deadlock II officially includes a Colony Assistant for automated tasks and automated unit/resource production, which is the canon foundation being extended into this project's full-autonomy rule.

## Offline progress and persistence

- Automation remains exactly one decision per completed minute.
- Offline time resolves the same decisions and can automatically complete multiple worlds.
- The offline-progress popup dismisses itself; no keypress is required.
- Autosave remains silent every second.
- Permanent progression and research never reset.
- Arbitrary-precision integers and unlimited suffixes remain in place.

## Chronicle and color

The Chronicle remains the center of the game and retains only the newest five actions with 12-hour timestamps and no seconds.

Semantic curses colors remain enabled when supported:

- cyan: structure and timestamps;
- yellow: world progression;
- green: persistent player progress;
- red: danger or blocked systems;
- magenta: research/shrine information;
- blue: autonomous decisions and scenario information.

The presentation uses a calm mixed-case title, centered segmented status bands, individually colored live metrics, and soft Unicode chrome so the screen reads as one balanced composition. Mixed-color rows are now clipped to the shared content width before centering, preventing compact terminals from spilling status text outside the intended visual column. Untitled dividers use a lighter dotted Unicode rule, and the footer is reduced to a short AUTO / countdown / SAVE / OFFLINE / Q strip. The five-entry Chronicle keeps the extra breathing room: newest action expanded, older four compact and progressively softer. The race selector remains narrow and focused. No tabs, dashboard panels, ASCII maps, or manual strategy menus have been added.

## Run

```bash
python deadlock2.py
```

On Windows, install a curses-compatible package such as `windows-curses` if needed.

## Tests

```bash
python -m unittest -v
```

The regression suite covers permanent manual race selection, absence of manual strategy methods, one-decision-per-minute execution, offline automation, automatic world rollover, research persistence, technology gating, procedural maps, uncapped scaling, unlimited number suffixes, save persistence, Chronicle limits, canon race-flag metadata, progress-meter bounds and percentages, countdown timing/formatting, responsive text fitting, centered content geometry, clipped segmented-status widths, section-rule layout, terminal layout modes, Chronicle glyphs/labels, offline-duration formatting, and color semantics.

## Canon boundary

Named factions, technologies, resources, Colony Assistant tasks, shrine classifications, and other exposed Deadlock II content remain canon-derived. Full autonomy, autonomous scenario-operation goals, procedural topology, permanent-power scoring, suffix encoding, and uncapped scaling are explicit project systems rather than claims about the original 1998 rules.
