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
# Create block design
create_bd_design "microblaze_tb"
update_compile_order -fileset sources_1

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
set dut [create_bd_cell -type module -reference {top_mod} dut_0]

# Associate AXI interfaces to clock
# Assumes there is one clock and all AXI pins use the same clock
set_property CONFIG.ASSOCIATED_BUSIF [concat_axi_pins $dut] [get_bd_clk_pins $dut]
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

"""
    ]

    # Configure and connect mmap noc
    for i, port in enumerate(mmap_ports):
        noc_s_port = f"S{i:02d}_AXI"
        tcl += [
            f"set_property -dict [list CONFIG.CONNECTIONS \
                {{M00_INI {{read_bw {{500}} write_bw {{500}}}}}}] \
                [get_bd_intf_pins /axi_noc_dut/{noc_s_port}]"
        ]

        tcl += [
            f"connect_bd_intf_net [get_bd_intf_pins $dut/{port}] \
                [get_bd_intf_pins axi_noc_dut/{noc_s_port}]"
        ]

    all_noc_s_ports = ":".join([f"S{i:02d}_AXI" for i in range(len(mmap_ports))])
    tcl += [
        f"set_property -dict [list CONFIG.ASSOCIATED_BUSIF {{{all_noc_s_ports}}}] \
            [get_bd_pins /axi_noc_dut/aclk0]"
    ]

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

"""
        ]

        for i, (src, dest) in enumerate(stream_ports.items()):
            noc_m_port = f"M{i:02d}_AXIS"
            noc_s_port = f"S{i:02d}_AXIS"
            tcl += [
                f"set_property -dict [list CONFIG.CONNECTIONS {{{noc_m_port} \
                    {{ write_bw {{500}} write_avg_burst {{4}}}}}}] \
                    [get_bd_intf_pins /axis_noc_dut/{noc_s_port}]"
            ]
            tcl += [
                f"connect_bd_intf_net [get_bd_intf_pins $dut/{dest}] \
                    [get_bd_intf_pins axis_noc_dut/{noc_m_port}]"
            ]
            tcl += [
                f"connect_bd_intf_net [get_bd_intf_pins $dut/{src}] \
                    [get_bd_intf_pins axis_noc_dut/{noc_s_port}]"
            ]
        tcl += ["endgroup"]

    return tcl


def connect_dut_sim_tcl(stream_ports: dict[str, str]) -> list[str]:
    """Connects dut in the simulation block design.

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
    if stream_ports:
        tcl += [
            "connect_bd_net [get_bd_pins axis_noc_dut/aclk0] \
                [get_bd_pins sim_clk_gen_1/clk]"
        ]
    return tcl


def assign_sim_bd_address() -> list[str]:
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


def arm_tcl() -> list[str]:
    """Generates the ARM block diagram for bitstream generation.

    It creates the block diagram that matches the example Vitis platform shell.
    The user clock is running at 300 MHz. ARM is connected to all three LPDDR banks.
    A NoC entry point of LPDDR (C0_DDR_CH1: 0x500_0000_0000:0x500_FFFF_FFFF) is
    reserved for the user kernel design. Kernel's control registers and interrupt
    should also be connected correspondingly.

    Returns a list of tcl commands.
    """
    return [
        """
# Create block design
create_bd_design "top_arm"
update_compile_order -fileset sources_1

# Create interface ports
set ch0_lpddr4_trip1 [ create_bd_intf_port -mode Master \
    -vlnv xilinx.com:interface:lpddr4_rtl:1.0 ch0_lpddr4_trip1 ]

set ch1_lpddr4_trip1 [ create_bd_intf_port -mode Master \
    -vlnv xilinx.com:interface:lpddr4_rtl:1.0 ch1_lpddr4_trip1 ]

set lpddr4_clk1 [ create_bd_intf_port -mode Slave \
    -vlnv xilinx.com:interface:diff_clock_rtl:1.0 lpddr4_clk1 ]

set_property -dict [ list \
    CONFIG.FREQ_HZ {200321000} \
] $lpddr4_clk1

set ch0_lpddr4_trip2 [ create_bd_intf_port -mode Master \
    -vlnv xilinx.com:interface:lpddr4_rtl:1.0 ch0_lpddr4_trip2 ]

