"""Selects cross-slot streams to use NoC."""

__copyright__ = """
Copyright (c) 2024 RapidStream Design Automation, Inc. and contributors.
All rights reserved. The contributor(s) of this file has/have agreed to the
RapidStream Contributor License Agreement.
"""

import random
from typing import Any

import networkx as nx
from pulp import GUROBI_CMD, LpMinimize, LpProblem, LpVariable, lpSum
from pydantic import BaseModel, ConfigDict

from device import Device
from ir_helper import (
    extract_slot_coord,
    extract_slot_range,
    get_slot_to_noc_nodes,
    round_up_to_noc_bw,
)
from tcl_helper import print_noc_loc_tcl


class NocUsage(BaseModel):
    """Represents NoC resource count of a slot."""

    model_config = ConfigDict(frozen=True)

    nmu: int
    nsu: int


def get_streams_noc_area(
    streams: dict[str, dict[str, str]], device: Device
) -> list[list[NocUsage]]:
    """Calculates the NMU and NSU usage in each slot for the cross-slot streams.

    Returns a 2d array of NocUsage for all slots.
    """
    slot_width = device.slot_width
    slot_height = device.slot_height
    nmu_usage = [[0 for y in range(slot_height)] for x in range(slot_width)]
    nsu_usage = [[0 for y in range(slot_height)] for x in range(slot_width)]
    for _, slots in streams.items():
        src_slot_range = slots["src"]
        dest_slot_range = slots["dest"]
        # FIXME assumed to use the first slot in the slot range
        for x, y in extract_slot_range(src_slot_range):
            nmu_usage[x][y] += 1
            break
        for x, y in extract_slot_range(dest_slot_range):
            nsu_usage[x][y] += 1
            break

    slots_usage: list[list[NocUsage]] = []
    for x in range(slot_width):
        slots_usage.append([])
        for y in range(slot_height):
            slots_usage[x].append(NocUsage(nmu=nmu_usage[x][y], nsu=nsu_usage[x][y]))
    return slots_usage


def print_ordered_edges(edges: list[tuple[str, str]]) -> None:
    """Orders the given list of edges into a valid path using NetworkX.

    Prints the ordered nodes.
    """
    graph = nx.DiGraph(edges)

    try:
        ordered_nodes = list(nx.topological_sort(graph))
        print(" -> ".join(ordered_nodes))
        return
    except nx.NetworkXUnfeasible:
        print("Graph contains a cycle or is invalid!")
        print(edges)
        return


def is_exceeding_avail_noc_nodes(
    slots_usage: list[list[NocUsage]], device: Device
) -> bool:
    """Checks if any slot exceeds the available NMU and NSU nodes.

    Returns a bool.
    """
    for x in range(device.slot_width):
        for y in range(device.slot_height):
            if slots_usage[x][y].nmu > device.get_num_nmu_in_slot(x, y):
                return True
            if slots_usage[x][y].nsu > device.get_num_nsu_in_slot(x, y):
                return True
    return False


def random_selector(
    streams_slots: dict[str, dict[str, str]], device: Device
) -> list[str]:
    """Randomly selects a subset of the streams to use NoC.

    Repeatedly generates (smaller) subsets of streams until the subset
    satisfies the number of available NMU and NSU nodes in the NoC.

    Returns a list of selected streams to use NoC.
    """
    num_to_select = len(streams_slots)
    while True:
        num_to_select = random.randint(1, num_to_select)
        random_streams = random.sample(sorted(streams_slots), num_to_select)
        slots_usage = get_streams_noc_area(
            {s: streams_slots[s] for s in random_streams}, device
        )
        print(f"try {num_to_select} streams.")
        print(slots_usage)

        if is_exceeding_avail_noc_nodes(slots_usage, device):
            num_to_select -= 1
        else:
            print("random selector success")
            return random_streams


