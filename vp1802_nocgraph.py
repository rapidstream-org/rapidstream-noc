"""Generates NoC graphs for FPGA devices."""

__copyright__ = """
Copyright (c) 2024 RapidStream Design Automation, Inc. and contributors.
All rights reserved. The contributor(s) of this file has/have agreed to the
RapidStream Contributor License Agreement.
"""


from typing import Any

from noc_graph import Edge, NocGraph, Node


def vp1802_nodes(
    num_slr: int, num_col: int, rows_per_slr: list[int]
) -> dict[str, list[Any]]:
    """Creates all vp1802 NoC's nodes.

    Returns a dictionary of all node types in the NocGraph.
    """
    num_row = sum(rows_per_slr)
    # each slr has two top and two bottom rows
    # except for slr0 which only has two top rows
    num_inter_rows = num_slr * 2 * 2 - 2

    all_nodes: dict[str, list[Any]] = {
        "nmu_nodes": [],
        "nsu_nodes": [],
        "nps_vnoc_nodes": [],
        "nps_hnoc_nodes": [],
        "nps_slr0_nodes": [],
        "ncrb_nodes": [],
    }

    # create nmu and nsu nodes
    for x in range(num_col):
        nmu_nodes_col = []
        nsu_nodes_col = []
        for y in range(num_row):
            nmu_nodes_col.append(Node(name=f"nmu_x{x}y{y}"))
            nsu_nodes_col.append(Node(name=f"nsu_x{x}y{y}"))
        all_nodes["nmu_nodes"].append(nmu_nodes_col)
        all_nodes["nsu_nodes"].append(nsu_nodes_col)

        # create nps_vnoc nodes
        col = []
        for y in range(num_row * 2):
            col.append(Node(name=f"nps_vnoc_x{x}y{y}"))
        all_nodes["nps_vnoc_nodes"].append(col)

        # create interconnect nps nodes
        col = []
        for y in range(num_inter_rows):
            col.append(Node(name=f"nps_hnoc_x{x}y{y}"))
        all_nodes["nps_hnoc_nodes"].append(col)

        # create bottom SLR0 nps nodes
        col = []
        for y in range(4):
            col.append(Node(name=f"nps_slr0_x{x}y{y}"))
        all_nodes["nps_slr0_nodes"].append(col)

    # create ncrb nodes for connecting interconnect rows within each slr
    # NoC Clock Re-convergent Buffer (NCRB)
    for x in range(num_col - 1):
        col = []
        for y in range(num_inter_rows):
            col.append(Node(name=f"ncrb_x{x}y{y}"))
        all_nodes["ncrb_nodes"].append(col)

    return all_nodes


def create_bidir_edges(n1: Node, n2: Node, **kwargs: int) -> list[Edge]:
    """Creates a bidirectional edge between nodes n1 and n2 with attributes.

    Returns a list of two edges.
    """
    return [
        Edge(src=n1, dest=n2, **kwargs),
        Edge(src=n2, dest=n1, **kwargs),
    ]


def create_nmu_nsu_edges(
    G: NocGraph, num_col: int, rows_per_slr: list[int]
) -> list[Edge]:
    """Creates edges between nmu, nsu, and nps_vnoc within the subgroup.

    Returns a list of edges.
    """
    num_row = sum(rows_per_slr)

    edges = []

    # create nmu <-> nps_vnoc <-> nps_vnoc <-> nsu edges
    y_at_slr_boundary = [
        sum(rows_per_slr[: i + 1]) - 1 for i in range(len(rows_per_slr))
    ]
    y = 0
    for x in range(num_col):
        for y in range(num_row):
            # nmu <-> nps_vnoc
            edges += create_bidir_edges(
                G.nmu_nodes[x][y], G.nps_vnoc_nodes[x][y * 2 + 1], bandwidth=16000
            )

            # nsu <-> nps_vnoc
            edges += create_bidir_edges(
                G.nsu_nodes[x][y], G.nps_vnoc_nodes[x][y * 2], bandwidth=16000
            )

            # horizontal nps_vnoc <-> nps_vnoc
            edges += create_bidir_edges(
                G.nps_vnoc_nodes[x][y * 2],
                G.nps_vnoc_nodes[x][y * 2 + 1],
                bandwidth=16000,
            )

            # vertical nps_vnoc <-> nps_vnoc
            if y not in y_at_slr_boundary:
                edges += create_bidir_edges(
                    G.nps_vnoc_nodes[x][y * 2],
                    G.nps_vnoc_nodes[x][(y + 1) * 2],
                    bandwidth=16000,
                )

                edges += create_bidir_edges(
                    G.nps_vnoc_nodes[x][y * 2 + 1],
                    G.nps_vnoc_nodes[x][(y + 1) * 2 + 1],
                    bandwidth=16000,
                )
    return edges


