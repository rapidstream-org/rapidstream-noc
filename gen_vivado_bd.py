"""Generates Vivado block designs to run RTL simulation and generate bitstreams.

As of 2023.2, Vitis only supports HLS kernels to use Versal NoC for memory (LPDDR/DDR).
This module enables HLS kernels to use Versal NoC between their sub-modules.
It dumps tcl files to create Vivado block designs for running simulation and generating
bitstreams. This module avoids the Vitis platform flow, and uses Vivado block designs
for directly instantiating NoC IPs. The HLS kernel should use top-level ports to infer
NoC connection between sub-modules. This module will use the AXI Stream NoC to connect
the sub-modules.

The simulation block design uses the 64-bit Microblaze as the host. Users should export
the pre-synthesis hardware to Vitis, and writes the bare-metal C program to send test
inputs to DUT and memory.
"""

__copyright__ = """
Copyright (c) 2024 RapidStream Design Automation, Inc. and contributors.
All rights reserved. The contributor(s) of this file has/have agreed to the
RapidStream Contributor License Agreement.
"""


def proc_tcl() -> list[str]:
    """User-defined tcl functions.

    Returns a list of tcl commands.
    """
    return [
        """
proc add_src_to_project { dir } {
    set contents [glob -nocomplain -directory $dir *]
    foreach item $contents {
    if { [regexp {.*\\.tcl} $item] } {
        source $item
    } else {
        add_files $item
    }
    }
}

proc concat_axi_pins { cell } {
    set pins [get_bd_intf_pins -of $cell]
    set result []

    foreach pin $pins {
        set last_word [lindex [split $pin /] end]
        lappend result $last_word
    }

    set final_result [join $result :]
    return $final_result
}

proc get_bd_clk_pins { cell } {
    set result [get_bd_pins -of $cell -filter {TYPE == clk}]
    return $result
}

proc get_bd_rst_pins { cell } {
    set result [get_bd_pins -of $cell -filter {TYPE == rst}]
    return $result
}

# Create block design
create_bd_design "microblaze_tb"
update_compile_order -fileset sources_1
"""
    ]