def greedy_selector(
    streams_slots: dict[str, dict[str, str]], device: Device
) -> list[str]:
    """Greedily selects streams to use NoC.

    Selects the maximum number of streams that can be satisfied by the number of
    available NMU and NSU nodes in the NoC.

    Returns a list of selected streams to use NoC.
    """
    selected_streams: dict[str, dict[str, str]] = {}
    for s, slots in streams_slots.items():
        slots_usage = get_streams_noc_area(selected_streams | {s: slots}, device)

        if not is_exceeding_avail_noc_nodes(slots_usage, device):
            selected_streams.update({s: slots})
    print(f"greedy selector has selected {len(selected_streams)} streams.")
    print("slot usage", get_streams_noc_area(selected_streams, device))
    return list(selected_streams.keys())


def get_stream_manhattan_dist(
    streams_slots: dict[str, dict[str, str]],
) -> dict[str, int]:
    """Calculates the minimum number of boundaries each stream crosses.

    Uses Manhattan distance abs(dest_x - src_x) + abs(dest_y - src_y).

    Returns a dictionary of {stream_name: num_boundaries_crossed}.

    Example:
    >>> get_stream_manhattan_dist(
    ...     {
    ...         "s1": {"src": "SLOT_X0Y0", "dest": "SLOT_X3Y2"},
    ...         "s2": {"src": "SLOT_X4Y8", "dest": "SLOT_X2Y4"},
    ...     }
    ... )
    {'s1': 5, 's2': 6}
    """
    streams_boundaries: dict[str, int] = {}
    for stream_name, slots in streams_slots.items():
        # assumes the two slots are the same
        src_x, src_y = extract_slot_coord(slots["src"].split("_TO_")[0])
        dest_x, dest_y = extract_slot_coord(slots["dest"].split("_TO_")[0])
        # using Manhattan distance
        streams_boundaries[stream_name] = abs(dest_x - src_x) + abs(dest_y - src_y)
    return streams_boundaries


def get_stream_manhattan_bw(
    streams_slots: dict[str, dict[str, str]], streams_bw: dict[str, float]
) -> dict[str, float]:
    """Calculates the Manhattan bandwidth of each stream.

    Returns the modified dictionary.

    Example:
    >>> get_stream_manhattan_bw(
    ...     {
    ...         "s1": {"src": "SLOT_X0Y0", "dest": "SLOT_X3Y2"},
    ...         "s2": {"src": "SLOT_X4Y8", "dest": "SLOT_X2Y4"},
    ...     },
    ...     {
    ...         "s1": 1000.0,
    ...         "s2": 16000.0,
    ...     },
    ... )
    {'s1': 5000.0, 's2': 96000.0}
    """
    streams_manhattan = get_stream_manhattan_dist(streams_slots)
    for stream_name, bw in streams_bw.items():
        streams_bw[stream_name] = bw * streams_manhattan[stream_name]
    return streams_bw


def get_nx_graph_from_noc_graph(device: Device) -> nx.DiGraph:
    """Converts NocGraph to NetworkX graph without the edge attributes.

    Returns a NetworkX directed graph.
    """
    noc_nx_graph = nx.DiGraph()
    noc_nx_graph.add_nodes_from(device.noc_graph.get_all_nodes())
    noc_nx_graph.add_edges_from(device.noc_graph.get_all_edges())
    return noc_nx_graph


def find_nx_shortest_path(device: Device, src: str, dest: str) -> None:
    """Finds and prints the shortest path from src to dest using NetworkX."""
    nx_graph = get_nx_graph_from_noc_graph(device)
    path = nx.shortest_path(nx_graph, source=src, target=dest)
    print("networkx shortest path:")
    print((" -> ".join(path)))


