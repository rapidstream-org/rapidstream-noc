"""The FPGA device class."""

__copyright__ = """
Copyright (c) 2024 RapidStream Design Automation, Inc. and contributors.
All rights reserved. The contributor(s) of this file has/have agreed to the
RapidStream Contributor License Agreement.
"""

from typing import Any

from pydantic import BaseModel

from noc_graph import NocGraph


class Device(BaseModel):
    """Represents an FPGA device with its attributes."""

    part_num: str
    board_part: str
    # user's partition choice: slot_width x slot_height (slots)
    slot_width: int
    slot_height: int
    cr_mapping: list[list[str]]

    # NoC graph
    noc_graph: NocGraph

    # generated
    nmu_per_slot: list[list[int]]
    nsu_per_slot: list[list[int]]

    def __init__(self, **data: Any) -> None:
        """Initialize class and generates per slot attributes."""
        super().__init__(**data)
        assert (
            self.noc_graph.num_slr == self.slot_height
        ), "Assumes slot_height equals number of SLRs."
        assert len(self.cr_mapping) <= self.slot_height
        if len(self.cr_mapping) > 0:
            assert len(self.cr_mapping[0]) <= self.slot_width

        # generate per slot data structure
        self.nmu_per_slot = [
            [0 for _ in range(self.slot_width)] for _ in range(self.slot_height)
        ]
        self.nsu_per_slot = [
            [0 for _ in range(self.slot_width)] for _ in range(self.slot_height)
        ]
        for j in range(self.slot_height):
            nodes_per_slr = self.noc_graph.rows_per_slr[j] * self.noc_graph.num_col
            for i in range(self.slot_width):
                self.nmu_per_slot[i][j] = nodes_per_slr // self.slot_width
                self.nsu_per_slot[i][j] = nodes_per_slr // self.slot_width
        print("nmu per slot", self.nmu_per_slot)

    def get_num_nmu_in_slot(self, x: int, y: int) -> int:
        """Returns the number of NMU nodes in a slot."""
        assert x < self.slot_width, "Slot X coordinate out of range!"
        assert y < self.slot_height, "Slot Y coordinate out of range!"
        return self.nmu_per_slot[x][y]

    def get_num_nsu_in_slot(self, x: int, y: int) -> int:
        """Returns the number of NSU nodes in a slot."""
        assert x < self.slot_width, "Slot X coordinate out of range!"
        assert y < self.slot_height, "Slot Y coordinate out of range!"
        return self.nsu_per_slot[x][y]

    def get_nmu_or_nsu_names_in_slot(self, node_type: str, x: int, y: int) -> list[str]:
        """Gets all NMU or NSU node names in a given slot.

        node: either "nmu" or "nsu".

        Returns a list of strings.
        """
        assert x < self.slot_width
        assert y < self.slot_height
        cols_per_slot = self.noc_graph.num_col // self.slot_width
        col_start = cols_per_slot * x
        col_end = col_start + cols_per_slot
        row_start = sum(self.noc_graph.rows_per_slr[:y]) if y > 0 else 0
        row_end = row_start + self.noc_graph.rows_per_slr[y]
        return [
            f"{node_type}_x{x}y{y}"
            for x in range(col_start, col_end)
            for y in range(row_start, row_end)
        ]

    def get_slot_cr(self, x: int, y: int) -> str:
        """Gets all Clock Regions of a slot.

        Returns a string
        """
        return self.cr_mapping[x][y]
