"""Helper functions to parse Rapidstream IR."""

__copyright__ = """
Copyright (c) 2024 RapidStream Design Automation, Inc. and contributors.
All rights reserved. The contributor(s) of this file has/have agreed to the
RapidStream Contributor License Agreement.
"""

import copy
from enum import Enum
from typing import Any


def extract_slot_coord(slot_name: str) -> tuple[int, int]:
    """Extracts the x and y coordinates from the slot name.

    Returns a coordinate tuple as (x, y) in int.

    Example:
    >>> extract_slot_coord("SLOT_X0Y1")
    (0, 1)
    """
    return int(slot_name.split("X")[1].split("Y")[0]), int(slot_name.split("Y")[1])


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


def parse_top_mod(ir: dict[str, Any]) -> Any:
    """Parses the top_mod dict in the Rapidstream IR.

    Return a dictionary.

    Example:
    >>> design = {
    ...     "modules": {
    ...         "top_name": "FINDME",
    ...         "module_definitions": [{"name": "FINDME"}],
    ...     }
    ... }
    >>> parse_top_mod(design)
    {'name': 'FINDME'}
    """
    top_mod = ir["modules"]["top_name"]
    for mod in ir["modules"]["module_definitions"]:
        if mod["name"] == top_mod:
            return mod
    raise AssertionError()


def parse_mod(ir: dict[str, Any], name: str) -> Any:
    """Parses a given module's IR in the Rapidstream IR.

    Return a dictionary.
    """
    for mod in ir["modules"]["module_definitions"]:
        if mod["name"] == name:
            return mod
    return {}


class IREnum(Enum):
    """Enums to parse Rapidstream NOC IR."""

    PIPELINE = "__rs_hs_pipeline"
    REGION = "REGION"
    HEAD_REGION = "__HEAD_REGION"
    TAIL_REGION = "__TAIL_REGION"
    DATA_WIDTH = "DATA_WIDTH"
    DEPTH = "DEPTH"
    PIPELINE_BODY_LEVEL = "PIPELINE_BODY_LEVEL"
    IF_DOUT = "if_dout"
    IF_EMPTY_N = "if_empty_n"
    IF_READ = "if_read"
    IF_DIN = "if_din"
    IF_FULL_N = "if_full_n"
    IF_WRITE = "if_write"


def eval_id_expr(expr: list[dict[str, str]]) -> int:
    """Evaluate the "id" type expr dictionary to an integer.

    Returns the result integer.
    """
    expr_str = "".join(item["repr"] for item in expr)
    # pylint: disable=eval-used
    return int(eval(expr_str))


def create_id_expr(val: int) -> list[dict[str, str]]:
    """Create an "id" type expr dictionary from an integer.

    Returns the list of dictionary.
    """
    return [{"type": "lit", "repr": str(val)}]


def parse_inter_slot(
    ir: dict[str, Any],
) -> tuple[dict[str, dict[str, str]], dict[str, int]]:
    """Parses the cross-slot streams in the Rapidstream NOC IR.

    Puts each stream's source slot range in "src".
    Puts each stream's destination slot range in "dest".
    Puts each stream's DATA_WIDTH in bits.

    Returns a dictionary of streams' slots
    and a dictionary of streams' data width.
    """
    slots: dict[str, dict[str, str]] = {}
    widths: dict[str, int] = {}
    for sub_mod in ir["submodules"]:
        if sub_mod["module"] == IREnum.PIPELINE.value:
            # a pipeline module with "REGION" parameters crosses slot boundaries
            if any(IREnum.REGION.value in p["name"] for p in sub_mod["parameters"]):
                name = sub_mod["name"]
                slots[name] = {}
                for p in sub_mod["parameters"]:
                    if p["name"] == IREnum.HEAD_REGION.value:
                        # removes quotations in p["expr"][0]["repr"]
                        slots[name]["src"] = p["expr"][0]["repr"][1:-1]
                    elif p["name"] == IREnum.TAIL_REGION.value:
                        # removes quotations in p["expr"][0]["repr"]
                        slots[name]["dest"] = p["expr"][0]["repr"][1:-1]

                for p in sub_mod["parameters"]:
                    if p["name"] == IREnum.DATA_WIDTH.value:
                        # assumes that we are discarding the eot bit in streams
                        data_width = eval_id_expr(p["expr"]) - 1
                        break
                widths[name] = data_width

    return slots, widths