set ch1_lpddr4_trip2 [ create_bd_intf_port -mode Master \
    -vlnv xilinx.com:interface:lpddr4_rtl:1.0 ch1_lpddr4_trip2 ]

set lpddr4_clk2 [ create_bd_intf_port -mode Slave \
    -vlnv xilinx.com:interface:diff_clock_rtl:1.0 lpddr4_clk2 ]

set_property -dict [ list \
    CONFIG.FREQ_HZ {200321000} \
] $lpddr4_clk2

set ch0_lpddr4_trip3 [ create_bd_intf_port -mode Master \
    -vlnv xilinx.com:interface:lpddr4_rtl:1.0 ch0_lpddr4_trip3 ]

set ch1_lpddr4_trip3 [ create_bd_intf_port -mode Master \
    -vlnv xilinx.com:interface:lpddr4_rtl:1.0 ch1_lpddr4_trip3 ]

set lpddr4_clk3 [ create_bd_intf_port -mode Slave \
    -vlnv xilinx.com:interface:diff_clock_rtl:1.0 lpddr4_clk3 ]

set_property -dict [ list \
    CONFIG.FREQ_HZ {200321000} \
] $lpddr4_clk3


# Create instance: CIPS_0, and set properties
set CIPS_0 [ create_bd_cell -type ip -vlnv xilinx.com:ip:versal_cips:3.4 CIPS_0 ]
set_property -dict [list \
CONFIG.CLOCK_MODE {Custom} \
CONFIG.DDR_MEMORY_MODE {Custom} \
CONFIG.PS_BOARD_INTERFACE {ps_pmc_fixed_io} \
CONFIG.PS_PL_CONNECTIVITY_MODE {Custom} \
CONFIG.PS_PMC_CONFIG { \
    CLOCK_MODE {Custom} \
    DDR_MEMORY_MODE {Custom} \
    DESIGN_MODE {1} \
    DEVICE_INTEGRITY_MODE {Sysmon temperature voltage and external IO monitoring} \
    PMC_CRP_PL0_REF_CTRL_FREQMHZ {99.999992} \
    PMC_GPIO0_MIO_PERIPHERAL {{ENABLE 1} {IO {PMC_MIO 0 .. 25}}} \
    PMC_GPIO1_MIO_PERIPHERAL {{ENABLE 1} {IO {PMC_MIO 26 .. 51}}} \
    PMC_MIO37 {{AUX_IO 0} {DIRECTION out} {DRIVE_STRENGTH 8mA} {OUTPUT_DATA high} \
        {PULL pullup} {SCHMITT 0} {SLEW slow} {USAGE GPIO}} \
    PMC_QSPI_FBCLK {{ENABLE 1} {IO {PMC_MIO 6}}} \
    PMC_QSPI_PERIPHERAL_DATA_MODE {x4} \
    PMC_QSPI_PERIPHERAL_ENABLE {1} \
    PMC_QSPI_PERIPHERAL_MODE {Dual Parallel} \
    PMC_REF_CLK_FREQMHZ {33.3333} \
    PMC_SD1 {{CD_ENABLE 1} {CD_IO {PMC_MIO 28}} {POW_ENABLE 1} {POW_IO {PMC_MIO 51}} \
        {RESET_ENABLE 0} {RESET_IO {PMC_MIO 12}} {WP_ENABLE 0} {WP_IO {PMC_MIO 1}}} \
        PMC_SD1_PERIPHERAL {{CLK_100_SDR_OTAP_DLY 0x3} {CLK_200_SDR_OTAP_DLY 0x2} \
        {CLK_50_DDR_ITAP_DLY 0x36} {CLK_50_DDR_OTAP_DLY 0x3} {CLK_50_SDR_ITAP_DLY 0x2C}\
        {CLK_50_SDR_OTAP_DLY 0x4} {ENABLE 1} {IO {PMC_MIO 26 .. 36}}} \
    PMC_SD1_SLOT_TYPE {SD 3.0} \
    PMC_USE_PMC_NOC_AXI0 {1} \
    PS_BOARD_INTERFACE {ps_pmc_fixed_io} \
    PS_ENET0_MDIO {{ENABLE 1} {IO {PS_MIO 24 .. 25}}} \
    PS_ENET0_PERIPHERAL {{ENABLE 1} {IO {PS_MIO 0 .. 11}}} \
    PS_GEN_IPI0_ENABLE {1} \
    PS_GEN_IPI0_MASTER {A72} \
    PS_GEN_IPI1_ENABLE {1} \
    PS_GEN_IPI1_MASTER {A72} \
    PS_GEN_IPI2_ENABLE {1} \
    PS_GEN_IPI2_MASTER {A72} \
    PS_GEN_IPI3_ENABLE {1} \
    PS_GEN_IPI3_MASTER {A72} \
    PS_GEN_IPI4_ENABLE {1} \
    PS_GEN_IPI4_MASTER {A72} \
    PS_GEN_IPI5_ENABLE {1} \
    PS_GEN_IPI5_MASTER {A72} \
    PS_GEN_IPI6_ENABLE {1} \
    PS_GEN_IPI6_MASTER {A72} \
    PS_I2C0_PERIPHERAL {{ENABLE 1} {IO {PMC_MIO 46 .. 47}}} \
    PS_I2C1_PERIPHERAL {{ENABLE 1} {IO {PMC_MIO 44 .. 45}}} \
    PS_I2CSYSMON_PERIPHERAL {{ENABLE 0} {IO {PMC_MIO 39 .. 40}}} \
    PS_IRQ_USAGE {{CH0 1} {CH1 0} {CH10 0} {CH11 0} {CH12 0} {CH13 0} {CH14 0} \
        {CH15 0} {CH2 0} {CH3 0} {CH4 0} {CH5 0} {CH6 0} {CH7 0} {CH8 0} {CH9 0}} \
    PS_MIO7 {{AUX_IO 0} {DIRECTION in} {DRIVE_STRENGTH 8mA} {OUTPUT_DATA default} \
        {PULL disable} {SCHMITT 0} {SLEW slow} {USAGE Reserved}} \
    PS_MIO9 {{AUX_IO 0} {DIRECTION in} {DRIVE_STRENGTH 8mA} {OUTPUT_DATA default} \
        {PULL disable} {SCHMITT 0} {SLEW slow} {USAGE Reserved}} \
    PS_NUM_FABRIC_RESETS {1} \
    PS_PCIE_EP_RESET1_IO {PS_MIO 18} \
    PS_PCIE_EP_RESET2_IO {PS_MIO 19} \
    PS_PCIE_RESET {ENABLE 1} \
    PS_PL_CONNECTIVITY_MODE {Custom} \
    PS_TTC0_PERIPHERAL_ENABLE {1} \
    PS_UART0_PERIPHERAL {{ENABLE 1} {IO {PMC_MIO 42 .. 43}}} \
    PS_USB3_PERIPHERAL {{ENABLE 1} {IO {PMC_MIO 13 .. 25}}} \
    PS_USE_FPD_AXI_NOC0 {1} \
    PS_USE_FPD_AXI_NOC1 {1} \
    PS_USE_FPD_CCI_NOC {1} \
    PS_USE_M_AXI_FPD {1} \
    PS_USE_NOC_LPD_AXI0 {1} \
    PS_USE_PMCPL_CLK0 {1} \
    SMON_ALARMS {Set_Alarms_On} \
    SMON_ENABLE_TEMP_AVERAGING {0} \
    SMON_INTERFACE_TO_USE {I2C} \
    SMON_PMBUS_ADDRESS {0x18} \
    SMON_TEMP_AVERAGING_SAMPLES {0} \
} \
] $CIPS_0

