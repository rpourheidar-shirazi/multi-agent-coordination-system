import asyncio
import logging
import json
import random
import re

from heapq import heapify, heappop, heappush
from collections import defaultdict, deque

import agentspeak
import agentspeak.runtime
import agentspeak.ext_stdlib

LOGGER = agentspeak.get_logger(__name__)


actions = agentspeak.Actions(agentspeak.ext_stdlib.actions)


###################################
# INSERT YOUR CUSTOM ACTIONS HERE #
###################################

# Must match massim.protocol.data.Position.moved.
DIRECTIONS = {
    "ne": (1, -1, 0),
    "nw": (-1, 0, 1),
    "se": (1, 0, -1),
    "sw": (-1, 1, 0),
    "n": (0, -1, 1),
    "s": (0, 1, -1),
}
DIRECTION_NAMES = tuple(DIRECTIONS)
DEFAULT_DIRECTION = DIRECTION_NAMES[0]

ORIGIN = (0, 0, 0)
MAX_EXPLORE_RADIUS = 30
MAX_PRODUCTIVE_HOP = 4
MAX_CNP_DISTANCE = MAX_EXPLORE_RADIUS
DATA_CLAIM_TIMEOUT = 20

known_mountains = defaultdict(set)
known_oases = defaultdict(set)
team_mountains = set()
team_oases = set()
visited_cells = defaultdict(set)
team_visit_counts = defaultdict(int)
last_counted_pos = {}
data_claims = {}


def _term_name(term):
    return term.functor if hasattr(term, "functor") else str(term)


def get_current_pos(agent):
    for beliefs in agent.beliefs.values():
        for belief in beliefs:
            if belief.functor == "pos" and len(belief.args) == 3:
                return tuple(int(x) for x in belief.args)
    return None


def get_mountains(agent):
    mountains = set()
    for beliefs in agent.beliefs.values():
        for belief in beliefs:
            if belief.functor == "mountain":
                if len(belief.args) == 1:
                    pos_term = belief.args[0]
                    if hasattr(pos_term, "functor") and pos_term.functor == "pos":
                        mountains.add(tuple(int(x) for x in pos_term.args))
                elif len(belief.args) == 3:
                    mountains.add(tuple(int(x) for x in belief.args))
    if mountains:
        known_mountains[agent.name].update(mountains)
        team_mountains.update(mountains)
    return set(team_mountains) | known_mountains[agent.name]


def get_data_positions(agent):
    data_positions = []
    for beliefs in agent.beliefs.values():
        for belief in beliefs:
            if belief.functor == "data" and len(belief.args) == 2:
                pos = _pos_from_term(belief.args[1])
                if pos is not None:
                    packets = int(belief.args[0])
                    data_positions.append((packets, pos))
    return data_positions


def get_claimed_data_positions(agent):
    claimed = []
    current_step = int(agent.simulation_step or 0)
    for packets, pos in get_data_positions(agent):
        if hex_distance(pos, ORIGIN) > MAX_EXPLORE_RADIUS:
            if data_claims.get(pos, {}).get("owner") == agent.name:
                data_claims.pop(pos, None)
            continue

        owner_info = data_claims.get(pos)
        if owner_info is None:
            data_claims[pos] = {"owner": agent.name, "step": current_step}
            owner = agent.name
        elif owner_info["owner"] == agent.name:
            owner_info["step"] = current_step
            owner = agent.name
        elif current_step - owner_info["step"] > DATA_CLAIM_TIMEOUT:
            data_claims[pos] = {"owner": agent.name, "step": current_step}
            owner = agent.name
        else:
            owner = owner_info["owner"]

        if owner == agent.name:
            claimed.append((packets, pos))
    return claimed


def _pos_from_term(term):
    if hasattr(term, "functor") and term.functor == "pos" and len(term.args) == 3:
        return tuple(int(x) for x in term.args)
    return None


def _data_pos_from_belief(belief):
    if belief.functor == "data" and len(belief.args) == 2:
        return _pos_from_term(belief.args[1])
    return None


def hex_distance(a, b):
    return max(abs(a[0] - b[0]), abs(a[1] - b[1]), abs(a[2] - b[2]))


def _neighbor_pos(pos, direction):
    delta = DIRECTIONS.get(direction)
    if delta is None:
        return None
    return (pos[0] + delta[0], pos[1] + delta[1], pos[2] + delta[2])


def _inside_zone(pos):
    return hex_distance(pos, ORIGIN) <= MAX_EXPLORE_RADIUS


def _move_radius_limit(start):
    return max(MAX_EXPLORE_RADIUS, hex_distance(start, ORIGIN))


def _bounded_move_direction(agent, requested_direction):
    current_pos = get_current_pos(agent)
    if current_pos is None:
        return (
            requested_direction
            if requested_direction in DIRECTIONS
            else DEFAULT_DIRECTION
        )

    mountains = get_mountains(agent)
    current_dist = hex_distance(current_pos, ORIGIN)
    requested_neighbor = _neighbor_pos(current_pos, requested_direction)
    if requested_neighbor is not None and requested_neighbor not in mountains:
        requested_dist = hex_distance(requested_neighbor, ORIGIN)
        if current_dist > MAX_EXPLORE_RADIUS:
            if requested_dist < current_dist:
                return requested_direction
        elif _inside_zone(requested_neighbor):
            return requested_direction

    candidates = []
    for direction in DIRECTIONS:
        neighbor = _neighbor_pos(current_pos, direction)
        if neighbor in mountains:
            continue
        distance = hex_distance(neighbor, ORIGIN)
        if current_dist > MAX_EXPLORE_RADIUS:
            if distance < current_dist:
                candidates.append((distance, direction))
        elif _inside_zone(neighbor):
            candidates.append((distance, direction))

    if not candidates:
        return None
    return min(candidates)[1]


