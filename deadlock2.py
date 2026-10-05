#!/usr/bin/env python3
"""Deadlock II: Shrine Wars — Chronicle-first endless curses strategy game.

Canon game names and rule data remain restricted to Deadlock II material.
The endless campaign, one-decision-per-minute automation, permanent progression,
uncapped suffix formatting, silent one-second autosave, and Chronicle-first
presentation are project rules layered around the canon scenario/campaign loop.
"""

from __future__ import annotations

import curses
import json
import math
import os
import random
import secrets
import sys
import textwrap
import time
from collections import deque
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Deque, Iterable, Optional

if hasattr(sys, "set_int_max_str_digits"):
    sys.set_int_max_str_digits(0)

APP_TITLE = "Deadlock II: Shrine Wars — Eternal Chronicle"
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
    moment = datetime.fromtimestamp(epoch if epoch is not None else time.time())
    return moment.strftime("%I:%M %p").lstrip("0")


def generated_suffix(group: int) -> str:
    """Return an uncapped suffix for a 1000-group.

    1-4 use familiar K/M/B/T labels. Group 5 begins aa, then ab ... zz,
    aaa ... forever. The algorithm has no final suffix.
    """
    if group <= 0:
        return ""
    familiar = {1: "K", 2: "M", 3: "B", 4: "T"}
    if group in familiar:
        return familiar[group]

    index = group - 5
    length = 2
    while index >= 26 ** length:
        index -= 26 ** length
        length += 1

    chars = ["a"] * length
    for position in range(length - 1, -1, -1):
        chars[position] = chr(ord("a") + (index % 26))
        index //= 26
    return "".join(chars)


def format_big_number(value: int) -> str:
    """Format arbitrary-precision integers without a suffix ceiling."""
    sign = "-" if value < 0 else ""
    scaled = abs(value)
    if scaled < 1000:
        return f"{value}"

    group = 0
    last_remainder = 0
    while scaled >= 1000:
        last_remainder = scaled % 1000
        scaled //= 1000
        group += 1

    tenths = (last_remainder * 10) // 1000
    decimal = f".{tenths}" if scaled < 100 and tenths else ""
    return f"{sign}{scaled}{decimal}{generated_suffix(group)}"


@dataclass
class ChronicleEntry:
    at: str
    detail: str


@dataclass
class GeneratedMap:
    """Persistent data for one procedurally generated scenario world."""

    seed: int
    territory_count: int
    links: list[tuple[int, int]]
    shrine_sites: list[tuple[int, str]]
    rival_races: list[str]

    @property
    def fingerprint(self) -> str:
        return f"{self.seed:016X}"[-12:]

    @classmethod
    def from_json_dict(cls, raw: dict) -> "GeneratedMap":
        return cls(
            seed=int(raw["seed"]),
            territory_count=max(1, int(raw["territory_count"])),
            links=[(int(a), int(b)) for a, b in raw.get("links", [])],
            shrine_sites=[
                (int(site), str(shrine))
                for site, shrine in raw.get("shrine_sites", [])
                if str(shrine) in SHRINE_TYPES
            ],
            rival_races=[
                str(race) for race in raw.get("rival_races", [])
                if str(race) in RACES
            ],
        )


