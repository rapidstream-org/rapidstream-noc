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

from noc_graph import NocGraph


class NocArea(BaseModel):
    """Represents NoC resource count of a slot."""

    model_config = ConfigDict(frozen=True)

    nmu: int
    nsu: int


SLOT_WIDTH = 1
SLOT_HEIGHT = 4

vp1802_noc_resource: list[list[NocArea]]
vp1802_nmu: list[list[list[str]]]
vp1802_nsu: list[list[list[str]]]

if SLOT_WIDTH == 1:
    vp1802_noc_resource = [
        [
            NocArea(nmu=28, nsu=28),
            NocArea(nmu=24, nsu=24),
            NocArea(nmu=24, nsu=24),
            NocArea(nmu=24, nsu=24),
        ]
    ]
    vp1802_nmu = [
        [
            [f"nmu_x{x}y{y}" for x in range(4) for y in range(0, 7)],  # range(0, 1)],
            [f"nmu_x{x}y{y}" for x in range(4) for y in range(7, 13)],  # range(1, 2)],
            [f"nmu_x{x}y{y}" for x in range(4) for y in range(13, 19)],  # range(2, 3)],
            [f"nmu_x{x}y{y}" for x in range(4) for y in range(19, 25)],  # range(3, 4)]
        ]
    ]
    vp1802_nsu = [
        [
            [f"nsu_x{x}y{y}" for x in range(4) for y in range(0, 7)],
            [f"nsu_x{x}y{y}" for x in range(4) for y in range(7, 13)],
            [f"nsu_x{x}y{y}" for x in range(4) for y in range(13, 19)],
            [f"nsu_x{x}y{y}" for x in range(4) for y in range(19, 25)],
        ]
    ]
else:
    # slot 2x4
    vp1802_noc_resource = [
        [
            NocArea(nmu=14, nsu=14),
            NocArea(nmu=12, nsu=12),
            NocArea(nmu=12, nsu=12),
            NocArea(nmu=12, nsu=12),
        ],
        [
            NocArea(nmu=14, nsu=14),
            NocArea(nmu=12, nsu=12),
            NocArea(nmu=12, nsu=12),
            NocArea(nmu=12, nsu=12),
        ],
    ]
    vp1802_nmu = [
        [
            [f"nmu_x{x}y{y}" for x in range(2) for y in range(0, 7)],
            [f"nmu_x{x}y{y}" for x in range(2) for y in range(7, 13)],
            [f"nmu_x{x}y{y}" for x in range(2) for y in range(13, 19)],
            [f"nmu_x{x}y{y}" for x in range(2) for y in range(19, 25)],
        ],
        [
            [f"nmu_x{x}y{y}" for x in range(2, 4) for y in range(0, 7)],
            [f"nmu_x{x}y{y}" for x in range(2, 4) for y in range(7, 13)],
            [f"nmu_x{x}y{y}" for x in range(2, 4) for y in range(13, 19)],
            [f"nmu_x{x}y{y}" for x in range(2, 4) for y in range(19, 25)],
        ],
    ]
    vp1802_nsu = [
        [
            [f"nsu_x{x}y{y}" for x in range(2) for y in range(0, 7)],
            [f"nsu_x{x}y{y}" for x in range(2) for y in range(7, 13)],
            [f"nsu_x{x}y{y}" for x in range(2) for y in range(13, 19)],
            [f"nsu_x{x}y{y}" for x in range(2) for y in range(19, 25)],
        ],
        [
            [f"nsu_x{x}y{y}" for x in range(2, 4) for y in range(0, 7)],
            [f"nsu_x{x}y{y}" for x in range(2, 4) for y in range(7, 13)],
            [f"nsu_x{x}y{y}" for x in range(2, 4) for y in range(13, 19)],
            [f"nsu_x{x}y{y}" for x in range(2, 4) for y in range(19, 25)],
        ],
    ]


def extract_slot_coord(slot_name: str) -> tuple[int, int]:
    """Extracts the x and y coordinates from the slot name.

    Returns a coordinate tuple as (x, y) in int.

    Example:
    >>> extract_slot_coord("SLOT_X0Y1")
    (0, 1)
    """
    return int(slot_name[6]), int(slot_name[8])


def extract_slot_range(slot_range: str) -> list[tuple[int, int]]:
    """Extracts and expands slot range to a list of slot coordinates.

    Returns a list of slot coordinates, (x, y), in int.

    Example:
    >>> extract_slot_range("SLOT_X0Y1_TO_SLOT_X0Y1")
    [(0, 1)]
    >>> extract_slot_range("SLOT_X0Y1_TO_SLOT_X0Y3")
    [(0, 1), (0, 2), (0, 3)]
    """
    slot_range_parts = slot_range.split("_TO_")
    llx, lly = extract_slot_coord(slot_range_parts[0])
    urx, ury = extract_slot_coord(slot_range_parts[1])
    assert (
        llx <= urx
    ), f"The input slot range {slot_range} is assumed to be \
        from lower left to upper right"
    assert (
        lly <= ury
    ), f"The input slot range {slot_range} is assumed to be \
        from lower left to upper right"

    # iterate all the coordinates between (llx, lly) to (urx, ury)
    slots = []
    for x in range(llx, urx + 1):
        for y in range(lly, ury + 1):
            slots.append((x, y))
    return slots