def astar_path(start, goals, blocked, max_depth=200, max_radius=None, rng=None):
    open_list = []
    heappush(open_list, (0, start))
    came_from = {start: None}
    g_score = {start: 0}
    closed = set()

    while open_list:
        _, current = heappop(open_list)

        if current in closed:
            continue
        closed.add(current)

        if current in goals:
            path = []
            while current is not None:
                path.append(current)
                current = came_from[current]
            path.reverse()
            return path

        if g_score[current] >= max_depth:
            continue

        for delta in DIRECTIONS.values():
            neighbor = (
                current[0] + delta[0],
                current[1] + delta[1],
                current[2] + delta[2],
            )
            if neighbor in blocked or neighbor in closed:
                continue
            if (
                max_radius is not None
                and hex_distance(neighbor, (0, 0, 0)) > max_radius
            ):
                continue
            new_g = g_score[current] + 1
            if neighbor not in g_score or new_g < g_score[neighbor]:
                g_score[neighbor] = new_g
                h = min(hex_distance(neighbor, goal) for goal in goals)
                if rng is not None:
                    h += rng.uniform(0, 2.0)
                heappush(open_list, (new_g + h, neighbor))
                came_from[neighbor] = current

    return None


def _direction_to_neighbor(current_pos, next_pos):
    for direction, delta in DIRECTIONS.items():
        if (
            current_pos[0] + delta[0],
            current_pos[1] + delta[1],
            current_pos[2] + delta[2],
        ) == next_pos:
            return direction
    return None


def _path_limits(start, goals, slack=40):
    goals = list(goals)
    if not goals:
        return 200, _move_radius_limit(start)

    farthest_goal = max(hex_distance(start, goal) for goal in goals)
    max_depth = max(200, farthest_goal + slack)
    max_radius = _move_radius_limit(start)
    return max_depth, max_radius


def _greedy_dir(current_pos, target_pos, mountains, max_radius=None):
    if max_radius is None:
        max_radius = _move_radius_limit(current_pos)
    best_dir = None
    best_d = float("inf")
    for direction, delta in DIRECTIONS.items():
        neighbor = (
            current_pos[0] + delta[0],
            current_pos[1] + delta[1],
            current_pos[2] + delta[2],
        )
        if neighbor in mountains:
            continue
        if max_radius is not None and hex_distance(neighbor, ORIGIN) > max_radius:
            continue
        d = hex_distance(neighbor, target_pos)
        if d < best_d:
            best_d = d
            best_dir = direction
    return (
        best_dir
        or _bounded_move_direction_from_pos(current_pos, mountains)
        or DEFAULT_DIRECTION
    )


def _bounded_move_direction_from_pos(current_pos, mountains):
    current_dist = hex_distance(current_pos, ORIGIN)
    candidates = []
    for direction in DIRECTIONS:
        neighbor = _neighbor_pos(current_pos, direction)
        if neighbor in mountains:
            continue
        distance = hex_distance(neighbor, ORIGIN)
        if current_dist > MAX_EXPLORE_RADIUS:
            if distance < current_dist:
                candidates.append((distance, direction))
        elif _inside_zone(neighbor):
            candidates.append((distance, direction))
    if not candidates:
        return None
    return min(candidates)[1]


_path_to_data_state = {}


@actions.add_function(".path_to_data", (agentspeak.runtime.Agent,))
def _path_to_data(agent):
    current_pos = get_current_pos(agent)
    if current_pos is None:
        return DEFAULT_DIRECTION

    data_positions = get_claimed_data_positions(agent)
    if not data_positions:
        return DEFAULT_DIRECTION

    if agent.name not in _path_to_data_state:
        _path_to_data_state[agent.name] = {
            "last_pos": None,
            "last_dir": None,
            "blocked": set(),
        }
    state = _path_to_data_state[agent.name]

    if state["last_pos"] == current_pos and state["last_dir"] is not None:
        delta = DIRECTIONS[state["last_dir"]]
        state["blocked"].add(
            (
                current_pos[0] + delta[0],
                current_pos[1] + delta[1],
                current_pos[2] + delta[2],
            )
        )
    elif state["last_pos"] != current_pos:
        state["blocked"].clear()

    mountains = get_mountains(agent) | state["blocked"]
    goals = {pos for _, pos in data_positions}

    agent_rng = random.Random(sum(ord(c) * (i + 1) for i, c in enumerate(agent.name)))
    max_depth, max_radius = _path_limits(current_pos, goals, slack=60)
    path = astar_path(
        current_pos,
        goals,
        mountains,
        max_depth=max_depth,
        max_radius=max_radius,
        rng=agent_rng,
    )
    if path is None or len(path) < 2:
        nearest = min(data_positions, key=lambda x: hex_distance(current_pos, x[1]))[1]
        direction = _greedy_dir(current_pos, nearest, mountains, max_radius=max_radius)
        state["last_pos"] = current_pos
        state["last_dir"] = direction
        return direction

    direction = _direction_to_neighbor(current_pos, path[1])
    if direction is not None:
        state["last_pos"] = current_pos
        state["last_dir"] = direction
        return direction

    nearest = min(data_positions, key=lambda x: hex_distance(current_pos, x[1]))[1]
    direction = _greedy_dir(current_pos, nearest, mountains, max_radius=max_radius)
    state["last_pos"] = current_pos
    state["last_dir"] = direction
    return direction


@actions.add(".should_pursue_data", 0)
def _should_pursue_data(agent, term, intention):
    current_pos = get_current_pos(agent)
    if current_pos is not None and get_claimed_data_positions(agent):
        yield


@actions.add(".at_oasis", 0)
def _at_oasis(agent, term, intention):
    current_pos = get_current_pos(agent)
    if current_pos is not None and current_pos in get_oases(agent):
        yield


PATROL_RADIUS = 8


@actions.add(".should_patrol_origin", 0)
def _should_patrol_origin(agent, term, intention):
    if _agent_index(agent) == 1:
        yield