def parse_floorplan(ir: dict[str, Any], grouped_mod_name: str) -> dict[str, list[str]]:
    """Parses the top module and grouped module's floorplan regions.

    Return a dictionary where keys are slots and values are submodules.
    """
    combined_mods = {
        # top
        "inst/": parse_top_mod(ir)["submodules"],
        # grouped module
        f"inst/{grouped_mod_name}_0/": parse_mod(ir, grouped_mod_name)["submodules"],
    }

    insts = {}
    for parent, mods in combined_mods.items():
        for sub_mod in mods:
            sub_mod_name = parent + sub_mod["name"]
            if (slot := sub_mod["floorplan_region"]) is None:
                # pipeline module, needs to extract slot of each reg
                for p in sub_mod["parameters"]:
                    # ignored clock and reset pipelining
                    # __rs___rs_ap_ctrl_pipeline_aux_split_aux_0__inst
                    # __rs___rs_ap_ctrl_pipeline_aux_split_aux_1__inst
                    inst_name = ""
                    if p["name"] == IREnum.HEAD_REGION.value:
                        # head reg
                        inst_name = sub_mod_name + "/head"
                    elif p["name"] == IREnum.TAIL_REGION.value:
                        # tail reg
                        inst_name = sub_mod_name + "/tail"
                    elif IREnum.REGION.value in p["name"]:
                        # body reg
                        body_num = p["name"].split("_")[3]
                        inst_name = sub_mod_name + f"/body_{body_num}"

                    if inst_name:
                        slot = p["expr"][0]["repr"].strip('"')
                        insts[inst_name] = slot
            else:
                # regular module
                insts[sub_mod_name] = slot

    # convert {instance: slot} to {slot: [instances]}
    floorplan: dict[str, list[str]] = {}
    for sub_mod_name, slot in insts.items():
        if slot not in floorplan:
            floorplan[slot] = []
        floorplan[slot].append(sub_mod_name)
    return floorplan


def create_port_ir(
    name: str, direction: str, range_left: str, range_right: str
) -> dict[str, Any]:
    """Create a port IR.

    Returns a dictionary.
    """
    port_range = (
        None
        if range_left == range_right
        else {
            "left": [{"type": "lit", "repr": range_left}],
            "right": [{"type": "lit", "repr": range_right}],
        }
    )
    new_port = {
        "name": name,
        "hierarchical_name": [name],
        "type": direction,
        "range": port_range,
    }
    return new_port


def create_m_axis_ports(name: str, datawidth: int) -> dict[str, dict[str, Any]]:
    """Create a master AXIS port IR.

    Returns a dictionary.
    """
    return {
        "tdata": create_port_ir(
            "m_axis_" + name + "_tdata", "output wire", str(datawidth - 1), "0"
        ),
        "tvalid": create_port_ir("m_axis_" + name + "_tvalid", "output wire", "0", "0"),
        "tready": create_port_ir("m_axis_" + name + "_tready", "input wire", "0", "0"),
        "tlast": create_port_ir("m_axis_" + name + "_tlast", "output wire", "0", "0"),
    }


def create_s_axis_ports(name: str, datawidth: int) -> dict[str, dict[str, Any]]:
    """Create a slave AXIS port IR.

    Returns a dictionary.
    """
    return {
        "tdata": create_port_ir(
            "s_axis_" + name + "_tdata", "input wire", str(datawidth - 1), "0"
        ),
        "tvalid": create_port_ir("s_axis_" + name + "_tvalid", "input wire", "0", "0"),
        "tready": create_port_ir("s_axis_" + name + "_tready", "output wire", "0", "0"),
        "tlast": create_port_ir("s_axis_" + name + "_tlast", "input wire", "0", "0"),
    }


