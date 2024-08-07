"""Generates NoC graphs for VH1582."""

__copyright__ = """
Copyright (c) 2024 RapidStream Design Automation, Inc. and contributors.
All rights reserved. The contributor(s) of this file has/have agreed to the
RapidStream Contributor License Agreement.
"""


from typing import Any

from noc_graph import Edge, NocGraph, Node


def vh1582_nodes(
    num_slr: int, num_col: int, rows_per_slr: list[int]
) -> dict[str, list[Any]]:
    """Creates all vh1582 NoC's nodes.

    Returns a dictionary of all node types in the NocGraph.
    """

    def create_nodes(node_type: str, x: int, y_range: int) -> list[Node]:
        return [Node(name=f"{node_type}_x{x}y{y}") for y in range(y_range)]

    num_row = sum(rows_per_slr)
    # each slr has two top and two bottom rows
    # except for bot slr which only has two top rows
    # except for top slr in hbm boards
    num_inter_rows = num_slr * 2 * 2 - 2 - 2

    all_nodes: dict[str, list[Any]] = {
        "nmu_nodes": [],
        "nsu_nodes": [],
        "nps_vnoc_nodes": [],
        "nps_hnoc_nodes": [],
        "nps_slr0_nodes": [],
        "ncrb_nodes": [],
        "nps_hbm_nodes": [],
        "ncrb_hbm_nodes": [],
        "hbm_mc_nodes": [],
        "nmu_hbm_nodes": [],
        "nps4_hbm_mc_nodes": [],
        "nps6_hbm_mc_nodes": [],
    }

    for x in range(num_col):
        # create nmu and nsu nodes
        all_nodes["nmu_nodes"].append(create_nodes("nmu", x, num_row))
        all_nodes["nsu_nodes"].append(create_nodes("nsu", x, num_row))
        # create nps vnoc nodes
        all_nodes["nps_vnoc_nodes"].append(create_nodes("nps_vnoc", x, num_row * 2))
        # create nps hnoc nodes
        all_nodes["nps_hnoc_nodes"].append(create_nodes("nps_hnoc", x, num_inter_rows))
        # create nps HBM nodes
        all_nodes["nps_hbm_nodes"].append(create_nodes("nps_hbm", x, 4))
        # create ncrb HBM nodes
        all_nodes["ncrb_hbm_nodes"].append(create_nodes("ncrb_hbm", x, 2))
        # create bottom SLR0 nps nodes
        all_nodes["nps_slr0_nodes"].append(create_nodes("nps_slr0", x, 4))

    # create ncrb nodes for connecting interconnect rows within each slr
    # NoC Clock Re-convergent Buffer (NCRB)
    for x in range(num_col - 1):
        all_nodes["ncrb_nodes"].append(create_nodes("ncrb", x, num_inter_rows))

    # create HBM Memory Controller (MC) nodes
    for x in range(16):
        all_nodes["hbm_mc_nodes"].append(
            [
                [Node(name=f"hbm_mc_x{x}y0_pc{pc}_port{p}") for p in range(2)]
                for pc in range(2)
            ]
        )
        # each MC has two Port Controllers (PC). Each PC supports two ports
        for xx in range(4):
            all_nodes["nmu_hbm_nodes"].append(Node(name=f"nmu_hbm_x{x*4+xx}y0"))
        all_nodes["nps4_hbm_mc_nodes"].append(Node(name=f"nps4_hbm_mc_x{x}y0"))

    for x in range(8):
        all_nodes["nps6_hbm_mc_nodes"].append(create_nodes("nps6_hbm_mc", x, 4))

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


