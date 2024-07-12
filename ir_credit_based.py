"""Helper functions to create credit-based Verilog controller modules in Rapidstream IR."""

__copyright__ = """
Copyright (c) 2024 RapidStream Design Automation, Inc. and contributors.
All rights reserved. The contributor(s) of this file has/have agreed to the
RapidStream Contributor License Agreement.
"""

import math
from typing import Any

from ir_helper import (
    FREQUENCY,
    CreditReturnEnum,
    IREnum,
    create_id_expr,
    create_id_expr_slice,
    create_lit_expr,
    create_m_axis_ports,
    create_module_inst_ir,
    create_port_ir,
    create_port_wire_connection,
    create_s_axis_ports,
    create_wire_ir,
    find_repr,
    get_credit_return_regions,
    parse_fifo_rs_routes,
    parse_mod,
    parse_top_mod,
    set_all_pipeline_regions,
    set_expr,
    split_slot_region,
)
from ir_verilog import create_cc_master, create_cc_slave, create_cc_slave_group


def add_cc_master(grouped_mod_ir: dict[str, Any], init_credit: str) -> None:
    """Modifies the Rapidstream IR to add credit-based master controllers.

    Returns None.
    """
    for fifo in grouped_mod_ir["submodules"]:
        if IREnum.NMU.value in fifo["name"]:
            fifo_name = fifo["name"].replace(IREnum.NMU.value, "")
            grouped_mod_ir["submodules"].append(
                create_module_inst_ir(
                    {
                        "module_name": "credit_control_master",
                        "inst_name": f"{fifo_name}{IREnum.CC_MASTER.value}",
                        "floorplan_region": find_repr(
                            fifo["parameters"], IREnum.HEAD_REGION.value
                        ).strip('"'),
                    },
                    {
                        "INIT_CREDIT": init_credit,
                        "CREDIT_CNT_WIDTH": str(int(init_credit).bit_length()),
                    },
                    {
                        "clk": ["ap_clk"],
                        "rst_n": ["ap_rst_n"],
                        "credit_valid_i": [f"{fifo_name}_slave_credit_valid_o"],
                        "credit_i": [f"{fifo_name}_slave_credit_o"],
                        "empty_n_i": [f"nmu_{fifo_name}_empty_n"],
                        "tready_i": [f"m_axis_{fifo_name}_tready"],
                        "read_o": [f"nmu_{fifo_name}_read"],
                        "tvalid_o": [f"m_axis_{fifo_name}_tvalid"],
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
                create_id_expr([f"nmu_{fifo_name}_empty_n"]),
            )
            set_expr(
                fifo["connections"],
                IREnum.IF_READ.value,
                create_id_expr([f"nmu_{fifo_name}_read"]),
            )

            # sets the inter-slot FIFO DEPTH
            # set_expr(
            #     fifo["parameters"], IREnum.DEPTH.value, create_lit_expr(init_credit)
            # )


def add_cc_slave(
    grouped_mod_ir: dict[str, Any],
    init_credit: str,
    timer_width: str,
) -> None:
    """Modifies the Rapidstream IR to add credit-based slave controllers.

    Returns None.
    """
    for fifo in grouped_mod_ir["submodules"]:
        if IREnum.NSU.value in fifo["name"]:
            fifo_name = fifo["name"].replace(IREnum.NSU.value, "")
            nsu_if_empty_n = find_repr(fifo["connections"], IREnum.IF_EMPTY_N.value)
            nsu_if_read = find_repr(fifo["connections"], IREnum.IF_READ.value)

            grouped_mod_ir["submodules"].append(
                create_module_inst_ir(
                    {
                        "module_name": "credit_control_slave",
                        "inst_name": f"{fifo_name}_cc_slave",
                        "floorplan_region": find_repr(
                            fifo["parameters"], IREnum.HEAD_REGION.value
                        ).strip('"'),
                    },
                    {
                        "INIT_CREDIT": init_credit,
                        "CREDIT_CNT_WIDTH": str(int(init_credit).bit_length()),
                        "TIMER_WIDTH": timer_width,
                    },
                    {
                        "clk": ["ap_clk"],
                        "rst_n": ["ap_rst_n"],
                        "read_i": [nsu_if_read],
                        "empty_n_i": [nsu_if_empty_n],
                        "credit_valid_o": [f"{fifo_name}_slave_credit_valid_o"],
                        "credit_o": [f"{fifo_name}_slave_credit_o"],
                    },
                    {},
                )
            )

            grouped_mod_ir["wires"] += [
                create_wire_ir(f"{fifo_name}_slave_credit_valid_o", "0", "0"),
                create_wire_ir(
                    f"{fifo_name}_slave_credit_o",
                    str(int(init_credit).bit_length() - 1),
                    "0",
                ),
            ]

            # sets the inter-slot FIFO DEPTH
            set_expr(
                fifo["parameters"], IREnum.DEPTH.value, create_lit_expr(init_credit)
            )


def add_cc_slave_group(
    grouped_mod_ir: dict[str, Any],
    init_credit: str,
    timer_width: str,
) -> dict[tuple[str, str], list[str]]:
    """Modifies the Rapidstream IR to add the credit-based slave group controllers.

    Returns None.
    """

    def get_srcdest_grp(
        submodules: list[dict[str, Any]],
    ) -> dict[tuple[str, str], list[str]]:
        # group the FIFOs by source-dest pair
        # source is the slot region of NSU FIFO
        # dest is the slot region of NMU FIFO
        srcdest_by_fifo = {}
        for fifo in submodules:
            if IREnum.NMU.value in fifo["name"]:
                n = fifo["name"].replace(IREnum.NMU.value, "")
                region = find_repr(fifo["parameters"], IREnum.HEAD_REGION.value)
                region = region.strip('"')
                srcdest_by_fifo[n] = (region, region)

        for fifo in submodules:
            if IREnum.NSU.value in fifo["name"]:
                n = fifo["name"].replace(IREnum.NSU.value, "")
                region = find_repr(fifo["parameters"], IREnum.HEAD_REGION.value)
                region = region.strip('"')
                srcdest_by_fifo[n] = (region,) + srcdest_by_fifo[n][1:]

        fifo_by_srcdest = {}
        for n, srcdest in srcdest_by_fifo.items():
            if srcdest not in fifo_by_srcdest:
                fifo_by_srcdest[srcdest] = [n]
            else:
                fifo_by_srcdest[srcdest].append(n)
        return fifo_by_srcdest

    fifo_by_srcdest = get_srcdest_grp(grouped_mod_ir["submodules"])

    def get_conn_dict(
        submodules: list[dict[str, Any]], key: str
    ) -> dict[str, list[dict[str, Any]]]:
        conn_dict = {}
        for fifo in submodules:
            if key in fifo["name"]:
                name = fifo["name"].replace(key, "")
                conn_dict[name] = fifo["connections"]
        return conn_dict

    cc_master_conn = get_conn_dict(grouped_mod_ir["submodules"], IREnum.CC_MASTER.value)
    nsu_conn = get_conn_dict(grouped_mod_ir["submodules"], IREnum.NSU.value)

    for srcdest, fifo_names in fifo_by_srcdest.items():
        merged_name = (
            f"{split_slot_region(srcdest[0])}_TO_{split_slot_region(srcdest[1])}"
        )
        cc_cnt_width = str(int(init_credit).bit_length())
        # round up to multiples of eight (Bytes) otherwise Vivado will round down
        cc_ret_width = str(math.ceil((int(cc_cnt_width) * len(fifo_names)) / 8) * 8)

        # grouped slave credit controller
        grouped_mod_ir["submodules"].append(
            create_module_inst_ir(
                {
                    "module_name": "credit_control_slave_group",
                    "inst_name": f"{merged_name}_cc_slave_group",
                    "floorplan_region": srcdest[0],
                },
                {
                    "INIT_CREDIT": init_credit,
                    "CREDIT_CNT_WIDTH": cc_cnt_width,
                    "TIMER_WIDTH": timer_width,
                    "GROUP_SIZE": str(len(fifo_names)),
                },
                {
                    "clk": ["ap_clk"],
                    "rst_n": ["ap_rst_n"],
                    "read_i": [
                        find_repr(nsu_conn[n], IREnum.IF_READ.value) for n in fifo_names
                    ],
                    "empty_n_i": [
                        find_repr(nsu_conn[n], IREnum.IF_EMPTY_N.value)
                        for n in fifo_names
                    ],
                    "ready_i": [f"{merged_name}_slave_credit_pp_full_n_i"],
                    "credit_valid_o": [f"{merged_name}_slave_credit_valid_o"],
                    "credit_o": [f"{merged_name}_slave_credit_o"],
                },
                {},
            )
        )

        # credit return NMU pipeline
        grouped_mod_ir["submodules"].append(
            create_module_inst_ir(
                {
                    "module_name": IREnum.PIPELINE.value,
                    "inst_name": f"nmu_{merged_name}{IREnum.CC_RET.value}",
                },
                {
                    "BODY_LEVEL": "1",
                    "DATA_WIDTH": cc_ret_width,
                    "DEPTH": "1",
                    "EXTRA_PIPELINE_BEFORE_TAIL": "0",
                    "PIPELINE_READY_IN_HEAD": "1",
                    "PIPELINE_VALID_AND_DATA_IN_HEAD": "1",
                }
                | set_all_pipeline_regions(srcdest[0]),
                {
                    "clk": ["ap_clk"],
                    "if_write": [f"{merged_name}_slave_credit_valid_o"],
                    "if_din": [f"{merged_name}_slave_credit_o"],
                    "if_full_n": [f"{merged_name}_slave_credit_pp_full_n_i"],
                    "if_read": [f"m_axis_{merged_name}_cc_ret_tready"],
                    "if_dout": [f"m_axis_{merged_name}_cc_ret_tdata"],
                    "if_empty_n": [f"m_axis_{merged_name}_cc_ret_tvalid"],
                },
                {
                    "reset": "1'b0",
                },
            )
        )

        # credit return NSU pipeline
        grouped_mod_ir["submodules"].append(
            create_module_inst_ir(
                {
                    "module_name": IREnum.PIPELINE.value,
                    "inst_name": f"nsu_{merged_name}{IREnum.CC_RET.value}",
                },
                {
                    "BODY_LEVEL": "1",
                    "DATA_WIDTH": cc_ret_width,
                    "DEPTH": "1",
                    "EXTRA_PIPELINE_BEFORE_TAIL": "0",
                    "PIPELINE_READY_IN_HEAD": "1",
                    "PIPELINE_VALID_AND_DATA_IN_HEAD": "1",
                }
                | set_all_pipeline_regions(srcdest[1]),
                {
                    "clk": ["ap_clk"],
                    "if_write": [f"s_axis_{merged_name}_cc_ret_tvalid"],
                    "if_din": [f"s_axis_{merged_name}_cc_ret_tdata"],
                    "if_full_n": [f"s_axis_{merged_name}_cc_ret_tready"],
                    "if_dout": [f"{merged_name}_master_credit_i"],
                    "if_empty_n": [f"{merged_name}_master_credit_valid_i"],
                },
                {
                    "if_read": "1'b1",
                    "reset": "1'b0",
                },
            )
        )

        # assign cc_master credit return inputs
        for i, n in enumerate(fifo_names[::-1]):  # little endian
            set_expr(
                cc_master_conn[n],
                "credit_i",
                create_id_expr_slice(
                    f"{merged_name}_master_credit_i",
                    str((i + 1) * int(cc_cnt_width) - 1),
                    str(i * int(cc_cnt_width)),
                ),
            )
            set_expr(
                cc_master_conn[n],
                "credit_valid_i",
                create_id_expr([f"{merged_name}_master_credit_valid_i"]),
            )

        grouped_mod_ir["wires"] += [
            create_wire_ir(f"{merged_name}_slave_credit_pp_full_n_i", "0", "0"),
            create_wire_ir(f"{merged_name}_slave_credit_valid_o", "0", "0"),
            create_wire_ir(
                f"{merged_name}_slave_credit_o",
                str(int(cc_ret_width) - 1),
                "0",
            ),
            create_wire_ir(f"{merged_name}_master_credit_valid_i", "0", "0"),
            create_wire_ir(
                f"{merged_name}_master_credit_i",
                str(int(cc_ret_width) - 1),
                "0",
            ),
        ]

    return fifo_by_srcdest


def pipeline_credit_ret(grouped_mod_ir: dict[str, Any]) -> None:
    """Pipeline the credit return wires in the Rapidstream IR.

    Returns None.
    """
    rs_routes = parse_fifo_rs_routes(grouped_mod_ir)
    new_modules = []
    for mod in grouped_mod_ir["submodules"]:
        if IREnum.CC_MASTER.value in mod["name"]:
            fifo_name = mod["name"].replace(IREnum.CC_MASTER.value, "")
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
                        "clk": ["ap_clk"],
                        "if_din": [f"{fifo_name}_slave_credit_o"],
                        "if_dout": [f"{fifo_name}_master_credit_i"],
                        "if_empty_n": [f"{fifo_name}_master_credit_valid_i"],
                        "if_write": [f"{fifo_name}_slave_credit_valid_o"],
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
                create_id_expr([f"{fifo_name}_master_credit_i"]),
            )
            set_expr(
                mod["connections"],
                "credit_valid_i",
                create_id_expr([f"{fifo_name}_master_credit_valid_i"]),
            )

    grouped_mod_ir["submodules"] += new_modules


def credit_ret_over_noc(
    ir: dict[str, Any],
    grouped_mod_name: str,
    init_credit: str,
    srcdest_fifos: dict[tuple[str, str], list[str]],
) -> dict[str, dict[str, str]]:
    """Use NoC for the credit return wires in the Rapidstream IR.

    Returns None.
    """
    top_ir = parse_top_mod(ir)
    grouped_mod_ir = parse_mod(ir, grouped_mod_name)

    # add ports
    axis_noc_ports = []
    cc_ret_noc_stream = {}
    for srcdest, fifos in srcdest_fifos.items():
        merged_name = (
            f"{split_slot_region(srcdest[0])}_TO_{split_slot_region(srcdest[1])}"
        )
        cc_ret_width = math.ceil(int(init_credit).bit_length() * len(fifos) / 8) * 8

        # create AXIS-NoC ports
        axis_noc_ports += list(
            create_m_axis_ports(f"{merged_name}_cc_ret", str(cc_ret_width)).values()
        )
        axis_noc_ports += list(
            create_s_axis_ports(f"{merged_name}_cc_ret", str(cc_ret_width)).values()
        )

        # drive tlast with constant 1
        grouped_mod_ir["submodules"].append(
            create_module_inst_ir(
                {
                    "module_name": "Const_1_Driver",
                    "inst_name": f"{merged_name}_cc_ret_tlast_inst",
                },
                {},
                {"out": [f"m_axis_{merged_name}_cc_ret_tlast"]},
                {},
            )
        )

        # return NoC attributes: src, dest, bandwidth, width
        cc_ret_noc_stream[f"{merged_name}{IREnum.CC_RET.value}"] = {
            "src": srcdest[0],
            "dest": srcdest[1],
            "width": str(cc_ret_width),
            "bandwidth": str(cc_ret_width * FREQUENCY / 8),
        }

    for m in grouped_mod_ir["submodules"]:
        if IREnum.NSU.value in m["name"] and IREnum.CC_RET.value not in m["name"]:
            # sets the inter-slot NSU FIFO DEPTH
            set_expr(m["parameters"], IREnum.DEPTH.value, create_lit_expr(init_credit))

    grouped_mod_ir["ports"] += axis_noc_ports

    # create top level AXIS-NoC ports
    top_ir["ports"] += axis_noc_ports
    # connect them to the grouped_module
    for m in top_ir["submodules"]:
        if m["module"] == grouped_mod_name:
            for p in axis_noc_ports:
                m["connections"].append(
                    create_port_wire_connection(p["name"], [p["name"]])
                )

    return cc_ret_noc_stream


def add_credit_control(
    ir: dict[str, Any],
    grouped_mod_name: str,
    init_credit: str,
    timer_width: str,
    credit_return: CreditReturnEnum,
) -> dict[str, dict[str, str]]:
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
            m["connections"].append(
                create_port_wire_connection("ap_rst_n", ["ap_rst_n"])
            )

    # save the original grouped pipeline submodules
    add_cc_master(grouped_mod_ir, init_credit)
    # add credit control master module definition
    ir["modules"]["module_definitions"].append(
        create_cc_master({"INIT_CREDIT": "15", "CREDIT_CNT_WIDTH": "4"})
    )

    # if credit return wires are neither pipelined or put over NoC,
    # the default is direct connection.
    if credit_return != CreditReturnEnum.NOC:
        add_cc_slave(grouped_mod_ir, init_credit, timer_width)
        # add credit control slave module definition
        ir["modules"]["module_definitions"].append(
            create_cc_slave(
                {"INIT_CREDIT": "15", "CREDIT_CNT_WIDTH": "4", "TIMER_WIDTH": "5"}
            )
        )
        if credit_return == CreditReturnEnum.PIPELINE:
            pipeline_credit_ret(grouped_mod_ir)
        return {}

    srcdest_fifos = add_cc_slave_group(grouped_mod_ir, init_credit, timer_width)
    # add credit control slave module definition
    ir["modules"]["module_definitions"].append(
        create_cc_slave_group(
            {
                "INIT_CREDIT": "15",
                "CREDIT_CNT_WIDTH": "4",
                "TIMER_WIDTH": "5",
                "GROUP_SIZE": "4",
            }
        )
    )
    return credit_ret_over_noc(ir, grouped_mod_name, init_credit, srcdest_fifos)