def testbench_tcl() -> list[str]:
    """Generates testbench block diagram.

    It creates simulation clock (300 MHz) and reset generators,
    NoC with LPDDR (C0_DDR_CH1: 0x500_0000_0000:0x500_FFFF_FFFF),
    and Vivado-generated microblaze (64-bit with floating point support).

    Returns a list of tcl commands.
    """
    return [
        """
# Hierarchical cell: microblaze_0_local_memory
proc create_hier_cell_microblaze_0_local_memory { parentCell nameHier } {

    variable script_folder

    if { $parentCell eq "" || $nameHier eq "" } {
    catch {
        common::send_gid_msg -ssname BD::TCL -id 2092 -severity "ERROR" \
        "create_hier_cell_microblaze_0_local_memory() - Empty argument(s)!"
    }
    return
    }

    # Get object for parentCell
    set parentObj [get_bd_cells $parentCell]
    if { $parentObj == "" } {
    catch {
        common::send_gid_msg -ssname BD::TCL -id 2090 -severity "ERROR" \
        "Unable to find parent cell <$parentCell>!"
    }
    return
    }

    # Make sure parentObj is hier blk
    set parentType [get_property TYPE $parentObj]
    if { $parentType ne "hier" } {
    catch {
        common::send_gid_msg -ssname BD::TCL -id 2091 -severity "ERROR" \
        "Parent <$parentObj> has TYPE = <$parentType>. Expected to be <hier>."
    }
    return
    }

    # Save current instance; Restore later
    set oldCurInst [current_bd_instance .]

    # Set parent object as current
    current_bd_instance $parentObj

    # Create cell and set as current instance
    set hier_obj [create_bd_cell -type hier $nameHier]
    current_bd_instance $hier_obj

    # Create interface pins
    create_bd_intf_pin -mode MirroredMaster -vlnv xilinx.com:interface:lmb_rtl:1.0 DLMB

    create_bd_intf_pin -mode MirroredMaster -vlnv xilinx.com:interface:lmb_rtl:1.0 ILMB


    # Create pins
    create_bd_pin -dir I -type clk LMB_Clk
    create_bd_pin -dir I -type rst SYS_Rst

    # Create instance: dlmb_v10, and set properties
    set dlmb_v10 [ create_bd_cell -type ip -vlnv xilinx.com:ip:lmb_v10:3.0 dlmb_v10 ]

    # Create instance: ilmb_v10, and set properties
    set ilmb_v10 [ create_bd_cell -type ip -vlnv xilinx.com:ip:lmb_v10:3.0 ilmb_v10 ]

    # Create instance: dlmb_bram_if_cntlr, and set properties
    set dlmb_bram_if_cntlr [ create_bd_cell -type ip \
    -vlnv xilinx.com:ip:lmb_bram_if_cntlr:4.0 dlmb_bram_if_cntlr ]
    set_property CONFIG.C_ECC {0} $dlmb_bram_if_cntlr


    # Create instance: ilmb_bram_if_cntlr, and set properties
    set ilmb_bram_if_cntlr [ create_bd_cell -type ip \
    -vlnv xilinx.com:ip:lmb_bram_if_cntlr:4.0 ilmb_bram_if_cntlr ]
    set_property CONFIG.C_ECC {0} $ilmb_bram_if_cntlr


    # Create instance: lmb_bram, and set properties
    set lmb_bram [ create_bd_cell -type ip -vlnv xilinx.com:ip:emb_mem_gen:1.0 lmb_bram ]
    set_property -dict [list \
    CONFIG.MEMORY_TYPE {True_Dual_Port_RAM} \
    CONFIG.READ_LATENCY_A {1} \
    CONFIG.READ_LATENCY_B {1} \
    ] $lmb_bram


    # Create interface connections
    connect_bd_intf_net -intf_net microblaze_0_dlmb \
    [get_bd_intf_pins dlmb_v10/LMB_M] [get_bd_intf_pins DLMB]
    connect_bd_intf_net -intf_net microblaze_0_dlmb_bus \
    [get_bd_intf_pins dlmb_v10/LMB_Sl_0] [get_bd_intf_pins dlmb_bram_if_cntlr/SLMB]
    connect_bd_intf_net -intf_net microblaze_0_dlmb_cntlr \
    [get_bd_intf_pins dlmb_bram_if_cntlr/BRAM_PORT] \
    [get_bd_intf_pins lmb_bram/BRAM_PORTA]
    connect_bd_intf_net -intf_net microblaze_0_ilmb \
    [get_bd_intf_pins ilmb_v10/LMB_M] [get_bd_intf_pins ILMB]
    connect_bd_intf_net -intf_net microblaze_0_ilmb_bus \
    [get_bd_intf_pins ilmb_v10/LMB_Sl_0] [get_bd_intf_pins ilmb_bram_if_cntlr/SLMB]
    connect_bd_intf_net -intf_net microblaze_0_ilmb_cntlr \
    [get_bd_intf_pins ilmb_bram_if_cntlr/BRAM_PORT] \
    [get_bd_intf_pins lmb_bram/BRAM_PORTB]

    # Create port connections
    connect_bd_net -net SYS_Rst_1 [get_bd_pins SYS_Rst] \
    [get_bd_pins dlmb_v10/SYS_Rst] [get_bd_pins dlmb_bram_if_cntlr/LMB_Rst] \
    [get_bd_pins ilmb_v10/SYS_Rst] [get_bd_pins ilmb_bram_if_cntlr/LMB_Rst]
    connect_bd_net -net microblaze_0_Clk [get_bd_pins LMB_Clk] \
    [get_bd_pins dlmb_v10/LMB_Clk] [get_bd_pins dlmb_bram_if_cntlr/LMB_Clk] \
    [get_bd_pins ilmb_v10/LMB_Clk] [get_bd_pins ilmb_bram_if_cntlr/LMB_Clk]

    # Restore current instance
    current_bd_instance $oldCurInst
}

# ======================= Adding TB =======================
startgroup
set ch0_lpddr4_trip1 [ create_bd_intf_port -mode Master \
    -vlnv xilinx.com:interface:lpddr4_rtl:1.0 ch0_lpddr4_trip1 ]
set ch1_lpddr4_trip1 [ create_bd_intf_port -mode Master \
    -vlnv xilinx.com:interface:lpddr4_rtl:1.0 ch1_lpddr4_trip1 ]

set axi_noc_0 [ create_bd_cell -type ip -vlnv xilinx.com:ip:axi_noc:1.0 axi_noc_0 ]
set_property -dict [list \
    CONFIG.CH0_LPDDR4_0_BOARD_INTERFACE {ch0_lpddr4_trip1} \
    CONFIG.CH1_LPDDR4_0_BOARD_INTERFACE {ch1_lpddr4_trip1} \
    CONFIG.MC1_FLIPPED_PINOUT {true} \
    CONFIG.MC_CHAN_REGION0 {DDR_CH1} \
    CONFIG.MC_DM_WIDTH {4} \
    CONFIG.MC_DQS_WIDTH {4} \
    CONFIG.MC_DQ_WIDTH {32} \
    CONFIG.MC_EN_INTR_RESP {TRUE} \
    CONFIG.MC_SYSTEM_CLOCK {Differential} \
    CONFIG.NUM_CLKS {1} \
    CONFIG.NUM_MC {1} \
    CONFIG.NUM_MCP {1} \
    CONFIG.NUM_MI {0} \
    CONFIG.NUM_SI {1} \
    CONFIG.NUM_NSI {1} \
    CONFIG.sys_clk0_BOARD_INTERFACE {lpddr4_clk1} \
] $axi_noc_0

set_property -dict [ list \
    CONFIG.CONNECTIONS {MC_0 {read_bw {500} write_bw {500} \
                            read_avg_burst {4} write_avg_burst {4}}} \
    CONFIG.NOC_PARAMS {} \
    CONFIG.CATEGORY {pl} \
] [get_bd_intf_pins /axi_noc_0/S00_AXI]

set_property -dict [list \
    CONFIG.CONNECTIONS {MC_0 {read_bw {500} write_bw {500} \
                            read_avg_burst {4} write_avg_burst {4}}} \
    CONFIG.NOC_PARAMS {} \
    CONFIG.CATEGORY {pl} \
] [get_bd_intf_pins /axi_noc_0/S00_INI]

set_property -dict [ list \
    CONFIG.ASSOCIATED_BUSIF {S00_AXI:S00_INI} \
] [get_bd_pins /axi_noc_0/aclk0]

# Create instance: rst_clk_wiz_100M, and set properties
set rst_clk_wiz_100M [ create_bd_cell -type ip \
    -vlnv xilinx.com:ip:proc_sys_reset:5.0 rst_clk_wiz_100M ]

# Create instance: sim_clk_gen_0, and set properties
set sim_clk_gen_0 [ create_bd_cell -type ip \
    -vlnv xilinx.com:ip:sim_clk_gen:1.0 sim_clk_gen_0 ]
set_property -dict [list \
    CONFIG.CLOCK_TYPE {Differential} \
    CONFIG.FREQ_HZ {200000000} \
] $sim_clk_gen_0


# Create instance: sim_clk_gen_1, and set properties
set sim_clk_gen_1 [ create_bd_cell -type ip \
    -vlnv xilinx.com:ip:sim_clk_gen:1.0 sim_clk_gen_1 ]
set_property CONFIG.FREQ_HZ {300000000} $sim_clk_gen_1


# Create instance: versal_cips_0, and set properties
set versal_cips_0 [ create_bd_cell -type ip \
    -vlnv xilinx.com:ip:versal_cips:3.4 versal_cips_0 ]

# Create instance: microblaze_0, and set properties
set microblaze_0 [ create_bd_cell -type ip \
    -vlnv xilinx.com:ip:microblaze:11.0 microblaze_0 ]
set_property -dict [list \
    CONFIG.C_DEBUG_ENABLED {0} \
    CONFIG.C_D_AXI {1} \
    CONFIG.C_D_LMB {1} \
    CONFIG.C_I_LMB {1} \
    CONFIG.C_ADDR_SIZE 64 \
    CONFIG.C_DATA_SIZE {64} \
    CONFIG.C_LMB_DATA_SIZE {64} \
    CONFIG.C_USE_FPU {1} \
    CONFIG.C_USE_HW_MUL {2} \
] $microblaze_0


# Create instance: microblaze_0_local_memory
create_hier_cell_microblaze_0_local_memory \
    [current_bd_instance .] microblaze_0_local_memory

# Create instance: smartconnect_0, and set properties
set smartconnect_0 [ create_bd_cell -type ip \
    -vlnv xilinx.com:ip:smartconnect:1.0 smartconnect_0 ]
set_property -dict [list \
    CONFIG.NUM_MI {2} \
    CONFIG.NUM_SI {1} \
] $smartconnect_0


connect_bd_intf_net -intf_net axi_noc_0_CH0_LPDDR4_0 \
    [get_bd_intf_ports ch0_lpddr4_trip1] [get_bd_intf_pins axi_noc_0/CH0_LPDDR4_0]
connect_bd_intf_net -intf_net axi_noc_0_CH1_LPDDR4_0 \
    [get_bd_intf_ports ch1_lpddr4_trip1] [get_bd_intf_pins axi_noc_0/CH1_LPDDR4_0]
connect_bd_intf_net -intf_net microblaze_0_M_AXI_DP \
    [get_bd_intf_pins smartconnect_0/S00_AXI] [get_bd_intf_pins microblaze_0/M_AXI_DP]
connect_bd_intf_net -intf_net microblaze_0_dlmb_1 \
    [get_bd_intf_pins microblaze_0/DLMB] \
    [get_bd_intf_pins microblaze_0_local_memory/DLMB]
connect_bd_intf_net -intf_net microblaze_0_ilmb_1 \
    [get_bd_intf_pins microblaze_0/ILMB] \
    [get_bd_intf_pins microblaze_0_local_memory/ILMB]
connect_bd_intf_net -intf_net sim_clk_gen_0_diff_clk \
    [get_bd_intf_pins sim_clk_gen_0/diff_clk] [get_bd_intf_pins axi_noc_0/sys_clk0]
connect_bd_intf_net -intf_net smartconnect_0_M00_AXI \
    [get_bd_intf_pins smartconnect_0/M00_AXI] [get_bd_intf_pins axi_noc_0/S00_AXI]

# Create port connections
connect_bd_net -net microblaze_0_Clk [get_bd_pins sim_clk_gen_1/clk] \
    [get_bd_pins axi_noc_0/aclk0] [get_bd_pins rst_clk_wiz_100M/slowest_sync_clk] \
    [get_bd_pins microblaze_0/Clk] [get_bd_pins microblaze_0_local_memory/LMB_Clk] \
    [get_bd_pins smartconnect_0/aclk] [get_bd_pins axis_noc_0/aclk0]
connect_bd_net -net rst_clk_wiz_100M_bus_struct_reset \
    [get_bd_pins rst_clk_wiz_100M/bus_struct_reset] \
    [get_bd_pins microblaze_0_local_memory/SYS_Rst]
connect_bd_net -net rst_clk_wiz_100M_mb_reset \
    [get_bd_pins rst_clk_wiz_100M/mb_reset] [get_bd_pins microblaze_0/Reset]
connect_bd_net -net sim_clk_gen_1_sync_rst [get_bd_pins sim_clk_gen_1/sync_rst] \
    [get_bd_pins rst_clk_wiz_100M/ext_reset_in]
endgroup
"""
    ]


