"""Helper functions to parse Rapidstream IR."""

__copyright__ = """
Copyright (c) 2024 RapidStream Design Automation, Inc. and contributors.
All rights reserved. The contributor(s) of this file has/have agreed to the
RapidStream Contributor License Agreement.
"""

from enum import Enum
from typing import Any


class IREnum(Enum):
    """Enums to parse Rapidstream NOC IR."""

    PIPELINE = "__rs_hs_pipeline"
    REGION = "REGION"
    HEAD_REGION = "__HEAD_REGION"
    TAIL_REGION = "__TAIL_REGION"
    DATA_WIDTH = "DATA_WIDTH"
    DEPTH = "DEPTH"
    BODY_LEVEL = "BODY_LEVEL"
    IF_DOUT = "if_dout"
    IF_EMPTY_N = "if_empty_n"
    IF_READ = "if_read"
    IF_DIN = "if_din"
    IF_FULL_N = "if_full_n"
    IF_WRITE = "if_write"
    NMU = "nmu"
    NSU = "nsu"
    CREDIT_CONTROL_MASTER = "_credit_control_master"
    RS_ROUTE = "RS_ROUTE"


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


def eval_id_expr(expr: list[dict[str, str]]) -> int:
    """Evaluate the "id" type expr dictionary to an integer.

    Returns the result integer.
    """
    expr_str = "".join(item["repr"] for item in expr)
    # pylint: disable=eval-used
    return int(eval(expr_str))


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
    }
    if grouped_mod_ir := parse_mod(ir, grouped_mod_name):
        print("No constraints from the grouped module.")
        # grouped module
        combined_mods[f"inst/{grouped_mod_name}_0/"] = grouped_mod_ir["submodules"]

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


def create_lit_expr(val: str) -> list[dict[str, str]]:
    """Create a "lit" type expr dictionary.

    Returns a list of dictionary.
    """
    return [{"type": "lit", "repr": val}]


def create_id_expr(val: str) -> list[dict[str, str]]:
    """Create an "id" type expr dictionary.

    Returns a list of dictionary.
    """
    return [{"type": "id", "repr": val}]


def set_expr(source: list[dict[str, Any]], key: str, val: list[dict[str, str]]) -> None:
    """Sets an expr in place.

    Return None
    """
    for c in source:
        if c["name"] == key:
            c["expr"] = val


def create_wire_ir(name: str, range_left: str, range_right: str) -> dict[str, Any]:
    """Create a wire IR.

    Returns a dictionary.
    """
    wire_range = (
        None
        if range_left == range_right
        else {
            "left": create_lit_expr(range_left),
            "right": create_lit_expr(range_right),
        }
    )
    new_wire = {
        "name": name,
        "hierarchical_name": [name],
        "range": wire_range,
    }
    return new_wire


def create_port_ir(
    name: str, direction: str, range_left: str, range_right: str
) -> dict[str, Any]:
    """Create a port IR.

    Returns a dictionary.
    """
    new_port = create_wire_ir(name, range_left, range_right)
    new_port["type"] = direction
    return new_port


def create_port_wire_connection(port_name: str, wire: str) -> dict[str, Any]:
    """Create a port connection to a wire.

    Returns a dictionary.
    """
    return {
        "name": port_name,
        "hierarchical_name": [port_name],
        "expr": create_id_expr(wire),
    }


def create_port_const_connection(port_name: str, wire: str) -> dict[str, Any]:
    """Create a port connection to a constant.

    Returns a dictionary.
    """
    return {
        "name": port_name,
        "hierarchical_name": [port_name],
        "expr": create_lit_expr(wire),
    }


def create_parameter_ir(name: str, value: str) -> dict[str, Any]:
    """Create a parameter IR.

    Returns a dictionary.
    """
    return {
        "name": name,
        "hierarchical_name": [name],
        "expr": create_lit_expr(value),
        "range": None,
    }