# Create instance: axi_intc_0, and set properties
set axi_intc_0 [ create_bd_cell -type ip -vlnv xilinx.com:ip:axi_intc:4.1 axi_intc_0 ]
set_property -dict [list \
    CONFIG.C_ASYNC_INTR {0xFFFFFFFF} \
    CONFIG.C_IRQ_CONNECTION {1} \
] $axi_intc_0

# Create instance: clk_wizard_0, and set properties
set clk_wizard_0 [ create_bd_cell -type ip \
    -vlnv xilinx.com:ip:clk_wizard:1.0 clk_wizard_0 ]
set_property -dict [list \
    CONFIG.CLKOUT_DRIVES {BUFG,BUFG,BUFG,BUFG,BUFG,BUFG,BUFG} \
    CONFIG.CLKOUT_DYN_PS {None,None,None,None,None,None,None} \
    CONFIG.CLKOUT_MATCHED_ROUTING {false,false,false,false,false,false,false} \
    CONFIG.CLKOUT_PORT {clk_out1,clk_out2,clk_out3,clk_out4,clk_out5,clk_out6,clk_out7}\
    CONFIG.CLKOUT_REQUESTED_DUTY_CYCLE \
        {50.000,50.000,50.000,50.000,50.000,50.000,50.000} \
    CONFIG.CLKOUT_REQUESTED_OUT_FREQUENCY \
        {300.000,250.000,200.000,100.000,100.000,100.000,100.000} \
    CONFIG.CLKOUT_REQUESTED_PHASE {0.000,0.000,0.000,0.000,0.000,0.000,0.000} \
    CONFIG.CLKOUT_USED {true,false,false,false,false,false,false} \
    CONFIG.JITTER_SEL {Min_O_Jitter} \
    CONFIG.PRIM_SOURCE {No_buffer} \
    CONFIG.RESET_TYPE {ACTIVE_LOW} \
    CONFIG.USE_LOCKED {true} \
    CONFIG.USE_PHASE_ALIGNMENT {true} \
    CONFIG.USE_RESET {true} \
] $clk_wizard_0

