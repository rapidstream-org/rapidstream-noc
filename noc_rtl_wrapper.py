"""Create Verilog wrapper modules to use NoC in Rapidstream IR."""

__copyright__ = """
Copyright (c) 2024 RapidStream Design Automation, Inc. and contributors.
All rights reserved. The contributor(s) of this file has/have agreed to the
RapidStream Contributor License Agreement.
"""

import copy
from typing import Any

from ir_helper import (
    PIPELINE_MAPPING,
    IREnum,
    create_m_axis_ports,
    create_module_inst_ir,
    create_port_wire_connection,
    create_s_axis_ports,
    find_repr_id,
    parse_fifo_params,
    parse_mod,
    parse_top_mod,
    round_up_to_noc_tdata,
    set_all_pipeline_regions,
)
from ir_verilog import create_const_one_driver


def add_dont_touch(ir: dict[str, Any]) -> None:
    """Adds dont_touch to the top-level's pipelining registers.

    Returns None.
    """
    top_ir = parse_top_mod(ir)
    for mod in top_ir["submodules"]:
        if any(IREnum.REGION.value in p["name"] for p in mod["parameters"]):
            print(f"Add dont_touch to {mod['name']}")
            module_name = mod["module"]
            mod["module"] = '(* dont_touch = "true" *) ' + module_name


def add_dont_touch_pp_grp(ir: dict[str, Any]) -> None:
    """Adds dont_touch to the pipeline group module's BODY registers.

    Returns None.
    """
    for mod in ir["modules"]["module_definitions"]:
        if mod["name"] in PIPELINE_MAPPING:
            print(f"Add dont_touch to {mod['name']} BODY registers")
            for m in mod["submodules"]:
                if IREnum.BODY.value in m["name"]:
                    module_name = m["module"]
                    print(m["name"])
                    m["module"] = '(* dont_touch = "true" *) ' + module_name


def noc_rtl_wrapper(
    ir: dict[str, Any], grouped_mod_name: str
) -> tuple[dict[str, Any], dict[str, dict[str, str]]]:
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
            fifo["name"],
            round_up_to_noc_tdata(fifo_params[IREnum.DATA_WIDTH.value], False),
        )
        axis_noc_ports += list(m_axis_ports.values())
        s_axis_ports = create_s_axis_ports(
            fifo["name"],
            round_up_to_noc_tdata(fifo_params[IREnum.DATA_WIDTH.value], False),
        )
        axis_noc_ports += list(s_axis_ports.values())

        # create the NMU fifo
        new_modules.append(
            create_module_inst_ir(
                {
                    "module_name": IREnum.PIPELINE.value,
                    "inst_name": f'{IREnum.NMU.value}{fifo["name"]}',
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
                    "clk": ["ap_clk"],
                    "if_read": [m_axis_ports["tready"]["name"]],
                    "if_dout": [m_axis_ports["tdata"]["name"]],
                    "if_empty_n": [m_axis_ports["tvalid"]["name"]],
                    "if_write": [find_repr_id(fifo["connections"], "if_write")],
                    "if_din": [find_repr_id(fifo["connections"], "if_din")],
                    "if_full_n": [find_repr_id(fifo["connections"], "if_full_n")],
                },
                {"reset": "1'b0"},
            )
        )

        # create the NSU fifo
        new_modules.append(
            create_module_inst_ir(
                {
                    "module_name": IREnum.PIPELINE.value,
                    "inst_name": f'{IREnum.NSU.value}{fifo["name"]}',
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
                    "clk": ["ap_clk"],
                    "if_read": [find_repr_id(fifo["connections"], "if_read")],
                    "if_dout": [find_repr_id(fifo["connections"], "if_dout")],
                    "if_empty_n": [find_repr_id(fifo["connections"], "if_empty_n")],
                    "if_write": [s_axis_ports["tvalid"]["name"]],
                    "if_din": [s_axis_ports["tdata"]["name"]],
                    "if_full_n": [s_axis_ports["tready"]["name"]],
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
                {"out": [m_axis_ports["tlast"]["name"]]},
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
                    create_port_wire_connection(p["name"], [p["name"]])
                )

            # remove the grouped mod if empty to avoid the Vivado black-box impl error
            if len(m["connections"]) == 0:
                top_ir["submodules"].remove(m)
            break

    # add const 1 driver module definition
    new_ir["modules"]["module_definitions"].append(create_const_one_driver())

    # add credit-based controllers to each NMU and NSU FIFOs
    cc_ret_noc_stream: dict[str, dict[str, str]] = {}  # no credit controllers
    # cc_ret_noc_stream = add_credit_control(
    #     new_ir, grouped_mod_name, "12", "5", CreditReturnEnum.NOC
    # )
    add_dont_touch(new_ir)

    return new_ir, cc_ret_noc_stream


if __name__ == "__main__":
    import json
    import subprocess

    TEST_DIR = "/home/jakeke/rapidstream-noc/test/serpens48_grb5"
    NOC_PASS_JSON = "noc_pass.json"
    NOC_PASS_WRAPPER_JSON = "noc_pass_wrapper.json"
    with open(f"{TEST_DIR}/{NOC_PASS_JSON}", "r", encoding="utf-8") as file:
        design = json.load(file)

    new_serpens_ir, _ = noc_rtl_wrapper(design, "axis_noc_if")

    with open(f"{TEST_DIR}/{NOC_PASS_WRAPPER_JSON}", "w", encoding="utf-8") as file:
        json.dump(new_serpens_ir, file, indent=4)

    zsh_cmds = f"""
rm -rf {TEST_DIR}/rtl
rapidstream-exporter -i {TEST_DIR}/{NOC_PASS_WRAPPER_JSON} -f {TEST_DIR}/rtl
"""
    # generate rtl folder
    print(zsh_cmds)
    subprocess.run(["zsh", "-c", zsh_cmds], check=True)