def create_nps_hnoc_edges(
    G: NocGraph, num_slr: int, num_col: int, rows_per_slr: list[int]
) -> list[Edge]:
    """Creates edges for horizontal and vertical nps nodes.

    Returns a list of edges.
    """
    edges = []

    y = rows_per_slr[0]
    for slr in range(num_slr - 1):
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
        y += rows_per_slr[slr + 1]

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

    for y in range(num_slr * 2 - 2):
        for x in range(num_col - 1):
            # west direction
            edges += [
                Edge(
                    src=G.ncrb_nodes[x][y * 2],
                    dest=G.nps_hnoc_nodes[x][y * 2],
                    bandwidth=16000,
                ),
                Edge(
                    src=G.ncrb_nodes[x][y * 2],
                    dest=G.nps_hnoc_nodes[x][y * 2 + 1],
                    bandwidth=16000,
                ),
                Edge(
                    src=G.nps_hnoc_nodes[x + 1][y * 2],
                    dest=G.ncrb_nodes[x][y * 2],
                    bandwidth=16000,
                ),
                Edge(
                    src=G.nps_hnoc_nodes[x + 1][y * 2 + 1],
                    dest=G.ncrb_nodes[x][y * 2],
                    bandwidth=16000,
                ),
            ]
            # print(f"ncrb_x{x}y{y*2} -> nps_x{x}y{y*2}")
            # print(f"ncrb_x{x}y{y*2} -> nps_x{x}y{y*2+1}")
            # print(f"nps_x{x+1}y{y*2} -> ncrb_x{x}y{y*2}")
            # print(f"nps_x{x+1}y{y*2+1} -> ncrb_x{x}y{y*2}")

            # east direction
            edges += [
                Edge(
                    src=G.nps_hnoc_nodes[x][y * 2],
                    dest=G.ncrb_nodes[x][y * 2 + 1],
                    bandwidth=16000,
                ),
                Edge(
                    src=G.nps_hnoc_nodes[x][y * 2 + 1],
                    dest=G.ncrb_nodes[x][y * 2 + 1],
                    bandwidth=16000,
                ),
                Edge(
                    src=G.ncrb_nodes[x][y * 2 + 1],
                    dest=G.nps_hnoc_nodes[x + 1][y * 2],
                    bandwidth=16000,
                ),
                Edge(
                    src=G.ncrb_nodes[x][y * 2 + 1],
                    dest=G.nps_hnoc_nodes[x + 1][y * 2 + 1],
                    bandwidth=16000,
                ),
            ]
            # print(f"nps_x{x}y{y*2} -> ncrb_x{x}y{y*2+1}")
            # print(f"nps_x{x}y{y*2+1} -> ncrb_x{x}y{y*2+1}")
            # print(f"ncrb_x{x}y{y*2+1} -> nps_x{x+1}y{y*2}")
            # print(f"ncrb_x{x}y{y*2+1} -> nps_x{x+1}y{y*2+1}")

    return edges


def create_nps_hbm_edges(G: NocGraph, num_col: int, num_row: int) -> list[Edge]:
    """Creates edges for nps_hbm_nodes and ncrb_hbm_nodes.

    Returns a list of edges.
    """
    edges = []

    for x in range(num_col):
        for r in range(2):
            edges += [
                # connect top vnoc nodes to HBM NCRB nodes
                Edge(
                    src=G.ncrb_hbm_nodes[x][0],
                    dest=G.nps_vnoc_nodes[x][num_row * 2 - 2 + r],
                    bandwidth=16000,
                ),
                Edge(
                    src=G.nps_vnoc_nodes[x][num_row * 2 - 2 + r],
                    dest=G.ncrb_hbm_nodes[x][1],
                    bandwidth=16000,
                ),
                # connect HBM NPS nodes to HBM NCRB nodes
                Edge(
                    src=G.nps_hbm_nodes[x][r],
                    dest=G.ncrb_hbm_nodes[x][0],
                    bandwidth=16000,
                ),
                Edge(
                    src=G.ncrb_hbm_nodes[x][1],
                    dest=G.nps_hbm_nodes[x][r],
                    bandwidth=16000,
                ),
            ]
            # print(f"ncrb_hbm_x{x}y{0} -> nps_vnoc_x{x}y{num_row * 2 - 2 + r}")
            # print(f"nps_vnoc_x{x}y{num_row * 2 - 2 + r} -> ncrb_hbm_x{x}y{1}")
            # print(f"nps_hbm_x{x}y{r} -> ncrb_hbm_x{x}y{0}")
            # print(f"ncrb_hbm_x{x}y{1} -> nps_hbm_x{x}y{r}")

    # connect HBM nps nodes vertically
    for x in range(num_col):
        # row 0 <-> row 2
        # row 1 <-> row 3
        for row in range(2):
            edges += create_bidir_edges(
                G.nps_hbm_nodes[x][row + 2],
                G.nps_hbm_nodes[x][row],
                bandwidth=16000,
            )
        # row 2 <-> row 3
        edges += create_bidir_edges(
            G.nps_hbm_nodes[x][2],
            G.nps_hbm_nodes[x][3],
            bandwidth=16000,
        )

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
                G.nps_slr0_nodes[x][row + 2],
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


