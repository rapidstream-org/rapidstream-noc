"""Helper functions to create Verilog modules in Rapidstream IR."""

__copyright__ = """
Copyright (c) 2024 RapidStream Design Automation, Inc. and contributors.
All rights reserved. The contributor(s) of this file has/have agreed to the
RapidStream Contributor License Agreement.
"""

import copy
from typing import Any

from ir_helper import (
    IREnum,
    create_id_expr,
    create_lit_expr,
    create_m_axis_ports,
    create_module_inst_ir,
    create_parameter_ir,
    create_port_ir,
    create_port_wire_connection,
    create_s_axis_ports,
    create_wire_ir,
    find_repr,
    parse_fifo_params,
    parse_fifo_rs_routes,
    parse_mod,
    parse_top_mod,
    set_expr,
)


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
        if (send_credit) begin
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


def get_credit_return_regions(fifo_route: list[str]) -> dict[str, str]:
    """Generates the credit return pipeline's floorplan region parameters.

    fifo_route: the inter-slot FIFO's RS_ROUTE.

    Returns a dictionary of strings.

    Example:
    >>> get_credit_return_regions(["SLOT_X0Y1_TO_SLOT_X0Y1", "SLOT_X1Y1_TO_SLOT_X1Y1"])
    {'__HEAD_REGION': '"SLOT_X1Y1_TO_SLOT_X1Y1"',
    '__BODY_0_REGION': '"SLOT_X1Y1_TO_SLOT_X1Y1"',
    '__BODY_1_REGION': '"SLOT_X0Y1_TO_SLOT_X0Y1"',
    '__TAIL_REGION': '"SLOT_X0Y1_TO_SLOT_X0Y1"',
    '__BODY_2_REGION': '"SLOT_X0Y1_TO_SLOT_X0Y1"',
    '__BODY_3_REGION': '"SLOT_X0Y1_TO_SLOT_X0Y1"',
    '__BODY_4_REGION': '"SLOT_X0Y1_TO_SLOT_X0Y1"',
    '__BODY_5_REGION': '"SLOT_X0Y1_TO_SLOT_X0Y1"',
    '__BODY_6_REGION': '"SLOT_X0Y1_TO_SLOT_X0Y1"',
    '__BODY_7_REGION': '"SLOT_X0Y1_TO_SLOT_X0Y1"',
    '__BODY_8_REGION': '"SLOT_X0Y1_TO_SLOT_X0Y1"'}
    >>> get_credit_return_regions(
    ...     [
    ...         "SLOT_X1Y1_TO_SLOT_X1Y1",
    ...         "SLOT_X0Y1_TO_SLOT_X0Y1",
    ...         "SLOT_X0Y0_TO_SLOT_X0Y0",
    ...         "SLOT_X1Y0_TO_SLOT_X1Y0",
    ...     ]
    ... )
    {'__HEAD_REGION': '"SLOT_X1Y0_TO_SLOT_X1Y0"',
    '__BODY_0_REGION': '"SLOT_X1Y0_TO_SLOT_X1Y0"',
    '__BODY_1_REGION': '"SLOT_X0Y0_TO_SLOT_X0Y0"',
    '__BODY_2_REGION': '"SLOT_X0Y0_TO_SLOT_X0Y0"',
    '__BODY_3_REGION': '"SLOT_X0Y1_TO_SLOT_X0Y1"',
    '__BODY_4_REGION': '"SLOT_X0Y1_TO_SLOT_X0Y1"',
    '__BODY_5_REGION': '"SLOT_X1Y1_TO_SLOT_X1Y1"',
    '__TAIL_REGION': '"SLOT_X1Y1_TO_SLOT_X1Y1"',
    '__BODY_6_REGION': '"SLOT_X1Y1_TO_SLOT_X1Y1"',
    '__BODY_7_REGION': '"SLOT_X1Y1_TO_SLOT_X1Y1"',
    '__BODY_8_REGION': '"SLOT_X1Y1_TO_SLOT_X1Y1"'}
    """
    regions = {}
    # reverse the routes for the credit return wires
    fifo_route.reverse()

    # double pipeline
    for i, r in enumerate(fifo_route):
        # HEAD
        if i == 0:
            regions["__HEAD_REGION"] = f'"{r}"'
            regions["__BODY_0_REGION"] = f'"{r}"'
        # TAIL
        elif i == len(fifo_route) - 1:
            regions[f"__BODY_{(i - 1) * 2 + 1}_REGION"] = f'"{r}"'
            regions["__TAIL_REGION"] = f'"{r}"'
        # BODY
        else:
            for j in range(2):
                regions[f"__BODY_{(i - 1) * 2 + j + 1}_REGION"] = f'"{r}"'

    # populates the remaining unused BODY REGIONs
    for i in range(len(fifo_route) * 2 - 2, 9):
        regions[f"__BODY_{i}_REGION"] = f'"{fifo_route[-1]}"'
    return regions