def create_port_connection(port_name: str, wire: str) -> dict[str, Any]:
    """Create a port connection.

    Returns a dictionary.
    """
    return {
        "name": port_name,
        "hierarchical_name": [port_name],
        "expr": [{"type": "id", "repr": wire}],
    }


def create_const_one_driver() -> dict[str, Any]:
    """Create the Const_1_Driver module definition.

    Return a dictionary IR.
    """
    return {
        "name": "Const_1_Driver",
        "hierarchical_name": ["Const_1_Driver"],
        "module_type": "verilog_module",
        "parameters": [],
        "ports": [
            {
                "name": "out",
                "hierarchical_name": ["out"],
                "type": "output wire",
                "range": None,
            }
        ],
        "verilog": """
module Const_1_Driver(
    output out
);
assign out = 1'b1;
endmodule
""",
        "metadata": None,
        "submodules_module_names": [],
    }


def add_const_one_driver(name: str, wire: str) -> dict[str, Any]:
    """Create a Const_1_Driver submodule.

    Return a dictionary IR.
    """
    return {
        "name": name,
        "hierarchical_name": None,
        "module": "Const_1_Driver",
        "connections": [
            {
                "name": "out",
                "hierarchical_name": None,
                "expr": [{"type": "id", "repr": wire}],
            }
        ],
        "parameters": [],
        "floorplan_region": None,
        "area": None,
    }


def parse_fifo_params(fifo: dict[str, Any]) -> dict[str, Any]:
    """Parses the parameters in the FIFO IR.

    Returns a dictionary of "depth", "data_width", "head_region", and "tail_region".
    """
    params = {}
    for p in fifo["parameters"]:
        if p["name"] == IREnum.DEPTH.value:
            params["depth"] = eval_id_expr(p["expr"])
        elif p["name"] == IREnum.HEAD_REGION.value:
            params["head_region"] = p["expr"]
        elif p["name"] == IREnum.TAIL_REGION.value:
            params["tail_region"] = p["expr"]
        elif p["name"] == IREnum.DATA_WIDTH.value:
            # assumes that we are discarding the eot bit in streams
            params["data_width"] = eval_id_expr(p["expr"]) - 1
    return params