def create_hbm_mc_edges(G: NocGraph, num_col: int) -> list[Edge]:
    """Creates edges for hbm_mc_nodes.

    Returns a list of edges.
    """
    edges = []

    # HBM MC nodes <-> HBM MC nps4 nodes
    for x in range(8):
        for pc in range(2):
            for p in range(2):
                # pc0/pc1 port0 <-> left nps4
                edges += create_bidir_edges(
                    G.hbm_mc_nodes[x * 2][pc][p],
                    G.nps4_hbm_mc_nodes[x * 2 + p],
                    bandwidth=16000,
                )
                # pc0/pc1 port1 <-> right nps4
                edges += create_bidir_edges(
                    G.hbm_mc_nodes[x * 2 + 1][pc][p],
                    G.nps4_hbm_mc_nodes[x * 2 + p],
                    bandwidth=16000,
                )
                # print(G.hbm_mc_nodes[x*2][pc][p].name, G.nps4_hbm_mc_nodes[x*2+p].name)
                # print(G.hbm_mc_nodes[x*2+1][pc][p].name, G.nps4_hbm_mc_nodes[x*2+p].name)

    # NMU HBM nodes <-> HBM MC nps6 nodes
    for x in range(8):
        # NMU x0/1 <-> nps6 y0
        # NMU x2/3 <-> nps6 y1
        # NMU x4/5 <-> nps6 y2
        # NMU x6/7 <-> nps6 y3
        for y in range(4):
            for xx in range(2):
                edges += create_bidir_edges(
                    G.nmu_hbm_nodes[x * 8 + y * 2 + xx],
                    G.nps6_hbm_mc_nodes[x][y],
                    bandwidth=16000,
                )
                # print(G.nmu_hbm_nodes[x*8+y*2+xx].name, G.nps6_hbm_mc_nodes[x][y].name)

    # HBM MC nps6 nodes <-> HBM MC nps4 nodes
    for x in range(8):
        # each nps6 has connections to two nps4
        for y in range(4):
            for xx in range(2):
                edges += create_bidir_edges(
                    G.nps6_hbm_mc_nodes[x][y],
                    G.nps4_hbm_mc_nodes[x * 2 + xx],
                    bandwidth=16000,
                )
                # print(G.nps6_hbm_mc_nodes[x][y].name, G.nps4_hbm_mc_nodes[x*2+xx].name)

    # connect each row of HBM nps nodes and HBM MC nps6 nodes horizontally
    # first column of HBM MC nps6 nodes <-> first column of HBM nps nodes
    # last column of HBM nps nodes <-> last column of HBM MC nps6 nodes
    for row in range(4):
        edges += create_bidir_edges(
            G.nps6_hbm_mc_nodes[0][row],
            G.nps_hbm_nodes[0][row],
            bandwidth=16000,
        )
        edges += create_bidir_edges(
            G.nps_hbm_nodes[3][row],
            G.nps6_hbm_mc_nodes[7][row],
            bandwidth=16000,
        )

    # HBM nps nodes <-> two HBM MC nps6 nodes <-> next HBM nps nodes
    for x in range(num_col - 1):
        for row in range(4):
            # starting from HBM MC nps6 x = 1
            edges += create_bidir_edges(
                G.nps_hbm_nodes[x][row],
                G.nps6_hbm_mc_nodes[x * 2 + 1][row],
                bandwidth=16000,
            )
            edges += create_bidir_edges(
                G.nps6_hbm_mc_nodes[x * 2 + 1][row],
                G.nps6_hbm_mc_nodes[x * 2 + 2][row],
                bandwidth=16000,
            )
            edges += create_bidir_edges(
                G.nps6_hbm_mc_nodes[x * 2 + 2][row],
                G.nps_hbm_nodes[x + 1][row],
                bandwidth=16000,
            )

    return edges


