<!--
Copyright (c) 2024 RapidStream Design Automation, Inc. and contributors.  All rights reserved.
The contributor(s) of this file has/have agreed to the RapidStream Contributor License Agreement.
-->

<img src="https://imagedelivery.net/AU8IzMTGgpVmEBfwPILIgw/1b565657-df33-41f9-f29e-0d539743e700/128" width="64px" alt="RapidStream Logo" />


RapidStream + NoC
=================


Composing Large-Scale FPGA-Based Systems
----------------------------------------

[RapidStream](https://rapidstream-da.com/) is a streamlined development flow for modern FPGAs, designed to help users quickly create high-performance systems. By working alongside FPGA vendor tools, RapidStream allows for the easy integration of small building blocks into complex, high-frequency designs. Users can take advantage of RapidStream's Python-based scripting language to efficiently implement high-performance FPGA accelerators using software-defined flows.


Requirements
------------

- `Python3`: 3.10 or later.
- `poetry`: to manage virtual environment and dependencies.

You must have RapidStream installed, a valid RapidStream license, and a valid Vivado Design Suite license to download or run the RapidStream DSE Engine. If you are an academic researcher or would like to contribute to this project, please contact us at https://rapidstream-da.com/ for a free RapidStream license.

The default branch always matches the latest RapidStream release. Please update your software before using the DSE engine.


Installation
------------

```bash
git clone https://github.com/rapidstream-org/rapidstream-noc.git
cd rapidstream-noc
curl -fsSL https://install.python-poetry.org/ | python3.10 -
poetry install --with=dev
```


Before Committing
-----------------

All tests and pre-commit checks shall pass before committing to the main repository.

Before your first commit, you must install pre-commit for Git:

```bash
poetry run pre-commit install
```

To invoke `pre-commit` without committing the changes:

```bash
poetry run pre-commit
```


License
-------

The RapidStream DSE Engine is an open source project managed by RapidStream Design Automation, Inc., who is authorized by the contributors to license the software under a dual licensing model:

1. **Open-Source License (AGPL):** The RapidStream DSE Engine is available as free and open-source software under the GNU Affero General Public License (AGPL) version 3.0 or later. You can redistribute it and/or modify it under the terms of the AGPL. If you use this software, in whole or in part, in any form (including binary, linked, or as a network service), in your product or to provide a service, you must make your complete source code, including any modifications or additions, available to users under the terms of the AGPL. This requirement applies regardless of how the software is integrated or deployed, ensuring that the entire codebase remains open-source and accessible to the community.

2. **Commercial License:** For customers who prefer a closed-source, commercial license that allows them to use the RapidStream DSE Engine in their products without the open-source requirements of the AGPL, RapidStream Design Automation, Inc. offers a separate commercial license. This commercial license eliminates the AGPL's stipulations, such as the requirement to make the source code of your product available to users. If you are interested in obtaining a commercial license for RapidStream, please contact info@rapidstream-da.com for more information.


Contributor License Agreement (CLA)
-----------------------------------

By contributing to this open-source repository, you agree to the RapidStream Contributor License Agreement.

Under this agreement, you grant to RapidStream Design Automation, Inc. and to recipients of software distributed by RapidStream a perpetual, worldwide, non-exclusive, no-charge, royalty-free, irrevocable copyright license to reproduce, prepare derivative works of, publicly display, publicly perform, sublicense, and distribute your contributions and such derivative works. You also grant to RapidStream Design Automation, Inc. and to recipients of software distributed by RapidStream a perpetual, worldwide, non-exclusive, no-charge, royalty-free, irrevocable patent license to make, have made, use, offer to sell, sell, import, and otherwise transfer the work,

Please note that this is a summary of the licensing terms, and the full text of the [AGPL](https://www.gnu.org/licenses/agpl-3.0.txt) and the [RapidStream Contributor License Agreement](CLA.md) should be consulted for detailed legal information.


-----

Copyright (c) 2024 RapidStream Design Automation, Inc. and contributors.  All rights reserved.
