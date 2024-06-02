"""Helper functions to generate tcl."""

__copyright__ = """
Copyright (c) 2024 RapidStream Design Automation, Inc. and contributors.
All rights reserved. The contributor(s) of this file has/have agreed to the
RapidStream Contributor License Agreement.
"""

import re

from device import Device
from ir_helper import extract_slot_coord


def print_noc_loc_tcl(node_loc: dict[str, tuple[str, str]]) -> None:
    """Prints the NMU and NSU location constraints in tcl."""
    tcl = []
    for port_num, (nmu_loc, nsu_loc) in enumerate(node_loc.values()):
        nmu_x, nmu_y = nmu_loc.split("x")[1].split("y")
        nsu_x, nsu_y = nsu_loc.split("x")[1].split("y")
        tcl += [
            f"set_property -dict [list CONFIG.PHYSICAL_LOC "
            f"{{NOC_NMU512_X{nmu_x}Y{nmu_y}}}] "
            f"[get_bd_intf_pins /axis_noc_dut/S{str(port_num).zfill(2)}"
            "_AXIS]"
        ]
        tcl += [
            f"set_property -dict [list CONFIG.PHYSICAL_LOC "
            f"{{NOC_NSU512_X{nsu_x}Y{nsu_y}}}] "
            f"[get_bd_intf_pins /axis_noc_dut/M{str(port_num).zfill(2)}"
            "_AXIS]"
        ]
    print("\n".join(tcl))


def dump_streams_loc_tcl(
    streams_nodes: dict[str, dict[str, list[str]]], noc_streams: list[str]
) -> list[str]:
    """Dumps the NoC streams' NMU and NSU location tcl.

    Return a list of tcl commands.
    """
    tcl = []
    for port_num, s in enumerate(noc_streams):
        slot_nmu_nodes = []
        slot_nsu_nodes = []
        for n in streams_nodes[s]["src"]:
            nmu_x, nmu_y = n.split("x")[1].split("y")
            slot_nmu_nodes.append(f"NOC_NMU512_X{nmu_x}Y{nmu_y}")
        for n in streams_nodes[s]["dest"]:
            nsu_x, nsu_y = n.split("x")[1].split("y")
            slot_nsu_nodes.append(f"NOC_NSU512_X{nsu_x}Y{nsu_y}")

        slot_nmu_nodes_str = ":".join(slot_nmu_nodes)
        slot_nsu_nodes_str = ":".join(slot_nsu_nodes)

        tcl += [
            f"""
set_property -dict [list CONFIG.PHYSICAL_LOC {{{slot_nmu_nodes_str}}}] \
    [get_bd_intf_pins /axis_noc_dut/S{str(port_num).zfill(2)}_AXIS]
set_property -dict [list CONFIG.PHYSICAL_LOC {{{slot_nsu_nodes_str}}}] \
    [get_bd_intf_pins /axis_noc_dut/M{str(port_num).zfill(2)}_AXIS]
"""
        ]
    return tcl


