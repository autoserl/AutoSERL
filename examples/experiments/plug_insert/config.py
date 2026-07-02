
import os
import jax
from jax._src.api import F
import jax.numpy as jnp
import numpy as np

from franka_env.envs.wrappers import (
    Quat2EulerWrapper,
    SpacemouseIntervention,
    MultiCameraBinaryRewardClassifierWrapper,
    SpacemouseActionRewardClassifierWrapper,
    GripperCloseEnv,
    auto_intervention_wrapper

)
from franka_env.envs.relative_env import RelativeFrame
from franka_env.envs.franka_env import DefaultEnvConfig
from serl_launcher.wrappers.serl_obs_wrappers import SERLObsWrapper
from serl_launcher.wrappers.chunking import ChunkingWrapper
from serl_launcher.networks.reward_classifier import load_classifier_func

from experiments.config import DefaultTrainingConfig
from experiments.plug_insert.wrapper import PlugInsertEnv

class EnvConfig(DefaultEnvConfig):
    SERVER_URL = "http://127.0.0.1:4000/"
    REALSENSE_CAMERAS = {
        "wrist_1": {
            "serial_number": "323622271139",
            "dim": (1280, 720),
            "exposure": 40000,
        },
        "wrist_2": {
            "serial_number": "230322271990",
            "dim": (1280, 720),
            "exposure": 40000,
        },
    }
    IMAGE_CROP = {
        "wrist_1": lambda img: img[:, 500:900],
        "wrist_2": lambda img: img[:, 500:900],
    }
    TARGET_POSE = np.array([0.7549959706206053,-0.06167101154454149,0.23046368580113635,-2.988483053349534,-0.92643416992811,-0.12250284877621564])
    
    GRASP_POSE = np.array([0.7549959706206053,-0.06167101154454149,0.23046368580113635,-2.988483053349534,-0.92643416992811,-0.12250284877621564])
    RESET_POSE = TARGET_POSE + np.array([0, 0, 0.15, 0, 0.0, 0])
    
    ABS_POSE_LIMIT_LOW = TARGET_POSE - np.array([0.03, 0.03, 0.01, 0.01, 0.01, 0.01])
    ABS_POSE_LIMIT_HIGH = TARGET_POSE + np.array([0.03, 0.03, 0.15+0.01, 0.01, 0.01, 0.01])
    
    RANDOM_RESET = False
    RANDOM_XY_RANGE = 0.03
    RANDOM_RZ_RANGE = 0
    

    ACTION_SCALE = (0.01, 0.06, 1)
    DISPLAY_IMAGE = True
    MAX_EPISODE_LENGTH = 300
    COMPLIANCE_PARAM = {
        "translational_stiffness": 3000,
        "translational_damping": 89,
        "rotational_stiffness": 150,
        "rotational_damping": 7,
        "translational_Ki": 0,
        "translational_clip_x": 0.0075,
        "translational_clip_y": 0.0016,
        "translational_clip_z": 0.0055,
        "translational_clip_neg_x": 0.002,
        "translational_clip_neg_y": 0.0016,
        "translational_clip_neg_z": 0.005,
        "rotational_clip_x": 0.01,
        "rotational_clip_y": 0.025,
        "rotational_clip_z": 0.02,
        "rotational_clip_neg_x": 0.01,
        "rotational_clip_neg_y": 0.025,
        "rotational_clip_neg_z": 0.02,
        "rotational_Ki": 0,
    }
    PRECISION_PARAM = {
        "translational_stiffness": 3000,
        "translational_damping": 89,
        "rotational_stiffness": 250,
        "rotational_damping": 9,
        "translational_Ki": 0.0,
        "translational_clip_x": 0.1,
        "translational_clip_y": 0.1,
        "translational_clip_z": 0.1,
        "translational_clip_neg_x": 0.1,
        "translational_clip_neg_y": 0.1,
        "translational_clip_neg_z": 0.1,
        "rotational_clip_x": 0.5,
        "rotational_clip_y": 0.5,
        "rotational_clip_z": 0.5,
        "rotational_clip_neg_x": 0.5,
        "rotational_clip_neg_y": 0.5,
        "rotational_clip_neg_z": 0.5,
        "rotational_Ki": 0.0,
    }


class TrainConfig(DefaultTrainingConfig):
    image_keys = ["wrist_1", "wrist_2"]
    classifier_keys = ["wrist_1", "wrist_2"]
    proprio_keys = ["tcp_pose", "tcp_vel", "tcp_force", "tcp_torque", "gripper_pose"]
    buffer_period = 1000
    checkpoint_period = 500
    steps_per_update = 50
    encoder_type = "resnet-pretrained"
    setup_mode = "single-arm-fixed-gripper"

    def get_environment(self, fake_env=False, save_video=False, classifier=False):
        env = PlugInsertEnv(
            fake_env=fake_env,
            save_video=save_video,
            config=EnvConfig(),
            set_load=False,
        )
        env = GripperCloseEnv(env)
        if not fake_env:
            env = SpacemouseActionRewardClassifierWrapper(env, target_pose=EnvConfig().TARGET_POSE)
                    
        env = RelativeFrame(env)
        
        
        env = Quat2EulerWrapper(env)
        env = SERLObsWrapper(env, proprio_keys=self.proprio_keys)
        env = ChunkingWrapper(env, obs_horizon=1, act_exec_horizon=None)
       
        env = auto_intervention_wrapper(env, EnvConfig().TARGET_POSE, demo_path="/home/cxl/hil-serl/examples/demo_data/plug_insert_1_demos_2026-02-27_16-30-01.pkl", th1=0.005, th2=0.02, l_term=10, l_stag=20, recover_point0=35, recover_point1=47, demo_initial_tcp_pose=EnvConfig().RESET_POSE) 
        return env