# Create instance: cips_noc, and set properties
set cips_noc [ create_bd_cell -type ip -vlnv xilinx.com:ip:axi_noc:1.0 cips_noc ]
set_property -dict [list \
    CONFIG.NUM_CLKS {9} \
    CONFIG.NUM_MI {0} \
    CONFIG.NUM_NMI {2} \
    CONFIG.NUM_NSI {0} \
    CONFIG.NUM_SI {8} \
] $cips_noc

set_property -dict [ list \
    CONFIG.CONNECTIONS {M00_INI { read_bw {128} write_bw {128}} \
                        M01_INI { read_bw {128} write_bw {128}} } \
    CONFIG.DEST_IDS {} \
    CONFIG.NOC_PARAMS {} \
    CONFIG.CATEGORY {ps_cci} \
] [get_bd_intf_pins /cips_noc/S00_AXI]

set_property -dict [ list \
    CONFIG.CONNECTIONS {M00_INI { read_bw {128} write_bw {128}} \
                        M01_INI { read_bw {128} write_bw {128}} } \
    CONFIG.DEST_IDS {} \
    CONFIG.NOC_PARAMS {} \
    CONFIG.CATEGORY {ps_cci} \
] [get_bd_intf_pins /cips_noc/S01_AXI]

set_property -dict [ list \
    CONFIG.CONNECTIONS {M00_INI { read_bw {128} write_bw {128}} \
                        M01_INI { read_bw {128} write_bw {128}} } \
    CONFIG.DEST_IDS {} \
    CONFIG.NOC_PARAMS {} \
    CONFIG.CATEGORY {ps_cci} \
] [get_bd_intf_pins /cips_noc/S02_AXI]

set_property -dict [ list \
    CONFIG.CONNECTIONS {M00_INI { read_bw {128} write_bw {128}} \
                        M01_INI { read_bw {128} write_bw {128}} } \
    CONFIG.DEST_IDS {} \
    CONFIG.NOC_PARAMS {} \
    CONFIG.CATEGORY {ps_cci} \
] [get_bd_intf_pins /cips_noc/S03_AXI]

set_property -dict [ list \
    CONFIG.CONNECTIONS {M00_INI { read_bw {128} write_bw {128}} \
                        M01_INI { read_bw {128} write_bw {128}} } \
    CONFIG.DEST_IDS {} \
    CONFIG.NOC_PARAMS {} \
    CONFIG.CATEGORY {ps_nci} \
] [get_bd_intf_pins /cips_noc/S04_AXI]

set_property -dict [ list \
    CONFIG.CONNECTIONS {M00_INI { read_bw {128} write_bw {128}} \
                        M01_INI { read_bw {128} write_bw {128}} } \
    CONFIG.DEST_IDS {} \
    CONFIG.NOC_PARAMS {} \
    CONFIG.CATEGORY {ps_nci} \
] [get_bd_intf_pins /cips_noc/S05_AXI]

set_property -dict [ list \
    CONFIG.CONNECTIONS {M00_INI { read_bw {128} write_bw {128}} \
                        M01_INI { read_bw {128} write_bw {128}} } \
    CONFIG.DEST_IDS {} \
    CONFIG.NOC_PARAMS {} \
    CONFIG.CATEGORY {ps_rpu} \
] [get_bd_intf_pins /cips_noc/S06_AXI]

