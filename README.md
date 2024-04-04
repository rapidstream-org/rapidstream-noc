<!--
Copyright (c) 2024 RapidStream Design Automation, Inc. and contributors.
All rights reserved. The contributor(s) of this file has/have agreed to the
RapidStream Contributor License Agreement.
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

The RapidStream + NoC Project is an open source project under [Apache License, Version 2.0](LICENSE). By contributing to this open-source repository, you agree to the [RapidStream Contributor License Agreement](CLA.md).

-----

Copyright (c) 2024 RapidStream Design Automation, Inc. and contributors.  All rights reserved.
