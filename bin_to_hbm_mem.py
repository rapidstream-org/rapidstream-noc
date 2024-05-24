"""Merge .bin memory files to .mem files."""

__copyright__ = """
Copyright (c) 2024 RapidStream Design Automation, Inc. and contributors.
All rights reserved. The contributor(s) of this file has/have agreed to the
RapidStream Contributor License Agreement.
"""


def bin_to_hbm_mem(bin_dir: str, bin_dict: dict[str, str], output_file: str) -> None:
    """Merge multiple .bin memory files to one .mem file for HBM initialization.

    bin_dir:        directory of the .bin files.
    bin_dict:       {"bin file name": "start address in hex"}.
    output_file:    .mem output file.

    Returns None.
    """
    with open(output_file, "w", encoding="utf-8") as mem_file:
        for binary_file, address in bin_dict.items():
            mem_file.write(f"@{address}\n")
            with open(bin_dir + binary_file, "rb") as f:
                while chunk := f.read(32):
                    hex_data = " ".join(format(x, "02X") for x in chunk)
                    mem_file.write(hex_data + "\n")
            mem_file.write("\n")


if __name__ == "__main__":
    # Example usage:
    # Serpens a = 48
    SERPENS_BIN_DIR = "/home/jakeke/Serpens/vhk158/build48/tapa_sim_nasa4704/"
    serpens_bin_dict = {
        "0.bin": "47C0000000",
        "1.bin": "4000000000",
        "2.bin": "4020000000",
        "3.bin": "4040000000",
        "4.bin": "4060000000",
        "5.bin": "4080000000",
        "6.bin": "40A0000000",
        "7.bin": "40C0000000",
        "8.bin": "40E0000000",
        "9.bin": "4100000000",
        "10.bin": "4120000000",
        "11.bin": "4140000000",
        "12.bin": "4180000000",
        "13.bin": "41A0000000",
        "14.bin": "41C0000000",
        "15.bin": "4200000000",
        "16.bin": "4220000000",
        "17.bin": "4240000000",
        "18.bin": "4280000000",
        "19.bin": "42A0000000",
        "20.bin": "42C0000000",
        "21.bin": "4300000000",
        "22.bin": "4320000000",
        "23.bin": "4340000000",
        "24.bin": "4380000000",
        "25.bin": "43A0000000",
        "26.bin": "43C0000000",
        "27.bin": "4400000000",
        "28.bin": "4420000000",
        "29.bin": "4440000000",
        "30.bin": "4480000000",
        "31.bin": "44A0000000",
        "32.bin": "44C0000000",
        "33.bin": "4500000000",
        "34.bin": "4520000000",
        "35.bin": "4540000000",
        "36.bin": "4580000000",
        "37.bin": "45A0000000",
        "38.bin": "45C0000000",
        "39.bin": "4600000000",
        "40.bin": "4620000000",
        "41.bin": "4640000000",
        "42.bin": "4680000000",
        "43.bin": "46A0000000",
        "44.bin": "46C0000000",
        "45.bin": "4700000000",
        "46.bin": "4720000000",
        "47.bin": "4740000000",
        "48.bin": "4760000000",
        "49.bin": "4780000000",
        "50.bin": "47E0000000",
        "51.bin": "47A0000000",
    }
    SERPENS_MEM_FILE = "serpens_hbm48_nasa4704.mem"

    # Serpens a = 24
    # SERPENS_BIN_DIR = "/home/jakeke/Serpens/build/tapa_sim_nasa4704/"
    # serpens_bin_dict = {
    #     "0.bin":    "4600000000",
    #     "1.bin":    "4000000000",
    #     "2.bin":    "4040000000",
    #     "3.bin":    "4080000000",
    #     "4.bin":    "40C0000000",
    #     "5.bin":    "4100000000",
    #     "6.bin":    "4140000000",
    #     "7.bin":    "4180000000",
    #     "8.bin":    "41C0000000",
    #     "9.bin":    "4200000000",
    #     "10.bin":   "4240000000",
    #     "11.bin":   "4280000000",
    #     "12.bin":   "42C0000000",
    #     "13.bin":   "4300000000",
    #     "14.bin":   "4340000000",
    #     "15.bin":   "4380000000",
    #     "16.bin":   "43C0000000",
    #     "17.bin":   "4400000000",
    #     "18.bin":   "4440000000",
    #     "19.bin":   "4480000000",
    #     "20.bin":   "44C0000000",
    #     "21.bin":   "4500000000",
    #     "22.bin":   "4540000000",
    #     "23.bin":   "4580000000",
    #     "24.bin":   "45C0000000",
    #     "25.bin":   "4640000000",
    #     "26.bin":   "4680000000",
    # }
    # SERPENS_MEM_FILE = 'serpens_hbm24_nasa4704.mem'

    bin_to_hbm_mem(SERPENS_BIN_DIR, serpens_bin_dict, SERPENS_MEM_FILE)