def ilp_noc_selector_add_var(
    streams_nodes: dict[str, dict[str, list[str]]], device: Device
) -> dict[str, dict[str, LpVariable | dict[str | tuple[str, str], LpVariable]]]:
    """Adds ilp_var for the NoC selector ILP.

    Returns a dictionary containing LpVariable.
    """
    ilp_var = {}

    edges = device.noc_graph.get_all_edges()

    for stream_name, end_nodes in streams_nodes.items():
        ilp_var[stream_name] = {
            # binary ilp_var of all edges for each stream
            "x": {
                e: LpVariable(name=f"x_{stream_name}_{e}", cat="Binary") for e in edges
            },
            # binary variable to determine the src nmu node for each stream
            "y": {
                n: LpVariable(name=f"y_{stream_name}_{n}", cat="Binary")
                for n in end_nodes["src"]
            },
            # binary variable to determine the dest nmu node for each stream
            "z": {
                n: LpVariable(name=f"z_{stream_name}_{n}", cat="Binary")
                for n in end_nodes["dest"]
            },
            # binary variable to determine if the stream is mapped to use NoC
            "not_mapped_stream": LpVariable(
                name=f"not_mapped_{stream_name}", cat="Binary"
            ),
        }
    return ilp_var


def ilp_noc_selector_add_constr(
    m: LpProblem,
    ilp_var: dict[str, dict[str, LpVariable | dict[Any, LpVariable]]],
    streams_nodes: dict[str, dict[str, list[str]]],
    streams_bw: dict[str, float],
    device: Device,
) -> None:
    """Adds constraints for the NoC selector ILP."""

    # create networkx graph for its helper functions
    noc_nx_graph = get_nx_graph_from_noc_graph(device)

    # 1. Exactly one source node must be chosen or its not mapped
    for stream_name, end_nodes in streams_nodes.items():
        m += (
            lpSum(ilp_var[stream_name]["y"][n] for n in end_nodes["src"])
            + ilp_var[stream_name]["not_mapped_stream"]
            == 1
        )

    # 2. Exactly one destination node must be chosen or its not mapped
    for stream_name, end_nodes in streams_nodes.items():
        m += (
            lpSum(ilp_var[stream_name]["z"][n] for n in end_nodes["dest"])
            + ilp_var[stream_name]["not_mapped_stream"]
            == 1
        )

    # 3. Flow conservation constraints
    for stream_name, end_nodes in streams_nodes.items():
        for node in noc_nx_graph.nodes():
            if node not in end_nodes["src"] and node not in end_nodes["dest"]:
                # intermediate nodes have conserved flow
                m += (
                    lpSum(
                        ilp_var[stream_name]["x"][(u, node)]
                        for u in noc_nx_graph.predecessors(node)
                    )
                    - lpSum(
                        ilp_var[stream_name]["x"][(node, v)]
                        for v in noc_nx_graph.successors(node)
                    )
                    == 0
                )

                # each node is visited at most once
                m += lpSum(
                    ilp_var[stream_name]["x"][(u, node)]
                    for u in noc_nx_graph.predecessors(node)
                ) + lpSum(
                    ilp_var[stream_name]["x"][(node, v)]
                    for v in noc_nx_graph.successors(node)
                ) <= (
                    1 + 1
                )

            # forbid disconnected edge cycles
            # may not be necessary

        # src has only one outgoing flow
        for n in end_nodes["src"]:
            m += (
                lpSum(
                    ilp_var[stream_name]["x"][(n, v)]
                    for v in noc_nx_graph.successors(n)
                )
                - ilp_var[stream_name]["y"][n]
                == 0
            )
            m += (
                lpSum(
                    ilp_var[stream_name]["x"][(v, n)]
                    for v in noc_nx_graph.predecessors(n)
                )
                == 0
            )

        # src has only one incoming flow
        for n in end_nodes["dest"]:
            m += (
                lpSum(
                    ilp_var[stream_name]["x"][(v, n)]
                    for v in noc_nx_graph.predecessors(n)
                )
                - ilp_var[stream_name]["z"][n]
                == 0
            )
            m += (
                lpSum(
                    ilp_var[stream_name]["x"][(n, v)]
                    for v in noc_nx_graph.successors(n)
                )
                == 0
            )

    # 4. Unique source and destination constraints
    for node in device.noc_graph.get_all_nmu_nodes():
        m += (
            lpSum(
                ilp_var[stream_name]["y"][node]
                for stream_name, end_nodes in streams_nodes.items()
                if node in end_nodes["src"]
            )
            <= 1
        )

    for node in device.noc_graph.get_all_nsu_nodes():
        m += (
            lpSum(
                ilp_var[stream_name]["z"][node]
                for stream_name, end_nodes in streams_nodes.items()
                if node in end_nodes["dest"]
            )
            <= 1
        )

    # 5. Bandwidth constraints
    for e in device.noc_graph.edges:
        e_tuple = (e.src.name, e.dest.name)
        m += (
            lpSum(
                round_up_to_noc_bw(bw) * ilp_var[stream_name]["x"][e_tuple]
                for stream_name, bw in streams_bw.items()
            )
            <= e.bandwidth
        )


