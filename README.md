# Deadlock II: Shrine Wars — Chronicle Command

A Chronicle-first, text-based Python reinterpretation of **Deadlock II: Shrine Wars** built with `curses`.

## Current playable foundation

- Uses the seven canon races from the official manual: ChCh-t, Cyth, Human, Maug, Re'Lu, Tarth, and Uva Mosk.
- Uses the official Colony Assistant task names instead of inventing replacement resources or systems.
- Makes exactly one Colony Assistant strategic decision per completed minute.
- Applies the same automation cadence while the game is closed and presents an in-game offline-progress popup on return.
- Silently autosaves state every second.
- Caps the Chronicle at the newest five actions.
- Uses 12-hour Chronicle timestamps with minutes and no seconds.
- Keeps the interface as one continuous text view: no tabs, no dashboard panels, and no ASCII art.
- Records actions as detailed development-style sentences so the Chronicle remains the center of play.

## Run

```bash
python deadlock2.py
```

On Windows, install a curses-compatible package such as `windows-curses` if Python does not provide `curses`.

## Controls

- `1`-`7`: choose a canon race on first launch
- `[` / `]`: select an official Colony Assistant task
- `Enter`: set the selected task as the assistant focus
- `A`: enable or disable the Colony Assistant
- `B`: issue a Build order
- `T`: issue a Trade order
- `R`: issue a Research order
- `X`: issue an Attack order
- `E`: end the current turn
- `Q`: quit

The save is stored at `~/.deadlock2_shrine_wars.json`.

## Canon boundary

Game names and systems currently exposed in the UI come from the official Deadlock II manual or the Steam description. The implementation intentionally avoids inventing new factions, units, buildings, technologies, resources, or lore while the project foundation is being established.
