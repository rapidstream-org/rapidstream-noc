"""Frontend to run the NoC pass."""

__copyright__ = """
Copyright (c) 2024 RapidStream Design Automation, Inc. and contributors.
All rights reserved. The contributor(s) of this file has/have agreed to the
RapidStream Contributor License Agreement.
"""

import copy
import json
import os
import subprocess
import sys
from enum import Enum, auto

from device import Device
from gen_vivado_bd import gen_arm_bd_ddr, gen_arm_bd_hbm
from ir_helper import (
    FREQUENCY,
    parse_floorplan,
    parse_inter_slot,
    parse_top_mod,
    round_up_to_noc_tdata,
)
from noc_pass import greedy_selector, ilp_noc_selector, random_selector
from noc_rtl_wrapper import add_dont_touch, noc_rtl_wrapper
from tcl_helper import (
    dump_neg_paths_summary,
    dump_streams_loc_tcl,
    export_constraint,
    export_control_s_axi_constraint,
    export_noc_constraint,
    gen_vivado_prj_tcl,
    parse_neg_paths,
    print_noc_loc_tcl,
)
from vh1582_nocgraph import vh1582_nocgraph
from vp1802_nocgraph import vp1802_nocgraph


class DeviceEnum(Enum):
    """Supported FPGA devices."""

    VH1582 = auto()
    VP1802 = auto()


class SelectorEnum(Enum):
    """Supported NoC selectors."""

    NONE = auto()
    EMPTY = auto()
    RANDOM = auto()
    GREEDY = auto()
    GRB = auto()