set_property -dict [ list \
    CONFIG.CONNECTIONS {M00_INI { read_bw {128} write_bw {128}} \
                        M01_INI { read_bw {128} write_bw {128}} } \
    CONFIG.DEST_IDS {} \
    CONFIG.NOC_PARAMS {} \
    CONFIG.CATEGORY {ps_pmc} \
] [get_bd_intf_pins /cips_noc/S07_AXI]

set_property -dict [ list \
    CONFIG.ASSOCIATED_BUSIF {} \
] [get_bd_pins /cips_noc/aclk0]

set_property -dict [ list \
    CONFIG.ASSOCIATED_BUSIF {S00_AXI} \
] [get_bd_pins /cips_noc/aclk1]

set_property -dict [ list \
    CONFIG.ASSOCIATED_BUSIF {S01_AXI} \
] [get_bd_pins /cips_noc/aclk2]

set_property -dict [ list \
    CONFIG.ASSOCIATED_BUSIF {S02_AXI} \
] [get_bd_pins /cips_noc/aclk3]

set_property -dict [ list \
    CONFIG.ASSOCIATED_BUSIF {S03_AXI} \
] [get_bd_pins /cips_noc/aclk4]

set_property -dict [ list \
    CONFIG.ASSOCIATED_BUSIF {S04_AXI} \
] [get_bd_pins /cips_noc/aclk5]

set_property -dict [ list \
    CONFIG.ASSOCIATED_BUSIF {S05_AXI} \
] [get_bd_pins /cips_noc/aclk6]

set_property -dict [ list \
    CONFIG.ASSOCIATED_BUSIF {S06_AXI} \
] [get_bd_pins /cips_noc/aclk7]

set_property -dict [ list \
    CONFIG.ASSOCIATED_BUSIF {S07_AXI} \
] [get_bd_pins /cips_noc/aclk8]

# Create instance: noc_lpddr4_0, and set properties
set noc_lpddr4_0 [ create_bd_cell -type ip \
    -vlnv xilinx.com:ip:axi_noc:1.0 noc_lpddr4_0 ]
set_property -dict [list \
    CONFIG.CH0_LPDDR4_0_BOARD_INTERFACE {ch0_lpddr4_trip1} \
    CONFIG.CH1_LPDDR4_0_BOARD_INTERFACE {ch1_lpddr4_trip1} \
    CONFIG.MC_CHANNEL_INTERLEAVING {true} \
    CONFIG.MC_CHAN_REGION1 {DDR_LOW1} \
    CONFIG.MC_CH_INTERLEAVING_SIZE {4K_Bytes} \
    CONFIG.NUM_CLKS {0} \
    CONFIG.NUM_MCP {1} \
    CONFIG.NUM_MI {0} \
    CONFIG.NUM_NSI {1} \
    CONFIG.NUM_SI {0} \
    CONFIG.sys_clk0_BOARD_INTERFACE {lpddr4_clk1} \
] $noc_lpddr4_0

set_property -dict [ list \
    CONFIG.CONNECTIONS \
        {MC_0 { read_bw {128} write_bw {128} read_avg_burst {4} write_avg_burst {4}} } \
] [get_bd_intf_pins /noc_lpddr4_0/S00_INI]

# Create instance: proc_sys_reset_0, and set properties
set proc_sys_reset_0 [ create_bd_cell -type ip \
    -vlnv xilinx.com:ip:proc_sys_reset:5.0 proc_sys_reset_0 ]

# Create instance: icn_ctrl, and set properties
set icn_ctrl [ create_bd_cell -type ip -vlnv xilinx.com:ip:smartconnect:1.0 icn_ctrl ]
set_property -dict [list \
    CONFIG.NUM_CLKS {1} \
    CONFIG.NUM_MI {2} \
    CONFIG.NUM_SI {1} \
] $icn_ctrl