def gen_vivado_prj_tcl(vivado_prj_params: dict[str, str]) -> list[str]:
    """Generates tcl to create a Vivado project.

    Returns a list of tcl commands.
    """
    build_dir = vivado_prj_params["build_dir"]
    part_num = vivado_prj_params["part_num"]
    board_part = vivado_prj_params["board_part"]
    bd_name = vivado_prj_params["bd_name"]
    rtl_dir = vivado_prj_params["rtl_dir"]
    tb_file = vivado_prj_params["tb_file"]
    constraint = vivado_prj_params["constraint"]
    bd_tcl = vivado_prj_params["bd_tcl"]
    noc_tcl = vivado_prj_params["noc_tcl"]

    tcl = [
        """
proc getEnvInt { varName defaultIntValue } {
    set value [expr {[info exists ::env($varName)] ?$::env($varName) :$defaultIntValue}]
    return [expr {int($value)}]
}

proc import_ips_from_dir {dir} {
    # Get a list of all .xci files in the specified directory and its subdirectories
    foreach file [glob -nocomplain -directory $dir *] {
        if {[file isdirectory $file]} {
            set ip_file [glob -nocomplain -directory $file *.xci]
            puts "Importing IP: $ip_file"
            import_ip $ip_file
        }
    }
}
"""
    ]

    tcl += [
        f"""
create_project vivado_proj {build_dir}/vivado_proj -part {part_num}
set_property board_part {board_part} [current_project]
import_ips_from_dir {build_dir}/{rtl_dir}
import_files {build_dir}/{rtl_dir}

set_property SOURCE_SET sources_1 [get_filesets sim_1]
add_files -fileset sim_1 -norecurse {tb_file}
set_property top tb [get_filesets sim_1]
set_property top_lib xil_defaultlib [get_filesets sim_1]
update_compile_order -fileset sim_1
set_property -name {{xsim.simulate.log_all_signals}} -value {{true}} \
    -objects [get_filesets sim_1]

set constr_file [import_files -fileset constrs_1 {build_dir}/{constraint}]
set_property used_in_synthesis false $constr_file

upgrade_ip -quiet [get_ips *]
generate_target synthesis [ get_files *.xci ]

source {build_dir}/{bd_tcl}
source {build_dir}/{noc_tcl}
validate_bd_design
save_bd_design
make_wrapper -files [get_files {bd_name}.bd] -top -import
set_property top {bd_name}_wrapper [current_fileset]
generate_target all [get_files {bd_name}.bd]

set_property -name {{STEPS.SYNTH_DESIGN.ARGS.MORE OPTIONS}} \
    -value {{-mode out_of_context}} \
    -objects [get_runs synth_1]
launch_runs synth_1 -jobs [getEnvInt VIVADO_SYNTH_JOBS 8]
wait_on_run synth_1
launch_runs impl_1 -jobs 8
wait_on_run impl_1
close_project
"""
    ]
    return tcl


def export_constraint(floorplan: dict[str, list[str]], device: Device) -> list[str]:
    """Generates tcl constraints given the floorplan dictionary.

    Returns a list of tcl commands.
    """
    tcl = [
        """
# assign tb clk and reset to dummy pins for synthesis
set_property PACKAGE_PIN BP53 [get_ports pl0_ref_clk_0]
set_property IOSTANDARD LVDCI_15 [get_ports pl0_ref_clk_0]
set_property PACKAGE_PIN BR53 [get_ports pl0_resetn_0]
set_property IOSTANDARD LVDCI_15 [get_ports pl0_resetn_0]
"""
    ]
    for slot in floorplan.keys():
        slot1, slot2 = slot.split("_TO_")
        assert slot1 == slot2
        x, y = extract_slot_coord(slot1)
        cr = device.get_slot_cr(x, y)
        tcl += [
            f"""
# begin defining a slot
create_pblock {slot}
resize_pblock {slot} -add {cr}
"""
        ]

    for slot, mods in floorplan.items():
        tcl += [f"add_cells_to_pblock [get_pblocks {slot}] [get_cells -regex {{"]
        for m in mods:
            tcl += [f"    top_arm_i/dut_0/{m}"]
        tcl += ["}]"]

    tcl += [
        """
foreach pblock [get_pblocks -regexp SLOT_X\\d+Y\\d+_To_SLOT_X\\d+Y\\d+] {
  if {[get_property CELL_COUNT $pblock] == 0} {
    puts "WARNING: delete empty pblock $pblock "
    delete_pblocks $pblock
  }
}
foreach pblock [get_pblocks] {
  report_utilization -pblocks $pblock
}
"""
    ]
    return tcl