@actions.add_function(".explore_near_origin", (agentspeak.runtime.Agent,))
def _explore_near_origin(agent):
    current_pos = get_current_pos(agent)
    if current_pos is None:
        return DEFAULT_DIRECTION
    visited = visited_cells[agent.name]
    visited.add(current_pos)
    if last_counted_pos.get(agent.name) != current_pos:
        team_visit_counts[current_pos] += 1
        last_counted_pos[agent.name] = current_pos
    mountains = get_mountains(agent)

    queue: deque = deque([(current_pos, None)])
    seen = {current_pos}
    best_step = None
    best_score = (float("inf"), float("inf"))
    while queue:
        pos, first_step = queue.popleft()
        for direction in _ordered_directions(agent):
            delta = DIRECTIONS[direction]
            neighbor = (pos[0] + delta[0], pos[1] + delta[1], pos[2] + delta[2])
            if neighbor in seen or neighbor in mountains:
                continue
            if hex_distance(neighbor, ORIGIN) > PATROL_RADIUS:
                continue
            seen.add(neighbor)
            step = direction if first_step is None else first_step
            if neighbor not in visited and team_visit_counts[neighbor] == 0:
                return step
            score = (team_visit_counts[neighbor], 1 if neighbor in visited else 0)
            if score < best_score:
                best_score = score
                best_step = step
            queue.append((neighbor, step))

    return best_step or _path_to_origin_direction(agent)


def get_oases(agent):
    oases = set()
    for beliefs in agent.beliefs.values():
        for belief in beliefs:
            if belief.functor == "oasis" and len(belief.args) in {1, 2}:
                pos_term = belief.args[0]
                if hasattr(pos_term, "functor") and pos_term.functor == "pos":
                    oases.add(tuple(int(x) for x in pos_term.args))
    if oases:
        known_oases[agent.name].update(oases)
        team_oases.update(oases)
    return set(team_oases) | known_oases[agent.name]


_path_to_oasis_state = {}


@actions.add_function(".path_to_oasis", (agentspeak.runtime.Agent,))
def _path_to_oasis(agent):
    current_pos = get_current_pos(agent)
    if current_pos is None:
        return DEFAULT_DIRECTION

    if agent.name not in _path_to_oasis_state:
        _path_to_oasis_state[agent.name] = {
            "last_pos": None,
            "last_dir": None,
            "blocked": set(),
        }
    state = _path_to_oasis_state[agent.name]

    if state["last_pos"] == current_pos and state["last_dir"] is not None:
        delta = DIRECTIONS[state["last_dir"]]
        state["blocked"].add(
            (
                current_pos[0] + delta[0],
                current_pos[1] + delta[1],
                current_pos[2] + delta[2],
            )
        )
    elif state["last_pos"] != current_pos:
        state["blocked"].clear()

    oases = get_oases(agent)
    mountains = get_mountains(agent) | state["blocked"]
    direction = None

    if oases:
        max_depth, max_radius = _path_limits(current_pos, oases, slack=60)
        path = astar_path(
            current_pos, oases, mountains, max_depth=max_depth, max_radius=max_radius
        )
        if path and len(path) >= 2:
            direction = _direction_to_neighbor(current_pos, path[1])

    if direction is None:
        if oases:
            max_depth, max_radius = _path_limits(current_pos, {ORIGIN}, slack=60)
            path = astar_path(
                current_pos, {ORIGIN}, mountains, max_depth=max_depth, max_radius=max_radius
            )
            if path and len(path) >= 2:
                direction = _direction_to_neighbor(current_pos, path[1])
        else:
            direction = _explore_direction(agent)

    if direction is None:
        target = (
            min(oases, key=lambda pos: hex_distance(current_pos, pos))
            if oases
            else ORIGIN
        )
        direction = _greedy_dir(
            current_pos, target, mountains, max_radius=_move_radius_limit(current_pos)
        )

    state["last_pos"] = current_pos
    state["last_dir"] = direction
    return direction


def _agent_index(agent):
    match = re.search(r"(\d+)$", agent.name)
    if match:
        return max(1, int(match.group(1)))
    return (sum(ord(c) for c in agent.name) % 10) + 1