# Create instance: noc_lpddr4_1, and set properties
set noc_lpddr4_1 [ create_bd_cell -type ip -vlnv xilinx.com:ip:axi_noc:1.0 noc_lpddr4_1 ]
set_property -dict [list \
    CONFIG.CH0_LPDDR4_0_BOARD_INTERFACE {ch0_lpddr4_trip2} \
    CONFIG.CH0_LPDDR4_1_BOARD_INTERFACE {ch0_lpddr4_trip3} \
    CONFIG.CH1_LPDDR4_0_BOARD_INTERFACE {ch1_lpddr4_trip2} \
    CONFIG.CH1_LPDDR4_1_BOARD_INTERFACE {ch1_lpddr4_trip3} \
    CONFIG.MC_CHAN_REGION0 {DDR_CH1} \
    CONFIG.NUM_CLKS {0} \
    CONFIG.NUM_MI {0} \
    CONFIG.NUM_NSI {2} \
    CONFIG.NUM_SI {0} \
    CONFIG.sys_clk0_BOARD_INTERFACE {lpddr4_clk2} \
    CONFIG.sys_clk1_BOARD_INTERFACE {lpddr4_clk3} \
] $noc_lpddr4_1

set_property -dict [ list \
    CONFIG.CONNECTIONS {MC_0 \
        { read_bw {128} write_bw {128} read_avg_burst {4} write_avg_burst {4}} } \
] [get_bd_intf_pins /noc_lpddr4_1/S00_INI]

set_property -dict [ list \
    CONFIG.CONNECTIONS \
        {MC_0 { read_bw {500} write_bw {500} read_avg_burst {4} write_avg_burst {4}} } \
] [get_bd_intf_pins /noc_lpddr4_1/S01_INI]

# Create interface connections
connect_bd_intf_net -intf_net CIPS_0_FPD_AXI_NOC_0 \
    [get_bd_intf_pins CIPS_0/FPD_AXI_NOC_0] [get_bd_intf_pins cips_noc/S04_AXI]
connect_bd_intf_net -intf_net CIPS_0_FPD_AXI_NOC_1 \
    [get_bd_intf_pins CIPS_0/FPD_AXI_NOC_1] [get_bd_intf_pins cips_noc/S05_AXI]
connect_bd_intf_net -intf_net CIPS_0_FPD_CCI_NOC_0 \
    [get_bd_intf_pins CIPS_0/FPD_CCI_NOC_0] [get_bd_intf_pins cips_noc/S00_AXI]
connect_bd_intf_net -intf_net CIPS_0_FPD_CCI_NOC_1 \
    [get_bd_intf_pins CIPS_0/FPD_CCI_NOC_1] [get_bd_intf_pins cips_noc/S01_AXI]
connect_bd_intf_net -intf_net CIPS_0_FPD_CCI_NOC_2 \
    [get_bd_intf_pins CIPS_0/FPD_CCI_NOC_2] [get_bd_intf_pins cips_noc/S02_AXI]
connect_bd_intf_net -intf_net CIPS_0_FPD_CCI_NOC_3 \
    [get_bd_intf_pins CIPS_0/FPD_CCI_NOC_3] [get_bd_intf_pins cips_noc/S03_AXI]
connect_bd_intf_net -intf_net CIPS_0_LPD_AXI_NOC_0 \
    [get_bd_intf_pins CIPS_0/LPD_AXI_NOC_0] [get_bd_intf_pins cips_noc/S06_AXI]
connect_bd_intf_net -intf_net CIPS_0_M_AXI_GP0 \
    [get_bd_intf_pins CIPS_0/M_AXI_FPD] [get_bd_intf_pins icn_ctrl/S00_AXI]
connect_bd_intf_net -intf_net CIPS_0_PMC_NOC_AXI_0 \
    [get_bd_intf_pins CIPS_0/PMC_NOC_AXI_0] [get_bd_intf_pins cips_noc/S07_AXI]
connect_bd_intf_net -intf_net cips_noc_M00_INI \
    [get_bd_intf_pins cips_noc/M00_INI] [get_bd_intf_pins noc_lpddr4_0/S00_INI]
connect_bd_intf_net -intf_net cips_noc_M01_INI \
    [get_bd_intf_pins cips_noc/M01_INI] [get_bd_intf_pins noc_lpddr4_1/S00_INI]
connect_bd_intf_net -intf_net icn_ctrl_M00_AXI \
    [get_bd_intf_pins axi_intc_0/s_axi] [get_bd_intf_pins icn_ctrl/M00_AXI]