if __name__ == "__main__":
    # command line inputs
    NUM_CMD_IN = 5
    if len(sys.argv) < NUM_CMD_IN:
        print(
            f"""
Please provide:
    1. the JSON file generated by Rapidstream's NOC pass
       or .xo file for the NONE selector
    2. device name: {[e.name for e in DeviceEnum]}
    3. design's <mmap_port.json>
    4. selector: {[e.name for e in SelectorEnum]}
    5. <optional> absolute path of build directory.
       If not specified, will only run selector.
"""
        )
        sys.exit(1)

    # autobridge json file to extract
    rapidstream_json = sys.argv[1]
    device_name = sys.argv[2]
    mmap_port_json = sys.argv[3]
    selector = sys.argv[4]
    build_dir = sys.argv[5]
    if rapidstream_json.endswith(".xo"):
        top_mod_name = sys.argv[6]

    # currently hard-coded parameters
    IMPL_FREQUENCY = "300.0"
    HBM_INIT_FILE = "/home/jakeke/rapidstream-noc/test/serpens_hbm48_nasa4704.mem"
    TB_FILE = "/home/jakeke/rapidstream-noc/test/serpens_tb_a48.sv"
    # HBM_INIT_FILE = "/home/jakeke/rapidstream-noc/test/serpens_hbm56_nasa4704.mem"
    # TB_FILE = "/home/jakeke/rapidstream-noc/test/serpens_tb_a56.sv"
    USE_M_AXI_FPD = False
    MULTI_SITE_NOC = False

    # intermediate dumps
    BD_NAME = "top_arm"
    GROUPED_MOD_NAME = "axis_noc_if"
    I_MMAP_PORT_JSON = "mmap_port.json"
    SELECTED_STREAMS_JSON = "noc_streams.json"
    NOC_PASS_JSON = "noc_pass.json"
    NOC_PASS_WRAPPER_JSON = "noc_pass_wrapper.json"
    RTL_FOLDER = "rtl/"
    NOC_CONSTRAINT_TCL = "noc_constraint.tcl"
    NOC_STREAMS_ATTR = "noc_streams_attr.json"
    CONSTRAINT_TCL = "constraint.tcl"
    VIVADO_BD_TCL = "arm_bd.tcl"
    VIVADO_PRJ_TCL = "run.tcl"
    DUMP_NEG_PATHS_TCL = "dump_neg_paths.tcl"

    with open(mmap_port_json, "r", encoding="utf-8") as file:
        mmap_port_ir = json.load(file)

    if device_name == DeviceEnum.VP1802.name:
        G = vp1802_nocgraph()
        PART_NUM = "xcvp1802-lsvc4072-2MP-e-S"
        BOARD_PART = "xilinx.com:vpk180:part0:1.2"
        cr_mapping = [
            [
                "CLOCKREGION_X0Y1:CLOCKREGION_X4Y4",
                "CLOCKREGION_X0Y5:CLOCKREGION_X4Y7",
                "CLOCKREGION_X0Y8:CLOCKREGION_X4Y10",
                "CLOCKREGION_X0Y11:CLOCKREGION_X4Y13",
            ],
            [
                "CLOCKREGION_X5Y1:CLOCKREGION_X9Y4",
                "CLOCKREGION_X5Y5:CLOCKREGION_X9Y7",
                "CLOCKREGION_X5Y8:CLOCKREGION_X9Y10",
                "CLOCKREGION_X5Y11:CLOCKREGION_X9Y13",
            ],
        ]

        D = Device(
            part_num=PART_NUM,
            board_part=BOARD_PART,
            slot_width=2,
            slot_height=4,
            noc_graph=G,
            nmu_per_slot=[],  # generated
            nsu_per_slot=[],  # generated
            cr_mapping=cr_mapping,
        )
    elif device_name == DeviceEnum.VH1582.name:
        G = vh1582_nocgraph()
        PART_NUM = "xcvh1582-vsva3697-2MP-e-S"
        BOARD_PART = "xilinx.com:vhk158:part0:1.1"
        cr_mapping = [
            [
                "CLOCKREGION_X0Y1:CLOCKREGION_X4Y4",
                "CLOCKREGION_X0Y5:CLOCKREGION_X4Y7",
            ],
            [
                "CLOCKREGION_X5Y1:CLOCKREGION_X9Y4",
                "CLOCKREGION_X5Y5:CLOCKREGION_X9Y7",
            ],
        ]

        D = Device(
            part_num=PART_NUM,
            board_part=BOARD_PART,
            slot_width=2,
            slot_height=2,
            noc_graph=G,
            nmu_per_slot=[],  # generated
            nsu_per_slot=[],  # generated
            cr_mapping=cr_mapping,
        )
    else:
        raise NotImplementedError

    if build_dir != "":
        if os.path.exists(build_dir):
            print(f"The folder '{build_dir}' already exists. Aborting.")
            sys.exit(1)
        else:
            zsh_cmds = f"""
mkdir {build_dir}
cp {rapidstream_json} {build_dir}/
cp {mmap_port_json} {build_dir}/{I_MMAP_PORT_JSON}
"""
            print(zsh_cmds)
            subprocess.run(["zsh", "-c", zsh_cmds], check=True)

    # Select streams for NoC
    if selector == SelectorEnum.NONE.name:
        streams_slots: dict[str, dict[str, str]] = {}
        noc_streams: list[str] = []
    else:
        with open(rapidstream_json, "r", encoding="utf-8") as file:
            rapidstream_ir = json.load(file)

        top_mod_name = rapidstream_ir["modules"]["top_name"]
        streams_slots, streams_widths = parse_inter_slot(parse_top_mod(rapidstream_ir))

        streams_bw = {}
        for s, w in streams_widths.items():
            streams_bw[s] = w * FREQUENCY / 8

        for s, attr in streams_slots.items():
            print(s, attr, streams_widths[s], streams_bw[s])
        assert len(streams_bw) == len(streams_slots), "parse_inter_slot ERROR"

        if selector == SelectorEnum.EMPTY.name:
            noc_streams = []
        elif selector == SelectorEnum.RANDOM.name:
            noc_streams = random_selector(streams_slots, D)
        elif selector == SelectorEnum.GREEDY.name:
            noc_streams = greedy_selector(streams_slots, D)
        elif selector == SelectorEnum.GRB.name:
            noc_streams, node_loc = ilp_noc_selector(streams_slots, streams_bw, D)
        else:
            raise NotImplementedError

    print("Top module name:", top_mod_name)
    print("Number of inter-slot streams:", len(streams_slots))
    print("Selected streams for NoC", noc_streams)
    for s in noc_streams:
        print(f"{s}\t {streams_slots[s]}\t {streams_widths[s]}")

    if build_dir != "":
        # dumps the selected streams json
        noc_stream_json = {GROUPED_MOD_NAME: noc_streams}
        with open(
            f"{build_dir}/{SELECTED_STREAMS_JSON}", "w", encoding="utf-8"
        ) as file:
            json.dump(noc_stream_json, file, indent=4)

        # generate grouped ir with the selected streams
        cc_ret_noc_stream: dict[str, dict[str, str]] = {}
        if selector == SelectorEnum.NONE.name:
            # skip generating grouped ir and wrapper
            assert rapidstream_json.endswith(".xo"), "NONE selector requires .xo input!"
            zsh_cmds = f"""
unzip {rapidstream_json} -d {build_dir}/tmp
mv {build_dir}/tmp/ip_repo/*/src {build_dir}/rtl
"""
        else:
            if selector == SelectorEnum.EMPTY.name:
                # skip generating grouped ir and wrapper
                # but add dont_touch to pipelining registers
                noc_pass_wrapper_ir = copy.deepcopy(rapidstream_ir)
                add_dont_touch(noc_pass_wrapper_ir)
            else:
                zsh_cmds = f"""
source ~/.zshrc && amd
rapidstream-optimizer -i {rapidstream_json} -o {build_dir}/{NOC_PASS_JSON} \
    create-group-wrapper --group-name-to-insts-json={build_dir}/{SELECTED_STREAMS_JSON}
"""
                print(zsh_cmds)
                subprocess.run(["zsh", "-c", zsh_cmds], check=True)

                # generate new rtl wrapper
                with open(
                    f"{build_dir}/{NOC_PASS_JSON}", "r", encoding="utf-8"
                ) as file:
                    noc_pass_ir = json.load(file)

                noc_pass_wrapper_ir, cc_ret_noc_stream = noc_rtl_wrapper(
                    noc_pass_ir, GROUPED_MOD_NAME
                )
                for s, attr in cc_ret_noc_stream.items():
                    print(f'{s}\t {attr["width"]}\t {attr["bandwidth"]}')

            with open(
                f"{build_dir}/{NOC_PASS_WRAPPER_JSON}", "w", encoding="utf-8"
            ) as file:
                json.dump(noc_pass_wrapper_ir, file, indent=4)

            zsh_cmds = f"""
rapidstream-exporter -i {build_dir}/{NOC_PASS_WRAPPER_JSON} -f {build_dir}/rtl
"""

        # export noc IPI constraints
        tcl = []
        if MULTI_SITE_NOC:
            # multi-site NoC constraints
            tcl = dump_streams_loc_tcl(
                streams_slots | cc_ret_noc_stream,
                noc_streams + list(cc_ret_noc_stream.keys()),
                D,
            )
        elif selector == SelectorEnum.GRB.name:
            # single site NoC constraint found by ILP
            tcl = print_noc_loc_tcl(node_loc)

        with open(f"{build_dir}/{NOC_CONSTRAINT_TCL}", "w", encoding="utf-8") as file:
            file.write("\n".join(tcl))

        # generate rtl folder
        print(zsh_cmds)
        subprocess.run(["zsh", "-c", zsh_cmds], check=True)

        # generate vivado bd tcl
        bd_attr = {
            "bd_name": BD_NAME,
            "top_mod": top_mod_name,
            "hbm_init_file": HBM_INIT_FILE,
            "frequency": IMPL_FREQUENCY,
        }

        noc_stream_attr: dict[str, dict[str, str]] = {}
        for s in noc_streams:
            noc_stream_attr[f"m_axis_{s}"] = {
                "dest": f"s_axis_{s}",
                "bandwidth": str(streams_bw[s]),
                "width": round_up_to_noc_tdata(str(streams_widths[s]), False),
            }

        for s, attr in cc_ret_noc_stream.items():
            noc_stream_attr[f"m_axis_{s}"] = {
                "dest": f"s_axis_{s}",
                "bandwidth": attr["bandwidth"],
                "width": attr["width"],
            }
        with open(f"{build_dir}/{NOC_STREAMS_ATTR}", "w", encoding="utf-8") as file:
            json.dump(noc_stream_attr, file, indent=4)

        if device_name == DeviceEnum.VP1802.name:
            tcl = gen_arm_bd_ddr(
                bd_attr=bd_attr,
                mmap_ports=mmap_port_ir,
                stream_attr=noc_stream_attr,
                fpd=USE_M_AXI_FPD,
            )
        elif device_name == DeviceEnum.VH1582.name:
            tcl = gen_arm_bd_hbm(
                bd_attr=bd_attr,
                mmap_ports=mmap_port_ir,
                stream_attr=noc_stream_attr,
                fpd=USE_M_AXI_FPD,
            )
        else:
            raise NotImplementedError
        with open(f"{build_dir}/{VIVADO_BD_TCL}", "w", encoding="utf-8") as file:
            file.write("\n".join(tcl))

        # export placement constraints
        if selector == SelectorEnum.NONE.name:
            tcl = []
        else:
            final_ir = (
                rapidstream_json
                if selector == SelectorEnum.EMPTY.name
                else f"{build_dir}/{NOC_PASS_WRAPPER_JSON}"
            )
            with open(final_ir, "r", encoding="utf-8") as file:
                noc_pass_wrapper_ir = json.load(file)

            floorplan = parse_floorplan(noc_pass_wrapper_ir, GROUPED_MOD_NAME)
            print("Number of modules:", sum(len(v) for v in floorplan.values()))
            print("Used slots: ", floorplan.keys())

            tcl = export_constraint(floorplan, D)

            # needed for multi-site NoC constraints
            if MULTI_SITE_NOC:
                tcl += export_noc_constraint(
                    streams_slots | cc_ret_noc_stream,
                    noc_streams + list(cc_ret_noc_stream.keys()),
                    D,
                )

            if not USE_M_AXI_FPD:
                tcl += export_control_s_axi_constraint(floorplan, D)

        with open(f"{build_dir}/{CONSTRAINT_TCL}", "w", encoding="utf-8") as file:
            file.write("\n".join(tcl))

        # generate vivado prj tcl
        tcl = gen_vivado_prj_tcl(
            {
                "build_dir": build_dir,
                "part_num": D.part_num,
                "board_part": D.board_part,
                "bd_name": BD_NAME,
                "rtl_dir": RTL_FOLDER,
                "tb_file": TB_FILE,
                "constraint": CONSTRAINT_TCL,
                "bd_tcl": VIVADO_BD_TCL,
                "noc_tcl": NOC_CONSTRAINT_TCL,
            }
        )
        with open(f"{build_dir}/{VIVADO_PRJ_TCL}", "w", encoding="utf-8") as file:
            file.write("\n".join(tcl))

        tcl = dump_neg_paths_summary(build_dir)
        with open(f"{build_dir}/{DUMP_NEG_PATHS_TCL}", "w", encoding="utf-8") as file:
            file.write("\n".join(tcl))

        # launch vivado
        zsh_cmds = f"""
source ~/.zshrc && amd
cd {build_dir}
vivado -mode batch -source {VIVADO_PRJ_TCL}
vivado -mode batch -source {DUMP_NEG_PATHS_TCL}
"""
        print(zsh_cmds)
        subprocess.run(["zsh", "-c", zsh_cmds], check=True)

        parse_neg_paths(build_dir, list(streams_slots.keys()), noc_streams)