def dump_neg_paths_summary(build_dir: str) -> list[str]:
    """Generates tcl commands to dump all negative slack paths in the routed checkpoint.

    Returns a list of tcl commands.
    """
    tcl = [
        f"""
open_checkpoint \
    {build_dir}/vivado_proj/vivado_proj.runs/impl_1/top_arm_wrapper_routed.dcp
report_timing_summary -setup -max_paths 1000000 -no_pblock -no_header \
    -path_type summary -slack_lesser_than 0 \
    -file {build_dir}/neg_paths_summary.rpt
close_design
"""
    ]
    return tcl


def parse_neg_paths(
    build_dir: str, inter_slot_streams: list[str], noc_streams: list[str]
) -> None:
    """Parses the inter-slot streams and NoC streams' negative slack paths.

    Returns None and prints.
    """

    with open(f"{build_dir}/neg_paths_summary.rpt", "r", encoding="utf-8") as f:
        content = f.read()

    # Find the "Max Delay Paths" section
    max_delay_paths_section = re.search(
        r"Max Delay Paths(.*?)Pulse Width Checks", content, re.DOTALL
    )

    # Check if the section is found
    if not max_delay_paths_section:
        print("Max Delay Paths section not found.")
        return

    # Extract the section content
    lines = max_delay_paths_section.group(1).strip().split("\n")

    paths = []
    # Iterate over the lines to extract startpoint and endpoint names
    for i in range(3, len(lines), 3):  # Start from the third line and step by 3
        if len(lines) > i + 2:
            startpoint = lines[i].strip()
            endpoint = lines[i + 1].strip()
            slack = lines[i + 2].strip()
            assert startpoint != ""
            assert endpoint != ""
            assert float(slack) < 0
            paths.append((startpoint, endpoint, slack))

    def get_count_and_slack(
        paths: list[tuple[str, str, str]], streams: list[str]
    ) -> tuple[int, float]:
        count = 0
        total_slack = 0.0
        for startpoint, endpoint, slack in paths:
            for s in streams:
                if s in startpoint and s in endpoint:
                    count += 1
                    total_slack += float(slack)
        return count, total_slack

    print("Number of failing endpoints:", len(paths))
    count, total_slack = get_count_and_slack(paths, inter_slot_streams)
    print("Number of inter-slot streams paths with negative slack", count)
    print("Total negative slack of inter-slot streams:", total_slack)
    count, total_slack = get_count_and_slack(paths, noc_streams)
    print("Number of selected streams paths with negative slack:", count)
    print("Total negative slack of noc-streams:", total_slack)