connect_bd_intf_net -intf_net lpddr4_clk1_1 \
    [get_bd_intf_ports lpddr4_clk1] [get_bd_intf_pins noc_lpddr4_0/sys_clk0]
connect_bd_intf_net -intf_net lpddr4_clk2_1 \
    [get_bd_intf_ports lpddr4_clk2] [get_bd_intf_pins noc_lpddr4_1/sys_clk0]
connect_bd_intf_net -intf_net lpddr4_clk3_1 \
    [get_bd_intf_ports lpddr4_clk3] [get_bd_intf_pins noc_lpddr4_1/sys_clk1]
connect_bd_intf_net -intf_net noc_lpddr4_0_CH0_LPDDR4_0 \
    [get_bd_intf_ports ch0_lpddr4_trip1] [get_bd_intf_pins noc_lpddr4_0/CH0_LPDDR4_0]
connect_bd_intf_net -intf_net noc_lpddr4_0_CH1_LPDDR4_0 \
    [get_bd_intf_ports ch1_lpddr4_trip1] [get_bd_intf_pins noc_lpddr4_0/CH1_LPDDR4_0]
connect_bd_intf_net -intf_net noc_lpddr4_1_CH0_LPDDR4_0 \
    [get_bd_intf_ports ch0_lpddr4_trip2] [get_bd_intf_pins noc_lpddr4_1/CH0_LPDDR4_0]
connect_bd_intf_net -intf_net noc_lpddr4_1_CH0_LPDDR4_1 \
    [get_bd_intf_ports ch0_lpddr4_trip3] [get_bd_intf_pins noc_lpddr4_1/CH0_LPDDR4_1]
connect_bd_intf_net -intf_net noc_lpddr4_1_CH1_LPDDR4_0 \
    [get_bd_intf_ports ch1_lpddr4_trip2] [get_bd_intf_pins noc_lpddr4_1/CH1_LPDDR4_0]
connect_bd_intf_net -intf_net noc_lpddr4_1_CH1_LPDDR4_1 \
    [get_bd_intf_ports ch1_lpddr4_trip3] [get_bd_intf_pins noc_lpddr4_1/CH1_LPDDR4_1]

# Create port connections
connect_bd_net -net CIPS_0_fpd_axi_noc_axi0_clk \
    [get_bd_pins CIPS_0/fpd_axi_noc_axi0_clk] [get_bd_pins cips_noc/aclk5]
connect_bd_net -net CIPS_0_fpd_axi_noc_axi1_clk \
    [get_bd_pins CIPS_0/fpd_axi_noc_axi1_clk] [get_bd_pins cips_noc/aclk6]
connect_bd_net -net CIPS_0_fpd_cci_noc_axi0_clk \
    [get_bd_pins CIPS_0/fpd_cci_noc_axi0_clk] [get_bd_pins cips_noc/aclk1]
connect_bd_net -net CIPS_0_fpd_cci_noc_axi1_clk \
    [get_bd_pins CIPS_0/fpd_cci_noc_axi1_clk] [get_bd_pins cips_noc/aclk2]
connect_bd_net -net CIPS_0_fpd_cci_noc_axi2_clk \
    [get_bd_pins CIPS_0/fpd_cci_noc_axi2_clk] [get_bd_pins cips_noc/aclk3]
connect_bd_net -net CIPS_0_fpd_cci_noc_axi3_clk \
    [get_bd_pins CIPS_0/fpd_cci_noc_axi3_clk] [get_bd_pins cips_noc/aclk4]
connect_bd_net -net CIPS_0_lpd_axi_noc_clk \
    [get_bd_pins CIPS_0/lpd_axi_noc_clk] [get_bd_pins cips_noc/aclk7]
connect_bd_net -net CIPS_0_pl_clk0 \
    [get_bd_pins CIPS_0/pl0_ref_clk] [get_bd_pins clk_wizard_0/clk_in1]
connect_bd_net -net CIPS_0_pl_resetn1 [get_bd_pins CIPS_0/pl0_resetn] \
    [get_bd_pins clk_wizard_0/resetn] [get_bd_pins proc_sys_reset_0/ext_reset_in]
connect_bd_net -net CIPS_0_pmc_axi_noc_axi0_clk \
    [get_bd_pins CIPS_0/pmc_axi_noc_axi0_clk] [get_bd_pins cips_noc/aclk8]