def get_streams_noc_area(streams: dict[str, dict[str, Any]]) -> list[list[NocArea]]:
    """Calculates the NMU and NSU usage in each slot for the cross-slot streams.

    Returns a 2d array of NocArea for all slots.
    """
    nmu_usage = [[0 for y in range(SLOT_HEIGHT)] for x in range(SLOT_WIDTH)]
    nsu_usage = [[0 for y in range(SLOT_HEIGHT)] for x in range(SLOT_WIDTH)]
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

    slots_usage: list[list[NocArea]] = []
    for x in range(SLOT_WIDTH):
        slots_usage.append([])
        for y in range(SLOT_HEIGHT):
            slots_usage[x].append(NocArea(nmu=nmu_usage[x][y], nsu=nsu_usage[x][y]))
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
        # Graph contains a cycle or is invalid
        return


def random_selector(streams_slots: dict[str, dict[str, int | list[str]]]) -> list[str]:
    """Randomly selects a subset of the streams to use NoC.

    Repeatedly generates (smaller) subsets of streams until the subset
    satisfies the number of available NMU and NSU nodes in the NoC.

    Returns a list of selected streams to use NoC.
    """
    num_to_select = len(streams_slots)
    while True:
        num_to_select = random.randint(1, num_to_select)
        random_streams = random.sample(sorted(streams_slots), num_to_select)
        random_streams = sorted(
            random_streams, key=lambda x: int(x.split("_")[2] + x.split("_")[3])
        )
        slots_usage = get_streams_noc_area(
            {s: streams_slots.get(s, {}) for s in random_streams}
        )
        print(f"try {num_to_select} streams.")
        print(slots_usage)
        overflow = False
        for x in range(SLOT_WIDTH):
            for y in range(SLOT_HEIGHT):
                if (
                    slots_usage[x][y].nmu > vp1802_noc_resource[x][y].nmu
                    or slots_usage[x][y].nsu > vp1802_noc_resource[x][y].nsu
                ):
                    overflow = True
                    break

        if overflow:
            num_to_select -= 1
        else:
            print("random selector success")
            return random_streams


def get_slot_nodes(slot_range: str, slot_resources: list[list[list[str]]]) -> list[str]:
    """Convert each slotname in the streams dict to a list of NMU and NSU nodes.

    Returns a new dictionary with 'src' and 'dest' list of nodes for each stream.

    Example:
    >>> slot_nmu = [[["nmu_x0y0"], ["nmu_x0y1"]]]
    >>> slot_nsu = [[["nsu_x0y0", "nsu_x0y1"], ["nsu_x0y2"]]]
    >>> streams = {
    ...     "a": {
    ...         "bandwidth": 16000,
    ...         "src": "SLOT_X0Y1_TO_SLOT_X0Y1",
    ...         "dest": "SLOT_X0Y0_TO_SLOT_X0Y0",
    ...     }
    ... }
    >>> get_slot_nodes("SLOT_X0Y1_TO_SLOT_X0Y1", slot_nmu)
    ['nmu_x0y1']
    >>> get_slot_nodes("SLOT_X0Y0_TO_SLOT_X0Y0", slot_nsu)
    ['nsu_x0y0', 'nsu_x0y1']
    """
    nodes = []
    for x, y in extract_slot_range(slot_range):
        assert x < len(slot_resources)
        assert y < len(slot_resources[x])
        nodes += slot_resources[x][y]
    return nodes


def get_nx_graph_from_noc_graph(noc_graph: NocGraph) -> nx.DiGraph:
    """Converts NocGraph to NetworkX graph without the edge attributes.

    Returns a NetworkX directed graph.
    """
    noc_nx_graph = nx.DiGraph()
    noc_nx_graph.add_nodes_from(noc_graph.get_all_nodes())
    noc_nx_graph.add_edges_from(noc_graph.get_all_edges())
    return noc_nx_graph


def find_nx_shortest_path(graph: NocGraph, src: str, dest: str) -> None:
    """Finds and prints the shortest path from src to dest using NetworkX."""
    nx_graph = get_nx_graph_from_noc_graph(graph)
    path = nx.shortest_path(nx_graph, source=src, target=dest)
    print("networkx shortest path:")
    print((" -> ".join(path)))


def print_noc_loc_tcl(node_loc: dict[str, tuple[str, str]]) -> None:
    """Prints the NMU and NSU location constraints in tcl."""
    tcl = []
    for port_num, (nmu_loc, nsu_loc) in enumerate(node_loc.values()):
        nmu_x, nmu_y = nmu_loc.split("x")[1].split("y")
        nsu_x, nsu_y = nsu_loc.split("x")[1].split("y")
        tcl += [
            f"set_property -dict [list CONFIG.PHYSICAL_LOC "
            f"{{NOC_NMU512_X{nmu_x}Y{nmu_y}}}] "
            f"[get_bd_intf_pins /axis_noc_dut/S{str(port_num).zfill(2)}"
            "_AXIS]"
        ]
        tcl += [
            f"set_property -dict [list CONFIG.PHYSICAL_LOC "
            f"{{NOC_NSU512_X{nsu_x}Y{nsu_y}}}] "
            f"[get_bd_intf_pins /axis_noc_dut/M{str(port_num).zfill(2)}"
            "_AXIS]"
        ]
    print("\n".join(tcl))


