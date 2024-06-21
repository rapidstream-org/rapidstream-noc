"""The NoC graph class."""

__copyright__ = """
Copyright (c) 2024 RapidStream Design Automation, Inc. and contributors.
All rights reserved. The contributor(s) of this file has/have agreed to the
RapidStream Contributor License Agreement.
"""

from typing import Any

from pydantic import BaseModel


class Node(BaseModel):
    """Represents a node in the NoC graph."""

    name: str


class Edge(BaseModel):
    """Represents an edge in the NoC graph."""

    src: Node
    dest: Node
    bandwidth: float


class NocGraph(BaseModel):
    """Represents a NoC graph.

    num_slr: number of slr
    num_col: number of vertical NoC
    rows_per_slr: number of NMU <-> NSU rows per SLR
    nmu_nodes: 2d array of all NMU nodes. Indexing follows Vivado.
    nsu_nodes: 2d array of all NSU nodes. Indexing follows Vivado.
    nps_vnoc_nodes: 2d array of all NPS nodes connected to NMUs and NSUs.
                    Indexing follows Vivado.
    nps_hnoc_nodes: 2d array of all interconnect NPS nodes bridging SLRs.
    nps_slr0_nodes: one row of the NPS nodes connecting the bottom SLR0 to DDR and CIPS.
    ncrb_nodes: 2d array of all NCRB nodes for east-west communication.

    Note: all 2d arrays are indexed as in the Cartesian plane.
    """

    num_slr: int
    num_col: int
    rows_per_slr: list[int]

    nmu_nodes: list[list[Node]]
    nsu_nodes: list[list[Node]]
    nps_vnoc_nodes: list[list[Node]]
    nps_hnoc_nodes: list[list[Node]]
    nps_hbm_nodes: list[list[Node]]
    ncrb_hbm_nodes: list[list[Node]]
    nps_slr0_nodes: list[list[Node]]
    ncrb_nodes: list[list[Node]]
    edges: list[Edge]

    def __init__(self, **data: Any) -> None:
        """Initialize class."""
        super().__init__(**data)
        assert self.num_slr == len(self.rows_per_slr), "Invalid class attributes!"

    def add_edge(self, edge: Edge) -> None:
        """Add an edge."""
        self.edges.append(edge)

    def add_edges(self, edges: list[Edge]) -> None:
        """Add a list of edges."""
        for e in edges:
            assert e.src != e.dest, f"Invalid edge! {e.src.name} -> {e.dest.name}"
            self.add_edge(e)

    def get_all_nodes(self) -> list[str]:
        """Get a list of all nodes' names.

        Returns a list of strings.
        """
        all_nodes: list[str] = []
        all_nodes += [n.name for row in self.nmu_nodes for n in row]
        all_nodes += [n.name for row in self.nsu_nodes for n in row]
        all_nodes += [n.name for row in self.nps_vnoc_nodes for n in row]
        all_nodes += [n.name for row in self.nps_hnoc_nodes for n in row]
        all_nodes += [n.name for row in self.nps_slr0_nodes for n in row]
        all_nodes += [n.name for row in self.ncrb_nodes for n in row]
        return all_nodes

    def get_all_nmu_nodes(self) -> list[str]:
        """Get a list of all NMU nodes' names.

        Returns a list of strings.
        """
        return [n.name for row in self.nmu_nodes for n in row]

    def get_all_nsu_nodes(self) -> list[str]:
        """Get a list of all NSU nodes' names.

        Returns a list of strings.
        """
        return [n.name for row in self.nsu_nodes for n in row]

    def get_column_nmu_nodes(self, col: int, slr: int) -> list[str]:
        """Get a list of NMU nodes' names in the given column and slr.

        Returns a list of strings.
        """
        row_start = sum(self.rows_per_slr[:slr])
        row_end = row_start + self.rows_per_slr[slr]
        return [self.nmu_nodes[col][r].name for r in range(row_start, row_end)]

    def get_column_nsu_nodes(self, col: int, slr: int) -> list[str]:
        """Get a list of NSU nodes' names in the given column and slr.

        Returns a list of strings.
        """
        row_start = sum(self.rows_per_slr[:slr])
        row_end = row_start + self.rows_per_slr[slr]
        return [self.nsu_nodes[col][r].name for r in range(row_start, row_end)]

    def get_all_edges(self) -> list[tuple[str, str]]:
        """Get a list of all edges without attributes.

        Returns a list of tuples[str, str].
        """
        return [(edge.src.name, edge.dest.name) for edge in self.edges]

    def get_edge_tuple(self, src: Node, dest: Node) -> list[tuple[str, str]]:
        """Get one edge tuple from src Node to dest Node.

        Returns a list of tuples[str, str].
        """
        return [(src.name, dest.name)]

    def get_bidir_edge_tuple(self, n1: Node, n2: Node) -> list[tuple[str, str]]:
        """Get two edge tuples between two Nodes.

        Returns a list of tuples[str, str].
        """
        return [(n1.name, n2.name), (n2.name, n1.name)]

    def get_column_cross_slr_edges(self, col: int) -> list[tuple[str, str]]:
        """Get a list of edges crossing the SLR in a column.

        Returns a list of tuples[str, str].
        """
        edges = []
        for r in range(self.num_slr - 1):
            edges += self.get_bidir_edge_tuple(
                self.nps_hnoc_nodes[col][r * 4], self.nps_hnoc_nodes[col][r * 4 + 2]
            )
            edges += self.get_bidir_edge_tuple(
                self.nps_hnoc_nodes[col][r * 4 + 1], self.nps_hnoc_nodes[col][r * 4 + 3]
            )
        return edges

    def get_column_entrance_edges(self, col: int) -> list[tuple[str, str]]:
        """Get a list of incoming/outgoing edges of each NMU/NSU group in a column.

        Returns a list of tuples[str, str].
        """
        edges = []
        # add the edges of bottom vnoc NPS <-> SLR0 NPS
        edges += self.get_bidir_edge_tuple(
            self.nps_slr0_nodes[col][0], self.nps_vnoc_nodes[col][0]
        )
        edges += self.get_bidir_edge_tuple(
            self.nps_slr0_nodes[col][1], self.nps_vnoc_nodes[col][1]
        )

        # if there is HBM,
        # add the edges of top vnoc NPS <-> HBM NCRB
        if self.ncrb_hbm_nodes:
            nps_vnoc_top_y = sum(self.rows_per_slr) * 2 - 2
            # incoming
            edges += self.get_edge_tuple(
                src=self.ncrb_hbm_nodes[col][0],
                dest=self.nps_vnoc_nodes[col][nps_vnoc_top_y],
            )
            edges += self.get_edge_tuple(
                src=self.ncrb_hbm_nodes[col][0],
                dest=self.nps_vnoc_nodes[col][nps_vnoc_top_y + 1],
            )
            # outgoing
            edges += self.get_edge_tuple(
                src=self.nps_vnoc_nodes[col][nps_vnoc_top_y],
                dest=self.ncrb_hbm_nodes[col][1],
            )
            edges += self.get_edge_tuple(
                src=self.nps_vnoc_nodes[col][nps_vnoc_top_y + 1],
                dest=self.ncrb_hbm_nodes[col][1],
            )

        # add the edges of hnoc NPS <-> vnoc NPS for each SLR
        for slr in range(self.num_slr - 1):
            lower_y_idx = self.rows_per_slr[slr] * 2 - 2
            upper_y_idx = self.rows_per_slr[slr] * 2
            edges += self.get_bidir_edge_tuple(
                self.nps_hnoc_nodes[col][slr * 4],
                self.nps_vnoc_nodes[col][lower_y_idx + 1],
            )
            edges += self.get_bidir_edge_tuple(
                self.nps_hnoc_nodes[col][slr * 4 + 1],
                self.nps_vnoc_nodes[col][lower_y_idx],
            )
            edges += self.get_bidir_edge_tuple(
                self.nps_hnoc_nodes[col][slr * 4 + 2],
                self.nps_vnoc_nodes[col][upper_y_idx + 1],
            )
            edges += self.get_bidir_edge_tuple(
                self.nps_hnoc_nodes[col][slr * 4 + 3],
                self.nps_vnoc_nodes[col][upper_y_idx],
            )
        return edges
