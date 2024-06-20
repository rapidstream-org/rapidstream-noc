"""Helper functions to generate tcl for Vivado block design."""

__copyright__ = """
Copyright (c) 2024 RapidStream Design Automation, Inc. and contributors.
All rights reserved. The contributor(s) of this file has/have agreed to the
RapidStream Contributor License Agreement.
"""


# Define named constants
NUM_HBM_CTRL = 64
PS_CCI_PORT = [0, 1, 2, 3]
PS_NCI_PORT = [4, 5]
PS_RPU_PORT = [6]
PS_PMC_PORT = [7]


def proc_tcl() -> list[str]:
    """User-defined tcl functions.

    Returns a list of tcl commands.
    """
    return [
        """
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


def arm_ddr_tcl() -> list[str]:
    """Generates the DDR NoC for ARM.

    Returns a list of tcl commands.
    """
    return [
        """
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

# add one more NMI
set_property -dict [list \
    CONFIG.NUM_CLKS {9} \
    CONFIG.NUM_MI {0} \
    CONFIG.NUM_NMI {2} \
    CONFIG.NUM_NSI {0} \
    CONFIG.NUM_SI {8} \
] $cips_noc

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


# Create instance: noc_lpddr4_1, and set properties
set noc_lpddr4_1 [ create_bd_cell -type ip -vlnv xilinx.com:ip:axi_noc:1.0 noc_lpddr4_1]
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
connect_bd_intf_net -intf_net cips_noc_M00_INI \
    [get_bd_intf_pins cips_noc/M00_INI] [get_bd_intf_pins noc_lpddr4_0/S00_INI]
connect_bd_intf_net -intf_net cips_noc_M01_INI \
    [get_bd_intf_pins cips_noc/M01_INI] [get_bd_intf_pins noc_lpddr4_1/S00_INI]
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
"""
    ]


def arm_tcl(bd_name: str, frequency: str, hbm: bool, fpd: bool) -> list[str]:
    """Generates the ARM block diagram for LPDDR.

    It creates the block diagram that matches the example Vitis platform shell.
    The user clock is running at 300 MHz. All ARM

    Returns a list of tcl commands.
    """
    tcl = [
        f"""
# Create block design
set top_bd_file [get_files {bd_name}.bd]
if {{[llength $top_bd_file] > 0}} {{
    remove_files $top_bd_file
}}
create_bd_design "{bd_name}"
update_compile_order -fileset sources_1

# Create instance: CIPS_0
set CIPS_0 [ create_bd_cell -type ip -vlnv xilinx.com:ip:versal_cips:3.4 CIPS_0 ]
"""
    ]

    if hbm:
        # vhk158
        tcl += [
            """
# Set CIPS properties
set_property -dict [list \
CONFIG.CLOCK_MODE {Custom} \
CONFIG.CLOCK_MODE {Custom} \
CONFIG.DDR_MEMORY_MODE {Custom} \
CONFIG.PS_BOARD_INTERFACE {ps_pmc_fixed_io} \
CONFIG.PS_PL_CONNECTIVITY_MODE {Custom} \
CONFIG.PS_PMC_CONFIG { \
    BOOT_MODE {Custom} \
    CLOCK_MODE {Custom} \
    DESIGN_MODE {1} \
    DEVICE_INTEGRITY_MODE {Sysmon temperature voltage and external IO monitoring} \
"""
        ]
        tcl += [f"PMC_CRP_PL0_REF_CTRL_FREQMHZ {{{frequency}}}"]
        tcl += [
            """
    PMC_GPIO0_MIO_PERIPHERAL {{ENABLE 1} {IO {PMC_MIO 0 .. 25}}} \
    PMC_GPIO1_MIO_PERIPHERAL {{ENABLE 1} {IO {PMC_MIO 26 .. 51}}} \
    PMC_MIO12 {{AUX_IO 0} {DIRECTION out} {DRIVE_STRENGTH 8mA} {OUTPUT_DATA default} \
        {PULL pullup} {SCHMITT 0} {SLEW slow} {USAGE GPIO}} \
    PMC_MIO37 {{AUX_IO 0} {DIRECTION out} {DRIVE_STRENGTH 8mA} {OUTPUT_DATA high} \
        {PULL pullup} {SCHMITT 0} {SLEW slow} {USAGE GPIO}} \
    PMC_OSPI_PERIPHERAL {{ENABLE 1} {IO {PMC_MIO 0 .. 11}} {MODE Single}} \
    PMC_QSPI_PERIPHERAL_ENABLE {0} \
    PMC_REF_CLK_FREQMHZ {33.333} \
    PMC_SD1 {{CD_ENABLE 1} {CD_IO {PMC_MIO 28}} {POW_ENABLE 1} {POW_IO {PMC_MIO 51}} \
        {RESET_ENABLE 0} {RESET_IO {PMC_MIO 12}} {WP_ENABLE 0} {WP_IO {PMC_MIO 1}}} \
    PMC_SD1_PERIPHERAL {{CLK_100_SDR_OTAP_DLY 0x3} {CLK_200_SDR_OTAP_DLY 0x2} \
        {CLK_50_DDR_ITAP_DLY 0x2A} {CLK_50_DDR_OTAP_DLY 0x3} {CLK_50_SDR_ITAP_DLY 0x25}\
        {CLK_50_SDR_OTAP_DLY 0x4} {ENABLE 1} {IO {PMC_MIO 26 .. 36}}} \
    PMC_SD1_SLOT_TYPE {SD 3.0 AUTODIR} \
    PMC_USE_PMC_NOC_AXI0 {1} \
    PS_BOARD_INTERFACE {ps_pmc_fixed_io} \
    PS_ENET0_MDIO {{ENABLE 1} {IO {PS_MIO 24 .. 25}}} \
    PS_ENET0_PERIPHERAL {{ENABLE 1} {IO {PS_MIO 0 .. 11}}} \
    PS_GEN_IPI0_ENABLE {1} \
    PS_GEN_IPI0_MASTER {A72} \
    PS_GEN_IPI1_ENABLE {1} \
    PS_GEN_IPI2_ENABLE {1} \
    PS_GEN_IPI3_ENABLE {1} \
    PS_GEN_IPI4_ENABLE {1} \
    PS_GEN_IPI5_ENABLE {1} \
    PS_GEN_IPI6_ENABLE {1} \
    PS_I2C0_PERIPHERAL {{ENABLE 1} {IO {PMC_MIO 46 .. 47}}} \
    PS_I2C1_PERIPHERAL {{ENABLE 1} {IO {PMC_MIO 44 .. 45}}} \
    PS_I2CSYSMON_PERIPHERAL {{ENABLE 0} {IO {PMC_MIO 39 .. 40}}} \
    PS_IRQ_USAGE {{CH0 0} {CH1 0} {CH10 0} {CH11 0} {CH12 0} {CH13 0} {CH14 0} \
        {CH15 0} {CH2 0} {CH3 0} {CH4 0} {CH5 0} {CH6 0} {CH7 0} {CH8 1} {CH9 0}} \
    PS_MIO7 {{AUX_IO 0} {DIRECTION in} {DRIVE_STRENGTH 8mA} {OUTPUT_DATA default} \
        {PULL disable} {SCHMITT 0} {SLEW slow} {USAGE Reserved}} \
    PS_MIO9 {{AUX_IO 0} {DIRECTION in} {DRIVE_STRENGTH 8mA} {OUTPUT_DATA default} \
        {PULL disable} {SCHMITT 0} {SLEW slow} {USAGE Reserved}} \
    PS_NUM_FABRIC_RESETS {1} \
    PS_PCIE_EP_RESET1_IO {PS_MIO 18} \
    PS_PCIE_EP_RESET2_IO {PS_MIO 19} \
    PS_PCIE_RESET {ENABLE 1} \
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
] [get_bd_cells CIPS_0]
"""
        ]
    else:
        tcl += [
            """
# Set CIPS properties
set_property -dict [list \
CONFIG.CLOCK_MODE {Custom} \
CONFIG.DDR_MEMORY_MODE {Custom} \
CONFIG.PS_BOARD_INTERFACE {ps_pmc_fixed_io} \
CONFIG.PS_PL_CONNECTIVITY_MODE {Custom} \
CONFIG.PS_PMC_CONFIG { \
    CLOCK_MODE {Custom} \
    DDR_MEMORY _MODE {Custom} \
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
    PS_IRQ_USAGE {{CH0 0} {CH1 0} {CH10 0} {CH11 0} {CH12 0} {CH13 0} {CH14 0} \
        {CH15 0} {CH2 0} {CH3 0} {CH4 0} {CH5 0} {CH6 0} {CH7 0} {CH8 1} {CH9 0}} \
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
"""
        ]

    if not fpd:
        tcl += ["set_property CONFIG.PS_PMC_CONFIG {PS_USE_M_AXI_FPD {0}} $CIPS_0"]

    if not hbm:
        tcl += [
            """
# Create instance: cips_noc, and set properties
set cips_noc [ create_bd_cell -type ip -vlnv xilinx.com:ip:axi_noc:1.0 cips_noc ]
set_property -dict [list \
    CONFIG.NUM_CLKS {8} \
    CONFIG.NUM_MI {0} \
    CONFIG.NUM_NMI {1} \
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
    CONFIG.ASSOCIATED_BUSIF {S00_AXI} \
] [get_bd_pins /cips_noc/aclk0]

set_property -dict [ list \
    CONFIG.ASSOCIATED_BUSIF {S01_AXI} \
] [get_bd_pins /cips_noc/aclk1]

set_property -dict [ list \
    CONFIG.ASSOCIATED_BUSIF {S02_AXI} \
] [get_bd_pins /cips_noc/aclk2]

set_property -dict [ list \
    CONFIG.ASSOCIATED_BUSIF {S03_AXI} \
] [get_bd_pins /cips_noc/aclk3]

set_property -dict [ list \
    CONFIG.ASSOCIATED_BUSIF {S04_AXI} \
] [get_bd_pins /cips_noc/aclk4]

set_property -dict [ list \
    CONFIG.ASSOCIATED_BUSIF {S05_AXI} \
] [get_bd_pins /cips_noc/aclk5]

set_property -dict [ list \
    CONFIG.ASSOCIATED_BUSIF {S06_AXI} \
] [get_bd_pins /cips_noc/aclk6]

set_property -dict [ list \
    CONFIG.ASSOCIATED_BUSIF {S07_AXI} \
] [get_bd_pins /cips_noc/aclk7]

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
connect_bd_intf_net -intf_net CIPS_0_PMC_NOC_AXI_0 \
    [get_bd_intf_pins CIPS_0/PMC_NOC_AXI_0] [get_bd_intf_pins cips_noc/S07_AXI]

# Create port connections
connect_bd_net [get_bd_pins CIPS_0/fpd_axi_noc_axi0_clk] [get_bd_pins cips_noc/aclk4]
connect_bd_net [get_bd_pins CIPS_0/fpd_axi_noc_axi1_clk] [get_bd_pins cips_noc/aclk5]
connect_bd_net [get_bd_pins CIPS_0/fpd_cci_noc_axi0_clk] [get_bd_pins cips_noc/aclk0]
connect_bd_net [get_bd_pins CIPS_0/fpd_cci_noc_axi1_clk] [get_bd_pins cips_noc/aclk1]
connect_bd_net [get_bd_pins CIPS_0/fpd_cci_noc_axi2_clk] [get_bd_pins cips_noc/aclk2]
connect_bd_net [get_bd_pins CIPS_0/fpd_cci_noc_axi3_clk] [get_bd_pins cips_noc/aclk3]
connect_bd_net [get_bd_pins CIPS_0/lpd_axi_noc_clk] [get_bd_pins cips_noc/aclk6]
connect_bd_net [get_bd_pins CIPS_0/pmc_axi_noc_axi0_clk] \
    [get_bd_pins cips_noc/aclk7]
"""
        ]

    tcl += [
        """
# Create instance: axi_intc_0, and set properties
set axi_intc_0 [ create_bd_cell -type ip -vlnv xilinx.com:ip:axi_intc:4.1 axi_intc_0 ]
set_property -dict [list \
    CONFIG.C_ASYNC_INTR {0xFFFFFFFF} \
    CONFIG.C_IRQ_CONNECTION {1} \
] $axi_intc_0

# Create instance: clk_wizard_0, and set properties
# set clk_wizard_0 [ create_bd_cell -type ip \
#     -vlnv xilinx.com:ip:clk_wizard:1.0 clk_wizard_0 ]
# set_property -dict [list \
#     CONFIG.CLKOUT_DRIVES {BUFG,BUFG,BUFG,BUFG,BUFG,BUFG,BUFG} \
#     CONFIG.CLKOUT_DYN_PS {None,None,None,None,None,None,None} \
#     CONFIG.CLKOUT_MATCHED_ROUTING {false,false,false,false,false,false,false} \
#     CONFIG.CLKOUT_PORT {clk_out1,clk_out2,clk_out3,clk_out4,clk_out5,clk_out6,clk_out7}\
#     CONFIG.CLKOUT_REQUESTED_DUTY_CYCLE \
#         {50.000,50.000,50.000,50.000,50.000,50.000,50.000} \
#     CONFIG.CLKOUT_REQUESTED_OUT_FREQUENCY \
#         {300.000,250.000,200.000,100.000,100.000,100.000,100.000} \
#     CONFIG.CLKOUT_REQUESTED_PHASE {0.000,0.000,0.000,0.000,0.000,0.000,0.000} \
#     CONFIG.CLKOUT_USED {true,false,false,false,false,false,false} \
#     CONFIG.JITTER_SEL {Min_O_Jitter} \
#     CONFIG.PRIM_SOURCE {No_buffer} \
#     CONFIG.RESET_TYPE {ACTIVE_LOW} \
#     CONFIG.USE_LOCKED {true} \
#     CONFIG.USE_PHASE_ALIGNMENT {true} \
#     CONFIG.USE_RESET {true} \
# ] $clk_wizard_0


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

# Create interface connections
connect_bd_intf_net -intf_net icn_ctrl_M00_AXI \
    [get_bd_intf_pins axi_intc_0/s_axi] [get_bd_intf_pins icn_ctrl/M00_AXI]

# Create port connections
connect_bd_net -net axi_intc_0_irq \
    [get_bd_pins axi_intc_0/irq] [get_bd_pins CIPS_0/pl_ps_irq8]
connect_bd_net -net proc_sys_reset_0_peripheral_aresetn \
    [get_bd_pins proc_sys_reset_0/peripheral_aresetn] \
    [get_bd_pins icn_ctrl/aresetn] [get_bd_pins axi_intc_0/s_axi_aresetn]

# with clk_wizard
# connect_bd_net \
#     [get_bd_pins CIPS_0/pl0_ref_clk] [get_bd_pins clk_wizard_0/clk_in1]
# connect_bd_net [get_bd_pins CIPS_0/pl0_resetn] \
#     [get_bd_pins clk_wizard_0/resetn] [get_bd_pins proc_sys_reset_0/ext_reset_in]
# connect_bd_net -net clk_wizard_0_clk_out1 [get_bd_pins clk_wizard_0/clk_out1] \
#     [get_bd_pins axi_intc_0/s_axi_aclk] [get_bd_pins icn_ctrl/aclk] \
#     [get_bd_pins proc_sys_reset_0/slowest_sync_clk]
# connect_bd_net -net clk_wizard_0_locked \
#     [get_bd_pins clk_wizard_0/locked] [get_bd_pins proc_sys_reset_0/dcm_locked]

# no clk_wizard
connect_bd_net [get_bd_pins CIPS_0/pl0_resetn] \
    [get_bd_pins proc_sys_reset_0/ext_reset_in]
connect_bd_net [get_bd_pins CIPS_0/pl0_ref_clk] \
    [get_bd_pins axi_intc_0/s_axi_aclk] [get_bd_pins icn_ctrl/aclk] \
    [get_bd_pins proc_sys_reset_0/slowest_sync_clk]
"""
    ]

    if fpd:
        tcl += [
            """
connect_bd_intf_net -intf_net CIPS_0_M_AXI_GP0 \
    [get_bd_intf_pins CIPS_0/M_AXI_FPD] [get_bd_intf_pins icn_ctrl/S00_AXI]
connect_bd_net [get_bd_pins CIPS_0/pl0_ref_clk] [get_bd_pins CIPS_0/m_axi_fpd_aclk]
# if clk_wizard
# connect_bd_net [get_bd_pins clk_wizard_0/clk_out1] [get_bd_pins CIPS_0/m_axi_fpd_aclk]
"""
        ]

    return tcl


def arm_hbm_tcl(mmap_ports: dict[str, dict[str, int]], fpd: bool) -> list[str]:
    """Generates the HBM tcl for ARM.

    Returns a list of tcl commands.
    """
    # Find the maximum value for the "bank" key
    hbm_chnl = ((max(attr["bank"] for attr in mmap_ports.values()) + 1) + 1) // 2
    assert len(mmap_ports) <= NUM_HBM_CTRL, "Running out of HBM controllers!"
    tcl = [
        f"""
# Create instance: noc_hbm_0, and set properties
set noc_hbm_0 [ create_bd_cell -type ip -vlnv xilinx.com:ip:axi_noc:1.0 noc_hbm_0 ]
set_property -dict [list \
    CONFIG.HBM_NUM_CHNL {{{hbm_chnl}}} \
    CONFIG.NUM_CLKS {{9}} \
    CONFIG.NUM_HBM_BLI {{0}} \
    CONFIG.NUM_MI {{{0 if fpd else 1}}} \
    CONFIG.NUM_SI {{8}} \
    CONFIG.NUM_NSI {{0}} \
] $noc_hbm_0
"""
    ]

    # ARM's NoC interfaces
    for i in range(8):
        # connect to all HBM channels
        if i in PS_CCI_PORT:
            category = "ps_cci"
        elif i in PS_NCI_PORT:
            category = "ps_nci"
        elif i in PS_RPU_PORT:
            category = "ps_rpu"
        elif i in PS_PMC_PORT:
            category = "ps_pmc"

        tcl += [
            f"set_property -dict [list \
                CONFIG.CATEGORY {{{category}}} \
                CONFIG.CONNECTIONS {{"
        ]
        if not fpd and i in PS_RPU_PORT:
            tcl += [
                "\
    M00_AXI {read_bw {50} write_bw {50} read_avg_burst {4} write_avg_burst {4}}"
            ]

        arm_s_axi = f"S{i:02d}_AXI"
        for _, attr in mmap_ports.items():
            # only provide read access to the output ports
            if attr["write_bw"] > 0:
                tcl += [
                    f"""\
    HBM{attr["bank"] // 2}_PORT{(attr["bank"] % 2) * 2} {{read_bw {{50}} write_bw {{0}}\
    read_avg_burst {{4}} write_avg_burst {{4}}}}"""
                ]
        tcl += [f"}}] [get_bd_intf_pins $noc_hbm_0/{arm_s_axi}]"]

        # associate busif to clk
        tcl += [
            f"""
set_property -dict [ list \
    CONFIG.ASSOCIATED_BUSIF {{{arm_s_axi}}} \
] [get_bd_pins $noc_hbm_0/aclk{i}]
"""
        ]

    tcl += [
        """
# Create interface connections
connect_bd_intf_net -intf_net CIPS_0_FPD_AXI_NOC_0 \
    [get_bd_intf_pins CIPS_0/FPD_AXI_NOC_0] [get_bd_intf_pins $noc_hbm_0/S04_AXI]
connect_bd_intf_net -intf_net CIPS_0_FPD_AXI_NOC_1 \
    [get_bd_intf_pins CIPS_0/FPD_AXI_NOC_1] [get_bd_intf_pins $noc_hbm_0/S05_AXI]
connect_bd_intf_net -intf_net CIPS_0_FPD_CCI_NOC_0 \
    [get_bd_intf_pins CIPS_0/FPD_CCI_NOC_0] [get_bd_intf_pins $noc_hbm_0/S00_AXI]
connect_bd_intf_net -intf_net CIPS_0_FPD_CCI_NOC_1 \
    [get_bd_intf_pins CIPS_0/FPD_CCI_NOC_1] [get_bd_intf_pins $noc_hbm_0/S01_AXI]
connect_bd_intf_net -intf_net CIPS_0_FPD_CCI_NOC_2 \
    [get_bd_intf_pins CIPS_0/FPD_CCI_NOC_2] [get_bd_intf_pins $noc_hbm_0/S02_AXI]
connect_bd_intf_net -intf_net CIPS_0_FPD_CCI_NOC_3 \
    [get_bd_intf_pins CIPS_0/FPD_CCI_NOC_3] [get_bd_intf_pins $noc_hbm_0/S03_AXI]
connect_bd_intf_net -intf_net CIPS_0_LPD_AXI_NOC_0 \
    [get_bd_intf_pins CIPS_0/LPD_AXI_NOC_0] [get_bd_intf_pins $noc_hbm_0/S06_AXI]
connect_bd_intf_net -intf_net CIPS_0_PMC_NOC_AXI_0 \
    [get_bd_intf_pins CIPS_0/PMC_NOC_AXI_0] [get_bd_intf_pins $noc_hbm_0/S07_AXI]

# Create port connections
connect_bd_net [get_bd_pins CIPS_0/fpd_axi_noc_axi0_clk] [get_bd_pins $noc_hbm_0/aclk4]
connect_bd_net [get_bd_pins CIPS_0/fpd_axi_noc_axi1_clk] [get_bd_pins $noc_hbm_0/aclk5]
connect_bd_net [get_bd_pins CIPS_0/fpd_cci_noc_axi0_clk] [get_bd_pins $noc_hbm_0/aclk0]
connect_bd_net [get_bd_pins CIPS_0/fpd_cci_noc_axi1_clk] [get_bd_pins $noc_hbm_0/aclk1]
connect_bd_net [get_bd_pins CIPS_0/fpd_cci_noc_axi2_clk] [get_bd_pins $noc_hbm_0/aclk2]
connect_bd_net [get_bd_pins CIPS_0/fpd_cci_noc_axi3_clk] [get_bd_pins $noc_hbm_0/aclk3]
connect_bd_net [get_bd_pins CIPS_0/lpd_axi_noc_clk] [get_bd_pins $noc_hbm_0/aclk6]
connect_bd_net [get_bd_pins CIPS_0/pmc_axi_noc_axi0_clk] \
    [get_bd_pins $noc_hbm_0/aclk7]
"""
    ]

    if fpd:
        tcl += [
            """
connect_bd_intf_net -intf_net CIPS_0_M_AXI_GP0 \
    [get_bd_intf_pins CIPS_0/M_AXI_FPD] [get_bd_intf_pins icn_ctrl/S00_AXI]
"""
        ]
    else:
        tcl += [
            """
connect_bd_intf_net -intf_net CIPS_0_M_AXI_GP0 \
    [get_bd_intf_pins /noc_hbm_0/M00_AXI] [get_bd_intf_pins icn_ctrl/S00_AXI]
set_property CONFIG.ASSOCIATED_BUSIF M00_AXI [get_bd_pins /noc_hbm_0/aclk8]
"""
        ]

    return tcl


def assign_arm_bd_address() -> list[str]:
    """Assigns the addresses of ARM, interrupt controller, DUT, and DDR.

    Returns a list of tcl commands.
    """
    return [
        """
# Auto-assigns all
assign_bd_address
"""
    ]
