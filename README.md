# One Demonstration Is Enough for Real-World Robotic Reinforcement Learning

[![License: Apache 2.0](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)
[![Static Badge](https://img.shields.io/badge/Project-Page-a)](https://autoserl.github.io/)

**Webpage: [https://autoserl.github.io/](https://autoserl.github.io/)**

We provide the code and usage instructions for AutoSERL, which is built upon the [HIL-SERL](https://github.com/rail-berkeley/hil-serl) codebase.

**Table of Contents**
- [One Demonstration Is Enough for Real-World Robotic Reinforcement Learning](#one-demonstration-is-enough-for-real-world-robotic-reinforcement-learning)
  - [Installation](#installation)
  - [Code and Usage Instructions](#code-and-usage-instructions)
  - [Contact](#contact)
  - [Acknowledgement](#acknowledgement)
  <!-- - [Citation](#citation) -->

## Installation

Please follow the same environment setup instructions as [HIL-SERL](https://github.com/rail-berkeley/hil-serl).

## Code and Usage Instructions

The implementations of the ***Sliding Window Intervention***, ***Safety Recovery***, and ***Intervention Termination*** mechanisms are located in the `auto_intervention_wrapper` class within the `serl_robot_infra/franka_env/envs/wrappers.py` file. During training, the `auto_intervention_wrapper` class must be imported and configured with the appropriate parameters in `examples/experiments/task/config.py`, as shown in the table below.

| Parameter | Description |
| :--- | :--- |
| `demo_path` | The single demonstration trajectory used for reference by the automatic intervention mechanism. |
| `th1` | Intervention termination threshold (in meters). |
| `th2` | Intervention start threshold (in meters). |
| `l_term` | Intervention termination threshold used by the Intervention Termination Criterion (in timesteps). |
| `l_stag` | Window length used by the Safety Recovery Mechanism to detect stagnation (in timesteps). |
| `recover_point0` | The index of the safe recovery target to which the robot can be guided when a safety risk occurs. |
| `recover_point1` | The index of a trajectory point at which the robot is in stable contact with the interaction object. |

## Contact

If you have any questions, please contact yuwanliu06@gmail.com.

## Acknowledgement

Our codebase is developed based on [HIL-SERL](https://github.com/rail-berkeley/hil-serl). We sincerely thank the HIL-SERL team for their excellent work.

<!-- ## Citation

If you use this code for your research, please cite our paper:

```bibtex

``` -->