if __name__ == "__main__":
    import subprocess

    DUMP_NEG_PATHS_TCL = "dump_neg_paths.tcl"
    TEST_DIR = "/home/jakeke/rapidstream-noc/test/build_a48_empty"
    test_tcl = dump_neg_paths_summary(TEST_DIR)
    with open(f"{TEST_DIR}/{DUMP_NEG_PATHS_TCL}", "w", encoding="utf-8") as file:
        file.write("\n".join(test_tcl))

    zsh_cmds = f"""
source ~/.zshrc && amd
vivado -mode batch -source {TEST_DIR}/{DUMP_NEG_PATHS_TCL}
"""
    print(zsh_cmds)
    subprocess.run(["zsh", "-c", zsh_cmds], check=True)

    inter_slot_fifos = [
        "PE_inst_Serpens_11_hs_if_din",
        "PE_inst_Serpens_26_hs_if_din",
        "PE_inst_Serpens_33_hs_if_din",
        "Yvec_inst_Serpens_2_hs_if_din",
        "Yvec_inst_Serpens_8_hs_if_din",
        "fifo_A_Serpens_0_hs_if_din",
        "fifo_A_Serpens_10_hs_if_din",
        "fifo_A_Serpens_1_hs_if_din",
        "fifo_A_Serpens_2_hs_if_din",
        "fifo_A_Serpens_33_hs_if_din",
        "fifo_A_Serpens_34_hs_if_din",
        "fifo_A_Serpens_35_hs_if_din",
        "fifo_A_Serpens_36_hs_if_din",
        "fifo_A_Serpens_37_hs_if_din",
        "fifo_A_Serpens_38_hs_if_din",
        "fifo_A_Serpens_39_hs_if_din",
        "fifo_A_Serpens_3_hs_if_din",
        "fifo_A_Serpens_40_hs_if_din",
        "fifo_A_Serpens_41_hs_if_din",
        "fifo_A_Serpens_42_hs_if_din",
        "fifo_A_Serpens_43_hs_if_din",
        "fifo_A_Serpens_44_hs_if_din",
        "fifo_A_Serpens_45_hs_if_din",
        "fifo_A_Serpens_46_hs_if_din",
        "fifo_A_Serpens_47_hs_if_din",
        "fifo_A_Serpens_4_hs_if_din",
        "fifo_A_Serpens_5_hs_if_din",
        "fifo_A_Serpens_6_hs_if_din",
        "fifo_A_Serpens_7_hs_if_din",
        "fifo_A_Serpens_8_hs_if_din",
        "fifo_A_Serpens_9_hs_if_din",
        "fifo_X_pe_Serpens_11_hs_if_din",
        "fifo_X_pe_Serpens_26_hs_if_din",
        "fifo_X_pe_Serpens_33_hs_if_din",
        "fifo_Y_pe_Serpens_11_hs_if_din",
        "fifo_Y_pe_Serpens_12_hs_if_din",
        "fifo_Y_pe_Serpens_13_hs_if_din",
        "fifo_Y_pe_Serpens_14_hs_if_din",
        "fifo_Y_pe_Serpens_15_hs_if_din",
        "fifo_Y_pe_Serpens_16_hs_if_din",
        "fifo_Y_pe_Serpens_17_hs_if_din",
        "fifo_Y_pe_Serpens_24_hs_if_din",
        "fifo_Y_pe_Serpens_25_hs_if_din",
        "fifo_Y_pe_Serpens_2_hs_if_din",
        "fifo_Y_pe_Serpens_33_hs_if_din",
        "fifo_Y_pe_Serpens_34_hs_if_din",
        "fifo_Y_pe_Serpens_35_hs_if_din",
        "fifo_Y_pe_Serpens_8_hs_if_din",
        "fifo_Y_pe_abd_Serpens_3_hs_if_din",
        "fifo_Y_pe_abd_Serpens_6_hs_if_din",
        "fifo_Y_pe_abd_Serpens_7_hs_if_din",
        "fifo_aXvec_Serpens_2_hs_if_din",
        "fifo_aXvec_Serpens_8_hs_if_din",
    ]

    selected = [
        "PE_inst_Serpens_11_hs_if_din",
        "Yvec_inst_Serpens_8_hs_if_din",
        "fifo_A_Serpens_0_hs_if_din",
        "fifo_A_Serpens_2_hs_if_din",
        "fifo_A_Serpens_39_hs_if_din",
        "fifo_A_Serpens_3_hs_if_din",
        "fifo_A_Serpens_43_hs_if_din",
        "fifo_A_Serpens_47_hs_if_din",
        "fifo_A_Serpens_7_hs_if_din",
        "fifo_X_pe_Serpens_11_hs_if_din",
        "fifo_X_pe_Serpens_26_hs_if_din",
        "fifo_X_pe_Serpens_33_hs_if_din",
        "fifo_Y_pe_Serpens_2_hs_if_din",
        "fifo_Y_pe_Serpens_33_hs_if_din",
        "fifo_Y_pe_Serpens_34_hs_if_din",
        "fifo_Y_pe_Serpens_35_hs_if_din",
        "fifo_Y_pe_abd_Serpens_6_hs_if_din",
        "fifo_Y_pe_abd_Serpens_7_hs_if_din",
        "fifo_aXvec_Serpens_8_hs_if_din",
    ]

    parse_neg_paths(TEST_DIR, inter_slot_fifos, selected)
