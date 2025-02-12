CDTN: Delay Tolerant Network Management Using Reinforcement Learning
=======================

## Installation

1. Create a conda environment using the conda_environment.yaml file:
```shell
conda env create -f conda_environment.yaml
```
2. Activate conda environment:

```shell
conda activate dtnsim
```

3. From project root install CDTN gym environment

```shell
pip install -e ./RL/gym-cdtn
```

## Usage

1. Run training using the file "training.py" from ./RL/ directory 

2. Run evaluation of the trained agent using the files "load_and_evaluate_lunar_agent.py" for the lunar scenario or "load_and_evaluate_EO_agent.py" for the Earth Observation Scenario, both located in the ./RL/ directory 

Note:

Several versions of the gym-cdtn environment have been included in this package. Check ./RL/gym-cdtn/gym_cdtn/__init__.py for the different environments ids.

- For the environment used in the ASCEND 2020 paper (https://arc.aiaa.org/doi/abs/10.2514/6.2020-4007) use `gym.make('cdtn-ASCEND2020-v0')`.
- For the environment used in the JAIS 2021 paper (https://arc.aiaa.org/doi/abs/10.2514/1.I010920) use `gym.make('cdtn-JAIS2021-v0')`.


## Plotting results

Check ./RL/results directory for the training/evaluation results obtained and the jupyter notebooks used to plot the figures that appear in published papers.

## DtnSim Simulator:

DtnSim documentation: https://dtnsim.readthedocs.io/en/latest/

License Terms
-------------

Copyright (c) 2019, California Institute of Technology ("Caltech").  
U.S. Government sponsorship acknowledged.

All rights reserved.

Redistribution and use in source and binary forms, with or without modification, 
are permitted provided that the following conditions are met:

* Redistributions of source code must retain the above copyright notice, 
  this list of conditions and the following disclaimer.
* Redistributions must reproduce the above copyright notice, this list 
  of conditions and the following disclaimer in the documentation and/or other 
  materials provided with the distribution.
* Neither the name of Caltech nor its operating division, the Jet Propulsion Laboratory, 
  nor the names of its contributors may be used to endorse or promote products 
  derived from this software without specific prior written permission.

THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS" AND 
ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED 
WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE DISCLAIMED. 
IN NO EVENT SHALL THE COPYRIGHT OWNER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, 
INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, 
BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA,
OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, 
WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) 
ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY 
OF SUCH DAMAGE.