def create_nps_hnoc_edges(G: NocGraph, num_slr: int, num_col: int) -> list[Edge]:
    """Creates edges for horizontal and vertical nps nodes.

    Returns a list of edges.
    """
    edges = []

    y = 7
    for slr in range(num_slr):
        for r in range(2):
            for x in range(num_col):
                # connect top interconnect nps nodes to vnoc nps nodes
                edges += create_bidir_edges(
                    G.nps_hnoc_nodes[x][slr * 4 + (1 - r)],
                    G.nps_vnoc_nodes[x][y * 2 - 2 + r],
                    bandwidth=16000,
                )
                # print(f"connecting nps_x{x}y{slr*4+r} <-> nps_vnoc_x{x}y{y*2-2+r}")

                # connect lower interconnect nps nodes to vnoc nps nodes
                if slr < num_slr - 1:
                    edges += create_bidir_edges(
                        G.nps_hnoc_nodes[x][slr * 4 + 2 + (1 - r)],
                        G.nps_vnoc_nodes[x][y * 2 + r],
                        bandwidth=16000,
                    )
                    # print(f"connecting nps_x{x}y{slr*4+2+r} <-> nps_vnoc_x{x}y{y*2+r}")
        y += 6

    # cross-slr edges
    # abstracted away the NoC Inter-Die Bridge (NIDB) nodes
    for slr in range(num_slr - 1):
        for r in range(2):
            for x in range(num_col):
                edges += create_bidir_edges(
                    G.nps_hnoc_nodes[x][slr * 4 + r],
                    G.nps_hnoc_nodes[x][slr * 4 + r + 2],
                    bandwidth=16000,
                )
                # print(f"nps_x{x}y{slr*4+r} <-> nps_x{x}y{slr*4+r+2}")

    return edges


def create_ncrb_edges(G: NocGraph, num_slr: int, num_col: int) -> list[Edge]:
    """Creates edges for ncrb nodes.

    Returns a list of edges.
    """
    edges = []

    for y in range(num_slr * 2 - 1):
        for x in range(num_col - 1):
            # west direction
            edges.append(
                Edge(
                    src=G.ncrb_nodes[x][y * 2],
                    dest=G.nps_hnoc_nodes[x][y * 2],
                    bandwidth=16000,  # 11500,
                )
            )
            edges.append(
                Edge(
                    src=G.ncrb_nodes[x][y * 2],
                    dest=G.nps_hnoc_nodes[x][y * 2 + 1],
                    bandwidth=16000,  # 11500,
                )
            )
            edges.append(
                Edge(
                    src=G.nps_hnoc_nodes[x + 1][y * 2],
                    dest=G.ncrb_nodes[x][y * 2],
                    bandwidth=16000,  # 11500,
                )
            )
            edges.append(
                Edge(
                    src=G.nps_hnoc_nodes[x + 1][y * 2 + 1],
                    dest=G.ncrb_nodes[x][y * 2],
                    bandwidth=16000,  # 11500,
                )
            )
            # print(f"ncrb_x{x}y{y*2} -> nps_x{x}y{y*2}")
            # print(f"ncrb_x{x}y{y*2} -> nps_x{x}y{y*2+1}")
            # print(f"nps_x{x+1}y{y*2} -> ncrb_x{x}y{y*2}")
            # print(f"nps_x{x+1}y{y*2+1} -> ncrb_x{x}y{y*2}")

            # east direction
            edges.append(
                Edge(
                    src=G.nps_hnoc_nodes[x][y * 2],
                    dest=G.ncrb_nodes[x][y * 2 + 1],
                    bandwidth=16000,  # 11500,
                )
            )
            edges.append(
                Edge(
                    src=G.nps_hnoc_nodes[x][y * 2 + 1],
                    dest=G.ncrb_nodes[x][y * 2 + 1],
                    bandwidth=16000,  # 11500,
                )
            )
            edges.append(
                Edge(
                    src=G.ncrb_nodes[x][y * 2 + 1],
                    dest=G.nps_hnoc_nodes[x + 1][y * 2],
                    bandwidth=16000,  # 11500,
                )
            )
            edges.append(
                Edge(
                    src=G.ncrb_nodes[x][y * 2 + 1],
                    dest=G.nps_hnoc_nodes[x + 1][y * 2 + 1],
                    bandwidth=16000,  # 11500,
                )
            )
            # print(f"nps_x{x}y{y*2} -> ncrb_x{x}y{y*2+1}")
            # print(f"nps_x{x}y{y*2+1} -> ncrb_x{x}y{y*2+1}")
            # print(f"ncrb_x{x}y{y*2+1} -> nps_x{x+1}y{y*2}")
            # print(f"ncrb_x{x}y{y*2+1} -> nps_x{x+1}y{y*2+1}")

    return edges