def build_random_map(player_race: str, seed: Optional[int] = None) -> GeneratedMap:
    """Generate a fresh random scenario topology using canon races/shrine types."""
    actual_seed = int(seed if seed is not None else secrets.randbits(63))
    rng = random.Random(actual_seed)

    territory_count = 18 + rng.randrange(13)
    link_set: set[tuple[int, int]] = set()

    # A connected ring guarantees every generated map is traversable.
    for territory in range(territory_count):
        a, b = sorted((territory, (territory + 1) % territory_count))
        link_set.add((a, b))

    # Random extra connections change strategic topology without ASCII-map UI.
    for territory in range(territory_count):
        extra = rng.randrange(territory_count)
        if extra != territory:
            a, b = sorted((territory, extra))
            link_set.add((a, b))

    shrine_count = 1 + rng.randrange(max(1, min(6, territory_count // 4)))
    shrine_territories = rng.sample(range(territory_count), shrine_count)
    shrine_sites = [
        (territory, rng.choice(SHRINE_TYPES))
        for territory in shrine_territories
    ]

    rival_pool = [race for race in RACES if race != player_race]
    rival_count = 2 + rng.randrange(max(1, len(rival_pool) - 1))
    rival_count = min(len(rival_pool), rival_count)
    rival_races = rng.sample(rival_pool, rival_count)

    return GeneratedMap(
        seed=actual_seed,
        territory_count=territory_count,
        links=sorted(link_set),
        shrine_sites=shrine_sites,
        rival_races=rival_races,
    )


@dataclass
class GameState:
    race: str = ""
    turn: int = 1
    world_number: int = 1
    worlds_completed: int = 0
    permanent_power: int = 0
    assistant_enabled: bool = True
    assistant_focus: str = "Construction"
    assistant_decisions: int = 0
    manual_orders: int = 0
    researched_technologies: list[str] = field(default_factory=list)
    world_map: Optional[GeneratedMap] = None
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
        if self.world_map is None:
            self.world_map = build_random_map(self.race)
        self.add_chronicle(
            f"Selected the {race} race and generated Eternal World {self.world_number} "
            f"with scenario seed {self.world_map.fingerprint}, "
            f"{self.world_map.territory_count} territories, "
            f"{len(self.world_map.shrine_sites)} canon shrine site(s), and "
            f"{len(self.world_map.rival_races)} rival race(s); this campaign has no final world."
        )

    def ensure_world(self) -> None:
        if self.race and self.world_map is None:
            self.world_map = build_random_map(self.race)

    def enemy_scale_rating(self) -> int:
        """Uncapped integer scaling from world depth and permanent progression."""
        world_pressure = self.world_number * self.world_number * 100
        player_response = math.isqrt(max(0, self.permanent_power)) * 25
        victory_pressure = self.worlds_completed * self.worlds_completed * 10
        return 100 + world_pressure + player_response + victory_pressure

    def complete_world(self, seed: Optional[int] = None) -> None:
        """Convert a scenario victory into permanent progress and a new random map."""
        self.ensure_world()
        if self.world_map is None:
            return

        old_world = self.world_number
        old_seed = self.world_map.seed
        old_scale = self.enemy_scale_rating()
        reward = old_scale * max(1, self.world_map.territory_count)

        self.worlds_completed += 1
        self.permanent_power += reward
        self.world_number += 1
        self.turn = 1

        next_seed = seed
        if next_seed is None:
            next_seed = secrets.randbits(63)
            while next_seed == old_seed:
                next_seed = secrets.randbits(63)

        self.world_map = build_random_map(self.race, next_seed)
        self.add_chronicle(
            f"Completed Eternal World {old_world} at enemy scale {format_big_number(old_scale)}, "
            f"banked {format_big_number(reward)} permanent empire power, and retained all "
            f"{len(self.researched_technologies)} researched canon technologies. Generated "
            f"Eternal World {self.world_number} with new scenario seed {self.world_map.fingerprint}, "
            f"{self.world_map.territory_count} territories, and enemy scale "
            f"{format_big_number(self.enemy_scale_rating())}; progression has no cap or reset."
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
            f"requires {prerequisites}. Canon effect: {rule.effect} This research is "
            "permanent and carries into every later procedurally generated world."
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
            f"Issued manual {order_name} order #{self.manual_orders} on Eternal World "
            f"{self.world_number}, Turn {self.turn}, against enemy scale "
            f"{format_big_number(self.enemy_scale_rating())}; the order remains inside "
            "Deadlock II's canon build, trade, research, and attack strategy loop."
        )

    def end_turn(self) -> None:
        previous = self.turn
        self.turn += 1
        self.add_chronicle(
            f"Ended Turn {previous} and advanced Eternal World {self.world_number} to "
            f"Turn {self.turn}; enemy scale remains {format_big_number(self.enemy_scale_rating())} "
            f"and the Colony Assistant remains {'enabled' if self.assistant_enabled else 'disabled'}."
        )

    def toggle_assistant(self) -> None:
        self.assistant_enabled = not self.assistant_enabled
        self.add_chronicle(
            f"{'Enabled' if self.assistant_enabled else 'Disabled'} the Colony "
            f"Assistant on Eternal World {self.world_number}; when enabled it makes "
            "exactly one technology-legal strategic task decision per completed minute."
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
            f"Colony Assistant decision #{format_big_number(self.assistant_decisions)} changed "
            f"focus from {previous} to {task} on Eternal World {self.world_number}, Turn "
            f"{self.turn}; enemy scale is {format_big_number(self.enemy_scale_rating())}, "
            f"and {gated_count} advanced task(s) remain blocked by unresearched technology.",
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
        data["permanent_power"] = str(self.permanent_power)
        data["world_number"] = str(self.world_number)
        data["worlds_completed"] = str(self.worlds_completed)
        return data

    @classmethod
    def from_json_dict(cls, raw: dict) -> "GameState":
        verified_tech = [
            name for name in raw.get("researched_technologies", [])
            if name in TECHNOLOGIES
        ]
        world_raw = raw.get("world_map")
        world_map = (
            GeneratedMap.from_json_dict(world_raw)
            if isinstance(world_raw, dict)
            else None
        )
        state = cls(
            race=raw.get("race", ""),
            turn=max(1, int(raw.get("turn", 1))),
            world_number=max(1, int(raw.get("world_number", 1))),
            worlds_completed=max(0, int(raw.get("worlds_completed", 0))),
            permanent_power=max(0, int(raw.get("permanent_power", 0))),
            assistant_enabled=bool(raw.get("assistant_enabled", True)),
            assistant_focus=raw.get("assistant_focus", "Construction"),
            assistant_decisions=max(0, int(raw.get("assistant_decisions", 0))),
            manual_orders=max(0, int(raw.get("manual_orders", 0))),
            researched_technologies=verified_tech,
            world_map=world_map,
            last_assistant_epoch=float(raw.get("last_assistant_epoch", time.time())),
            last_active_epoch=float(raw.get("last_active_epoch", time.time())),
        )
        if state.race and state.race not in RACES:
            state.race = ""
            state.world_map = None
        if not state.can_use_task(state.assistant_focus):
            state.assistant_focus = "Construction"
        for entry in raw.get("chronicle", [])[-CHRONICLE_LIMIT:]:
            at = str(entry.get("at", timestamp_12h()))
            detail = str(entry.get("detail", "")).strip()
            if detail:
                state.chronicle.append(ChronicleEntry(at=at, detail=detail))
        state.ensure_world()
        return state


def load_state(path: Path = SAVE_PATH) -> GameState:
    if not path.exists():
        return GameState()
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        return GameState.from_json_dict(raw)
    except (OSError, ValueError, TypeError, KeyError, json.JSONDecodeError):
        state = GameState()
        state.add_chronicle(
            "Started a fresh eternal campaign because the previous save could not "
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
            f"Applied offline progress after {away_seconds // 60} completed minute(s) "
            f"away, resolving {format_big_number(decisions)} technology-legal Colony "
            "Assistant decision(s) at exactly one decision per completed minute while "
            "preserving permanent eternal-campaign progression.",
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
        f"was closed. The Colony Assistant resolved {format_big_number(report.decisions_applied)} "
        "technology-legal strategic decision(s), maintaining exactly one decision "
        "per completed minute. Permanent campaign progress was retained. Press any key."
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
            "Q quits. Autosave is silent every second. Campaign progression never resets.",
        )
        stdscr.refresh()
        return

    state.ensure_world()
    selected_task = COLONY_ASSISTANT_TASKS[selected_task_index]
    missing = state.missing_task_requirements(selected_task)
    legality = "legal" if not missing else f"blocked by {', '.join(missing)}"
    assistant_status = "enabled" if state.assistant_enabled else "disabled"
    eligible = state.eligible_technologies()
    next_tech = eligible[0] if eligible else "blocked by prerequisites"
    world = state.world_map

    safe_addstr(
        stdscr,
        2,
        0,
        f"Race: {state.race}   Eternal World: {format_big_number(state.world_number)}   Turn: {state.turn}   Assistant: {assistant_status}",
    )
    safe_addstr(
        stdscr,
        3,
        0,
        f"Permanent power: {format_big_number(state.permanent_power)}   Worlds completed: {format_big_number(state.worlds_completed)}   Enemy scale: {format_big_number(state.enemy_scale_rating())}",
    )
    if world is not None:
        safe_addstr(
            stdscr,
            4,
            0,
            f"Scenario seed: {world.fingerprint}   Territories: {world.territory_count}   Rivals: {len(world.rival_races)}   Shrine sites: {len(world.shrine_sites)}",
        )
    safe_addstr(
        stdscr,
        5,
        0,
        f"Selected task: {selected_task} [{legality}]   Next verified research: {next_tech}",
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
        "[ / ] task   Enter focus   A assistant   B build   T trade   "
        "R research   X attack   E end turn   V world victory   Q quit"
    )
    safe_addstr(stdscr, height - 2, 0, controls)
    safe_addstr(
        stdscr,
        height - 1,
        0,
        "Eternal campaign: random worlds, permanent progress, uncapped scaling/suffixes, silent 1s save.",
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
        elif key in (ord("v"), ord("V")):
            state.complete_world()
            selected_task_index = COLONY_ASSISTANT_TASKS.index(state.assistant_focus)
            silent_save(state)

    silent_save(state)


def main() -> None:
    curses.wrapper(run_game)


if __name__ == "__main__":
    main()
