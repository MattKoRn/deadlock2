#!/usr/bin/env python3
"""Deadlock II: Shrine Wars — Chronicle-first curses strategy foundation.

All exposed game names and rule data in this prototype are restricted to
Deadlock II canon. The one-decision-per-minute automation cadence, silent
one-second autosave, and Chronicle presentation are project rules.
"""

from __future__ import annotations

import curses
import json
import os
import textwrap
import time
from collections import deque
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Deque, Iterable, Optional

APP_TITLE = "Deadlock II: Shrine Wars — Chronicle Command"
SAVE_PATH = Path.home() / ".deadlock2_shrine_wars.json"
AUTOSAVE_INTERVAL_SECONDS = 1.0
ASSISTANT_INTERVAL_SECONDS = 60.0
CHRONICLE_LIMIT = 5

RACES = (
    "ChCh-t",
    "Cyth",
    "Human",
    "Maug",
    "Re'Lu",
    "Tarth",
    "Uva Mosk",
)

COLONY_ASSISTANT_TASKS = (
    "Construction",
    "Upgrade",
    "Mine Iron",
    "Mine Endurium",
    "Research",
    "Electronic Parts",
    "Culture",
    "Create Art",
    "House Populace",
    "Iron to Steel",
    "Endurium to Triidium",
    "Food",
    "Wood",
    "Trade",
    "Energy",
    "Anti-Matter Pods",
)

SHRINE_TYPES = (
    "Great Shrine",
    "Hidden Shrine",
    "Underwater Shrine",
)

# Canon metal values described by the Deadlock II manual:
# Endurium and Steel are worth five Iron; Tridium is worth ten Iron.
METAL_VALUES = {
    "Iron": 1,
    "Steel": 5,
    "Endurium": 5,
    "Tridium": 10,
}


@dataclass(frozen=True)
class TechnologyRule:
    prerequisites: tuple[str, ...]
    effect: str


# Resource/production technologies whose prerequisites and effects are explicitly
# described by the official Deadlock II manual. This intentionally remains a
# focused subset until the complete technology table is imported and verified.
TECHNOLOGIES: dict[str, TechnologyRule] = {
    "Nuclear Fusion": TechnologyRule(
        (),
        "Allows construction of the Fusion Plant.",
    ),
    "Electronics": TechnologyRule(
        (),
        "Lets research centers make Electronic Parts.",
    ),
    "Metallurgy": TechnologyRule(
        (),
        "Lets factories transform Iron into Steel; Steel has five times the metal value of Iron.",
    ),
    "Chaos Computer": TechnologyRule(
        ("Electronics", "Nuclear Fusion"),
        "Allows construction of the Tech Lab.",
    ),
    "Molecular Bonding": TechnologyRule(
        ("Metallurgy",),
        "Allows the Mantle Drill, increasing Iron and Endurium production.",
    ),
    "Synthetic Fertilizer": TechnologyRule(
        ("Metallurgy", "Advanced Medicine"),
        "Allows construction of Hydroponic Farms.",
    ),
    "Anti-Matter Containment": TechnologyRule(
        ("Flak", "Chaos Computer"),
        "Lets power plants produce Anti-Matter Pods and allows construction of the Anti-Matter Plant.",
    ),
    "Endurium Mining": TechnologyRule(
        ("Fusion Cannon", "Neutronic Fuel"),
        "Allows mines to produce Endurium; Endurium has five times the metal value of Iron.",
    ),
    "Tridium Processing": TechnologyRule(
        ("Endurium Mining",),
        "Lets factories refine Endurium into Tridium; Tridium has ten times the metal value of Iron.",
    ),
    "Food Replication": TechnologyRule(
        ("Power Cells", "Anti-Matter Rifles"),
        "Allows Food Replicators, which exceed Hydroponic Farm Food and Wood production.",
    ),
}

TASK_TECH_REQUIREMENTS: dict[str, tuple[str, ...]] = {
    "Mine Endurium": ("Endurium Mining",),
    "Electronic Parts": ("Electronics",),
    "Iron to Steel": ("Metallurgy",),
    "Endurium to Triidium": ("Tridium Processing",),
    "Anti-Matter Pods": ("Anti-Matter Containment",),
}


