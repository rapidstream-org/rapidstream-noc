"""Helper functions to generate tcl."""

__copyright__ = """
Copyright (c) 2024 RapidStream Design Automation, Inc. and contributors.
All rights reserved. The contributor(s) of this file has/have agreed to the
RapidStream Contributor License Agreement.
"""

import json

from device import Device
from ir_helper import extract_slot_coord, parse_floorplan


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
    streams_nodes: dict[str, dict[str, list[str]]], selected: list[str]
) -> list[str]:
    """Dumps the selected streams' NMU and NSU location tcl.

    Return a list of tcl commands.
    """
    tcl = []
    for port_num, s in enumerate(selected):
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
add_files -fileset sim_1 -norecurse /home/jakeke/rapidstream-noc/serpens_tb_a48.sv
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


if __name__ == "__main__":
    from vh1582_nocgraph import vh1582_nocgraph

    # autobridge json file to extract
    SERPENS_IR = "/home/jakeke/Serpens/vhk158/rs_ch28_noc_vivado/noc_pass.json"
    with open(SERPENS_IR, "r", encoding="utf-8") as file:
        design = json.load(file)

        serpens_floorplan = parse_floorplan(design, "axis_noc_if")

        print("Number of modules:", sum(len(v) for v in serpens_floorplan.values()))
        print(serpens_floorplan.keys())

        D = Device(
            name="",
            slot_width=2,
            slot_height=2,
            noc_graph=vh1582_nocgraph(),
            nmu_per_slot=[],  # generated
            nsu_per_slot=[],  # generated
            cr_mapping=[
                [
                    "CLOCKREGION_X0Y0:CLOCKREGION_X4Y4",
                    "CLOCKREGION_X0Y5:CLOCKREGION_X4Y7",
                ],
                [
                    "CLOCKREGION_X5Y0:CLOCKREGION_X9Y4",
                    "CLOCKREGION_X5Y5:CLOCKREGION_X9Y7",
                ],
            ],
        )

        test_tcl = export_constraint(serpens_floorplan, D)
        with open("constraint.tcl", "w", encoding="utf-8") as file:
            file.write("\n".join(test_tcl))