def ilp_noc_selector_add_constr_special(
    m: LpProblem,
    ilp_var: dict[str, dict[str, LpVariable | dict[Any, LpVariable]]],
    streams_nodes: dict[str, dict[str, list[str]]],
    device: Device,
) -> None:
    """Adds special constraints for the NoC selector ILP."""

    # 6. Vivado 2023.2 NoC Compiler Corner Cases
    # if there are more than one mapped stream,
    # Note: I am not putting the if-more-than-one-mapped-stream check because
    #       if there is only one stream to map, we can use column 1
    # column 0 can only have max 1 src and 1 dest
    for slr in range(device.noc_graph.num_slr):
        m += (
            lpSum(
                ilp_var[stream_name]["y"][node]
                for stream_name, end_nodes in streams_nodes.items()
                for node in end_nodes["src"]
                if node in device.noc_graph.get_column_nmu_nodes(0, slr)
            )
            <= 1
        )
        m += (
            lpSum(
                ilp_var[stream_name]["z"][node]
                for stream_name, end_nodes in streams_nodes.items()
                for node in end_nodes["dest"]
                if node in device.noc_graph.get_column_nsu_nodes(0, slr)
            )
            <= 1
        )

    # forbid any cross-SLR edges in column 0
    for stream_name, _ in streams_nodes.items():
        m += (
            lpSum(
                ilp_var[stream_name]["x"][e]
                for e in device.noc_graph.get_column_cross_slr_edges(0)
            )
            == 0
        )

    # forbid using column 0 as a bypass path
    for stream_name, _ in streams_nodes.items():
        m += (
            lpSum(
                ilp_var[stream_name]["x"][e]
                for e in device.noc_graph.get_column_entrance_edges(0)
            )
            <= 1
        )


def ilp_noc_selector_add_obj(
    m: LpProblem,
    ilp_var: dict[str, dict[str, LpVariable]],
    streams_bw: dict[str, float],
) -> None:
    """Adds objectives for the NoC selector ILP."""
    # not used
    # total_path_length = lpSum(
    #     ilp_var[stream_name]["x"][e]
    #     for stream_name, _ in streams_nodes.items()
    #     for e in device.noc_graph.get_all_edges()
    # )
    total_not_mapped_bandwidth = lpSum(
        bw * ilp_var[stream_name]["not_mapped_stream"]
        for stream_name, bw in streams_bw.items()
    )
    m += total_not_mapped_bandwidth


