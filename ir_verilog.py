"""Helper functions to create Verilog modules in Rapidstream IR."""

__copyright__ = """
Copyright (c) 2024 RapidStream Design Automation, Inc. and contributors.
All rights reserved. The contributor(s) of this file has/have agreed to the
RapidStream Contributor License Agreement.
"""

from typing import Any

from ir_helper import create_parameter_ir, create_port_ir


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


def create_cc_master(params: dict[str, str]) -> dict[str, Any]:
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


def create_cc_slave(params: dict[str, str]) -> dict[str, Any]:
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


def create_cc_slave_group(params: dict[str, str]) -> dict[str, Any]:
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
