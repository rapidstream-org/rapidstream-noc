"""Generates Vivado block designs to run RTL simulation and generate bitstreams.

As of 2023.2, Vitis only supports HLS kernels to use Versal NoC for memory (LPDDR/DDR).
This module enables HLS kernels to use Versal NoC between their sub-modules.
It dumps tcl files to create Vivado block designs for running simulation and generating
bitstreams. This module avoids the Vitis platform flow, and uses Vivado block designs
for directly instantiating NoC IPs. The HLS kernel should use top-level ports to infer
NoC connection between sub-modules. This module will use the AXI Stream NoC to connect
the sub-modules.

The Microblaze block design uses the 64-bit Microblaze as the host. Users should export
the pre-synthesis hardware to Vitis, and writes the bare-metal C program to send test
inputs to DUT and memory.

The ARM block design can be simulated by writing a CIPS VIP testbench,
and can be directly synthesized and implemented to run on the board.
"""

__copyright__ = """
Copyright (c) 2024 RapidStream Design Automation, Inc. and contributors.
All rights reserved. The contributor(s) of this file has/have agreed to the
RapidStream Contributor License Agreement.
"""


from ir_helper import VALID_TDATA_NUM_BYTES, round_up_to_noc_tdata
from vivado_bd_helper import (
    arm_ddr_tcl,
    arm_hbm_tcl,
    arm_tcl,
    assign_arm_bd_address,
    proc_tcl,
)


def dut_mmap_tcl(
    mmap_ports: dict[str, dict[str, int]],
    hbm: bool,
    hbm_init_file: str,
) -> list[str]:
    """Adds DUT's MMAP ports related tcl commands to the block design.

    Returns a list of tcl commands.
    """
    tcl = []
    if hbm:
        # if using regular NoC slave ports
        # CONFIG.NUM_SI {{{len(mmap_ports)+8}}} \
        tcl += [
            f"""
startgroup

set_property -dict [list \
    CONFIG.NUM_HBM_BLI {{{len(mmap_ports)}}} \
    CONFIG.NUM_CLKS {{9}} \
    CONFIG.HBM_MEM_BACKDOOR_WRITE {{true}} \
    CONFIG.HBM_MEM_INIT_FILE {{{hbm_init_file}}} \
] $noc_hbm_0
"""
        ]

        # counters to even the usage of hbm ports of each bank
        hbm_bank_cnt = {}
        for i in range(32):
            # initialize with CIPS connections
            hbm_bank_cnt[i] = 1
    else:
        tcl += [
            f"""
# Create mmap noc
startgroup
set axi_noc_dut [ create_bd_cell -type ip -vlnv xilinx.com:ip:axi_noc:1.0 axi_noc_dut ]

set_property -dict [list \
    CONFIG.NUM_CLKS {{1}} \
    CONFIG.NUM_MI {{0}} \
    CONFIG.NUM_NMI {{1}} \
    CONFIG.NUM_NSI {{0}} \
    CONFIG.NUM_SI {{{len(mmap_ports)}}} \
] $axi_noc_dut
"""
        ]

    # Configure and connect mmap noc
    all_busif_ports = []
    for i, (port, attr) in enumerate(mmap_ports.items()):
        if hbm:
            bank = attr["bank"]
            port_idx = bank % 2 * 2 + hbm_bank_cnt[bank] % 2
            hbm_bank_cnt[bank] += 1
            hbm_port = f"HBM{bank // 2}_PORT{port_idx}"
            # if using HBM NoC slave ports
            noc_s_port = f"HBM{i:02d}_AXI"

            # if using regular NoC slave ports with smartconnect
            # noc_s_port = f"S{(i + 8):02d}_AXI"
            #             tcl += [
            #                 f"""
            # create_bd_cell -type ip -vlnv xilinx.com:ip:smartconnect:1.0 \
            #     smartconnect_{i}
            # set_property CONFIG.NUM_SI {{1}} [get_bd_cells smartconnect_{i}]
            # connect_bd_intf_net [get_bd_intf_pins smartconnect_{i}/S00_AXI] \
            #     [get_bd_intf_pins $dut/{port}]
            # connect_bd_net [get_bd_pins smartconnect_{i}/aclk] \
            #     [get_bd_pins clk_wizard_0/clk_out1]
            # connect_bd_net [get_bd_pins smartconnect_{i}/aresetn] \
            #     [get_bd_pins proc_sys_reset_0/peripheral_aresetn]
            # connect_bd_intf_net [get_bd_intf_pins smartconnect_{i}/M00_AXI] \
            #     [get_bd_intf_pins noc_hbm_0/HBM{i:02d}_AXI]
            # """
            #             ]

            tcl += [
                f"set_property -dict [list CONFIG.CONNECTIONS \
                    {{{hbm_port} {{read_bw {{{attr['read_bw']}}} \
                        write_bw {{{attr['write_bw']}}}}}}}] \
                    [get_bd_intf_pins $noc_hbm_0/{noc_s_port}]"
            ]

            tcl += [
                f"connect_bd_intf_net [get_bd_intf_pins $dut/{port}] \
                    [get_bd_intf_pins $noc_hbm_0/{noc_s_port}]"
            ]
        else:
            noc_s_port = f"S{i:02d}_AXI"
            tcl += [
                f"set_property -dict [list CONFIG.CONNECTIONS \
                    {{M00_INI {{read_bw {{{attr['read_bw']}}} \
                        write_bw {{{attr['write_bw']}}}}}}}] \
                    [get_bd_intf_pins /axi_noc_dut/{noc_s_port}]"
            ]

            tcl += [
                f"connect_bd_intf_net [get_bd_intf_pins $dut/{port}] \
                    [get_bd_intf_pins /axi_noc_dut/{noc_s_port}]"
            ]

        all_busif_ports.append(noc_s_port)
    s_busif_ports = ":".join(all_busif_ports)

    if hbm:
        tcl += [
            f"set_property -dict [list CONFIG.ASSOCIATED_BUSIF {{{s_busif_ports}}}] \
                [get_bd_pins $noc_hbm_0/aclk8]"
        ]
    else:
        tcl += [
            f"set_property -dict [list CONFIG.ASSOCIATED_BUSIF {{{s_busif_ports}}}] \
                [get_bd_pins /axi_noc_dut/aclk0]"
        ]

    tcl += ["endgroup"]
    return tcl