def post_process_noc_ilp(
    ilp_var: dict[str, dict[str, LpVariable | dict[Any, LpVariable]]],
    streams_nodes: dict[str, dict[str, list[str]]],
) -> tuple[list[str], dict[str, tuple[str, str]]]:
    """Post-process the ILP ilp_var after solver.

    Parses the selected streams. Prints the selected NoC nodes and edges.

    Returns a list of selected streams in str.
    """
    noc_streams = []
    node_loc = {}

    for stream_name, end_nodes in streams_nodes.items():
        selected_src = next(
            (
                node
                for node in end_nodes["src"]
                if ilp_var[stream_name]["y"][node].value() == 1
            ),
            None,
        )
        selected_dest = next(
            (
                node
                for node in end_nodes["dest"]
                if ilp_var[stream_name]["z"][node].value() == 1
            ),
            None,
        )
        if selected_src and selected_dest:
            noc_streams.append(stream_name)
            node_loc[stream_name] = (selected_src, selected_dest)
            selected_edges = [
                e for e, var in ilp_var[stream_name]["x"].items() if var.value() >= 1
            ]
            print(stream_name)
            print("optimizer shortest path:")
            print_ordered_edges(selected_edges)

            # prints the NetworkX shortest path as comparison
            # find_nx_shortest_path(device, selected_src, selected_dest)
            print()

    # prints the tcl constraints for the selected NMU and NSU nodes
    print_noc_loc_tcl(node_loc)

    print(f"ILP has selected {len(noc_streams)} streams")
    return noc_streams, node_loc


def ilp_noc_selector(
    streams_slots: dict[str, dict[str, str]],
    streams_bw: dict[str, float],
    device: Device,
) -> tuple[list[str], dict[str, tuple[str, str]]]:
    """Selects a subset of the streams to use NoC using ILP.

    Minimizes the total bandwidth not using NoC and the total path length.

    Args:
        streams_slots:  dictionary of the cross-slot stream's
                        "src" and "dest" slot ranges
        streams_bw:     dictionary of the cross-slot stream's bandwidth target
        device:         Device class with slot attributes and NoC graph.

    Returns a dict of selected streams to use NoC with their nodes.
    """
    m = LpProblem("noc", LpMinimize)

    streams_nodes = get_slot_to_noc_nodes(streams_slots, device)

    # decision ilp_var
    ilp_var = ilp_noc_selector_add_var(streams_nodes, device)

    # Constraints
    ilp_noc_selector_add_constr(m, ilp_var, streams_nodes, streams_bw, device)
    ilp_noc_selector_add_constr_special(m, ilp_var, streams_nodes, device)

    # Objective function
    streams_manhattan_bw = get_stream_manhattan_bw(streams_slots, streams_bw)
    # mypy bug: sees LpVariable as Any
    # declaring a new function and trick mypy to see ilp_var's values as LpVariable
    ilp_noc_selector_add_obj(m, ilp_var, streams_manhattan_bw)

    m.solve(GUROBI_CMD(options=[("TimeLimit", 300)]))

    # Post-solve operations
    return post_process_noc_ilp(ilp_var, streams_nodes)


