"""The NoC graph class."""

__copyright__ = """
Copyright (c) 2024 RapidStream Design Automation, Inc. and contributors.
All rights reserved. The contributor(s) of this file has/have agreed to the
RapidStream Contributor License Agreement.
"""

from pydantic import BaseModel


class Node(BaseModel):
    """Represents a node in the NoC graph."""

    name: str


class Edge(BaseModel):
    """Represents an edge in the NoC graph."""

    src: Node
    dest: Node
    bandwidth: int


class NocGraph(BaseModel):
    """Represents a NoC graph.

    nmu_nodes: 2d array of all NMU nodes. Indexing follows Vivado.
    nsu_nodes: 2d array of all NSU nodes. Indexing follows Vivado.
    nps_vnoc_nodes: 2d array of all NPS nodes connected to NMUs and NSUs.
                    Indexing follows Vivado.
    nps_hnoc_nodes: 2d array of all interconnect NPS nodes bridging SLRs.
    nps_slr0_nodes: one row of the NPS nodes connecting the bottom SLR0 to DDR and CIPS.
    ncrb_nodes: 2d array of all NCRB nodes for east-west communication.
    """

    nmu_nodes: list[list[Node]]
    nsu_nodes: list[list[Node]]
    nps_vnoc_nodes: list[list[Node]]
    nps_hnoc_nodes: list[list[Node]]
    nps_slr0_nodes: list[Node]
    ncrb_nodes: list[list[Node]]
    edges: list[Edge]

    def add_edge(self, edge: Edge) -> None:
        """Add an edge."""
        self.edges.append(edge)

    def add_edges(self, edges: list[Edge]) -> None:
        """Add a list of edges."""
        for e in edges:
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
        all_nodes += [n.name for n in self.nps_slr0_nodes]
        all_nodes += [n.name for row in self.ncrb_nodes for n in row]
        return all_nodes

    def get_all_nmu_nodes(self) -> list[str]:
        """Get a list of all nmu_nodes' names.

        Returns a list of strings.
        """
        return [n.name for row in self.nmu_nodes for n in row]

    def get_all_nsu_nodes(self) -> list[str]:
        """Get a list of all nsu_nodes' names.

        Returns a list of strings.
        """
        return [n.name for row in self.nsu_nodes for n in row]

    def get_all_edges(self) -> list[tuple[str, str]]:
        """Get a list of all edges without attributes.

        Returns a list of tuples[str, str].
        """
        return [(edge.src.name, edge.dest.name) for edge in self.edges]