def timestamp_12h(epoch: Optional[float] = None) -> str:
    """Return a compact 12-hour timestamp with minutes and no seconds."""
    moment = datetime.fromtimestamp(epoch if epoch is not None else time.time())
    return moment.strftime("%I:%M %p").lstrip("0")


@dataclass
class ChronicleEntry:
    at: str
    detail: str


@dataclass
class GameState:
    race: str = ""
    turn: int = 1
    assistant_enabled: bool = True
    assistant_focus: str = "Construction"
    assistant_decisions: int = 0
    manual_orders: int = 0
    researched_technologies: list[str] = field(default_factory=list)
    last_assistant_epoch: float = field(default_factory=time.time)
    last_active_epoch: float = field(default_factory=time.time)
    chronicle: Deque[ChronicleEntry] = field(
        default_factory=lambda: deque(maxlen=CHRONICLE_LIMIT)
    )

    def add_chronicle(self, detail: str, epoch: Optional[float] = None) -> None:
        self.chronicle.append(
            ChronicleEntry(at=timestamp_12h(epoch), detail=detail)
        )

    def choose_race(self, race: str) -> None:
        if race not in RACES:
            raise ValueError(f"Unknown canon race: {race}")
        self.race = race
        self.add_chronicle(
            f"Selected the {race} race for colony command and kept the Colony "
            "Assistant enabled; all automated task choices are now checked "
            "against verified Deadlock II technology requirements before use."
        )

    def has_technology(self, name: str) -> bool:
        return name in self.researched_technologies

    def missing_task_requirements(self, task: str) -> tuple[str, ...]:
        requirements = TASK_TECH_REQUIREMENTS.get(task, ())
        return tuple(name for name in requirements if not self.has_technology(name))

    def can_use_task(self, task: str) -> bool:
        return task in COLONY_ASSISTANT_TASKS and not self.missing_task_requirements(task)

    def legal_assistant_tasks(self) -> tuple[str, ...]:
        return tuple(task for task in COLONY_ASSISTANT_TASKS if self.can_use_task(task))

    def eligible_technologies(self) -> tuple[str, ...]:
        eligible: list[str] = []
        researched = set(self.researched_technologies)
        for name, rule in TECHNOLOGIES.items():
            if name in researched:
                continue
            if all(prerequisite in researched for prerequisite in rule.prerequisites):
                eligible.append(name)
        return tuple(eligible)

    def complete_next_research(self) -> Optional[str]:
        """Complete the next currently legal verified technology field.

        Research speed is intentionally abstract in this prototype. This method
        never invents research-point costs; it only enforces canon prerequisite
        relationships and records the canon effect of the completed field.
        """
        eligible = self.eligible_technologies()
        if not eligible:
            unresolved = [
                f"{name}: {', '.join(rule.prerequisites)}"
                for name, rule in TECHNOLOGIES.items()
                if name not in self.researched_technologies and rule.prerequisites
            ]
            detail = "; ".join(unresolved[:3]) if unresolved else "no verified fields remain"
            self.add_chronicle(
                "Research order could not complete a verified technology because "
                f"its canon prerequisite chain is not yet satisfied; current blockers include {detail}."
            )
            return None

        technology = eligible[0]
        self.researched_technologies.append(technology)
        rule = TECHNOLOGIES[technology]
        prerequisites = (
            ", ".join(rule.prerequisites) if rule.prerequisites else "no base technologies"
        )
        self.manual_orders += 1
        self.add_chronicle(
            f"Completed research order #{self.manual_orders}: {technology}, which "
            f"requires {prerequisites}. Canon effect: {rule.effect}"
        )
        return technology

    def set_assistant_focus(self, task: str) -> bool:
        if task not in COLONY_ASSISTANT_TASKS:
            raise ValueError(f"Unknown canon Colony Assistant task: {task}")
        missing = self.missing_task_requirements(task)
        if missing:
            self.add_chronicle(
                f"Rejected Colony Assistant focus change to {task} because the "
                f"verified Deadlock II rule requires {', '.join(missing)} first."
            )
            return False
        previous = self.assistant_focus
        self.assistant_focus = task
        self.add_chronicle(
            f"Changed the Colony Assistant focus from {previous} to {task}; the "
            "task passed all currently verified technology requirement checks."
        )
        return True

    def issue_manual_order(self, order_name: str) -> None:
        self.manual_orders += 1
        self.add_chronicle(
            f"Issued manual {order_name} order #{self.manual_orders} on Turn "
            f"{self.turn}, preserving Colony Assistant focus on {self.assistant_focus} "
            "and keeping the order inside Deadlock II's canon build, trade, research, "
            "and attack strategy loop."
        )

    def end_turn(self) -> None:
        previous = self.turn
        self.turn += 1
        self.add_chronicle(
            f"Ended Turn {previous} and advanced the colony to Turn {self.turn}; "
            f"the Colony Assistant remains {'enabled' if self.assistant_enabled else 'disabled'} "
            f"with {self.assistant_focus} as its verified legal focus."
        )

    def toggle_assistant(self) -> None:
        self.assistant_enabled = not self.assistant_enabled
        self.add_chronicle(
            f"{'Enabled' if self.assistant_enabled else 'Disabled'} the Colony "
            f"Assistant on Turn {self.turn}; when enabled it makes exactly one "
            "technology-legal strategic task decision per completed minute."
        )

    def make_assistant_decision(self, decision_epoch: float) -> None:
        if not self.assistant_enabled:
            self.last_assistant_epoch = decision_epoch
            return

        legal_tasks = self.legal_assistant_tasks()
        task_index = self.assistant_decisions % len(legal_tasks)
        task = legal_tasks[task_index]
        previous = self.assistant_focus
        self.assistant_focus = task
        self.assistant_decisions += 1
        self.last_assistant_epoch = decision_epoch

        gated_count = len(COLONY_ASSISTANT_TASKS) - len(legal_tasks)
        self.add_chronicle(
            f"Colony Assistant decision #{self.assistant_decisions} changed focus "
            f"from {previous} to {task} on Turn {self.turn}; the decision used only "
            f"canon-legal tasks, with {gated_count} advanced task(s) currently blocked "
            "by unresearched technology requirements.",
            epoch=decision_epoch,
        )

    def apply_due_assistant_decisions(self, now: Optional[float] = None) -> int:
        current = now if now is not None else time.time()
        if current <= self.last_assistant_epoch:
            return 0
        due = int((current - self.last_assistant_epoch) // ASSISTANT_INTERVAL_SECONDS)
        for _ in range(due):
            decision_epoch = self.last_assistant_epoch + ASSISTANT_INTERVAL_SECONDS
            self.make_assistant_decision(decision_epoch)
        return due

    def to_json_dict(self) -> dict:
        data = asdict(self)
        data["chronicle"] = [asdict(entry) for entry in self.chronicle]
        return data

    @classmethod
    def from_json_dict(cls, raw: dict) -> "GameState":
        verified_tech = [
            name for name in raw.get("researched_technologies", [])
            if name in TECHNOLOGIES
        ]
        state = cls(
            race=raw.get("race", ""),
            turn=max(1, int(raw.get("turn", 1))),
            assistant_enabled=bool(raw.get("assistant_enabled", True)),
            assistant_focus=raw.get("assistant_focus", "Construction"),
            assistant_decisions=max(0, int(raw.get("assistant_decisions", 0))),
            manual_orders=max(0, int(raw.get("manual_orders", 0))),
            researched_technologies=verified_tech,
            last_assistant_epoch=float(raw.get("last_assistant_epoch", time.time())),
            last_active_epoch=float(raw.get("last_active_epoch", time.time())),
        )
        if state.race and state.race not in RACES:
            state.race = ""
        if not state.can_use_task(state.assistant_focus):
            state.assistant_focus = "Construction"
        for entry in raw.get("chronicle", [])[-CHRONICLE_LIMIT:]:
            at = str(entry.get("at", timestamp_12h()))
            detail = str(entry.get("detail", "")).strip()
            if detail:
                state.chronicle.append(ChronicleEntry(at=at, detail=detail))
        return state


def load_state(path: Path = SAVE_PATH) -> GameState:
    if not path.exists():
        return GameState()
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        return GameState.from_json_dict(raw)
    except (OSError, ValueError, TypeError, json.JSONDecodeError):
        state = GameState()
        state.add_chronicle(
            "Started a fresh colony command because the previous save could not "
            "be read safely; no replacement faction, technology, or resource data was invented."
        )
        return state


def silent_save(state: GameState, path: Path = SAVE_PATH) -> None:
    state.last_active_epoch = time.time()
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_suffix(path.suffix + ".tmp")
    temp_path.write_text(
        json.dumps(state.to_json_dict(), indent=2, sort_keys=True),
        encoding="utf-8",
    )
    os.replace(temp_path, path)


@dataclass(frozen=True)
class OfflineReport:
    away_seconds: int
    decisions_applied: int


def apply_offline_progress(
    state: GameState,
    now: Optional[float] = None,
) -> OfflineReport:
    current = now if now is not None else time.time()
    away_seconds = max(0, int(current - state.last_active_epoch))
    decisions = state.apply_due_assistant_decisions(current)
    state.last_active_epoch = current
    if away_seconds >= ASSISTANT_INTERVAL_SECONDS:
        state.add_chronicle(
            f"Applied offline progress after {away_seconds // 60} completed "
            f"minute(s) away, resolving {decisions} technology-legal Colony "
            "Assistant decision(s) at exactly one decision per completed minute.",
            epoch=current,
        )
    return OfflineReport(away_seconds=away_seconds, decisions_applied=decisions)


def wrapped_lines(text: str, width: int) -> Iterable[str]:
    return textwrap.wrap(text, width=max(10, width), replace_whitespace=False) or [""]


def safe_addstr(
    window: "curses._CursesWindow",
    y: int,
    x: int,
    text: str,
    attr: int = 0,
) -> None:
    height, width = window.getmaxyx()
    if not (0 <= y < height) or x >= width:
        return
    clipped = text[: max(0, width - x - 1)]
    try:
        window.addstr(y, x, clipped, attr)
    except curses.error:
        pass


def show_offline_popup(
    stdscr: "curses._CursesWindow",
    report: OfflineReport,
) -> None:
    if report.away_seconds < ASSISTANT_INTERVAL_SECONDS:
        return
    height, width = stdscr.getmaxyx()
    minutes = report.away_seconds // 60
    message = (
        f"Offline progress: {minutes} completed minute(s) passed while the game "
        f"was closed. The Colony Assistant resolved {report.decisions_applied} "
        "technology-legal strategic decision(s), maintaining exactly one decision "
        "per completed minute. Press any key to return to the Chronicle."
    )
    lines = list(wrapped_lines(message, max(24, width - 8)))
    start_y = max(1, (height - len(lines)) // 2)
    stdscr.erase()
    for index, line in enumerate(lines):
        safe_addstr(
            stdscr,
            start_y + index,
            3,
            line,
            curses.A_BOLD if index == 0 else 0,
        )
    stdscr.refresh()
    stdscr.nodelay(False)
    stdscr.getch()
    stdscr.nodelay(True)


def render(
    stdscr: "curses._CursesWindow",
    state: GameState,
    selected_task_index: int,
) -> None:
    stdscr.erase()
    height, width = stdscr.getmaxyx()
    safe_addstr(stdscr, 0, 0, APP_TITLE, curses.A_BOLD)

    if not state.race:
        safe_addstr(stdscr, 2, 0, "Choose a canon race by pressing 1-7:", curses.A_BOLD)
        for idx, race in enumerate(RACES, start=1):
            safe_addstr(stdscr, 2 + idx, 2, f"{idx}. {race}")
        safe_addstr(
            stdscr,
            min(height - 2, 11),
            0,
            "Q quits. Autosave is silent every second.",
        )
        stdscr.refresh()
        return

    selected_task = COLONY_ASSISTANT_TASKS[selected_task_index]
    missing = state.missing_task_requirements(selected_task)
    legality = "legal" if not missing else f"blocked by {', '.join(missing)}"
    assistant_status = "enabled" if state.assistant_enabled else "disabled"
    eligible = state.eligible_technologies()
    next_tech = eligible[0] if eligible else "blocked by prerequisites"

    safe_addstr(
        stdscr,
        2,
        0,
        f"Race: {state.race}   Turn: {state.turn}   Colony Assistant: {assistant_status}",
    )
    safe_addstr(
        stdscr,
        3,
        0,
        f"Focus: {state.assistant_focus}   Decisions: {state.assistant_decisions}   Researched: {len(state.researched_technologies)}",
    )
    safe_addstr(
        stdscr,
        4,
        0,
        f"Selected task: {selected_task} [{legality}]",
    )
    safe_addstr(
        stdscr,
        5,
        0,
        f"Next verified research: {next_tech}   Metal value: Iron 1 / Steel 5 / Endurium 5 / Tridium 10",
    )

    safe_addstr(stdscr, 7, 0, "Chronicle — newest five actions", curses.A_BOLD)
    row = 8
    for entry in reversed(state.chronicle):
        prefix = f"{entry.at} — "
        available = max(16, width - len(prefix) - 1)
        parts = list(wrapped_lines(entry.detail, available))
        safe_addstr(stdscr, row, 0, prefix + parts[0])
        row += 1
        for continuation in parts[1:]:
            if row >= height - 4:
                break
            safe_addstr(stdscr, row, len(prefix), continuation)
            row += 1
        if row >= height - 4:
            break

    controls = (
        "[ / ] select task   Enter set focus   A assistant   B build   "
        "T trade   R research   X attack   E end turn   Q quit"
    )
    safe_addstr(stdscr, height - 2, 0, controls)
    safe_addstr(
        stdscr,
        height - 1,
        0,
        "No tabs/panels. Autosave: 1s silent. Automation: 1 legal decision/completed minute.",
    )
    stdscr.refresh()


def run_game(stdscr: "curses._CursesWindow") -> None:
    curses.curs_set(0)
    stdscr.nodelay(True)
    stdscr.timeout(100)

    state = load_state()
    offline_report = apply_offline_progress(state)
    selected_task_index = COLONY_ASSISTANT_TASKS.index(state.assistant_focus)
    last_save = time.monotonic()

    render(stdscr, state, selected_task_index)
    show_offline_popup(stdscr, offline_report)

    running = True
    while running:
        now = time.time()
        due = state.apply_due_assistant_decisions(now)
        if due:
            selected_task_index = COLONY_ASSISTANT_TASKS.index(state.assistant_focus)

        current_monotonic = time.monotonic()
        if current_monotonic - last_save >= AUTOSAVE_INTERVAL_SECONDS:
            silent_save(state)
            last_save = current_monotonic

        render(stdscr, state, selected_task_index)
        key = stdscr.getch()
        if key == -1:
            continue

        if not state.race:
            if ord("1") <= key <= ord("7"):
                state.choose_race(RACES[key - ord("1")])
                state.last_assistant_epoch = time.time()
                selected_task_index = COLONY_ASSISTANT_TASKS.index(state.assistant_focus)
                silent_save(state)
            elif key in (ord("q"), ord("Q")):
                running = False
            continue

        if key in (ord("q"), ord("Q")):
            running = False
        elif key == ord("["):
            selected_task_index = (selected_task_index - 1) % len(COLONY_ASSISTANT_TASKS)
        elif key == ord("]"):
            selected_task_index = (selected_task_index + 1) % len(COLONY_ASSISTANT_TASKS)
        elif key in (curses.KEY_ENTER, 10, 13):
            state.set_assistant_focus(COLONY_ASSISTANT_TASKS[selected_task_index])
        elif key in (ord("a"), ord("A")):
            state.toggle_assistant()
            state.last_assistant_epoch = time.time()
        elif key in (ord("b"), ord("B")):
            state.issue_manual_order("Build")
        elif key in (ord("t"), ord("T")):
            state.issue_manual_order("Trade")
        elif key in (ord("r"), ord("R")):
            state.complete_next_research()
        elif key in (ord("x"), ord("X")):
            state.issue_manual_order("Attack")
        elif key in (ord("e"), ord("E")):
            state.end_turn()

    silent_save(state)


def main() -> None:
    curses.wrapper(run_game)


if __name__ == "__main__":
    main()