def dut_tcl(
    rtl_folder: str, top_mod: str, mmap_ports: list[str], stream_ports: dict[str, str]
) -> list[str]:
    """Adds the design-under-test (dut) to the block diagram.

    It assumes dut uses one clock for all top-level AXI ports.
    It assumes the configurations registers use "s_axi_control".
    The mmap ports are connected to the DDR through AXI-NoC.
    The stream ports, if any, are connected to each other through AXIS-NoC.

    Args:
        rtl_folder:   the directory containing the exported design from RapidStream.
        top_mod:      name of the top-level module.
        mmap_ports:   list of top-level mmap ports connected to the memory.
        stream_ports: dictionary of top-level stream ports
                      {"src": "dest"}. It can be empty.

    Returns a list of tcl commands.
    """
    tcl = [
        f"""
# ======================= Adding DUT =======================
# Add src directory
add_src_to_project {rtl_folder}
update_compile_order -fileset sources_1

startgroup
# Add RTL module to BD
set dut [create_bd_cell -type module -reference {top_mod} {top_mod}_0]

# Associate AXI interfaces to clock
# Assumes there is one clock and all AXI pins use the same clock
set_property CONFIG.ASSOCIATED_BUSIF [concat_axi_pins $dut] [get_bd_clk_pins $dut]

connect_bd_net [get_bd_pins sim_clk_gen_1/clk] [get_bd_clk_pins $dut]
connect_bd_net [get_bd_pins rst_clk_wiz_100M/peripheral_aresetn] [get_bd_rst_pins $dut]
connect_bd_intf_net [get_bd_intf_pins smartconnect_0/M01_AXI] \
    [get_bd_intf_pins {top_mod}_0/s_axi_control]
endgroup


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

connect_bd_net [get_bd_pins axi_noc_dut/aclk0] [get_bd_pins sim_clk_gen_1/clk]
connect_bd_intf_net [get_bd_intf_pins axi_noc_dut/M00_INI] \
    [get_bd_intf_pins axi_noc_0/S00_INI]
"""
    ]

    # Configure and connect mmap noc
    for i, port in enumerate(mmap_ports):
        noc_s_port = f"S{i:02d}_AXI"
        one_line = [
            "set_property -dict [list CONFIG.CONNECTIONS ",
            "{M00_INI {read_bw {500} write_bw {500}}}] ",
            f"[get_bd_intf_pins /axi_noc_dut/{noc_s_port}]",
        ]
        tcl += ["".join(one_line)]

        one_line = [
            f"connect_bd_intf_net [get_bd_intf_pins $dut/{port}] ",
            f"[get_bd_intf_pins axi_noc_dut/{noc_s_port}]",
        ]
        tcl += ["".join(one_line)]

    all_noc_s_ports = ":".join([f"S{i:02d}_AXI" for i in range(len(mmap_ports))])
    one_line = [
        "set_property -dict [list CONFIG.ASSOCIATED_BUSIF {",
        all_noc_s_ports,
        "}] [get_bd_pins /axi_noc_dut/aclk0]",
    ]
    tcl += ["".join(one_line)]

    if stream_ports:
        tcl += [
            f"""
endgroup


# Create stream noc
startgroup
set axis_noc_dut [ create_bd_cell -type ip -vlnv \
    xilinx.com:ip:axis_noc:1.0 axis_noc_dut ]
set_property -dict [list \
    CONFIG.MI_TDEST_VALS {{}} \
    CONFIG.NUM_MI {{{len(stream_ports)}}} \
    CONFIG.NUM_SI {{{len(stream_ports)}}} \
    CONFIG.SI_DESTID_PINS {{}} \
    CONFIG.TDEST_WIDTH {{0}} \
] $axis_noc_dut
set_property CONFIG.ASSOCIATED_BUSIF [concat_axi_pins $axis_noc_dut] \
    [get_bd_pins axis_noc_dut/aclk0]

connect_bd_net [get_bd_pins axis_noc_dut/aclk0] [get_bd_pins sim_clk_gen_1/clk]
"""
        ]

        for i, (src, dest) in enumerate(stream_ports.items()):
            noc_m_port = f"M{i:02d}_AXIS"
            noc_s_port = f"S{i:02d}_AXIS"
            one_line = [
                "set_property -dict [list CONFIG.CONNECTIONS {",
                noc_m_port,
                " { write_bw {500} write_avg_burst {4}}}] ",
                f"[get_bd_intf_pins /axis_noc_dut/{noc_s_port}]",
            ]
            tcl += ["".join(one_line)]
            one_line = [
                f"connect_bd_intf_net [get_bd_intf_pins $dut/{dest}] ",
                f"[get_bd_intf_pins axis_noc_dut/{noc_m_port}]",
            ]
            tcl += ["".join(one_line)]
            one_line = [
                f"connect_bd_intf_net [get_bd_intf_pins $dut/{src}] ",
                f"[get_bd_intf_pins axis_noc_dut/{noc_s_port}]",
            ]
            tcl += ["".join(one_line)]

        tcl += ["endgroup"]

    return tcl