def vh1582_edges(
    G: NocGraph, num_slr: int, num_col: int, rows_per_slr: list[int]
) -> list[Edge]:
    """Creates all vh1582 NoC's edges.

    Returns a list of all edges.
    """
    sum(rows_per_slr)

    edges = []
    edges += create_nmu_nsu_edges(G, num_col, rows_per_slr)
    edges += create_nps_hnoc_edges(G, num_slr, num_col, rows_per_slr)
    edges += create_ncrb_edges(G, num_slr, num_col)
    edges += create_nps_hbm_edges(G, num_col, sum(rows_per_slr))
    edges += create_nps_slr0_edges(G, num_col)
    edges += create_hbm_mc_edges(G, num_col)
    return edges


def vh1582_nocgraph() -> NocGraph:
    """Generates vh1582's NoC graph.

    Example:
    >>> import networkx as nx
    >>> G = vh1582_nocgraph()
    >>> nx_g = nx.DiGraph()
    >>> nx_g.add_nodes_from(G.get_all_nodes())
    >>> nx_g.add_edges_from(G.get_all_edges())
    >>> nx.shortest_path(nx_g, source="nmu_x0y0", target="nsu_x0y0")
    ['nmu_x0y0', 'nps_vnoc_x0y1', 'nps_vnoc_x0y0', 'nsu_x0y0']
    >>> nx.shortest_path(nx_g, source="nmu_x0y0", target="nsu_x1y0")
    ['nmu_x0y0', 'nps_vnoc_x0y1', 'nps_slr0_x0y1', 'nps_slr0_x1y1', 'nps_vnoc_x1y1', \
        'nps_vnoc_x1y0', 'nsu_x1y0']
    """

    num_slr = 2
    num_col = 4
    rows_per_slr = [7, 6]
    nodes = vh1582_nodes(num_slr, num_col, rows_per_slr)

    # Create a directed graph
    G = NocGraph(
        num_slr=num_slr,
        num_col=num_col,
        rows_per_slr=rows_per_slr,
        nmu_nodes=nodes["nmu_nodes"],
        nsu_nodes=nodes["nsu_nodes"],
        nps_vnoc_nodes=nodes["nps_vnoc_nodes"],
        nps_hnoc_nodes=nodes["nps_hnoc_nodes"],
        nps_slr0_nodes=nodes["nps_slr0_nodes"],
        ncrb_nodes=nodes["ncrb_nodes"],
        nps_hbm_nodes=nodes["nps_hbm_nodes"],
        ncrb_hbm_nodes=nodes["ncrb_hbm_nodes"],
        hbm_mc_nodes=nodes["hbm_mc_nodes"],
        nmu_hbm_nodes=nodes["nmu_hbm_nodes"],
        nps4_hbm_mc_nodes=nodes["nps4_hbm_mc_nodes"],
        nps6_hbm_mc_nodes=nodes["nps6_hbm_mc_nodes"],
        edges=[],
    )

    edges = vh1582_edges(G, num_slr, num_col, rows_per_slr)
    G.add_edges(edges)

    return G


if __name__ == "__main__":
    import networkx as nx
    from networkx.drawing.nx_pydot import write_dot

    noc_graph = vh1582_nocgraph()
    nx_g = nx.DiGraph()
    nx_g.add_nodes_from(noc_graph.get_all_nodes())
    nx_g.add_edges_from(noc_graph.get_all_edges())
    write_dot(nx_g, "test/vh1582.dot")
