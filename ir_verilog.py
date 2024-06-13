"""Helper functions to create Verilog modules in Rapidstream IR."""

__copyright__ = """
Copyright (c) 2024 RapidStream Design Automation, Inc. and contributors.
All rights reserved. The contributor(s) of this file has/have agreed to the
RapidStream Contributor License Agreement.
"""

import copy
from typing import Any

from ir_helper import (
    CreditReturnEnum,
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
    find_expr,
    find_repr,
    get_credit_return_regions,
    parse_fifo_params,
    parse_fifo_rs_routes,
    parse_mod,
    parse_top_mod,
    set_all_pipeline_regions,
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


def create_credit_control_master(params: dict[str, str]) -> dict[str, Any]:
    """Create the credit_control_master module definition.

    Return a dictionary IR.
    """
    return {
        "name": "credit_control_mastser",
        "hierarchical_name": ["credit_control_mastser"],
        "module_type": "verilog_module",
        "parameters": [
            create_parameter_ir(param, val) for param, val in params.items()
        ],
        "ports": [
            create_port_ir("clk", "input wire", "0", "0"),
            create_port_ir("rst_n", "input wire", "0", "0"),
            create_port_ir("credit_valid_i", "input wire", "0", "0"),
            create_port_ir(
                "credit_i", "input wire", str(int(params["CREDIT_CNT_WIDTH"]) - 1), "0"
            ),
            create_port_ir("empty_n_i", "input wire", "0", "0"),
            create_port_ir("tready_i", "input wire", "0", "0"),
            create_port_ir("read_o", "output wire", "0", "0"),
            create_port_ir("tvalid_o", "output wire", "0", "0"),
        ],
        "verilog": f"""
module credit_control_master # (
    parameter INIT_CREDIT           = {params['INIT_CREDIT']},
    parameter CREDIT_CNT_WIDTH      = {params['CREDIT_CNT_WIDTH']}
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


def create_credit_control_slave(params: dict[str, str]) -> dict[str, Any]:
    """Create the credit_control_slave module definition.

    Return a dictionary IR.
    """
    return {
        "name": "credit_control_slave",
        "hierarchical_name": ["credit_control_slave"],
        "module_type": "verilog_module",
        "parameters": [
            create_parameter_ir(param, val) for param, val in params.items()
        ],
        "ports": [
            create_port_ir("clk", "input wire", "0", "0"),
            create_port_ir("rst_n", "input wire", "0", "0"),
            create_port_ir("read_i", "input wire", "0", "0"),
            create_port_ir("empty_n_i", "input wire", "0", "0"),
            create_port_ir("credit_valid_o", "output wire", "0", "0"),
            create_port_ir(
                "credit_o", "output wire", str(int(params["CREDIT_CNT_WIDTH"]) - 1), "0"
            ),
        ],
        "verilog": f"""
module credit_control_slave # (
    parameter INIT_CREDIT           = {params['INIT_CREDIT']},
    parameter CREDIT_CNT_WIDTH      = {params['CREDIT_CNT_WIDTH']},
    parameter TIMER_WIDTH           = {params['TIMER_WIDTH']}
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


def create_credit_control_slave_group(params: dict[str, str]) -> dict[str, Any]:
    """Create the credit_control_slave_group module definition.

    Return a dictionary IR.
    """
    return {
        "name": "credit_control_slave",
        "hierarchical_name": ["credit_control_slave"],
        "module_type": "verilog_module",
        "parameters": [
            create_parameter_ir(param, val) for param, val in params.items()
        ],
        "ports": [
            create_port_ir("clk", "input wire", "0", "0"),
            create_port_ir("rst_n", "input wire", "0", "0"),
            create_port_ir(
                "read_i", "input wire", str(int(params["GROUP_SIZE"]) - 1), "0"
            ),
            create_port_ir(
                "empty_n_i", "input wire", str(int(params["GROUP_SIZE"]) - 1), "0"
            ),
            create_port_ir("ready_i", "input wire", "0", "0"),
            create_port_ir("credit_valid_o", "output wire", "0", "0"),
            create_port_ir(
                "credit_o",
                "output wire",
                str(int(params["CREDIT_CNT_WIDTH"]) * int(params["GROUP_SIZE"]) - 1),
                "0",
            ),
        ],
        "verilog": f"""
module credit_control_slave_group # (
    parameter INIT_CREDIT           = {params['INIT_CREDIT']},
    parameter CREDIT_CNT_WIDTH      = {params['CREDIT_CNT_WIDTH']},
    parameter TIMER_WIDTH           = {params['TIMER_WIDTH']},
    parameter GROUP_SIZE            = {params['GROUP_SIZE']}
) (
    input  wire                                                     clk,
    input  wire                                                     rst_n,
    input  wire [GROUP_SIZE - 1:0]                                  read_i,
    input  wire [GROUP_SIZE - 1:0]                                  empty_n_i,
    input  wire                                                     ready_i,
    output wire                                                     credit_valid_o,
    output wire [GROUP_SIZE - 1:0][CREDIT_CNT_WIDTH - 1:0]          credit_o
);

reg [TIMER_WIDTH - 1:0] timer;


reg [CREDIT_CNT_WIDTH - 1:0] credit_cnt_r [GROUP_SIZE - 1:0];
reg credit_valid_o_r;
reg [CREDIT_CNT_WIDTH - 1:0] credit_o_r [GROUP_SIZE - 1:0];
wire [GROUP_SIZE - 1:0] credits_loaded;
wire [GROUP_SIZE - 1:0] credits_present;
wire send_credit;
wire credit_sent;

assign send_credit = (&timer) | (|credits_loaded);
assign credit_sent = credit_valid_o_r & ready_i;

always @ (posedge clk) begin
    if (!rst_n) timer <= 0;
    else begin
        if (send_credit) timer <= 0;
        else if (&timer) timer <= timer;
        else if (|credits_present) timer <= timer + 1;
    end
end

genvar i;
generate
    for (i = 0; i < GROUP_SIZE; i = i + 1) begin : credit_cnt_gen_block
        always @ (posedge clk) begin
            if (!rst_n) credit_cnt_r[i] <= 0;
            else begin
                if (read_i[i] & empty_n_i[i]) begin
                    if (send_credit) begin
                        credit_cnt_r[i] <= 1;
                    end else begin
                        credit_cnt_r[i] <= credit_cnt_r[i] + 1;
                    end
                end
                else if (send_credit) begin
                    credit_cnt_r[i] <= 0;
                end
            end
        end
        // loaded enough credits -- half of the buffer size
        assign credits_loaded[i] = credit_cnt_r[i] == (INIT_CREDIT >> 1);
        assign credits_present[i] = credit_cnt_r[i] > 0;
    end
endgenerate

integer j;
always @ (posedge clk) begin
    if (!rst_n) begin
        for (j = 0; j < GROUP_SIZE; j = j + 1) begin
            credit_o_r[j] <= 0;
        end
        credit_valid_o_r <= 0;
    end else begin
        for (j = 0; j < GROUP_SIZE; j = j + 1) begin
            if (send_credit) begin
                credit_o_r[j] <= credit_cnt_r[j];
            end
            else begin
                credit_o_r[j] <= credit_o_r[j];
            end
        end

        credit_valid_o_r <= credit_valid_o_r;
        if (credit_sent) begin
            credit_valid_o_r <= 1'b0;
        end
        else if (send_credit) begin
            credit_valid_o_r <= 1'b1;
        end
    end
end

assign credit_valid_o = credit_valid_o_r;
generate
    for (i = 0; i < GROUP_SIZE; i = i + 1) begin : credit_o_assign_block
        assign credit_o[i] = credit_o_r[i];
    end
endgenerate

endmodule
""",
        "metadata": None,
        "submodules_module_names": [],
    }


def pipeline_credit_ret(grouped_mod_ir: dict[str, Any]) -> None:
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
                    {
                        "module_name": IREnum.PIPELINE.value,
                        "inst_name": f"{fifo_name}_credit_pipeline",
                    },
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


def credit_ret_over_noc(ir: dict[str, Any], grouped_mod_name: str) -> None:
    """Use NoC for the credit return wires in the Rapidstream IR.

    Returns None.
    """
    # the following mutable variables can be modified in place
    parse_top_mod(ir)
    parse_mod(ir, grouped_mod_name)


def add_credit_control_master(
    grouped_mod_ir: dict[str, Any], init_credit: str, noc_fifos: list[dict[str, Any]]
) -> None:
    """Modifies the Rapidstream IR to add credit-based master controllers.

    Returns None.
    """
    for fifo in noc_fifos:
        if IREnum.NMU.value in fifo["name"]:
            fifo_name = fifo["name"][4:]
            grouped_mod_ir["submodules"].append(
                create_module_inst_ir(
                    {
                        "module_name": "credit_control_master",
                        "inst_name": f"{fifo_name}_credit_control_master",
                        "floorplan_region": find_repr(
                            fifo["parameters"], IREnum.HEAD_REGION.value
                        ).strip('"'),
                    },
                    {
                        "INIT_CREDIT": init_credit,
                        "CREDIT_CNT_WIDTH": str(int(init_credit).bit_length()),
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

            # sets the inter-slot FIFO DEPTH
            set_expr(
                fifo["parameters"], IREnum.DEPTH.value, create_lit_expr(init_credit)
            )


def add_credit_control_slave(
    grouped_mod_ir: dict[str, Any], init_credit: str, noc_fifos: list[dict[str, Any]]
) -> None:
    """Modifies the Rapidstream IR to add credit-based slave controllers.

    Returns None.
    """
    for fifo in noc_fifos:
        if IREnum.NSU.value in fifo["name"]:
            fifo_name = fifo["name"][4:]
            nsu_if_empty_n = find_repr(fifo["connections"], IREnum.IF_EMPTY_N.value)
            nsu_if_read = find_repr(fifo["connections"], IREnum.IF_READ.value)

            grouped_mod_ir["submodules"].append(
                create_module_inst_ir(
                    {
                        "module_name": "credit_control_slave",
                        "inst_name": f"{fifo_name}_credit_control_slave",
                        "floorplan_region": find_repr(
                            fifo["parameters"], IREnum.HEAD_REGION.value
                        ).strip('"'),
                    },
                    {
                        "INIT_CREDIT": init_credit,
                        "CREDIT_CNT_WIDTH": str(int(init_credit).bit_length()),
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
                    str((int(init_credit).bit_length() - 1)),
                    "0",
                ),
            ]

            # sets the inter-slot FIFO DEPTH
            set_expr(
                fifo["parameters"], IREnum.DEPTH.value, create_lit_expr(init_credit)
            )


def add_credit_control(
    ir: dict[str, Any],
    grouped_mod_name: str,
    init_credit: str,
    credit_return: CreditReturnEnum,
) -> None:
    """Modifies the Rapidstream IR to add credit-based master and slave controllers.

    Returns None.
    """

    # the following mutable variables can be modified in place
    top_ir = parse_top_mod(ir)
    grouped_mod_ir = parse_mod(ir, grouped_mod_name)

    # adds the reset ports
    grouped_mod_ir["ports"].append(create_port_ir("ap_rst_n", "input wire", "0", "0"))
    for m in top_ir["submodules"]:
        if m["module"] == grouped_mod_name:
            m["connections"].append(create_port_wire_connection("ap_rst_n", "ap_rst_n"))

    noc_fifos = grouped_mod_ir["submodules"]
    add_credit_control_master(grouped_mod_ir, init_credit, noc_fifos)
    # add credit control master module definition
    ir["modules"]["module_definitions"].append(
        create_credit_control_master({"INIT_CREDIT": "15", "CREDIT_CNT_WIDTH": "4"})
    )

    # if credit return wires are neither pipelined or put over NoC,
    # the default is direct connection.
    if credit_return == CreditReturnEnum.PIPELINE:
        add_credit_control_slave(grouped_mod_ir, init_credit, noc_fifos)
        # add credit control slave module definition
        ir["modules"]["module_definitions"].append(
            create_credit_control_slave(
                {"INIT_CREDIT": "15", "CREDIT_CNT_WIDTH": "4", "TIMER_WIDTH": "5"}
            )
        )
        pipeline_credit_ret(grouped_mod_ir)
    elif credit_return == CreditReturnEnum.NOC:
        # add credit control slave module definition
        ir["modules"]["module_definitions"].append(
            create_credit_control_slave_group(
                {
                    "INIT_CREDIT": "15",
                    "CREDIT_CNT_WIDTH": "4",
                    "TIMER_WIDTH": "5",
                    "GROUP_SIZE": "",
                }
            )
        )
        credit_ret_over_noc(ir, grouped_mod_name)


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
        m_axis_ports = create_m_axis_ports(
            fifo["name"], fifo_params[IREnum.DATA_WIDTH.value]
        )
        axis_noc_ports += list(m_axis_ports.values())
        s_axis_ports = create_s_axis_ports(
            fifo["name"], fifo_params[IREnum.DATA_WIDTH.value]
        )
        axis_noc_ports += list(s_axis_ports.values())

        # create the NMU fifo
        # new_modules.append(create_nmu_fifo_ir(fifo, fifo_params, m_axis_ports))
        new_modules.append(
            create_module_inst_ir(
                {
                    "module_name": IREnum.PIPELINE.value,
                    "inst_name": f'{IREnum.NMU.value}_{fifo["name"]}',
                    "pragmas": fifo["pragmas"],
                },
                {
                    "BODY_LEVEL": "0",
                    "DATA_WIDTH": fifo_params[IREnum.DATA_WIDTH.value],
                    "DEPTH": str(int(fifo_params[IREnum.DEPTH.value]) // 2),
                    "EXTRA_PIPELINE_BEFORE_TAIL": "0",
                    "PIPELINE_READY_IN_HEAD": "1",
                    "PIPELINE_VALID_AND_DATA_IN_HEAD": "1",
                }
                | set_all_pipeline_regions(fifo_params[IREnum.HEAD_REGION.value]),
                {
                    "clk": "ap_clk",
                    "if_read": m_axis_ports["tready"]["name"],
                    "if_dout": m_axis_ports["tdata"]["name"],
                    "if_empty_n": m_axis_ports["tvalid"]["name"],
                    "if_write": find_expr(fifo["connections"], "if_write"),
                    "if_din": find_expr(fifo["connections"], "if_din"),
                    "if_full_n": find_expr(fifo["connections"], "if_full_n"),
                },
                {"reset": "1'b0"},
            )
        )

        # create the NSU fifo
        # new_modules.append(create_nsu_fifo_ir(fifo, fifo_params, s_axis_ports))
        new_modules.append(
            create_module_inst_ir(
                {
                    "module_name": IREnum.PIPELINE.value,
                    "inst_name": f'{IREnum.NSU.value}_{fifo["name"]}',
                },
                {
                    "BODY_LEVEL": "0",
                    "DATA_WIDTH": fifo_params[IREnum.DATA_WIDTH.value],
                    "DEPTH": str(int(fifo_params[IREnum.DEPTH.value]) // 2),
                    "EXTRA_PIPELINE_BEFORE_TAIL": "0",
                    "PIPELINE_READY_IN_HEAD": "1",
                    "PIPELINE_VALID_AND_DATA_IN_HEAD": "1",
                }
                | set_all_pipeline_regions(fifo_params[IREnum.TAIL_REGION.value]),
                {
                    "clk": "ap_clk",
                    "if_read": find_expr(fifo["connections"], "if_read"),
                    "if_dout": find_expr(fifo["connections"], "if_dout"),
                    "if_empty_n": find_expr(fifo["connections"], "if_empty_n"),
                    "if_write": s_axis_ports["tvalid"]["name"],
                    "if_din": s_axis_ports["tdata"]["name"],
                    "if_full_n": s_axis_ports["tready"]["name"],
                },
                {"reset": "1'b0"},
            )
        )

        # drive tlast with constant 1
        new_modules.append(
            create_module_inst_ir(
                {
                    "module_name": "Const_1_Driver",
                    "inst_name": f"{fifo['name']}_tlast_inst",
                },
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
    add_credit_control(new_ir, grouped_mod_name, "12", CreditReturnEnum.PIPELINE)

    return new_ir


if __name__ == "__main__":
    import json
    import subprocess

    TEST_DIR = "/home/jakeke/rapidstream-noc/test/build_a48_grb"
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