def create_nmu_fifo_ir(
    fifo: dict[str, Any], fifo_params: dict[str, Any], m_axis_ports: dict[str, Any]
) -> dict[str, Any]:
    """Create a NMU FIFO IR from the original FIFO.

    Returns a FIFO IR.
    """
    nmu_fifo = copy.deepcopy(fifo)
    nmu_fifo["name"] = "nmu_" + fifo["name"]

    for p in nmu_fifo["parameters"]:
        # half the depth
        if p["name"] == IREnum.DEPTH.value:
            p["expr"] = create_id_expr(fifo_params["depth"] // 2)
        # remove the body level pipelines
        elif p["name"] == IREnum.PIPELINE_BODY_LEVEL.value:
            p["expr"] = create_id_expr(0)
        # assign NMU fifo regions to head region
        elif IREnum.REGION.value in p["name"]:
            p["expr"] = fifo_params["head_region"]

    # modify the NMU fifo connections
    for c in nmu_fifo["connections"]:
        if c["name"] == IREnum.IF_DOUT.value:
            c["expr"] = [{"type": "id", "repr": m_axis_ports["tdata"]["name"]}]
        elif c["name"] == IREnum.IF_EMPTY_N.value:
            c["expr"] = [{"type": "id", "repr": m_axis_ports["tvalid"]["name"]}]
        elif c["name"] == IREnum.IF_READ.value:
            c["expr"] = [{"type": "id", "repr": m_axis_ports["tready"]["name"]}]
    return nmu_fifo


def create_nsu_fifo_ir(
    fifo: dict[str, Any], fifo_params: dict[str, Any], s_axis_ports: dict[str, Any]
) -> dict[str, Any]:
    """Create a NSU FIFO IR from the original FIFO.

    Returns a FIFO IR.
    """
    nsu_fifo = copy.deepcopy(fifo)
    nsu_fifo["name"] = "nsu_" + fifo["name"]

    for p in nsu_fifo["parameters"]:
        # half the depth
        if p["name"] == IREnum.DEPTH.value:
            p["expr"] = create_id_expr(fifo_params["depth"] // 2)
        # remove the body level pipelines
        elif p["name"] == IREnum.PIPELINE_BODY_LEVEL.value:
            p["expr"] = create_id_expr(0)
        # assign NSU fifo regions to tail region
        elif IREnum.REGION.value in p["name"]:
            p["expr"] = fifo_params["tail_region"]

    # modify the NSU fifo connections
    for c in nsu_fifo["connections"]:
        if c["name"] == IREnum.IF_DIN.value:
            c["expr"] = [{"type": "id", "repr": s_axis_ports["tdata"]["name"]}]
        elif c["name"] == IREnum.IF_FULL_N.value:
            c["expr"] = [{"type": "id", "repr": s_axis_ports["tready"]["name"]}]
        elif c["name"] == IREnum.IF_WRITE.value:
            c["expr"] = [{"type": "id", "repr": s_axis_ports["tvalid"]["name"]}]
    return nsu_fifo


def noc_rtl_wrapper(ir: dict[str, Any], grouped_mod_name: str) -> dict[str, Any]:
    """Modifies the Rapidstream IR to replace the selected FIFOs with AXIS-NoC.

    Returns the modified json.
    """
    new_ir = copy.deepcopy(ir)
    # the following mutable variables can be modified in place
    top_ir = parse_top_mod(new_ir)
    grouped_mod_ir = parse_mod(new_ir, grouped_mod_name)

    # add ports
    axis_noc_ports = []
    new_modules = []
    # split each fifo into two smaller fifos
    # before:   in_data -> fifo -> out_data
    # after:    in_data -> NMU fifo -> AXIS-NoC -> NSU fifo -> out_data
    for fifo in grouped_mod_ir["submodules"]:
        fifo_params = parse_fifo_params(fifo)

        # create AXIS-NoC ports
        m_axis_ports = create_m_axis_ports(fifo["name"], fifo_params["data_width"])
        axis_noc_ports += list(m_axis_ports.values())
        s_axis_ports = create_s_axis_ports(fifo["name"], fifo_params["data_width"])
        axis_noc_ports += list(s_axis_ports.values())

        # create the NMU fifo
        nmu_fifo = create_nmu_fifo_ir(fifo, fifo_params, m_axis_ports)
        new_modules.append(nmu_fifo)

        # create the NSU fifo
        nsu_fifo = create_nsu_fifo_ir(fifo, fifo_params, s_axis_ports)
        new_modules.append(nsu_fifo)

        # drive tlast with constant 1
        new_modules.append(
            add_const_one_driver(
                f"{fifo['name']}_tlast_inst", m_axis_ports["tlast"]["name"]
            )
        )

    grouped_mod_ir["submodules"] = new_modules
    grouped_mod_ir["ports"] += axis_noc_ports

    # create top level AXIS-NoC ports
    top_ir["ports"] += axis_noc_ports
    # connect them to the grouped_module
    for m in top_ir["submodules"]:
        if m["module"] == grouped_mod_name:
            for p in axis_noc_ports:
                m["connections"].append(create_port_connection(p["name"], p["name"]))

            # remove the grouped mod if empty to avoid the Vivado black-box impl error
            if len(m["connections"]) == 0:
                top_ir["submodules"].remove(m)
            break

    # add const 1 driver module definition
    new_ir["modules"]["module_definitions"].append(create_const_one_driver())

    return new_ir


if __name__ == "__main__":
    import json

    SERPENS_IR = "/home/jakeke/Serpens/vhk158/rs_ch28_noc_vivado/noc_pass.json"
    with open(SERPENS_IR, "r", encoding="utf-8") as file:
        design = json.load(file)

        new_serpens_ir = noc_rtl_wrapper(design, "axis_noc_if")

        with open("noc_pass_wrapper.json", "w", encoding="utf-8") as file:
            json.dump(new_serpens_ir, file, indent=4)