def create_nps_slr0_edges(G: NocGraph, num_col: int) -> list[Edge]:
    """Creates edges for nps_slr0_nodes.

    Returns a list of edges.
    """
    edges = []

    # slr0's nps_vnoc <-> nps_slr0
    for x in range(num_col):
        for y in range(2):
            edges += create_bidir_edges(
                G.nps_slr0_nodes[x][y], G.nps_vnoc_nodes[x][y], bandwidth=16000
            )
        # print(f"nps_slr0_x{x}y{y}", f"nps_vnoc_x{x}y{y}")

    # connect slr0 nps nodes vertically
    for x in range(num_col):
        # row 0 <-> row 2
        # row 1 <-> row 3
        for row in range(2):
            edges += create_bidir_edges(
                G.nps_slr0_nodes[x][row * 2 + row],
                G.nps_slr0_nodes[x][row],
                bandwidth=16000,
            )

    # connect each row of slr0 nps nodes horizontally
    for x in range(num_col - 1):
        for row in range(4):
            edges += create_bidir_edges(
                G.nps_slr0_nodes[x][row],
                G.nps_slr0_nodes[x + 1][row],
                bandwidth=16000,
            )
    return edges


def vp1802_edges(
    G: NocGraph, num_slr: int, num_col: int, rows_per_slr: list[int]
) -> list[Edge]:
    """Creates all vp1802 NoC's edges.

    Returns a list of all edges.
    """
    sum(rows_per_slr)

    edges = []
    edges += create_nmu_nsu_edges(G, num_col, rows_per_slr)
    edges += create_nps_hnoc_edges(G, num_slr, num_col)
    edges += create_ncrb_edges(G, num_slr, num_col)
    edges += create_nps_slr0_edges(G, num_col)
    return edges


def vp1802_nocgraph() -> NocGraph:
    """Generates VP1802's NoC graph.

    Example:
    >>> import networkx as nx
    >>> G = vp1802_nocgraph()
    >>> nx_g = nx.DiGraph()
    >>> nx_g.add_nodes_from(G.get_all_nodes())
    >>> nx_g.add_edges_from(G.get_all_edges())
    >>> nx.shortest_path(nx_g, source="nmu_x0y0", target="nsu_x0y0")
    ['nmu_x0y0', 'nps_vnoc_x0y1', 'nps_vnoc_x0y0', 'nsu_x0y0']
    >>> nx.shortest_path(nx_g, source="nmu_x0y0", target="nsu_x1y0")
    ['nmu_x0y0', 'nps_vnoc_x0y1', 'nps_slr0_x0y1', 'nps_slr0_x1y1', 'nps_vnoc_x1y1', \
        'nps_vnoc_x1y0', 'nsu_x1y0']
    """

    num_slr = 4
    num_col = 4
    rows_per_slr = [7, 6, 6, 6]
    nodes = vp1802_nodes(num_slr, num_col, rows_per_slr)

    # Create a directed graph
    G = NocGraph(
        num_slr=num_slr,
        num_col=num_col,
        rows_per_slr=rows_per_slr,
        nmu_nodes=nodes["nmu_nodes"],
        nsu_nodes=nodes["nsu_nodes"],
        nps_vnoc_nodes=nodes["nps_vnoc_nodes"],
        nps_hnoc_nodes=nodes["nps_hnoc_nodes"],
        nps_hbm_nodes=[],
        ncrb_hbm_nodes=[],
        nps_slr0_nodes=nodes["nps_slr0_nodes"],
        ncrb_nodes=nodes["ncrb_nodes"],
        edges=[],
    )

    edges = vp1802_edges(G, num_slr, num_col, rows_per_slr)
    G.add_edges(edges)

    return G