def pipeline_credit_ack(grouped_mod_ir: dict[str, Any]) -> None:
    """Pipeline the credit return wires in the Rapidstream IR.

    Returns None.
    """
    rs_routes = parse_fifo_rs_routes(grouped_mod_ir)
    new_modules = []
    for mod in grouped_mod_ir["submodules"]:
        if IREnum.CREDIT_CONTROL_MASTER.value in mod["name"]:
            fifo_name = mod["name"].split(IREnum.CREDIT_CONTROL_MASTER.value)[0]
            credit_cnt_width = find_repr(mod["parameters"], "CREDIT_CNT_WIDTH")
            rs_route = rs_routes[fifo_name]

            new_modules.append(
                create_module_inst_ir(
                    "__rs_hs_pipeline",
                    f"{fifo_name}_credit_pipeline",
                    {
                        "BODY_LEVEL": str(len(rs_route) * 2 - 2),
                        "DATA_WIDTH": credit_cnt_width,
                        "DEPTH": "1",
                        "EXTRA_PIPELINE_BEFORE_TAIL": "0",
                        "PIPELINE_READY_IN_HEAD": "1",
                        "PIPELINE_VALID_AND_DATA_IN_HEAD": "1",
                    }
                    | get_credit_return_regions(rs_route),
                    {
                        "clk": "ap_clk",
                        "if_din": f"{fifo_name}_slave_credit_o",
                        "if_dout": f"{fifo_name}_master_credit_i",
                        "if_empty_n": f"{fifo_name}_master_credit_valid_i",
                        "if_write": f"{fifo_name}_slave_credit_valid_o",
                    },
                    {
                        "reset": "1'b0",
                        "if_full_n": "",
                        "if_read": "1'b1",
                    },
                )
            )

            grouped_mod_ir["wires"] += [
                create_wire_ir(f"{fifo_name}_master_credit_valid_i", "0", "0"),
                create_wire_ir(
                    f"{fifo_name}_master_credit_i",
                    str(int(credit_cnt_width) - 1),
                    "0",
                ),
            ]

            set_expr(
                mod["connections"],
                "credit_i",
                create_id_expr(f"{fifo_name}_master_credit_i"),
            )
            set_expr(
                mod["connections"],
                "credit_valid_i",
                create_id_expr(f"{fifo_name}_master_credit_valid_i"),
            )

    grouped_mod_ir["submodules"] += new_modules


def add_credit_control(
    ir: dict[str, Any], grouped_mod_name: str, init_credit: str
) -> None:
    """Modifies the Rapidstream IR to add credit-based controllers.

    Returns None.
    """

    def str_bit_width(num: str) -> str:
        return str(int(num).bit_length())

    def str_minus_one(num: str) -> str:
        return str((int(num) - 1))

    # the following mutable variables can be modified in place
    top_ir = parse_top_mod(ir)
    grouped_mod_ir = parse_mod(ir, grouped_mod_name)

    # adds the reset ports
    grouped_mod_ir["ports"].append(create_port_ir("ap_rst_n", "input wire", "0", "0"))
    for m in top_ir["submodules"]:
        if m["module"] == grouped_mod_name:
            m["connections"].append(create_port_wire_connection("ap_rst_n", "ap_rst_n"))

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
                        "credit_valid_i": f"{fifo_name}_slave_credit_valid_o",
                        "credit_i": f"{fifo_name}_slave_credit_o",
                        "empty_n_i": f"nmu_{fifo_name}_empty_n",
                        "tready_i": f"m_axis_{fifo_name}_tready",
                        "read_o": f"nmu_{fifo_name}_read",
                        "tvalid_o": f"m_axis_{fifo_name}_tvalid",
                    },
                    {},
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
                        "credit_valid_o": f"{fifo_name}_slave_credit_valid_o",
                        "credit_o": f"{fifo_name}_slave_credit_o",
                    },
                    {},
                )
            )

            grouped_mod_ir["wires"] += [
                create_wire_ir(f"{fifo_name}_slave_credit_valid_o", "0", "0"),
                create_wire_ir(
                    f"{fifo_name}_slave_credit_o",
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
                {},
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
                m["connections"].append(
                    create_port_wire_connection(p["name"], p["name"])
                )

            # remove the grouped mod if empty to avoid the Vivado black-box impl error
            if len(m["connections"]) == 0:
                top_ir["submodules"].remove(m)
            break

    # add const 1 driver module definition
    new_ir["modules"]["module_definitions"].append(create_const_one_driver())

    # add credit-based controllers to each NMU and NSU FIFOs
    add_credit_control(new_ir, grouped_mod_name, "12")
    pipeline_credit_ack(grouped_mod_ir)

    return new_ir


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