def ilp_noc_selector_add_var(
    streams_nodes: dict[str, dict[str, list[str]]], noc_graph: NocGraph
) -> dict[str, dict[str, LpVariable | dict[str | tuple[str, str], LpVariable]]]:
    """Adds ilp_var for the NoC selector ILP.

    Returns a dictionary containing LpVariable.
    """
    ilp_var = {}

    edges = noc_graph.get_all_edges()

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
    streams_bw: dict[str, int],
    noc_graph: NocGraph,
) -> None:
    """Adds constraints for the NoC selector ILP."""

    # create networkx graph for its helper functions
    noc_nx_graph = get_nx_graph_from_noc_graph(noc_graph)

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
    for node in noc_graph.get_all_nmu_nodes():
        m += (
            lpSum(
                ilp_var[stream_name]["y"][node]
                for stream_name, end_nodes in streams_nodes.items()
                if node in end_nodes["src"]
            )
            <= 1
        )

    for node in noc_graph.get_all_nsu_nodes():
        m += (
            lpSum(
                ilp_var[stream_name]["z"][node]
                for stream_name, end_nodes in streams_nodes.items()
                if node in end_nodes["dest"]
            )
            <= 1
        )

    # 5. Bandwidth constraints
    for e in noc_graph.edges:
        e_tuple = (e.src.name, e.dest.name)
        m += (
            lpSum(
                bw * ilp_var[stream_name]["x"][e_tuple]
                for stream_name, bw in streams_bw.items()
            )
            <= e.bandwidth
        )


def ilp_noc_selector_add_obj(
    m: LpProblem,
    ilp_var: dict[str, dict[str, LpVariable]],
    streams_nodes: dict[str, dict[str, list[str]]],
    streams_bw: dict[str, int],
    noc_graph: NocGraph,
) -> None:
    """Adds objectives for the NoC selector ILP."""
    total_path_length = lpSum(
        ilp_var[stream_name]["x"][e]
        for stream_name, _ in streams_nodes.items()
        for e in noc_graph.get_all_edges()
    )
    total_not_mapped_bandwidth = lpSum(
        bw * ilp_var[stream_name]["not_mapped_stream"]
        for stream_name, bw in streams_bw.items()
    )
    m += total_path_length + total_not_mapped_bandwidth


def post_process_noc_ilp(
    ilp_var: dict[str, dict[str, LpVariable | dict[Any, LpVariable]]],
    streams_nodes: dict[str, dict[str, list[str]]],
    noc_graph: NocGraph,
) -> list[str]:
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
            print("optimizer shortest path:")
            print_ordered_edges(selected_edges)

            # prints the NetworkX shortest path as comparison
            find_nx_shortest_path(noc_graph, selected_src, selected_dest)
            print()

    # prints the tcl constraints for the selected NMU and NSU nodes
    print_noc_loc_tcl(node_loc)

    print(f"mip has selected {len(noc_streams)} streams")
    return noc_streams


def ilp_noc_selector(
    streams_slots: dict[str, dict[str, str]],
    streams_bw: dict[str, int],
    noc_graph: NocGraph,
) -> list[str]:
    """Selects a subset of the streams to use NoC using ILP.

    Minimizes the total bandwidth not using NoC and the total path length.

    Args:
        streams_slots:  dictionary of the cross-slot stream's
                        "src" and "dest" slot ranges
        streams_bw:     dictionary of the cross-slot stream's bandwidth target
        noc_graph:      graph representing the NoC topology.

    Returns a list of selected streams to use NoC.
    """
    m = LpProblem("noc", LpMinimize)

    streams_nodes: dict[str, dict[str, list[str]]] = {}
    # expands each slot range to a list of node names
    for stream_name, slots in streams_slots.items():
        streams_nodes[stream_name] = {
            "src": get_slot_nodes(slots["src"], vp1802_nmu),
            "dest": get_slot_nodes(slots["dest"], vp1802_nsu),
        }

    # decision ilp_var
    ilp_var = ilp_noc_selector_add_var(streams_nodes, noc_graph)

    # Constraints
    ilp_noc_selector_add_constr(m, ilp_var, streams_nodes, streams_bw, noc_graph)

    # Objective function
    # mypy bug: sees LpVariable as Any
    # fix: declare a new function and trick mypy to see ilp_var's values as LpVariable
    ilp_noc_selector_add_obj(m, ilp_var, streams_nodes, streams_bw, noc_graph)

    m.solve(GUROBI_CMD(options=[("TimeLimit", 300)]))

    # Post-solve operations
    return post_process_noc_ilp(ilp_var, streams_nodes, noc_graph)