# playground
if __name__ == "__main__":
    from vh1582_nocgraph import vh1582_nocgraph

    test_G = vh1582_nocgraph()
    test_D = Device(
        part_num="",
        board_part="",
        slot_width=2,
        slot_height=2,
        noc_graph=test_G,
        nmu_per_slot=[],  # generated
        nsu_per_slot=[],  # generated
        cr_mapping=[
            ["CLOCKREGION_X0Y0:CLOCKREGION_X4Y4", "CLOCKREGION_X0Y5:CLOCKREGION_X4Y7"],
            ["CLOCKREGION_X5Y0:CLOCKREGION_X9Y4", "CLOCKREGION_X5Y5:CLOCKREGION_X9Y7"],
        ],
    )
    test_streams_slots = {
        "a1": {"src": "SLOT_X0Y1_TO_SLOT_X0Y1", "dest": "SLOT_X1Y1_TO_SLOT_X1Y1"},
        "a2": {"src": "SLOT_X1Y1_TO_SLOT_X1Y1", "dest": "SLOT_X0Y1_TO_SLOT_X0Y1"},
        "a3": {"src": "SLOT_X0Y0_TO_SLOT_X0Y0", "dest": "SLOT_X1Y0_TO_SLOT_X1Y0"},
        "a4": {"src": "SLOT_X1Y0_TO_SLOT_X1Y0", "dest": "SLOT_X0Y0_TO_SLOT_X0Y0"},
        "b1": {"src": "SLOT_X0Y1_TO_SLOT_X0Y1", "dest": "SLOT_X1Y1_TO_SLOT_X1Y1"},
        "b2": {"src": "SLOT_X0Y1_TO_SLOT_X0Y1", "dest": "SLOT_X1Y1_TO_SLOT_X1Y1"},
        "b3": {"src": "SLOT_X0Y1_TO_SLOT_X0Y1", "dest": "SLOT_X1Y1_TO_SLOT_X1Y1"},
        "b4": {"src": "SLOT_X0Y1_TO_SLOT_X0Y1", "dest": "SLOT_X1Y1_TO_SLOT_X1Y1"},
        "g1": {"src": "SLOT_X1Y1_TO_SLOT_X1Y1", "dest": "SLOT_X0Y1_TO_SLOT_X0Y1"},
        "g2": {"src": "SLOT_X1Y1_TO_SLOT_X1Y1", "dest": "SLOT_X0Y1_TO_SLOT_X0Y1"},
        "g3": {"src": "SLOT_X1Y1_TO_SLOT_X1Y1", "dest": "SLOT_X0Y1_TO_SLOT_X0Y1"},
        "g4": {"src": "SLOT_X1Y1_TO_SLOT_X1Y1", "dest": "SLOT_X0Y1_TO_SLOT_X0Y1"},
        "c1": {"src": "SLOT_X0Y0_TO_SLOT_X0Y0", "dest": "SLOT_X1Y0_TO_SLOT_X1Y0"},
        "c2": {"src": "SLOT_X0Y0_TO_SLOT_X0Y0", "dest": "SLOT_X1Y0_TO_SLOT_X1Y0"},
        "c3": {"src": "SLOT_X0Y0_TO_SLOT_X0Y0", "dest": "SLOT_X1Y0_TO_SLOT_X1Y0"},
        "c4": {"src": "SLOT_X0Y0_TO_SLOT_X0Y0", "dest": "SLOT_X1Y0_TO_SLOT_X1Y0"},
        "h1": {"src": "SLOT_X1Y0_TO_SLOT_X1Y0", "dest": "SLOT_X0Y0_TO_SLOT_X0Y0"},
        "h2": {"src": "SLOT_X1Y0_TO_SLOT_X1Y0", "dest": "SLOT_X0Y0_TO_SLOT_X0Y0"},
        "h3": {"src": "SLOT_X1Y0_TO_SLOT_X1Y0", "dest": "SLOT_X0Y0_TO_SLOT_X0Y0"},
        "h4": {"src": "SLOT_X1Y0_TO_SLOT_X1Y0", "dest": "SLOT_X0Y0_TO_SLOT_X0Y0"},
    }
    test_streams_bw = {
        "a1": 16000.0,
        "a2": 16000.0,
        "a3": 16000.0,
        "a4": 16000.0,
        "b1": 16000.0,
        "b2": 16000.0,
        "b3": 16000.0,
        "b4": 16000.0,
        "g1": 16000.0,
        "g2": 16000.0,
        "g3": 16000.0,
        "g4": 16000.0,
        "c1": 16000.0,
        "c2": 16000.0,
        "c3": 16000.0,
        "c4": 16000.0,
        "h1": 16000.0,
        "h2": 16000.0,
        "h3": 16000.0,
        "h4": 16000.0,
    }
    test_selected = ilp_noc_selector(test_streams_slots, test_streams_bw, test_D)
    print(test_selected)
    assert len(test_selected) == len(test_streams_slots), "Test failed!"
