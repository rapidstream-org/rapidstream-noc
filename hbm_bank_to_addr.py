"""Merge .bin memory files to .mem files."""

__copyright__ = """
Copyright (c) 2024 RapidStream Design Automation, Inc. and contributors.
All rights reserved. The contributor(s) of this file has/have agreed to the
RapidStream Contributor License Agreement.
"""


import json
import sys


def hbm_bank_to_addr(bank: dict[str, int]) -> dict[str, str]:
    """Generates starting address in hex for each HBM port.

    Maximum two ports can share an HBM bank.

    Returns a dictionary of string ports and addresses.
    """
    start_addr = 0x4000000000
    bank_incr = 0x40000000
    sharing_incr = 0x20000000

    # if two ports share a bank, divide the address range by half
    # assuming max. two ports sharing a bank
    bank_cnt = [0 for i in range(32)]

    addr = {}
    for p, b in bank.items():
        addr_p = start_addr + b * bank_incr + bank_cnt[b] * sharing_incr
        bank_cnt[b] += 1
        # Format the address as a 44-bit hexadecimal string
        addr[p] = f"44'h{addr_p:011x}"

    return addr


if __name__ == "__main__":
    # command line inputs
    NUM_CMD_IN = 2
    if len(sys.argv) < NUM_CMD_IN:
        print("Needs mmap.json for the HBM bank of each memory port.")
        sys.exit(1)

    with open(sys.argv[1], "r", encoding="utf-8") as file:
        mmap_port_ir = json.load(file)

    mmap_addr = hbm_bank_to_addr({k: v["bank"] for k, v in mmap_port_ir.items()})
    print("addr of each memory port:")
    for k, v in mmap_addr.items():
        print(f"{k:<30} {v}")