def _ordered_directions(agent):
    directions = list(DIRECTIONS.keys())
    index = _agent_index(agent) - 1
    shift = index % len(directions)
    ordered = directions[shift:] + directions[:shift]
    if (index // len(directions)) % 2:
        ordered = list(reversed(ordered))
    return ordered


def _direction_bias(agent, pos):
    primary = DIRECTIONS[_ordered_directions(agent)[0]]
    return pos[0] * primary[0] + pos[1] * primary[1] + pos[2] * primary[2]


@actions.add_function(".explore_direction", (agentspeak.runtime.Agent,))
def _explore_direction(agent):
    current_pos = get_current_pos(agent)
    if current_pos is None:
        return DEFAULT_DIRECTION
    visited = visited_cells[agent.name]
    visited.add(current_pos)
    if last_counted_pos.get(agent.name) != current_pos:
        team_visit_counts[current_pos] += 1
        last_counted_pos[agent.name] = current_pos
    mountains = get_mountains(agent)

    if hex_distance(current_pos, ORIGIN) > MAX_EXPLORE_RADIUS:
        return _path_to_origin_direction(agent)

    queue = deque([(current_pos, None)])
    seen = {current_pos}
    best_step = None
    best_score = (float("inf"), float("inf"), float("inf"))
    while queue:
        pos, first_step = queue.popleft()
        for direction in _ordered_directions(agent):
            delta = DIRECTIONS[direction]
            neighbor = (pos[0] + delta[0], pos[1] + delta[1], pos[2] + delta[2])
            if neighbor in seen or neighbor in mountains:
                continue
            if hex_distance(neighbor, ORIGIN) > MAX_EXPLORE_RADIUS:
                continue
            seen.add(neighbor)
            step = direction if first_step is None else first_step
            if neighbor not in visited and team_visit_counts[neighbor] == 0:
                return step
            score = (
                team_visit_counts[neighbor],
                1 if neighbor in visited else 0,
                -_direction_bias(agent, neighbor),
            )
            if score < best_score:
                best_score = score
                best_step = step
            queue.append((neighbor, step))

    visited.clear()
    return best_step or random.choice(_ordered_directions(agent))


@actions.add_function(".best_direction_to_origin", (agentspeak.runtime.Agent,))
def _best_direction_to_origin(agent):
    current_pos = get_current_pos(agent)
    if current_pos is None:
        return DEFAULT_DIRECTION
    mountains = get_mountains(agent)
    current_dist = hex_distance(current_pos, (0, 0, 0))
    improving, neutral, worsening = [], [], []
    for direction, delta in DIRECTIONS.items():
        neighbor = (
            current_pos[0] + delta[0],
            current_pos[1] + delta[1],
            current_pos[2] + delta[2],
        )
        if neighbor in mountains:
            continue
        d = hex_distance(neighbor, (0, 0, 0))
        if d < current_dist:
            improving.append(direction)
        elif d == current_dist:
            neutral.append(direction)
        else:
            worsening.append(direction)
    if improving:
        return random.choice(improving)
    if neutral:
        return random.choice(neutral)
    if worsening:
        return random.choice(worsening)
    return random.choice(DIRECTION_NAMES)


_path_to_origin_state = {}


def _path_to_origin_direction(agent):
    current_pos = get_current_pos(agent)
    if current_pos is None:
        return DEFAULT_DIRECTION

    if agent.name not in _path_to_origin_state:
        _path_to_origin_state[agent.name] = {
            "last_pos": None,
            "last_dir": None,
            "blocked": set(),
        }
    state = _path_to_origin_state[agent.name]

    if state["last_pos"] == current_pos and state["last_dir"] is not None:
        delta = DIRECTIONS[state["last_dir"]]
        state["blocked"].add(
            (
                current_pos[0] + delta[0],
                current_pos[1] + delta[1],
                current_pos[2] + delta[2],
            )
        )
    elif state["last_pos"] != current_pos:
        state["blocked"].clear()

    mountains = get_mountains(agent) | state["blocked"]
    max_depth, max_radius = _path_limits(current_pos, {ORIGIN}, slack=80)
    path = astar_path(
        current_pos, {ORIGIN}, mountains, max_depth=max_depth, max_radius=max_radius
    )
    direction = None
    if path and len(path) >= 2:
        direction = _direction_to_neighbor(current_pos, path[1])
    if direction is None:
        direction = _greedy_dir(current_pos, ORIGIN, mountains, max_radius=max_radius)

    state["last_pos"] = current_pos
    state["last_dir"] = direction
    return direction


@actions.add_function(".path_to_origin", (agentspeak.runtime.Agent,))
def _path_to_origin(agent):
    return _path_to_origin_direction(agent)


@actions.add_function(".within_send_range", (agentspeak.runtime.Agent,))
def _within_send_range(agent):
    pos = get_current_pos(agent)
    if pos is None:
        return False
    return hex_distance(pos, (0, 0, 0)) <= 4


@actions.add_function(".dist_to_origin", (int, int, int))
def _dist_to_origin(q, r, s):
    return hex_distance((q, r, s), (0, 0, 0))


@actions.add_function(".hex_dist", (int, int, int, int, int, int))
def _hex_dist(q1, r1, s1, q2, r2, s2):
    return hex_distance((q1, r1, s1), (q2, r2, s2))


_path_to_pos_state = {}


@actions.add_function(".path_to_pos", (agentspeak.runtime.Agent, int, int, int))
def _path_to_pos(agent, tq, tr, ts):
    current_pos = get_current_pos(agent)
    if current_pos is None:
        return DEFAULT_DIRECTION
    target = (int(tq), int(tr), int(ts))
    state_key = (agent.name, target)
    if state_key not in _path_to_pos_state:
        _path_to_pos_state[state_key] = {
            "last_pos": None,
            "last_dir": None,
            "blocked": set(),
        }
    state = _path_to_pos_state[state_key]

    if state["last_pos"] == current_pos and state["last_dir"] is not None:
        delta = DIRECTIONS[state["last_dir"]]
        state["blocked"].add(
            (
                current_pos[0] + delta[0],
                current_pos[1] + delta[1],
                current_pos[2] + delta[2],
            )
        )
    elif state["last_pos"] != current_pos:
        state["blocked"].clear()

    mountains = get_mountains(agent) | state["blocked"]
    max_depth, max_radius = _path_limits(current_pos, {target}, slack=60)
    path = astar_path(
        current_pos, {target}, mountains, max_depth=max_depth, max_radius=max_radius
    )
    if path and len(path) >= 2:
        direction = _direction_to_neighbor(current_pos, path[1])
        if direction is not None:
            state["last_pos"] = current_pos
            state["last_dir"] = direction
            return direction
    direction = _greedy_dir(current_pos, target, mountains, max_radius=max_radius)
    state["last_pos"] = current_pos
    state["last_dir"] = direction
    return direction


@actions.add_function(".cnp_select_winner", (agentspeak.runtime.Agent,))
def _cnp_select_winner(agent):
    best_name = ""
    best_dist = float("inf")
    for beliefs in agent.beliefs.values():
        for belief in beliefs:
            if belief.functor == "bid" and len(belief.args) >= 5:
                bidder_arg = belief.args[0]
                manager_arg = belief.args[1]
                bidder = (
                    bidder_arg.functor
                    if hasattr(bidder_arg, "functor")
                    else str(bidder_arg)
                )
                manager = (
                    manager_arg.functor
                    if hasattr(manager_arg, "functor")
                    else str(manager_arg)
                )
                if manager != agent.name:
                    continue
                try:
                    q = int(belief.args[2])
                    r = int(belief.args[3])
                    s = int(belief.args[4])
                    d = hex_distance((q, r, s), (0, 0, 0))
                    if d < best_dist:
                        best_dist = d
                        best_name = bidder
                except (ValueError, TypeError):
                    pass
    return agentspeak.Literal(best_name) if best_name else agentspeak.Literal("none")


def _add_belief(agent, name, *args):
    term = agentspeak.Literal(name, tuple(args))
    agent.call(
        agentspeak.Trigger.addition,
        agentspeak.GoalType.belief,
        term,
        agentspeak.runtime.Intention(),
    )


def _remove_belief(agent, name, *args):
    term = agentspeak.Literal(name, tuple(args))
    agent.call(
        agentspeak.Trigger.removal,
        agentspeak.GoalType.belief,
        term,
        agentspeak.runtime.Intention(),
    )


def _data_at_current_position(agent, current_pos):
    for _, pos in get_data_positions(agent):
        if pos == current_pos:
            return True
    return False


def _collect_cnp_bids(agent, current_step):
    bids = {}
    for beliefs in agent.beliefs.values():
        for belief in beliefs:
            if belief.functor != "bid" or len(belief.args) < 6:
                continue

            bidder = _term_name(belief.args[0])
            manager = _term_name(belief.args[1])
            if manager != agent.name or bidder == agent.name:
                continue

            try:
                q = int(belief.args[2])
                r = int(belief.args[3])
                s = int(belief.args[4])
                cfp_step = int(belief.args[5])
                energy = int(belief.args[6]) if len(belief.args) >= 7 else 100
            except (ValueError, TypeError):
                continue

            if current_step - cfp_step > 3 or energy < 15:
                continue
            bids[bidder] = {
                "pos": (q, r, s),
                "cfp_step": cfp_step,
                "energy": energy,
            }
    return bids


def _best_cnp_route(start, bids):
    nodes = [("sender", "", start)]
    nodes.extend(("relay", name, bid["pos"]) for name, bid in bids.items())
    nodes.append(("origin", "", ORIGIN))

    origin_index = len(nodes) - 1
    queue = [(0, 0, 0, (0,))]
    best = {0: (0, 0)}

    while queue:
        max_hop, hops, index, path = heappop(queue)
        if index == origin_index:
            return [nodes[i] for i in path], max_hop
        if best.get(index, (float("inf"), float("inf"))) < (max_hop, hops):
            continue

        _, _, current_pos = nodes[index]
        for next_index, (_, _, next_pos) in enumerate(nodes):
            if next_index == index or next_index in path:
                continue
            hop = hex_distance(current_pos, next_pos)
            if hop > MAX_PRODUCTIVE_HOP:
                continue
            new_cost = (max(max_hop, hop), hops + 1)
            if new_cost < best.get(next_index, (float("inf"), float("inf"))):
                best[next_index] = new_cost
                heappush(
                    queue, (new_cost[0], new_cost[1], next_index, path + (next_index,))
                )

    return None, None


def _schedule_cnp_retry(agent, current_step, wait_steps=8):
    _add_belief(agent, "cnp_retry_after", int(current_step) + wait_steps)


def _remove_bid_state(relay, manager_name, cfp_step):
    _remove_belief(
        relay,
        "cnp_state",
        agentspeak.Literal(
            "bidding", (agentspeak.Literal(manager_name), int(cfp_step))
        ),
    )


def _mark_relay_committed(relay, manager_name, exec_step):
    _add_belief(
        relay,
        "cnp_state",
        agentspeak.Literal(
            "relaying", (agentspeak.Literal(manager_name), int(exec_step))
        ),
    )


def _mark_manager_committed(agent, exec_step):
    _add_belief(agent, "cnp_state", agentspeak.Literal("committed", (int(exec_step),)))


def _schedule_immediate_route(agent, route, bids, current_step, max_hop):
    exec_step = int(current_step) + 1
    first_target = route[1][2]
    relay_assignments = []

    for index in range(1, len(route) - 1):
        _, relay_name, _ = route[index]
        _, _, next_pos = route[index + 1]
        relay = agent.env.agents.get(relay_name)
        if relay is None:
            _schedule_cnp_retry(agent, current_step)
            return agentspeak.Literal("missing_relay")
        relay_assignments.append((relay, relay_name, next_pos))

    _add_belief(
        agent, "send_task", first_target[0], first_target[1], first_target[2], exec_step
    )
    _mark_manager_committed(agent, exec_step)

    for relay, relay_name, next_pos in relay_assignments:
        _remove_bid_state(relay, agent.name, bids[relay_name]["cfp_step"])
        _mark_relay_committed(relay, agent.name, exec_step)
        _add_belief(
            relay,
            "relay_task",
            agentspeak.Literal(agent.name),
            next_pos[0],
            next_pos[1],
            next_pos[2],
            exec_step,
        )

    LOGGER.info(
        "%s prepared CNP route with %d relay/relays, max hop %d, exec step %d",
        agent.name,
        len(route) - 2,
        max_hop,
        exec_step,
    )
    return agentspeak.Literal("route_ready")



def _planned_relay_targets_minimal(start, blocked):
    """Single-relay fallback: one relay at MAX_PRODUCTIVE_HOP from start,
    relays to ORIGIN using the game relay range (50) instead of MAX_PRODUCTIVE_HOP."""
    max_depth, max_radius = _path_limits(start, {ORIGIN}, slack=60)
    path = astar_path(
        start,
        {ORIGIN},
        blocked,
        max_depth=max_depth,
        max_radius=max_radius,
    )
    if path is None or len(path) < 2:
        return None
    first_idx = min(MAX_PRODUCTIVE_HOP, len(path) - 2)
    return [path[first_idx], ORIGIN]


def _relay_travel_distance(start, target, blocked):
    max_depth, max_radius = _path_limits(start, {target}, slack=60)
    path = astar_path(
        start,
        {target},
        blocked,
        max_depth=max_depth,
        max_radius=max_radius,
    )
    if path is None:
        return hex_distance(start, target)
    return max(0, len(path) - 1)


def _assign_relay_targets(bids, relay_targets, blocked):
    remaining = set(bids.keys())
    assignments = []

    for target in relay_targets:
        best_name = None
        best_cost = (float("inf"), float("inf"))
        for name in remaining:
            start = bids[name]["pos"]
            travel = _relay_travel_distance(start, target, blocked)
            cost = (travel, hex_distance(start, target))
            if cost < best_cost:
                best_cost = cost
                best_name = name

        if best_name is None:
            return None

        remaining.remove(best_name)
        assignments.append((best_name, target, best_cost[0]))

    return assignments


def _schedule_mobilized_route(agent, current_pos, bids, current_step):
    blocked = get_mountains(agent)
    # Always use single-relay: one relay positions at MAX_PRODUCTIVE_HOP from
    # sender, then uses game relay range (50) to reach ORIGIN directly.
    # Multi-relay chains were unreliable — any stuck intermediate breaks the chain.
    targets = _planned_relay_targets_minimal(current_pos, blocked)
    if targets is None:
        _schedule_cnp_retry(agent, current_step)
        return agentspeak.Literal("no_path")

    relay_targets = targets[:-1]
    if len(bids) < len(relay_targets):
        _schedule_cnp_retry(agent, current_step)
        return agentspeak.Literal("no_route")

    assignments = _assign_relay_targets(bids, relay_targets, blocked)
    if assignments is None:
        _schedule_cnp_retry(agent, current_step)
        return agentspeak.Literal("no_route")

    relay_agents = []
    for relay_name, target, travel_steps in assignments:
        relay = agent.env.agents.get(relay_name)
        if relay is None:
            _schedule_cnp_retry(agent, current_step)
            return agentspeak.Literal("missing_relay")
        relay_agents.append((relay, relay_name, target, travel_steps))

    max_travel = max(
        (travel_steps for _, _, _, travel_steps in relay_agents), default=0
    )
    exec_step = int(current_step) + max_travel + 8
    first_target = relay_targets[0] if relay_targets else ORIGIN

    _add_belief(
        agent, "send_task", first_target[0], first_target[1], first_target[2], exec_step
    )
    _mark_manager_committed(agent, exec_step)

    for index, (relay, relay_name, target, _) in enumerate(relay_agents):
        next_target = targets[index + 1]
        _remove_bid_state(relay, agent.name, bids[relay_name]["cfp_step"])
        _mark_relay_committed(relay, agent.name, exec_step)
        _add_belief(
            relay,
            "move_task",
            agentspeak.Literal(agent.name),
            target[0],
            target[1],
            target[2],
            exec_step,
        )
        _add_belief(
            relay,
            "relay_task",
            agentspeak.Literal(agent.name),
            next_target[0],
            next_target[1],
            next_target[2],
            exec_step,
        )

    LOGGER.info(
        "%s mobilized %d relay/relays for CNP transfer at step %d via %s",
        agent.name,
        len(relay_agents),
        exec_step,
        relay_targets,
    )
    return agentspeak.Literal("mobilizing")


@actions.add_function(
    ".cnp_prepare_route", (agentspeak.runtime.Agent, agentspeak.Literal, int, int, int, int)
)
def _cnp_prepare_route(agent, manager_name_term, data_q, data_r, data_s, current_step):
    manager_name = _term_name(manager_name_term)
    data_pos = (int(data_q), int(data_r), int(data_s))
    current_pos = get_current_pos(agent)

    # Check if data still exists at the announced position (not current position)
    data_exists = False
    for _, pos in get_data_positions(agent):
        if pos == data_pos:
            data_exists = True
            break

    if not data_exists:
        LOGGER.warning(
            "%s: no data at announced position %s (agent at %s)",
            manager_name,
            data_pos,
            current_pos,
        )
        _schedule_cnp_retry(agent, current_step, wait_steps=8)
        return agentspeak.Literal("no_data")

    if hex_distance(data_pos, ORIGIN) > MAX_CNP_DISTANCE:
        LOGGER.warning(
            "%s: announced data position %s exceeds distance limit",
            manager_name,
            data_pos,
        )
        return agentspeak.Literal("too_far")

    bids = _collect_cnp_bids(agent, int(current_step))
    if not bids:
        LOGGER.info("%s: no bids received for data at %s", manager_name, data_pos)
        _schedule_cnp_retry(agent, current_step)
        return agentspeak.Literal("no_bids")

    route, max_hop = _best_cnp_route(data_pos, bids)
    if route is not None and len(route) >= 3:
        return _schedule_immediate_route(agent, route, bids, current_step, max_hop)

    result = _schedule_mobilized_route(agent, data_pos, bids, current_step)
    if result == agentspeak.Literal("no_route"):
        LOGGER.info("%s: no valid route from data pos %s", manager_name, data_pos)
        _schedule_cnp_retry(agent, current_step)
    return result


@actions.add(".tell_agent", 2)
def _tell_agent(agent, term, intention):
    name_term = agentspeak.grounded(term.args[0], intention.scope)
    name = name_term.functor if hasattr(name_term, "functor") else str(name_term)
    message = agentspeak.freeze(term.args[1], intention.scope, {})
    tagged = message.with_annotation(
        agentspeak.Literal("source", (agentspeak.Literal(agent.name),))
    )
    receiver = agent.env.agents.get(name)
    if receiver:
        receiver.call(
            agentspeak.Trigger.addition,
            agentspeak.GoalType.belief,
            tagged,
            agentspeak.runtime.Intention(),
        )
    yield


@actions.add_function(".custom_action", (int,))
def _custom_action(x):
    return x**2


@actions.add_function(".random_direction", ())
def _random_direction():
    return random.choice(DIRECTION_NAMES)


@actions.add_function(".safe_escape_direction", (agentspeak.runtime.Agent,))
def _safe_escape_direction(agent):
    current_pos = get_current_pos(agent)
    if current_pos is None:
        return random.choice(DIRECTION_NAMES)
    mountains = get_mountains(agent)
    dist = hex_distance(current_pos, (0, 0, 0))
    improving, neutral, worsening = [], [], []
    for direction, delta in DIRECTIONS.items():
        neighbor = (
            current_pos[0] + delta[0],
            current_pos[1] + delta[1],
            current_pos[2] + delta[2],
        )
        if neighbor in mountains:
            continue
        d = hex_distance(neighbor, (0, 0, 0))
        if d < dist:
            improving.append(direction)
        elif d == dist:
            neutral.append(direction)
        elif d <= MAX_EXPLORE_RADIUS:
            worsening.append(direction)
    if dist > MAX_EXPLORE_RADIUS:
        candidates = improving
    elif dist >= MAX_EXPLORE_RADIUS - 3:
        candidates = improving or neutral or worsening
    else:
        candidates = improving + neutral + worsening
    fallback = _bounded_move_direction_from_pos(current_pos, mountains)
    return (
        random.choice(candidates)
        if candidates
        else fallback or random.choice(DIRECTION_NAMES)
    )


PERCEPT_TAG = frozenset(
    [agentspeak.Literal("source", (agentspeak.Literal("percept"),))]
)


class Environment(agentspeak.runtime.Environment):
    def __init__(self):
        super(Environment, self).__init__()
        self._reset_global_state()

    def _reset_global_state(self):
        global known_mountains, known_oases, team_mountains, team_oases
        global visited_cells, team_visit_counts, last_counted_pos, data_claims

        known_mountains = defaultdict(set)
        known_oases = defaultdict(set)
        team_mountains = set()
        team_oases = set()
        visited_cells = defaultdict(set)
        team_visit_counts = defaultdict(int)
        last_counted_pos = {}
        data_claims = {}

    def time(self):
        return asyncio.get_event_loop().time()

    def run(self):
        super(Environment, self).run()
        self.dispatch_wait_until()

    def dispatch_wait_until(self):
        earliest = None
        for agent in self.agents.values():
            for intention_stack in agent.intentions:
                wait = intention_stack[-1].wait_until
                if wait and (not earliest or wait < earliest):
                    earliest = wait

        if earliest:
            loop = asyncio.get_event_loop()
            loop.call_at(earliest, self.run)


class Agent(agentspeak.runtime.Agent, asyncio.Protocol):
    def __init__(self, env, name):
        super(Agent, self).__init__(env, name)
        self.action_id = None
        self.simulation_step = None

    def connect(self, username, password, host="localhost", port=12300):
        self.action_id = None
        self.username = username
        self.password = password

        if self.name != username:
            LOGGER.warning(
                "username %r does not equal agent name %r", username, self.name
            )

        loop = asyncio.get_event_loop()
        return loop.create_connection(lambda: self, host, port)

    @actions.add(".disconnect", 0)
    def _disconnect(self, term, intention):
        self.transport.close()
        yield

    @actions.add(".stopMAS", 0)
    def _stop_mas(self, term, intention):
        asyncio.get_event_loop().stop()
        yield

    @actions.add(".printBeliefs", 0)
    def _print_beliefs(self, term, intention):
        for beliefs in self.beliefs.values():
            for belief in beliefs:
                print(agentspeak.asl_repr(belief))
        yield

    @actions.add(".send", 3)
    @actions.add(".send", 1)
    @actions.add(".relay", 2)
    @actions.add(".relay", 4)
    @actions.add(".move", 1)
    @actions.add(".recharge", 0)
    @actions.add(".skip", 0)
    def _mapc_action(self, term, intention):
        if self.action_id is None:
            LOGGER.warning("%s already did an action in this step", self.name)
            return

        action_type = term.functor.lstrip(".")
        params = []
        for param in term.args:
            p = agentspeak.grounded(param, intention.scope)
            if isinstance(p, float) and p.is_integer():
                p = int(p)
            params.append(p)

        if action_type == "move" and params:
            requested_direction = _term_name(params[0])
            safe_direction = _bounded_move_direction(self, requested_direction)
            if safe_direction is None:
                LOGGER.info(
                    "%s skipped unsafe move %s at zone boundary",
                    self.name,
                    requested_direction,
                )
                action_type = "skip"
                params = []
            else:
                if safe_direction != requested_direction:
                    LOGGER.info(
                        "%s adjusted move %s -> %s to stay within radius %d",
                        self.name,
                        requested_direction,
                        safe_direction,
                        MAX_EXPLORE_RADIUS,
                    )
                params = [safe_direction]

        message = {
            "type": "ActionMessage",
            "id": self.action_id,
            "actionType": action_type,
            "actionParams": [],
        }
        for param in params:
            message["actionParams"].append(str(param))
        self.send_message(message)
        self.action_id = None
        yield

    def send_message(self, message):
        LOGGER.debug("%s >> %s", self.name, message)
        self.transport.write(json.dumps(message).encode("utf-8") + b"\0")

    def connection_made(self, transport):
        LOGGER.info("socket for %s connected", self.name)

        self.transport = transport
        self.buffer = b""

        # Authenticate
        message = {
            "type": "AuthRequestMessage",
            "username": self.username,
            "password": self.password,
        }
        self.send_message(message)

    def connection_lost(self, exc):
        LOGGER.warning("socket connection lost (reason: %s)", exc)

        self.call(
            agentspeak.Trigger.removal,
            agentspeak.GoalType.belief,
            agentspeak.Literal("connected", (self.name,)),
            agentspeak.runtime.Intention(),
        )

        self.env.run()

    def data_received(self, data):
        self.buffer += data
        while b"\0" in self.buffer:
            message, self.buffer = self.buffer.split(b"\0", 1)
            json_str = message.decode("utf-8")
            LOGGER.debug("%s << %s", self.name, json_str)
            self.message_received(json.loads(json_str))

    def message_received(self, message):
        if message.get("type") == "AuthResponseMessage":
            self.handle_auth_response(message)
        elif message.get("type") == "SimStartMessage":
            self.handle_sim_start(message)
        elif message.get("type") == "SimEndMessage":
            self.handle_sim_end(message)
        elif message.get("type") == "RequestActionMessage":
            self.handle_request_action(message)
        else:
            LOGGER.error("unknown message type: %r", message.get("type"))

        # Delay run until all agents are in a consistent state.
        if all(
            agent.simulation_step is None
            or agent.simulation_step == self.simulation_step
            for agent in self.env.agents.values()
        ):
            if self.simulation_step is not None:
                LOGGER.debug(
                    "%s was the last agent to receive step %d",
                    self.name,
                    self.simulation_step,
                )
            self.env.run()
        else:
            LOGGER.debug(
                "%s will wait for other agents to be in step %d",
                self.name,
                self.simulation_step,
            )

    # removes all beliefs of the same "type" (name and arity)
    def _set_belief(self, name, *args):
        term = agentspeak.Literal(name, tuple(args), PERCEPT_TAG)

        found = False

        for belief in list(self.beliefs[term.literal_group()]):
            if agentspeak.unifies(term, belief):
                found = True
            else:
                self.call(
                    agentspeak.Trigger.removal,
                    agentspeak.GoalType.belief,
                    belief,
                    agentspeak.runtime.Intention(),
                )

        if not found:
            self.call(
                agentspeak.Trigger.addition,
                agentspeak.GoalType.belief,
                term,
                agentspeak.runtime.Intention(),
            )

    def _replace_beliefs(self, group, beliefs):
        old_beliefs = list(self.beliefs[group])
        new_beliefs = beliefs
        heapify(old_beliefs)
        heapify(new_beliefs)
        while len(old_beliefs) > 0 and len(new_beliefs) > 0:
            old_belief = old_beliefs[0]
            new_belief = new_beliefs[0]
            if old_belief == new_belief:
                heappop(old_beliefs)
                heappop(new_beliefs)
            elif old_belief < new_belief:
                self.call(
                    agentspeak.Trigger.removal,
                    agentspeak.GoalType.belief,
                    old_belief,
                    agentspeak.runtime.Intention(),
                )
                heappop(old_beliefs)
            elif old_belief > new_belief:
                self.call(
                    agentspeak.Trigger.addition,
                    agentspeak.GoalType.belief,
                    new_belief,
                    agentspeak.runtime.Intention(),
                )
                heappop(new_beliefs)

        while len(old_beliefs) > 0:
            self.call(
                agentspeak.Trigger.removal,
                agentspeak.GoalType.belief,
                old_beliefs[0],
                agentspeak.runtime.Intention(),
            )
            heappop(old_beliefs)
        while len(new_beliefs) > 0:
            self.call(
                agentspeak.Trigger.addition,
                agentspeak.GoalType.belief,
                new_beliefs[0],
                agentspeak.runtime.Intention(),
            )
            heappop(new_beliefs)

    def handle_auth_response(self, response):
        if response.get("result") != "ok":
            LOGGER.error("auth response for %s: %r", self.name, response.get("result"))
        else:
            self._set_belief("connected", self.name)

    def _get_params(self, params):
        result = []
        for param in params:
            if "id" in param:
                result.append(param["id"])
            elif "n" in param:
                result.append(param["n"])
            elif "lParams" in param:
                result.append(tuple(self._get_params(param["lParams"])))
            elif "fParams" in param:
                fName = param["name"]
                result.append(
                    agentspeak.Literal(fName, tuple(self._get_params(param["fParams"])))
                )
            else:
                LOGGER.error("unknown percept parameter type %s: %r", self.name, param)
        return result

    def _handle_percepts(self, percepts):
        simulation_step = -1
        new_beliefs = defaultdict(lambda: list())
        current_pos = None
        current_data_positions = set()
        for percept in percepts:
            name = percept["name"]
            if name == "step":
                simulation_step = percept["pParams"][0]["n"]
            params = self._get_params(percept["pParams"])
            if name == "pos" and len(params) == 3:
                current_pos = tuple(int(x) for x in params)
            elif name == "data" and len(params) == 2:
                pos = _pos_from_term(params[1])
                if pos is not None:
                    current_data_positions.add(pos)
            percept = agentspeak.Literal(name, params, PERCEPT_TAG)
            new_beliefs[(name, len(params))].append(percept)
            LOGGER.debug(f"Perceived {percept.asl_repr()}")
        for name_and_arity, beliefs in new_beliefs.items():
            name, arity = name_and_arity
            if name in {"mountain", "oasis"}:
                merged = {
                    belief.asl_repr(): belief
                    for belief in list(self.beliefs[name_and_arity]) + beliefs
                }
                self._replace_beliefs(name_and_arity, list(merged.values()))
            elif name == "data" and arity == 2:
                by_pos = {}
                for belief in list(self.beliefs[name_and_arity]) + beliefs:
                    pos = _data_pos_from_belief(belief)
                    if pos is not None:
                        by_pos[pos] = belief
                self._replace_beliefs(name_and_arity, list(by_pos.values()))
            else:
                self._replace_beliefs(name_and_arity, beliefs)
        if current_pos is not None and current_pos not in current_data_positions:
            data_claims.pop(current_pos, None)
            for belief in list(self.beliefs[("data", 2)]):
                if _data_pos_from_belief(belief) == current_pos:
                    self.call(
                        agentspeak.Trigger.removal,
                        agentspeak.GoalType.belief,
                        belief,
                        agentspeak.runtime.Intention(),
                    )
        return simulation_step

    def handle_sim_start(self, simulation):
        self._handle_percepts(simulation["percepts"])

    def handle_sim_end(self, end):
        self._set_belief("ranking", int(end.get("ranking")))
        self._set_belief("score", int(end.get("score")))

    def handle_request_action(self, req):
        if self.action_id is not None:
            LOGGER.warning(
                "%s: action id %d was not used, auto-skipping stale request",
                self.name,
                self.action_id,
            )
            self.send_message(
                {
                    "type": "ActionMessage",
                    "id": self.action_id,
                    "actionType": "skip",
                    "actionParams": [],
                }
            )
            self.action_id = None

        self.action_id = int(req.get("id"))
        self.simulation_step = self._handle_percepts(req["percepts"])

        self._set_belief("timestamp", int(req.get("time")))
        self._set_belief("deadline", int(req.get("deadline")))
