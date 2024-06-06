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
    BODY_LEVEL = "BODY_LEVEL"
    IF_DOUT = "if_dout"
    IF_EMPTY_N = "if_empty_n"
    IF_READ = "if_read"
    IF_DIN = "if_din"
    IF_FULL_N = "if_full_n"
    IF_WRITE = "if_write"
    NMU = "nmu"
    NSU = "nsu"


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


def create_port_connection(port_name: str, wire: str) -> dict[str, Any]:
    """Create a port connection.

    Returns a dictionary.
    """
    return {
        "name": port_name,
        "hierarchical_name": [port_name],
        "expr": create_id_expr(wire),
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
    connections: dict[str, str],
) -> dict[str, Any]:
    """Create a module's instance IR with port connections.

    Return a dictionary IR.
    """
    return {
        "name": inst_name,
        "hierarchical_name": None,
        "module": module_name,
        "connections": [
            create_port_connection(port, wire) for port, wire in connections.items()
        ],
        "parameters": [
            create_parameter_ir(param, val) for param, val in params.items()
        ],
        "floorplan_region": None,
        "area": None,
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
        "ports": [create_port_ir("out", "output wire", "0", "0")],
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


def create_credit_control_master(
    init_credit: str, credit_cnt_width: int
) -> dict[str, Any]:
    """Create the credit_control_master module definition.

    Return a dictionary IR.
    """
    return {
        "name": "credit_control_mastser",
        "hierarchical_name": ["credit_control_mastser"],
        "module_type": "verilog_module",
        "parameters": [
            create_parameter_ir("INIT_CREDIT", init_credit),
            create_parameter_ir("CREDIT_CNT_WIDTH", str(credit_cnt_width)),
        ],
        "ports": [
            create_port_ir("clk", "input wire", "0", "0"),
            create_port_ir("rst_n", "input wire", "0", "0"),
            create_port_ir("credit_valid_i", "input wire", "0", "0"),
            create_port_ir("credit_i", "input wire", str(credit_cnt_width - 1), "0"),
            create_port_ir("empty_n_i", "input wire", "0", "0"),
            create_port_ir("tready_i", "input wire", "0", "0"),
            create_port_ir("read_o", "output wire", "0", "0"),
            create_port_ir("tvalid_o", "output wire", "0", "0"),
        ],
        "verilog": f"""
module credit_control_master # (
    parameter INIT_CREDIT           = {init_credit},
    parameter CREDIT_CNT_WIDTH      = {credit_cnt_width}
) (
    input  wire                                 clk,
    input  wire                                 rst_n,
    input  wire                                 credit_valid_i,
    input  wire [CREDIT_CNT_WIDTH - 1:0]        credit_i,
    input  wire                                 empty_n_i,
    input  wire                                 tready_i,
    output wire                                 read_o,
    output wire                                 tvalid_o
);

reg [CREDIT_CNT_WIDTH - 1:0] credit_cnt_w;
reg [CREDIT_CNT_WIDTH - 1:0] credit_cnt_r;

always @ (*) begin
    credit_cnt_w = credit_cnt_r;

    if (empty_n_i && tready_i && (credit_cnt_r > 0)) begin
        credit_cnt_w = credit_cnt_w - 1'b1;
    end

    if (credit_valid_i) begin
        credit_cnt_w = credit_cnt_w + credit_i;
    end
end

always @(posedge clk) begin
    if (!rst_n) credit_cnt_r <= INIT_CREDIT;
    else credit_cnt_r <= credit_cnt_w;
end

assign read_o = tready_i & (credit_cnt_r > 0);
assign tvalid_o = empty_n_i & (credit_cnt_r > 0);

endmodule
""",
        "metadata": None,
        "submodules_module_names": [],
    }


def create_credit_control_slave(
    init_credit: str, credit_cnt_width: int, timer_width: str
) -> dict[str, Any]:
    """Create the credit_control_slave module definition.

    Return a dictionary IR.
    """
    return {
        "name": "credit_control_slave",
        "hierarchical_name": ["credit_control_slave"],
        "module_type": "verilog_module",
        "parameters": [
            create_parameter_ir("INIT_CREDIT", init_credit),
            create_parameter_ir("CREDIT_CNT_WIDTH", str(credit_cnt_width)),
            create_parameter_ir("TIMER_WIDTH", timer_width),
        ],
        "ports": [
            create_port_ir("clk", "input wire", "0", "0"),
            create_port_ir("rst_n", "input wire", "0", "0"),
            create_port_ir("read_i", "input wire", "0", "0"),
            create_port_ir("empty_n_i", "input wire", "0", "0"),
            create_port_ir("credit_valid_o", "output wire", "0", "0"),
            create_port_ir("credit_o", "output wire", str(credit_cnt_width - 1), "0"),
        ],
        "verilog": f"""
module credit_control_slave # (
    parameter INIT_CREDIT           = {init_credit},
    parameter CREDIT_CNT_WIDTH      = {credit_cnt_width},
    parameter TIMER_WIDTH           = {timer_width}
) (
    input  wire                                 clk,
    input  wire                                 rst_n,
    input  wire                                 read_i,
    input  wire                                 empty_n_i,
    output wire                                 credit_valid_o,
    output wire [CREDIT_CNT_WIDTH - 1:0]        credit_o
);

reg [TIMER_WIDTH - 1:0] timer;
reg [CREDIT_CNT_WIDTH - 1:0] credit_cnt_r;
reg credit_valid_o_r;
reg [CREDIT_CNT_WIDTH - 1:0] credit_o_r;
wire send_credit;

assign send_credit = (&timer) | (credit_cnt_r == (INIT_CREDIT >> 1));

always @ (posedge clk) begin
    if (!rst_n) timer <= 0;
    else begin
        if (send_credit) timer <= 0;
        else if (credit_cnt_r > 0) timer <= timer + 1;
    end
end

always @ (posedge clk) begin
    if (!rst_n) credit_cnt_r <= 0;
    else begin
        if (read_i & empty_n_i) begin
            if (send_credit) begin
                credit_cnt_r <= 1;
            end else begin
                credit_cnt_r <= credit_cnt_r + 1;
            end
        end
        else if (send_credit) begin
            credit_cnt_r <= 0;
        end
    end
end

always @ (posedge clk) begin
    if (!rst_n) begin
        credit_valid_o_r <= 0;
        credit_o_r <= 0;
    end else begin
        credit_o_r <= credit_cnt_r;
        credit_valid_o_r <= 0;
        if (send_credit & (credit_cnt_r > 0)) begin
            credit_valid_o_r <= 1'b1;
        end
    end
end

assign credit_valid_o = credit_valid_o_r;
assign credit_o = credit_o_r;

endmodule
""",
        "metadata": None,
        "submodules_module_names": [],
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


def create_nmu_fifo_ir(
    fifo: dict[str, Any], fifo_params: dict[str, str], m_axis_ports: dict[str, Any]
) -> dict[str, Any]:
    """Create a NMU FIFO IR from the original FIFO.

    Returns a FIFO IR.
    """
    nmu_fifo = copy.deepcopy(fifo)
    nmu_fifo["name"] = "nmu_" + fifo["name"]

    for p in nmu_fifo["parameters"]:
        # half the depth
        if p["name"] == IREnum.DEPTH.value:
            p["expr"] = create_lit_expr(str(int(fifo_params["depth"]) // 2))
        # remove the body level pipelines
        elif p["name"] == IREnum.BODY_LEVEL.value:
            p["expr"] = create_lit_expr("0")
        # assign NMU fifo regions to head region
        elif IREnum.REGION.value in p["name"]:
            p["expr"] = create_lit_expr(fifo_params["head_region"])

    # modify the NMU fifo connections
    for c in nmu_fifo["connections"]:
        if c["name"] == IREnum.IF_DOUT.value:
            c["expr"] = create_id_expr(m_axis_ports["tdata"]["name"])
        elif c["name"] == IREnum.IF_EMPTY_N.value:
            c["expr"] = create_id_expr(m_axis_ports["tvalid"]["name"])
        elif c["name"] == IREnum.IF_READ.value:
            c["expr"] = create_id_expr(m_axis_ports["tready"]["name"])
    return nmu_fifo


def create_nsu_fifo_ir(
    fifo: dict[str, Any], fifo_params: dict[str, str], s_axis_ports: dict[str, Any]
) -> dict[str, Any]:
    """Create a NSU FIFO IR from the original FIFO.

    Returns a FIFO IR.
    """
    nsu_fifo = copy.deepcopy(fifo)
    nsu_fifo["name"] = "nsu_" + fifo["name"]

    for p in nsu_fifo["parameters"]:
        # half the depth
        if p["name"] == IREnum.DEPTH.value:
            p["expr"] = create_lit_expr(str(int(fifo_params["depth"]) // 2))
        # remove the body level pipelines
        elif p["name"] == IREnum.BODY_LEVEL.value:
            p["expr"] = create_lit_expr("0")
        # assign NSU fifo regions to tail region
        elif IREnum.REGION.value in p["name"]:
            p["expr"] = create_lit_expr(fifo_params["tail_region"])

    # modify the NSU fifo connections
    for c in nsu_fifo["connections"]:
        if c["name"] == IREnum.IF_DIN.value:
            c["expr"] = create_id_expr(s_axis_ports["tdata"]["name"])
        elif c["name"] == IREnum.IF_FULL_N.value:
            c["expr"] = create_id_expr(s_axis_ports["tready"]["name"])
        elif c["name"] == IREnum.IF_WRITE.value:
            c["expr"] = create_id_expr(s_axis_ports["tvalid"]["name"])
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
        new_modules.append(create_nmu_fifo_ir(fifo, fifo_params, m_axis_ports))

        # create the NSU fifo
        new_modules.append(create_nsu_fifo_ir(fifo, fifo_params, s_axis_ports))

        # drive tlast with constant 1
        new_modules.append(
            create_module_inst_ir(
                "Const_1_Driver",
                f"{fifo['name']}_tlast_inst",
                {},
                {"out": m_axis_ports["tlast"]["name"]},
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

    # add credit-based controllers to each NMU and NSU FIFOs
    new_ir = add_credit_control(new_ir, grouped_mod_name, "12")

    return new_ir


def add_credit_control(
    ir: dict[str, Any], grouped_mod_name: str, init_credit: str
) -> dict[str, Any]:
    """Modifies the Rapidstream IR to add credit-based controllers.

    Returns the modified json.
    """

    def str_bit_width(num: str) -> str:
        return str(int(num).bit_length())

    def str_minus_one(num: str) -> str:
        return str((int(num) - 1))

    def find_repr(source: list[dict[str, Any]], key: str) -> str:
        for c in source:
            if c["name"] == key:
                return str(c["expr"][0]["repr"])
        return ""

    def set_expr(
        source: list[dict[str, Any]], key: str, val: list[dict[str, str]]
    ) -> None:
        for c in source:
            if c["name"] == key:
                c["expr"] = val

    # the following mutable variables can be modified in place
    top_ir = parse_top_mod(ir)
    grouped_mod_ir = parse_mod(ir, grouped_mod_name)

    # adds the reset ports
    grouped_mod_ir["ports"].append(create_port_ir("ap_rst_n", "input wire", "0", "0"))
    for m in top_ir["submodules"]:
        if m["module"] == grouped_mod_name:
            m["connections"].append(create_port_connection("ap_rst_n", "ap_rst_n"))

    new_modules = []
    for fifo in grouped_mod_ir["submodules"]:
        fifo_name = fifo["name"][4:]
        if IREnum.NMU.value in fifo["name"]:
            new_modules.append(
                create_module_inst_ir(
                    "credit_control_master",
                    f"{fifo_name}_credit_control_master",
                    {
                        "INIT_CREDIT": init_credit,
                        "CREDIT_CNT_WIDTH": str_bit_width(init_credit),
                    },
                    {
                        "clk": "ap_clk",
                        "rst_n": "ap_rst_n",
                        "credit_valid_i": f"{fifo_name}_credit_valid",
                        "credit_i": f"{fifo_name}_credit",
                        "empty_n_i": f"nmu_{fifo_name}_empty_n",
                        "tready_i": f"m_axis_{fifo_name}_tready",
                        "read_o": f"nmu_{fifo_name}_read",
                        "tvalid_o": f"m_axis_{fifo_name}_tvalid",
                    },
                )
            )

            grouped_mod_ir["wires"] += [
                create_wire_ir(f"nmu_{fifo_name}_empty_n", "0", "0"),
                create_wire_ir(f"nmu_{fifo_name}_read", "0", "0"),
            ]

            set_expr(
                fifo["connections"],
                IREnum.IF_EMPTY_N.value,
                create_id_expr(f"nmu_{fifo_name}_empty_n"),
            )
            set_expr(
                fifo["connections"],
                IREnum.IF_READ.value,
                create_id_expr(f"nmu_{fifo_name}_read"),
            )

        elif IREnum.NSU.value in fifo["name"]:
            nsu_if_empty_n = find_repr(fifo["connections"], IREnum.IF_EMPTY_N.value)
            nsu_if_read = find_repr(fifo["connections"], IREnum.IF_READ.value)

            new_modules.append(
                create_module_inst_ir(
                    "credit_control_slave",
                    f"{fifo_name}_credit_control_slave",
                    {
                        "INIT_CREDIT": init_credit,
                        "CREDIT_CNT_WIDTH": str_bit_width(init_credit),
                        "TIMER_WIDTH": "5",
                    },
                    {
                        "clk": "ap_clk",
                        "rst_n": "ap_rst_n",
                        "read_i": nsu_if_read,
                        "empty_n_i": nsu_if_empty_n,
                        "credit_valid_o": f"{fifo_name}_credit_valid",
                        "credit_o": f"{fifo_name}_credit",
                    },
                )
            )

            grouped_mod_ir["wires"] += [
                create_wire_ir(f"{fifo_name}_credit_valid", "0", "0"),
                create_wire_ir(
                    f"{fifo_name}_credit",
                    str_minus_one(str_bit_width(init_credit)),
                    "0",
                ),
            ]

        set_expr(fifo["parameters"], IREnum.DEPTH.value, create_lit_expr(init_credit))

    grouped_mod_ir["submodules"] += new_modules

    # add credit control master and slave module definition
    ir["modules"]["module_definitions"].append(
        create_credit_control_master(init_credit="15", credit_cnt_width=4)
    )
    ir["modules"]["module_definitions"].append(
        create_credit_control_slave(
            init_credit="15", credit_cnt_width=4, timer_width="5"
        )
    )

    return ir


if __name__ == "__main__":
    import json
    import subprocess

    TEST_DIR = "/home/jakeke/rapidstream-noc/test/credit_based"
    NOC_PASS_JSON = "noc_pass.json"
    NOC_PASS_WRAPPER_JSON = "noc_pass_wrapper.json"
    with open(f"{TEST_DIR}/{NOC_PASS_JSON}", "r", encoding="utf-8") as file:
        design = json.load(file)

    new_serpens_ir = noc_rtl_wrapper(design, "axis_noc_if")

    with open(f"{TEST_DIR}/{NOC_PASS_WRAPPER_JSON}", "w", encoding="utf-8") as file:
        json.dump(new_serpens_ir, file, indent=4)

    zsh_cmds = f"""
rm -rf {TEST_DIR}/rtl
rapidstream-exporter -i {TEST_DIR}/{NOC_PASS_WRAPPER_JSON} -f {TEST_DIR}/rtl
"""

    # generate rtl folder
    print(zsh_cmds)
    subprocess.run(["zsh", "-c", zsh_cmds], check=True)