def dut_stream_noc_tcl(stream_attr: dict[str, dict[str, str]]) -> list[str]:
    """Adds DUT's AXIS NoC related tcl commands to the block design.

    Return a list of tcl commands
    """
    tcl = [
        f"""
# Create stream noc
startgroup
set axis_noc_dut [ create_bd_cell -type ip -vlnv \
    xilinx.com:ip:axis_noc:1.0 axis_noc_dut ]
set_property -dict [list \
    CONFIG.MI_TDEST_VALS {{}} \
    CONFIG.NUM_MI {{{len(stream_attr)}}} \
    CONFIG.NUM_SI {{{len(stream_attr)}}} \
    CONFIG.SI_DESTID_PINS {{}} \
    CONFIG.TDEST_WIDTH {{0}} \
] $axis_noc_dut
set_property CONFIG.ASSOCIATED_BUSIF [concat_axi_pins $axis_noc_dut] \
    [get_bd_pins axis_noc_dut/aclk0]

"""
    ]

    for i, (src, attr) in enumerate(stream_attr.items()):
        noc_m_port = f"M{i:02d}_AXIS"
        noc_s_port = f"S{i:02d}_AXIS"
        tcl += [
            f"""
set_property -dict [list CONFIG.CONNECTIONS {{{noc_m_port} \
    {{ write_bw {{{float(attr["bandwidth"]) - 50}}} write_avg_burst {{4}}}}}}] \
[get_bd_intf_pins /axis_noc_dut/{noc_s_port}]
"""
        ]

        # rounds the width up to the nearest supported TDATA_NUM_BYTES
        if ((int(attr["width"]) + 7) // 8) not in VALID_TDATA_NUM_BYTES:
            roundup_num_bytes = round_up_to_noc_tdata(attr["width"], True)

            tcl += [
                f"""
create_bd_cell -type ip -vlnv xilinx.com:ip:axis_dwidth_converter:1.1 \
    axis_dwidth_converter_to_noc_{i}
set_property CONFIG.M_TDATA_NUM_BYTES {{{roundup_num_bytes}}} \
    [get_bd_cells axis_dwidth_converter_to_noc_{i}]
# connect_bd_net [get_bd_pins axis_dwidth_converter_to_noc_{i}/aclk] \
#     [get_bd_pins clk_wizard_0/clk_out1]
connect_bd_net [get_bd_pins axis_dwidth_converter_to_noc_{i}/aclk] \
    [get_bd_pins CIPS_0/pl0_ref_clk]
connect_bd_net [get_bd_pins axis_dwidth_converter_to_noc_{i}/aresetn] \
    [get_bd_pins proc_sys_reset_0/peripheral_aresetn]
connect_bd_intf_net [get_bd_intf_pins $dut/{src}] \
    [get_bd_intf_pins axis_dwidth_converter_to_noc_{i}/S_AXIS]
connect_bd_intf_net [get_bd_intf_pins axis_dwidth_converter_to_noc_{i}/M_AXIS] \
    [get_bd_intf_pins axis_noc_dut/{noc_s_port}]

create_bd_cell -type ip -vlnv xilinx.com:ip:axis_dwidth_converter:1.1 \
    axis_dwidth_converter_to_dut_{i}
set_property -dict [list \
    CONFIG.S_TDATA_NUM_BYTES {{{roundup_num_bytes}}} \
    CONFIG.M_TDATA_NUM_BYTES {{{(int(attr["width"]) + 7) // 8}}} \
] [get_bd_cells axis_dwidth_converter_to_dut_{i}]
# connect_bd_net [get_bd_pins axis_dwidth_converter_to_dut_{i}/aclk] \
#     [get_bd_pins clk_wizard_0/clk_out1]
connect_bd_net [get_bd_pins axis_dwidth_converter_to_dut_{i}/aclk] \
    [get_bd_pins CIPS_0/pl0_ref_clk]
connect_bd_net [get_bd_pins axis_dwidth_converter_to_dut_{i}/aresetn] \
    [get_bd_pins proc_sys_reset_0/peripheral_aresetn]
connect_bd_intf_net [get_bd_intf_pins axis_noc_dut/{noc_m_port}]\
    [get_bd_intf_pins axis_dwidth_converter_to_dut_{i}/S_AXIS]
connect_bd_intf_net [get_bd_intf_pins axis_dwidth_converter_to_dut_{i}/M_AXIS] \
    [get_bd_intf_pins $dut/{attr["dest"]}]
"""
            ]
        else:
            tcl += [
                f"""
connect_bd_intf_net [get_bd_intf_pins $dut/{attr["dest"]}] \
    [get_bd_intf_pins axis_noc_dut/{noc_m_port}]

connect_bd_intf_net [get_bd_intf_pins $dut/{src}] \
    [get_bd_intf_pins axis_noc_dut/{noc_s_port}]
"""
            ]

    tcl += ["endgroup"]
    return tcl


def dut_tcl(
    top_mod: str,
    mmap_ports: dict[str, dict[str, int]],
    stream_attr: dict[str, dict[str, str]],
    hbm: bool,
    hbm_init_file: str,
) -> list[str]:
    """Adds the design-under-test (DUT) to the block diagram.

    It assumes DUT uses one clock for all top-level AXI ports.
    It assumes the configurations registers use "s_axi_control".
    The mmap ports are connected to the DDR through AXI-NoC.
    The stream ports, if any, are connected to each other through AXIS-NoC.

    Returns a list of tcl commands.
    """
    tcl = [
        f"""
# ======================= Adding DUT =======================

startgroup
# Add RTL module to BD
set dut [create_bd_cell -type module -reference {top_mod} dut_0]

# Associate AXI interfaces to clock
# Assumes there is one clock and all AXI pins use the same clock
set_property CONFIG.ASSOCIATED_BUSIF [concat_axi_pins $dut] [get_bd_clk_pins $dut]
endgroup
"""
    ]

    tcl += dut_mmap_tcl(mmap_ports, hbm, hbm_init_file)

    if stream_attr:
        tcl += dut_stream_noc_tcl(stream_attr)

    return tcl


def connect_dut_mb_tcl(stream_attr: dict[str, dict[str, str]]) -> list[str]:
    """Connects dut in the Microblaze block design.

    Returns a list of tcl commands.
    """
    tcl = [
        """
connect_bd_net [get_bd_pins sim_clk_gen_1/clk] [get_bd_clk_pins $dut]
connect_bd_net [get_bd_pins rst_clk_wiz_100M/peripheral_aresetn] [get_bd_rst_pins $dut]
connect_bd_intf_net [get_bd_intf_pins smartconnect_0/M01_AXI] \
    [get_bd_intf_pins dut_0/s_axi_control]
connect_bd_net [get_bd_pins axi_noc_dut/aclk0] [get_bd_pins sim_clk_gen_1/clk]
connect_bd_intf_net [get_bd_intf_pins axi_noc_dut/M00_INI] \
    [get_bd_intf_pins axi_noc_0/S00_INI]
"""
    ]
    if stream_attr:
        tcl += [
            "connect_bd_net [get_bd_pins axis_noc_dut/aclk0] \
                [get_bd_pins sim_clk_gen_1/clk]"
        ]
    return tcl


def connect_dut_arm_ddr_tcl(stream_attr: dict[str, dict[str, str]]) -> list[str]:
    """Connects dut in the ARM-DDR block design.

    Returns a list of tcl commands.
    """
    tcl = [
        """
# connect_bd_net [get_bd_pins clk_wizard_0/clk_out1] [get_bd_clk_pins $dut] \
#     [get_bd_pins axi_noc_dut/aclk0]
connect_bd_net [get_bd_pins CIPS_0/pl0_ref_clk] [get_bd_clk_pins $dut] \
    [get_bd_pins axi_noc_dut/aclk0]
connect_bd_net [get_bd_pins proc_sys_reset_0/peripheral_aresetn] [get_bd_rst_pins $dut]
connect_bd_intf_net [get_bd_intf_pins icn_ctrl/M01_AXI] \
    [get_bd_intf_pins dut_0/s_axi_control]
connect_bd_intf_net [get_bd_intf_pins axi_noc_dut/M00_INI] \
    [get_bd_intf_pins noc_lpddr4_1/S01_INI]
connect_bd_net [get_bd_pins dut_0/interrupt] [get_bd_pins axi_intc_0/intr]
"""
    ]
    if stream_attr:
        tcl += [
            "connect_bd_net [get_bd_pins axis_noc_dut/aclk0] \
                [get_bd_pins CIPS_0/pl0_ref_clk]"
            # "connect_bd_net [get_bd_pins axis_noc_dut/aclk0] \
            #     [get_bd_pins clk_wizard_0/clk_out1]"
        ]
    return tcl


def connect_dut_arm_hbm_tcl(stream_attr: dict[str, dict[str, str]]) -> list[str]:
    """Connects dut in the ARM-HBM block design.

    Returns a list of tcl commands.
    """
    tcl = [
        """
# Create external clk and reset ports for simulation
set pl0_ref_clk_0 [ create_bd_port -dir O -type clk pl0_ref_clk_0 ]
set pl0_resetn_0 [ create_bd_port -dir O -type rst pl0_resetn_0 ]
connect_bd_net [get_bd_pins CIPS_0/pl0_ref_clk] [get_bd_ports pl0_ref_clk_0]
connect_bd_net [get_bd_pins CIPS_0/pl0_resetn] [get_bd_ports pl0_resetn_0]

# connect_bd_net [get_bd_pins clk_wizard_0/clk_out1] [get_bd_clk_pins $dut] \
#     [get_bd_pins $noc_hbm_0/aclk8]
connect_bd_net [get_bd_pins CIPS_0/pl0_ref_clk] [get_bd_clk_pins $dut] \
    [get_bd_pins $noc_hbm_0/aclk8]
connect_bd_net [get_bd_pins proc_sys_reset_0/peripheral_aresetn] [get_bd_rst_pins $dut]
connect_bd_intf_net [get_bd_intf_pins icn_ctrl/M01_AXI] \
    [get_bd_intf_pins dut_0/s_axi_control]
connect_bd_net [get_bd_pins dut_0/interrupt] [get_bd_pins axi_intc_0/intr]
"""
    ]
    if stream_attr:
        tcl += [
            "connect_bd_net [get_bd_pins axis_noc_dut/aclk0] \
                [get_bd_pins CIPS_0/pl0_ref_clk]"
            # "connect_bd_net [get_bd_pins axis_noc_dut/aclk0] \
            #     [get_bd_pins clk_wizard_0/clk_out1]"
        ]
    return tcl


def gen_arm_bd_ddr(
    bd_attr: dict[str, str],
    mmap_ports: dict[str, dict[str, int]],
    stream_attr: dict[str, dict[str, str]],
    fpd: bool,
) -> list[str]:
    """Generates Vivado block design with ARM and LPDDR.

    Merges the tcl commands from the helper functions and dumps to a file.

    Args:
        bd_attr:        bd_name: name of the block design
                        top_mod: name of the top-level module.
                        frequency: frequency of the CIPS pl ref clk.
        mmap_ports:     list of top-level mmap ports connected to the memory.
        stream_attr:    dictionary of top-level stream ports. Keys are "src" name.
                        Values are "dest" name, "bandwidth", and "width".
        fpd:            True if using CIPS M_AXI_FPD for kernel's control_s_axi,
                        else uses CIPS LPD_AXI_NOC_0 with NoC.


    Returns a list of tcl commands.
    """
    tcl = []
    tcl += proc_tcl()
    tcl += arm_tcl(bd_attr["bd_name"], bd_attr["frequency"], False, fpd)
    tcl += arm_ddr_tcl(fpd)
    tcl += dut_tcl(
        bd_attr["top_mod"],
        mmap_ports,
        stream_attr,
        False,
        bd_attr["hbm_init_file"],
    )
    tcl += connect_dut_arm_ddr_tcl(stream_attr)
    tcl += assign_arm_bd_address()
    return tcl


def gen_arm_bd_hbm(
    bd_attr: dict[str, str],
    mmap_ports: dict[str, dict[str, int]],
    stream_attr: dict[str, dict[str, str]],
    fpd: bool,
) -> list[str]:
    """Generates Vivado block design with ARM and HBM.

    Merges the tcl commands from the helper functions and dumps to a file.

    Args:
        bd_attr:        bd_name: name of the block design
                        top_mod: name of the top-level module.
                        hbm_init_file: backdoor HBM initialization mem file.
                        frequency: frequency of the CIPS pl ref clk.
        mmap_ports:     list of top-level mmap ports connected to the memory.
        stream_attr:    dictionary of top-level stream ports. Keys are "src" name.
                        Values are "dest" name, "bandwidth", and "width".
        fpd:            True if using CIPS M_AXI_FPD for kernel's control_s_axi,
                        else uses CIPS LPD_AXI_NOC_0 with NoC.


    Returns a list of tcl commands.
    """
    tcl = []
    tcl += proc_tcl()
    tcl += arm_tcl(bd_attr["bd_name"], bd_attr["frequency"], True, fpd)
    tcl += arm_hbm_tcl(mmap_ports, fpd)
    tcl += dut_tcl(
        bd_attr["top_mod"],
        mmap_ports,
        stream_attr,
        True,
        bd_attr["hbm_init_file"],
    )
    tcl += connect_dut_arm_hbm_tcl(stream_attr)
    tcl += assign_arm_bd_address()
    return tcl


if __name__ == "__main__":
    import json

    TEST_DIR = "/home/jakeke/AutoSA/cnn_out/20x14/build/cnn20x14_none"
    TOP_MOD_NAME = "kernel0"
    I_ADD_PIPELINE_JSON = "add_pipeline.json"
    I_MMAP_PORT_JSON = "mmap_port.json"
    NOC_STREAM_ATTR_JSON = "noc_streams_attr.json"
    VIVADO_BD_TCL = "arm_bd.tcl"
    BD_NAME = "top_arm"
    USE_M_AXI_FPD = False
    IMPL_FREQUENCY = "300.0"
    HBM_INIT_FILE = "/home/jakeke/rapidstream-noc/test/serpens_hbm48_nasa4704.mem"
    with open(f"{TEST_DIR}/{I_MMAP_PORT_JSON}", "r", encoding="utf-8") as file:
        test_mmap = json.load(file)
    with open(f"{TEST_DIR}/{NOC_STREAM_ATTR_JSON}", "r", encoding="utf-8") as file:
        test_stream_attr = json.load(file)

    arm_bd_tcl = gen_arm_bd_ddr(
        {
            "bd_name": BD_NAME,
            "top_mod": TOP_MOD_NAME,
            "hbm_init_file": HBM_INIT_FILE,
            "frequency": IMPL_FREQUENCY,
        },
        test_mmap,
        test_stream_attr,
        USE_M_AXI_FPD,
    )

    with open(f"{TEST_DIR}/{VIVADO_BD_TCL}", "w", encoding="utf-8") as file:
        file.write("\n".join(arm_bd_tcl))