connect_bd_net -net axi_intc_0_irq \
    [get_bd_pins axi_intc_0/irq] [get_bd_pins CIPS_0/pl_ps_irq0]
connect_bd_net -net clk_wizard_0_clk_out1 [get_bd_pins clk_wizard_0/clk_out1] \
    [get_bd_pins CIPS_0/m_axi_fpd_aclk] [get_bd_pins cips_noc/aclk0] \
    [get_bd_pins icn_ctrl/aclk] [get_bd_pins proc_sys_reset_0/slowest_sync_clk] \
    [get_bd_pins axi_intc_0/s_axi_aclk]
connect_bd_net -net clk_wizard_0_locked \
    [get_bd_pins clk_wizard_0/locked] [get_bd_pins proc_sys_reset_0/dcm_locked]
connect_bd_net -net proc_sys_reset_0_peripheral_aresetn \
    [get_bd_pins proc_sys_reset_0/peripheral_aresetn] \
    [get_bd_pins icn_ctrl/aresetn] [get_bd_pins axi_intc_0/s_axi_aresetn]

"""
    ]


def connect_dut_bit_tcl(stream_ports: dict[str, str]) -> list[str]:
    """Connects dut in the bitstream-generation block design.

    Returns a list of tcl commands.
    """
    tcl = [
        """
connect_bd_net [get_bd_pins clk_wizard_0/clk_out1] [get_bd_clk_pins $dut] \
    [get_bd_pins axi_noc_dut/aclk0]
connect_bd_net [get_bd_pins proc_sys_reset_0/peripheral_aresetn] [get_bd_rst_pins $dut]
connect_bd_intf_net [get_bd_intf_pins icn_ctrl/M01_AXI] \
    [get_bd_intf_pins dut_0/s_axi_control]
connect_bd_intf_net [get_bd_intf_pins axi_noc_dut/M00_INI] \
    [get_bd_intf_pins noc_lpddr4_1/S01_INI]
connect_bd_net [get_bd_pins dut_0/interrupt] [get_bd_pins axi_intc_0/intr]
"""
    ]
    if stream_ports:
        tcl += [
            "connect_bd_net [get_bd_pins axis_noc_dut/aclk0] \
                [get_bd_pins clk_wizard_0/clk_out1]"
        ]
    return tcl


def assign_bit_bd_address() -> list[str]:
    """Assigns the addresses of ARM, interrupt controller, DUT, and DDR.

    Auto-assigns all.

    Returns a list of tcl commands.
    """
    return [
        """
# Auto-assigns all
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

    Returns None. Dumps tcl commands to ./<top_mod>_sim_bd.tcl.
    """
    tcl = []
    tcl += proc_tcl()
    tcl += testbench_tcl()
    tcl += dut_tcl(rtl_folder, top_mod, mmap_ports, stream_ports)
    tcl += connect_dut_sim_tcl(stream_ports)
    tcl += assign_sim_bd_address()

    with open(f"{top_mod}_sim_bd.tcl", "w", encoding="utf-8") as file:
        file.write("\n".join(tcl))


def gen_bit_bd(
    rtl_folder: str, top_mod: str, mmap_ports: list[str], stream_ports: dict[str, str]
) -> None:
    """Generates Vivado block design to run on the board.

    Merges the tcl commands from the helper functions and dumps to a file.

    Args:
        rtl_folder:   the directory containing the exported design from RapidStream.
        top_mod:      name of the top-level module.
        mmap_ports:   list of top-level mmap ports connected to the memory.
        stream_ports: dictionary of top-level stream ports
                      {"src": "dest"}. It can be empty.

    Returns None. Dumps tcl commands to ./<top_mod>_bit_bd.tcl.
    """
    tcl = []
    tcl += proc_tcl()
    tcl += arm_tcl()
    tcl += dut_tcl(rtl_folder, top_mod, mmap_ports, stream_ports)
    tcl += connect_dut_bit_tcl(stream_ports)
    tcl += assign_bit_bd_address()

    with open(f"{top_mod}_bit_bd.tcl", "w", encoding="utf-8") as file:
        file.write("\n".join(tcl))


if __name__ == "__main__":
    # Unit test
    gen_bit_bd(
        "", "VecAdd", ["m_axi_a", "m_axi_b", "m_axi_c"], {"m_axis_ab_q": "s_axis_ab_q"}
    )