def assign_bd_address() -> list[str]:
    """Assigns the addresses of microblaze, DUT, and DDR.

    Assigns 64K local instruction and data memory for microblaze starting at 0x0.
    Auto-assigns the rest.

    Returns a list of tcl commands.
    """
    return [
        """
assign_bd_address -offset 0x00000000 -range 0x00010000 -target_address_space \
    [get_bd_addr_spaces microblaze_0/Data] \
    [get_bd_addr_segs microblaze_0_local_memory/dlmb_bram_if_cntlr/SLMB/Mem] -force
assign_bd_address -offset 0x00000000 -range 0x00010000 -target_address_space \
    [get_bd_addr_spaces microblaze_0/Instruction] \
    [get_bd_addr_segs microblaze_0_local_memory/ilmb_bram_if_cntlr/SLMB/Mem] -force

# Auto-assign the rest
assign_bd_address

validate_bd_design
save_bd_design
"""
    ]


def gen_sim_bd(
    rtl_folder: str, top_mod: str, mmap_ports: list[str], stream_ports: dict[str, str]
) -> None:
    """Generates Vivado block design to run RTL simulation.

    Merges the tcl commands from the helper functions and dumps to a file.

    Args:
        rtl_folder:   the directory containing the exported design from RapidStream.
        top_mod:      name of the top-level module.
        mmap_ports:   list of top-level mmap ports connected to the memory.
        stream_ports: dictionary of top-level stream ports
                      {"src": "dest"}. It can be empty.

    Returns None. Dumps tcl commands to ./gen_sim_bd.tcl.
    """
    tcl = []
    tcl += proc_tcl()
    tcl += testbench_tcl()
    tcl += dut_tcl(rtl_folder, top_mod, mmap_ports, stream_ports)
    tcl += assign_bd_address()

    with open(f"{top_mod}_sim_bd.tcl", "w", encoding="utf-8") as file:
        file.write("\n".join(tcl))


if __name__ == "__main__":
    # Unit test
    gen_sim_bd(
        "", "VecAdd", ["m_axi_a", "m_axi_b", "m_axi_c"], {"m_axis_ab_q": "s_axis_ab_q"}
    )