def find_repr(source: list[dict[str, Any]], key: str) -> str:
    """Finds the repr value of a key in the Rapidstream expr IR.

    Returns a string.
    """
    for c in source:
        if c["name"] == key:
            return str(c["expr"][0]["repr"])
    return ""


def create_m_axis_ports(name: str, datawidth: str) -> dict[str, dict[str, Any]]:
    """Create a master AXIS port IR.

    Returns a dictionary.
    """
    return {
        "tdata": create_port_ir(
            "m_axis_" + name + "_tdata", "output wire", str(int(datawidth) - 1), "0"
        ),
        "tvalid": create_port_ir("m_axis_" + name + "_tvalid", "output wire", "0", "0"),
        "tready": create_port_ir("m_axis_" + name + "_tready", "input wire", "0", "0"),
        "tlast": create_port_ir("m_axis_" + name + "_tlast", "output wire", "0", "0"),
    }


def create_s_axis_ports(name: str, datawidth: str) -> dict[str, dict[str, Any]]:
    """Create a slave AXIS port IR.

    Returns a dictionary.
    """
    return {
        "tdata": create_port_ir(
            "s_axis_" + name + "_tdata", "input wire", str(int(datawidth) - 1), "0"
        ),
        "tvalid": create_port_ir("s_axis_" + name + "_tvalid", "input wire", "0", "0"),
        "tready": create_port_ir("s_axis_" + name + "_tready", "output wire", "0", "0"),
        "tlast": create_port_ir("s_axis_" + name + "_tlast", "input wire", "0", "0"),
    }


def create_module_inst_ir(
    module_name: str,
    inst_name: str,
    params: dict[str, str],
    wire_connections: dict[str, str],
    const_connections: dict[str, str],
) -> dict[str, Any]:
    """Create a module's instance IR with port connections.

    Return a dictionary IR.
    """
    return {
        "name": inst_name,
        "hierarchical_name": None,
        "module": module_name,
        "connections": [
            create_port_wire_connection(port, wire)
            for port, wire in wire_connections.items()
        ]
        + [
            create_port_const_connection(port, wire)
            for port, wire in const_connections.items()
        ],
        "parameters": [
            create_parameter_ir(param, val) for param, val in params.items()
        ],
        "floorplan_region": None,
        "area": None,
    }


def parse_fifo_params(fifo: dict[str, Any]) -> dict[str, str]:
    """Parses the parameters in the FIFO IR.

    Returns a dictionary of "depth", "data_width", "head_region", and "tail_region".
    """
    params = {}
    for p in fifo["parameters"]:
        if p["name"] == IREnum.DEPTH.value:
            params["depth"] = str(eval_id_expr(p["expr"]))
        elif p["name"] == IREnum.HEAD_REGION.value:
            params["head_region"] = p["expr"][0]["repr"]
        elif p["name"] == IREnum.TAIL_REGION.value:
            params["tail_region"] = p["expr"][0]["repr"]
        elif p["name"] == IREnum.DATA_WIDTH.value:
            # assumes that we are discarding the eot bit in streams
            params["data_width"] = str(eval_id_expr(p["expr"]) - 1)
    return params


def parse_fifo_rs_routes(grouped_mod_ir: dict[str, Any]) -> dict[str, list[str]]:
    """Parses the RS_ROUTE of each inter-slot FIFO in the Rapidstream IR.

    Returns a dictionary of FIFO names and lists of RS_ROUTE.
    """
    rs_routes = {}
    for fifo in grouped_mod_ir["submodules"]:
        if IREnum.NMU.value in fifo["name"]:
            fifo_name = fifo["name"][4:]
            for p in fifo["pragmas"]:
                if p[0] == IREnum.RS_ROUTE.value:
                    rs_routes[fifo_name] = p[1].strip('"').split(",")
            assert (
                fifo_name in rs_routes
            ), f'RS_ROUTE not found in pragma {fifo["pragmas"]}'
    return rs_routes
