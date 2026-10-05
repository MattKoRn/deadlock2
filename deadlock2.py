#!/usr/bin/env python3
"""Deadlock II: Shrine Wars — fully autonomous Eternal Chronicle.

Canon game names and verified rule data remain restricted to Deadlock II material.
The endless campaign, one-decision-per-minute full automation, permanent
progression, uncapped suffix formatting, silent one-second autosave, and
Chronicle-first presentation are project systems layered around the canon loop.
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

APP_TITLE = "Deadlock II: Shrine Wars — Autonomous Eternal Chronicle"
SAVE_PATH = Path.home() / ".deadlock2_shrine_wars.json"
AUTOSAVE_INTERVAL_SECONDS = 1.0
ASSISTANT_INTERVAL_SECONDS = 60.0
CHRONICLE_LIMIT = 5

PAIR_TITLE = 1
PAIR_WORLD = 2
PAIR_GOOD = 3
PAIR_WARNING = 4
PAIR_DANGER = 5
PAIR_RESEARCH = 6
PAIR_INFO = 7
COLORS_ACTIVE = False

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

# Deadlock II's advertised strategic loop. These are now AI-owned only.
STRATEGIC_ACTIONS = ("Build", "Trade", "Research", "Attack")

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


def init_colors() -> None:
    """Enable semantic colors with a safe monochrome fallback."""
    global COLORS_ACTIVE
    COLORS_ACTIVE = False
    try:
        if not curses.has_colors():
            return
        curses.start_color()
        try:
            curses.use_default_colors()
            background = -1
        except curses.error:
            background = curses.COLOR_BLACK

        palette = (
            (PAIR_TITLE, curses.COLOR_CYAN),
            (PAIR_WORLD, curses.COLOR_YELLOW),
            (PAIR_GOOD, curses.COLOR_GREEN),
            (PAIR_WARNING, curses.COLOR_YELLOW),
            (PAIR_DANGER, curses.COLOR_RED),
            (PAIR_RESEARCH, curses.COLOR_MAGENTA),
            (PAIR_INFO, curses.COLOR_BLUE),
        )
        for pair, foreground in palette:
            curses.init_pair(pair, foreground, background)
        COLORS_ACTIVE = True
    except curses.error:
        COLORS_ACTIVE = False


def ui_attr(pair: int, *, bold: bool = False, reverse: bool = False) -> int:
    attr = curses.color_pair(pair) if COLORS_ACTIVE else 0
    if bold:
        attr |= curses.A_BOLD
    if reverse:
        attr |= curses.A_REVERSE
    return attr


def chronicle_pair_for_detail(detail: str) -> int:
    lowered = detail.lower()
    if "completed eternal world" in lowered or "generated eternal world" in lowered:
        return PAIR_WORLD
    if "autonomous decision" in lowered or "offline progress" in lowered:
        return PAIR_INFO
    if "research" in lowered:
        return PAIR_RESEARCH
    if "could not" in lowered or "blocked" in lowered:
        return PAIR_DANGER
    return PAIR_GOOD


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
    """Return an uncapped suffix for a 1000-group."""
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
                str(race)
                for race in raw.get("rival_races", [])
                if str(race) in RACES
            ],
        )


def build_random_map(player_race: str, seed: Optional[int] = None) -> GeneratedMap:
    actual_seed = int(seed if seed is not None else secrets.randbits(63))
    rng = random.Random(actual_seed)

    territory_count = 18 + rng.randrange(13)
    link_set: set[tuple[int, int]] = set()

    for territory in range(territory_count):
        a, b = sorted((territory, (territory + 1) % territory_count))
        link_set.add((a, b))

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
    assistant_focus: str = "Construction"
    assistant_decisions: int = 0
    strategic_actions: int = 0
    world_actions: int = 0
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

    def bootstrap_autonomous_campaign(
        self,
        race: Optional[str] = None,
        seed: Optional[int] = None,
        epoch: Optional[float] = None,
    ) -> None:
        """Start a new save without asking the player for any gameplay choice."""
        if self.race:
            self.ensure_world()
            return

        selected_race = race if race in RACES else secrets.choice(RACES)
        current = epoch if epoch is not None else time.time()
        self.race = selected_race
        self.world_map = build_random_map(self.race, seed)
        self.last_assistant_epoch = current
        self.last_active_epoch = current
        self.add_chronicle(
            f"Autonomous campaign initialization selected the canon {self.race} race "
            f"and generated Eternal World {self.world_number} with scenario seed "
            f"{self.world_map.fingerprint}, {self.world_map.territory_count} territories, "
            f"{len(self.world_map.shrine_sites)} shrine site(s), and "
            f"{len(self.world_map.rival_races)} rival race(s); no player gameplay input is required.",
            epoch=current,
        )

    def ensure_world(self) -> None:
        if self.race and self.world_map is None:
            self.world_map = build_random_map(self.race)

    def enemy_scale_rating(self) -> int:
        world_pressure = self.world_number * self.world_number * 100
        player_response = math.isqrt(max(0, self.permanent_power)) * 25
        victory_pressure = self.worlds_completed * self.worlds_completed * 10
        return 100 + world_pressure + player_response + victory_pressure

    def world_action_goal(self) -> int:
        """Project pacing rule for autonomous scenario rollover, not a canon victory rule."""
        self.ensure_world()
        if self.world_map is None:
            return 1
        return max(
            8,
            self.world_map.territory_count
            + len(self.world_map.rival_races) * 2
            + len(self.world_map.shrine_sites) * 3,
        )

    def complete_world(
        self,
        seed: Optional[int] = None,
        epoch: Optional[float] = None,
    ) -> None:
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
        self.world_actions = 0

        next_seed = seed
        if next_seed is None:
            next_seed = secrets.randbits(63)
            while next_seed == old_seed:
                next_seed = secrets.randbits(63)

        self.world_map = build_random_map(self.race, next_seed)
        self.add_chronicle(
            f"Completed Eternal World {old_world} automatically after the autonomous "
            f"scenario-operation goal was satisfied at enemy scale {format_big_number(old_scale)}; "
            f"banked {format_big_number(reward)} permanent empire power, retained all "
            f"{len(self.researched_technologies)} verified technologies, and generated "
            f"Eternal World {self.world_number} with seed {self.world_map.fingerprint}, "
            f"{self.world_map.territory_count} territories, and enemy scale "
            f"{format_big_number(self.enemy_scale_rating())}.",
            epoch=epoch,
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

    def resolve_autonomous_research(self) -> str:
        eligible = self.eligible_technologies()
        if not eligible:
            return (
                "Research found no currently eligible verified technology because "
                "the remaining imported fields are blocked by prerequisite technologies."
            )

        technology = eligible[0]
        self.researched_technologies.append(technology)
        rule = TECHNOLOGIES[technology]
        prerequisites = (
            ", ".join(rule.prerequisites)
            if rule.prerequisites
            else "no prerequisite technology"
        )
        return (
            f"Research completed {technology}, requiring {prerequisites}. "
            f"Canon effect: {rule.effect} The unlock remains permanent across later worlds."
        )

    def make_assistant_decision(self, decision_epoch: float) -> None:
        """Execute the game's one fully autonomous strategic decision for this minute."""
        self.ensure_world()
        legal_tasks = self.legal_assistant_tasks()
        decision_number = self.assistant_decisions + 1

        # One decision controls both the canon strategic verb and production focus.
        strategic_action = STRATEGIC_ACTIONS[
            self.strategic_actions % len(STRATEGIC_ACTIONS)
        ]
        task = legal_tasks[self.assistant_decisions % len(legal_tasks)]
        previous_focus = self.assistant_focus
        turn_resolved = self.turn

        self.assistant_focus = task
        self.assistant_decisions = decision_number
        self.strategic_actions += 1
        self.world_actions += 1
        self.turn += 1
        self.last_assistant_epoch = decision_epoch

        if strategic_action == "Research":
            action_result = self.resolve_autonomous_research()
        elif strategic_action == "Build":
            action_result = (
                "Build execution advanced the current scenario without inventing "
                "an unverified building cost or production yield."
            )
        elif strategic_action == "Trade":
            action_result = (
                "Trade execution advanced the current scenario without inventing "
                "an unverified exchange rate."
            )
        else:
            action_result = (
                "Attack execution advanced military pressure without inventing "
                "unverified unit statistics or combat results."
            )

        gated_count = len(COLONY_ASSISTANT_TASKS) - len(legal_tasks)
        progress = f"{self.world_actions}/{self.world_action_goal()}"
        self.add_chronicle(
            f"Autonomous decision #{format_big_number(decision_number)} on Eternal World "
            f"{self.world_number}, Turn {turn_resolved} chose {strategic_action} and changed "
            f"Colony Assistant focus from {previous_focus} to {task}. {action_result} "
            f"Scenario operations are {progress}; enemy scale is "
            f"{format_big_number(self.enemy_scale_rating())}, with {gated_count} advanced "
            "assistant task(s) still technology-gated.",
            epoch=decision_epoch,
        )

        if self.world_actions >= self.world_action_goal():
            self.complete_world(epoch=decision_epoch)

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
        data["strategic_actions"] = str(self.strategic_actions)
        data["world_actions"] = str(self.world_actions)
        return data

    @classmethod
    def from_json_dict(cls, raw: dict) -> "GameState":
        verified_tech = [
            name
            for name in raw.get("researched_technologies", [])
            if name in TECHNOLOGIES
        ]
        world_raw = raw.get("world_map")
        world_map = (
            GeneratedMap.from_json_dict(world_raw)
            if isinstance(world_raw, dict)
            else None
        )
        legacy_actions = int(raw.get("manual_orders", 0))
        state = cls(
            race=raw.get("race", ""),
            turn=max(1, int(raw.get("turn", 1))),
            world_number=max(1, int(raw.get("world_number", 1))),
            worlds_completed=max(0, int(raw.get("worlds_completed", 0))),
            permanent_power=max(0, int(raw.get("permanent_power", 0))),
            assistant_focus=raw.get("assistant_focus", "Construction"),
            assistant_decisions=max(0, int(raw.get("assistant_decisions", 0))),
            strategic_actions=max(
                0,
                int(raw.get("strategic_actions", legacy_actions)),
            ),
            world_actions=max(0, int(raw.get("world_actions", 0))),
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
            "Started a fresh autonomous eternal campaign because the previous save "
            "could not be read safely; no replacement canon data was invented."
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
            f"away, resolving {format_big_number(decisions)} fully autonomous strategic "
            "decision(s) at exactly one decision per completed minute while preserving "
            "permanent eternal-campaign progression.",
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


def safe_add_segments(
    window: "curses._CursesWindow",
    y: int,
    segments: Iterable[tuple[str, int]],
) -> None:
    x = 0
    for text, attr in segments:
        safe_addstr(window, y, x, text, attr)
        x += len(text)


def show_offline_popup(
    stdscr: "curses._CursesWindow",
    report: OfflineReport,
) -> None:
    """Show offline progress briefly and dismiss it automatically."""
    if report.away_seconds < ASSISTANT_INTERVAL_SECONDS:
        return
    height, width = stdscr.getmaxyx()
    minutes = report.away_seconds // 60
    message = (
        f"Offline progress: {minutes} completed minute(s) passed while the game "
        f"was closed. The AI resolved {format_big_number(report.decisions_applied)} "
        "strategic decision(s), including automatic world transitions when earned. "
        "Permanent progression was retained."
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
            ui_attr(PAIR_INFO, bold=index == 0),
        )
    stdscr.refresh()
    curses.napms(1500)


def render(stdscr: "curses._CursesWindow", state: GameState) -> None:
    stdscr.erase()
    height, width = stdscr.getmaxyx()
    state.ensure_world()
    world = state.world_map

    safe_addstr(
        stdscr,
        0,
        0,
        APP_TITLE,
        ui_attr(PAIR_TITLE, bold=True),
    )

    safe_add_segments(
        stdscr,
        2,
        (
            ("Race: ", ui_attr(PAIR_TITLE, bold=True)),
            (state.race or "initializing", ui_attr(PAIR_GOOD, bold=True)),
            ("   Eternal World: ", ui_attr(PAIR_TITLE)),
            (format_big_number(state.world_number), ui_attr(PAIR_WORLD, bold=True)),
            ("   Turn: ", ui_attr(PAIR_TITLE)),
            (format_big_number(state.turn), ui_attr(PAIR_WORLD)),
            ("   AI: ", ui_attr(PAIR_TITLE)),
            ("FULL AUTONOMY", ui_attr(PAIR_GOOD, bold=True)),
        ),
    )
    safe_add_segments(
        stdscr,
        3,
        (
            ("Permanent power: ", ui_attr(PAIR_TITLE)),
            (format_big_number(state.permanent_power), ui_attr(PAIR_GOOD, bold=True)),
            ("   Worlds completed: ", ui_attr(PAIR_TITLE)),
            (format_big_number(state.worlds_completed), ui_attr(PAIR_WORLD)),
            ("   Enemy scale: ", ui_attr(PAIR_TITLE)),
            (format_big_number(state.enemy_scale_rating()), ui_attr(PAIR_DANGER, bold=True)),
        ),
    )
    if world is not None:
        safe_add_segments(
            stdscr,
            4,
            (
                ("Scenario seed: ", ui_attr(PAIR_TITLE)),
                (world.fingerprint, ui_attr(PAIR_INFO)),
                ("   Territories: ", ui_attr(PAIR_TITLE)),
                (str(world.territory_count), ui_attr(PAIR_WORLD)),
                ("   Rivals: ", ui_attr(PAIR_TITLE)),
                (str(len(world.rival_races)), ui_attr(PAIR_DANGER)),
                ("   Shrine sites: ", ui_attr(PAIR_TITLE)),
                (str(len(world.shrine_sites)), ui_attr(PAIR_RESEARCH)),
            ),
        )

    eligible = state.eligible_technologies()
    next_tech = eligible[0] if eligible else "awaiting verified prerequisites"
    safe_add_segments(
        stdscr,
        5,
        (
            ("AI focus: ", ui_attr(PAIR_TITLE)),
            (state.assistant_focus, ui_attr(PAIR_INFO, bold=True)),
            ("   Operations: ", ui_attr(PAIR_TITLE)),
            (
                f"{state.world_actions}/{state.world_action_goal()}",
                ui_attr(PAIR_WORLD, bold=True),
            ),
            ("   Next research: ", ui_attr(PAIR_TITLE)),
            (next_tech, ui_attr(PAIR_RESEARCH)),
        ),
    )

    safe_addstr(
        stdscr,
        7,
        0,
        "Chronicle — newest five autonomous actions",
        ui_attr(PAIR_WORLD, bold=True),
    )
    row = 8
    for entry in reversed(state.chronicle):
        prefix = f"{entry.at} — "
        available = max(16, width - len(prefix) - 1)
        parts = list(wrapped_lines(entry.detail, available))
        detail_attr = ui_attr(chronicle_pair_for_detail(entry.detail))
        safe_addstr(stdscr, row, 0, prefix, ui_attr(PAIR_TITLE, bold=True))
        safe_addstr(stdscr, row, len(prefix), parts[0], detail_attr)
        row += 1
        for continuation in parts[1:]:
            if row >= height - 4:
                break
            safe_addstr(stdscr, row, len(prefix), continuation, detail_attr)
            row += 1
        if row >= height - 4:
            break

    safe_addstr(
        stdscr,
        height - 2,
        0,
        "FULL AUTONOMY ACTIVE — no gameplay controls. Q exits the program only.",
        ui_attr(PAIR_WARNING, bold=True),
    )
    safe_addstr(
        stdscr,
        height - 1,
        0,
        "1 AI decision/minute • random eternal worlds • permanent progress • silent 1s autosave",
        ui_attr(PAIR_GOOD),
    )
    stdscr.refresh()


def run_game(stdscr: "curses._CursesWindow") -> None:
    curses.curs_set(0)
    init_colors()
    stdscr.nodelay(True)
    stdscr.timeout(100)

    state = load_state()
    state.bootstrap_autonomous_campaign()
    offline_report = apply_offline_progress(state)
    last_save = time.monotonic()

    render(stdscr, state)
    show_offline_popup(stdscr, offline_report)

    running = True
    while running:
        now = time.time()
        state.apply_due_assistant_decisions(now)

        current_monotonic = time.monotonic()
        if current_monotonic - last_save >= AUTOSAVE_INTERVAL_SECONDS:
            silent_save(state)
            last_save = current_monotonic

        render(stdscr, state)
        key = stdscr.getch()
        if key in (ord("q"), ord("Q")):
            running = False

    silent_save(state)


def main() -> None:
    curses.wrapper(run_game)


if __name__ == "__main__":
    main()
