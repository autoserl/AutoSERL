from re import T
import time
from gymnasium import Env, spaces
import gymnasium as gym
from jax._src.api import F
import numpy as np
from gymnasium.spaces import Box
import copy

# from sympy.core.logic import And
from franka_env.spacemouse.spacemouse_expert import SpaceMouseExpert
import requests
from scipy.spatial.transform import Rotation as R
from franka_env.envs.franka_env import FrankaEnv
from typing import List
import pickle

sigmoid = lambda x: 1 / (1 + np.exp(-x))

class HumanClassifierWrapper(gym.Wrapper):
    def __init__(self, env):
        super().__init__(env)
    
    def step(self, action):
        obs, rew, done, truncated, info = self.env.step(action)
        if done:
            while True:
                try:
                    rew = int(input("Success? (1/0)"))
                    assert rew == 0 or rew == 1
                    break
                except:
                    continue
        info['succeed'] = rew
        return obs, rew, done, truncated, info
    
    def reset(self, **kwargs):
        obs, info = self.env.reset(**kwargs)
        return obs, info
    
class MultiCameraBinaryRewardClassifierWrapper(gym.Wrapper):
    """
    This wrapper uses the camera images to compute the reward,
    which is not part of the observation space
    """

    def __init__(self, env: Env, reward_classifier_func, target_hz = None):
        super().__init__(env)
        self.reward_classifier_func = reward_classifier_func
        self.target_hz = target_hz

    def compute_reward(self, obs):
        if self.reward_classifier_func is not None:
            return self.reward_classifier_func(obs)
        return 0

    def step(self, action):
        start_time = time.time()
        obs, rew, done, truncated, info = self.env.step(action)
        rew = self.compute_reward(obs)
        done = done or rew
        info['succeed'] = bool(rew)
        if self.target_hz is not None:
            time.sleep(max(0, 1/self.target_hz - (time.time() - start_time)))
            
        return obs, rew, done, truncated, info

    def reset(self, **kwargs):
        obs, info = self.env.reset(**kwargs)
        info['succeed'] = False
        return obs, info

class SpacemouseActionRewardClassifierWrapper(gym.ActionWrapper):
    def __init__(self, env, target_pose, action_indices=None):
        super().__init__(env)
        self.target_pose = target_pose
        self.gripper_enabled = True
        if self.action_space.shape == (6,):
            self.gripper_enabled = False

        self.expert = SpaceMouseExpert()
        self.left, self.right = False, False
        self.action_indices = action_indices

    def action(self, action: np.ndarray) -> np.ndarray:
        """
        Input:
        - action: policy action
        Output:
        - action: spacemouse action if nonezero; else, policy action
        """
        expert_a, buttons = self.expert.get_action()
        self.left, self.right = tuple(buttons)
        intervened = False
        
        if np.linalg.norm(expert_a) > 0.001:
            intervened = True

        if self.gripper_enabled:
            if self.left:  # close gripper
                gripper_action = np.random.uniform(-1, -0.9, size=(1,))
                intervened = True
            elif self.right:  # open gripper
                gripper_action = np.random.uniform(0.9, 1, size=(1,))
                intervened = True
            else:
                gripper_action = np.zeros((1,))
            expert_a = np.concatenate((expert_a, gripper_action), axis=0)

        if self.action_indices is not None:
            filtered_expert_a = np.zeros_like(expert_a)
            filtered_expert_a[self.action_indices] = expert_a[self.action_indices]
            expert_a = filtered_expert_a

        if intervened:
            return expert_a, True

        return action, False

    def step(self, action):

        new_action, replaced = self.action(action)

        obs, rew, done, truncated, info = self.env.step(new_action)
        rew = (self.left)
        
        done = (done or rew) or self.right
        info['succeed'] = bool(rew)
        if replaced:
            info["intervene_action"] = new_action
        info["left"] = self.left
        info["right"] = self.right
        return obs, rew, done, truncated, info
    
    
class MultiStageBinaryRewardClassifierWrapper(gym.Wrapper):
    def __init__(self, env: Env, reward_classifier_func: List[callable]):
        super().__init__(env)
        self.reward_classifier_func = reward_classifier_func
        self.received = [False] * len(reward_classifier_func)
    
    def compute_reward(self, obs):
        rewards = [0] * len(self.reward_classifier_func)
        for i, classifier_func in enumerate(self.reward_classifier_func):
            if self.received[i]:
                continue

            logit = classifier_func(obs).item()
            if sigmoid(logit) >= 0.75:
                self.received[i] = True
                rewards[i] = 1

        reward = sum(rewards)
        return reward

    def step(self, action):
        obs, rew, done, truncated, info = self.env.step(action)
        rew = self.compute_reward(obs)
        done = (done or all(self.received)) # either environment done or all rewards satisfied
        info['succeed'] = all(self.received)
        return obs, rew, done, truncated, info

    def reset(self, **kwargs):
        obs, info = self.env.reset(**kwargs)
        self.received = [False] * len(self.reward_classifier_func)
        info['succeed'] = False
        return obs, info


class Quat2EulerWrapper(gym.ObservationWrapper):
    """
    Convert the quaternion representation of the tcp pose to euler angles
    """

    def __init__(self, env: Env):
        super().__init__(env)
        assert env.observation_space["state"]["tcp_pose"].shape == (7,)
        # from xyz + quat to xyz + euler
        self.observation_space["state"]["tcp_pose"] = spaces.Box(
            -np.inf, np.inf, shape=(6,)
        )

    def observation(self, observation):
        # convert tcp pose from quat to euler
        tcp_pose = observation["state"]["tcp_pose"]
        observation["state"]["tcp_pose"] = np.concatenate(
            (tcp_pose[:3], R.from_quat(tcp_pose[3:]).as_euler("xyz"))
        )
        return observation


class Quat2R2Wrapper(gym.ObservationWrapper):
    """
    Convert the quaternion representation of the tcp pose to rotation matrix
    """

    def __init__(self, env: Env):
        super().__init__(env)
        assert env.observation_space["state"]["tcp_pose"].shape == (7,)
        # from xyz + quat to xyz + euler
        self.observation_space["state"]["tcp_pose"] = spaces.Box(
            -np.inf, np.inf, shape=(9,)
        )

    def observation(self, observation):
        tcp_pose = observation["state"]["tcp_pose"]
        r = R.from_quat(tcp_pose[3:]).as_matrix()
        observation["state"]["tcp_pose"] = np.concatenate(
            (tcp_pose[:3], r[..., :2].flatten())
        )
        return observation


class DualQuat2EulerWrapper(gym.ObservationWrapper):
    """
    Convert the quaternion representation of the tcp pose to euler angles
    """

    def __init__(self, env: Env):
        super().__init__(env)
        assert env.observation_space["state"]["left/tcp_pose"].shape == (7,)
        assert env.observation_space["state"]["right/tcp_pose"].shape == (7,)
        # from xyz + quat to xyz + euler
        self.observation_space["state"]["left/tcp_pose"] = spaces.Box(
            -np.inf, np.inf, shape=(6,)
        )
        self.observation_space["state"]["right/tcp_pose"] = spaces.Box(
            -np.inf, np.inf, shape=(6,)
        )

    def observation(self, observation):
        # convert tcp pose from quat to euler
        tcp_pose = observation["state"]["left/tcp_pose"]
        observation["state"]["left/tcp_pose"] = np.concatenate(
            (tcp_pose[:3], R.from_quat(tcp_pose[3:]).as_euler("xyz"))
        )
        tcp_pose = observation["state"]["right/tcp_pose"]
        observation["state"]["right/tcp_pose"] = np.concatenate(
            (tcp_pose[:3], R.from_quat(tcp_pose[3:]).as_euler("xyz"))
        )
        return observation
    
    def reset(self, **kwargs):
        obs, info = self.env.reset(**kwargs)
        return self.observation(obs), info

class GripperCloseEnv(gym.ActionWrapper):
    """
    Use this wrapper to task that requires the gripper to be closed
    """

    def __init__(self, env):
        super().__init__(env)
        ub = self.env.action_space
        assert ub.shape == (7,)
        self.action_space = Box(ub.low[:6], ub.high[:6])

    def action(self, action: np.ndarray) -> np.ndarray:
        new_action = np.zeros((7,), dtype=np.float32)
        new_action[:6] = action.copy()
        return new_action

    def step(self, action):
        new_action = self.action(action)
        obs, rew, done, truncated, info = self.env.step(new_action)
        if "intervene_action" in info:
            info["intervene_action"] = info["intervene_action"][:6]
        return obs, rew, done, truncated, info
    
    def reset(self, **kwargs):
        return self.env.reset(**kwargs)

    
class SpacemouseIntervention(gym.ActionWrapper):
    def __init__(self, env, action_indices=None):
        super().__init__(env)

        self.gripper_enabled = True
        if self.action_space.shape == (6,):
            self.gripper_enabled = False

        self.expert = SpaceMouseExpert()
        self.left, self.right = False, False
        self.action_indices = action_indices

    def action(self, action: np.ndarray) -> np.ndarray:
        """
        Input:
        - action: policy action
        Output:
        - action: spacemouse action if nonezero; else, policy action
        """
        expert_a, buttons = self.expert.get_action()
        self.left, self.right = tuple(buttons)
        intervened = False
        
        if np.linalg.norm(expert_a) > 0.001:
            intervened = True

        if self.gripper_enabled:
            if self.left:  # close gripper
                gripper_action = np.random.uniform(-1, -0.9, size=(1,))
                intervened = True
            elif self.right:  # open gripper
                gripper_action = np.random.uniform(0.9, 1, size=(1,))
                intervened = True
            else:
                gripper_action = np.zeros((1,))
            expert_a = np.concatenate((expert_a, gripper_action), axis=0)

        if self.action_indices is not None:
            filtered_expert_a = np.zeros_like(expert_a)
            filtered_expert_a[self.action_indices] = expert_a[self.action_indices]
            expert_a = filtered_expert_a

        if intervened:
            return expert_a, True

        return action, False

    def step(self, action):

        new_action, replaced = self.action(action)

        obs, rew, done, truncated, info = self.env.step(new_action)
        if replaced:
            info["intervene_action"] = new_action
        info["left"] = self.left
        info["right"] = self.right
        return obs, rew, done, truncated, info
import random
class auto_intervention_wrapper(gym.ActionWrapper):
    def __init__(self, env, target_pose, demo_path="", th1=0.005, th2=0.02, l_term=10, l_stag=20, recover_point0=35, recover_point1=None, demo_initial_tcp_pose=np.array([0.5011313039503567,-0.031375358554046454,0.14910479220979933+0.05, np.pi, 0, 1.54927934])):
        super().__init__(env)
        self.demo_path = demo_path
        self.demo_tcp_list = []
        self.target_pose = target_pose
        # params
        ####################################
        self.expert = SpaceMouseExpert()
        self.left, self.right = False, False
        self.intervened_slide_idx = -1
        self.demo_initial_tcp_pose = demo_initial_tcp_pose 
        self.demo_action_in_eeframe_list = []
        self.load_intervention_demo()
        self.demo_tcp_buffer = []
        self.demo_tcp_buffer.append(copy.deepcopy(self.demo_tcp_list))
        self.current_demo_tcp_list = copy.deepcopy(self.demo_tcp_list)
        self.total_recover_cnt = 0
        self.total_episode_cnt = 0

        self.trans_dist_threshold = th2
        self.intervention_conclusion_trans_threshold = th1
        self.continued_control_step_cnt_threshold = l_stag 
        self.intervention_termination_step_threshold = l_term
        self.intervened_slide_idx_buffer_recover_threshold = 1

        self.recover_index0 = recover_point0
        if recover_point1 != None:
            self.recover_index1 = recover_point1
        else:
            self.recover_index1 = len(self.current_demo_tcp_list)-1
        self.window_length = (self.recover_index1 - self.recover_index0 + 1)
        
        self.slide_window = [i for i in range(self.window_length)]
        self.recover_action_list = []
        self.intervened_slide_idx_buffer = {i: [] for i in range(len(self.current_demo_tcp_list))}
        self.intervened_slide_idx_buffer[-1] = []
        self.current_step = 0
        self.before_intervened_completed_traj_min_idx = -1
        self.detect_nomove_window = [np.array([100, 100, 100, 0, 0, 0, 1]) for i in range(self.continued_control_step_cnt_threshold)]
        
        self.intervention_cnt = 0
        self.total_intervention_cnt = 0
        self.forever_no_window_intervention = False
        self.stagnation_pose = np.array([100, 100, 100, 0, 0, 0, 1])

    def load_intervention_demo(self):
        with open(self.demo_path, 'rb') as f:
            demo_data = pickle.load(f)
            demo_tcp_list = []
            demo_data_list = demo_data
            for data in demo_data_list:
                demo_tcp_list.append(data['observations']['state'][0][4:11])
            curr_demo_tcp_list = np.array(copy.deepcopy(demo_tcp_list))
            
            curr_demo_tcp_list[:, :3] = R.from_euler("xyz", np.tile(self.demo_initial_tcp_pose[3:], (len(curr_demo_tcp_list), 1))).apply(curr_demo_tcp_list[:, :3]) + np.tile(self.demo_initial_tcp_pose[:3], (len(curr_demo_tcp_list), 1))
            curr_demo_tcp_list[:, 3:] = (R.from_euler("xyz", np.tile(self.demo_initial_tcp_pose[3:], (len(curr_demo_tcp_list), 1)))*R.from_quat(curr_demo_tcp_list[:, 3:])).as_quat()
            
            self.demo_tcp_list = curr_demo_tcp_list
            self.demo_action_in_eeframe_list = [data["actions"] for data in demo_data]
            
    def select_minidist_point(self, tcp_pose, input_curr_demo_tcp_list):
        
        curr_demo_tcp_list = copy.deepcopy(input_curr_demo_tcp_list)
        tcp_pose = np.array(tcp_pose)

        demo_tcp_pos = curr_demo_tcp_list[:, :3]
        demo_tcp_quat = curr_demo_tcp_list[:, 3:]

        trans_dist = np.linalg.norm(demo_tcp_pos - tcp_pose[:3], axis=1)

        tcp_rot = R.from_quat(tcp_pose[3:])
        demo_rot = R.from_quat(demo_tcp_quat)
        relative_rot = demo_rot.inv() * tcp_rot
        rot_dist = relative_rot.magnitude()  

        min_idx = np.argmin(trans_dist)

        return trans_dist[min_idx], rot_dist[min_idx], min_idx

    def compute_delta_pose(self, curr_pose, target_pose):
        t_curr, q_curr = np.array(curr_pose[:3]), np.array(curr_pose[3:])
        t_tgt,  q_tgt  = np.array(target_pose[:3]), np.array(target_pose[3:])
        
        r_curr = R.from_quat(q_curr)
        r_tgt  = R.from_quat(q_tgt)

        r_rel = (r_tgt*r_curr.inv()).as_rotvec()/self.action_scale[1]
        t_rel = (t_tgt - t_curr)/self.action_scale[0]

        delta_pose = np.clip(np.concatenate([t_rel, r_rel]), -1, 1)
        return delta_pose

    def find_closest_intervention_point(self, min_idx):
        point0 = self.recover_index0
        point1 = self.recover_index1
        
        if (min_idx in range(point0, point1+1)) and (len(self.intervened_slide_idx_buffer[self.recover_index0]) >= self.intervened_slide_idx_buffer_recover_threshold):
            return self.recover_index0
        return -1

    def judge_whether_true_intervention(self, intervention_point, completed_traj_min_idx):
        if completed_traj_min_idx == len(self.current_demo_tcp_list) - 1:
            demo_point0 = self.current_demo_tcp_list[completed_traj_min_idx-1]
            demo_point1 = self.current_demo_tcp_list[completed_traj_min_idx]
        else:
            demo_point0 = self.current_demo_tcp_list[completed_traj_min_idx]
            demo_point1 = self.current_demo_tcp_list[completed_traj_min_idx+1]
        direction = demo_point1[:3] - demo_point0[:3]
        direction = direction / np.linalg.norm(direction)
        current_direction = intervention_point[:3] - self.env.currpos[:3]
        current_direction = current_direction / np.linalg.norm(current_direction)
        cos_theta = np.dot(direction, current_direction)
        if cos_theta >= 0:
            return True
        else:
            return False

    def check_action_converged(self, pos_threshold=0.001, rot_threshold=0.01):
        pos_error = np.linalg.norm(self.env.currpos[:3] - self.prev_currpos[:3])
        
        r_curr = R.from_quat(self.env.currpos[3:])
        r_prev = R.from_quat(self.prev_currpos[3:])
        rot_error = (r_prev.inv() * r_curr).magnitude()
        converged = pos_error < pos_threshold and rot_error < rot_threshold
        
        return converged

    def cal_action(self, action: np.ndarray) -> np.ndarray:
        intervened = False
        trans_dist, rot_dist, min_idx = self.select_minidist_point(copy.deepcopy(self.env.currpos), copy.deepcopy(self.current_demo_tcp_list[np.array(self.slide_window)]))
        completed_traj_trans_dist, completed_traj_rot_dist, completed_traj_min_idx = self.select_minidist_point(copy.deepcopy(self.env.currpos), copy.deepcopy(self.current_demo_tcp_list))
       
       # Sliding Window Intervention
        if (trans_dist > self.trans_dist_threshold) and (self.before_intervened_completed_traj_min_idx == -1) and (not self.forever_no_window_intervention):
            if self.judge_whether_true_intervention(self.current_demo_tcp_list[self.slide_window[min_idx]], completed_traj_min_idx):
                self.intervened_slide_idx = self.slide_window[min_idx]

        # Safety Recovery Mechanism    
        idx = self.find_closest_intervention_point(completed_traj_min_idx)
        if len(self.detect_nomove_window) == self.continued_control_step_cnt_threshold:
            self.detect_nomove_window.pop(0)
        self.detect_nomove_window.append(copy.deepcopy(self.current_demo_tcp_list[completed_traj_min_idx]))
        if ((self.before_intervened_completed_traj_min_idx == -1) and (idx != -1)) and (not self.forever_no_window_intervention):
            self.intervened_slide_idx = copy.deepcopy(idx)
            self.recover_action_list = self.demo_action_in_eeframe_list[self.intervened_slide_idx:(self.intervened_slide_idx_buffer[self.intervened_slide_idx] + 1)]
            self.before_intervened_completed_traj_min_idx = copy.deepcopy(idx)
            self.total_recover_cnt += 1
        
        if (self.intervened_slide_idx != -1):
            target_point = copy.deepcopy(self.current_demo_tcp_list[self.intervened_slide_idx])
            tcp_rot = R.from_quat(self.env.currpos[3:])
            demo_rot = R.from_quat(target_point[3:])
            relative_rot = demo_rot.inv() * tcp_rot
            rot_dist = relative_rot.magnitude()  # gives the rotation angle (radians)
            trans_dist = np.linalg.norm(target_point[:3] - self.env.currpos[:3])
            if (trans_dist < self.intervention_conclusion_trans_threshold) or (self.check_action_converged() and (np.linalg.norm(self.env.currpos[:3] - self.stagnation_pose[:3]) > self.intervention_conclusion_trans_threshold)):
                if len(self.intervened_slide_idx_buffer[self.before_intervened_completed_traj_min_idx]) >= self.intervened_slide_idx_buffer_recover_threshold:
                    self.intervened_slide_idx_buffer[self.before_intervened_completed_traj_min_idx] = []
                self.intervened_slide_idx = -1
        
        if ((self.before_intervened_completed_traj_min_idx == -1) and (np.linalg.norm(self.detect_nomove_window[-1][:3] - self.detect_nomove_window[0][:3]) < self.intervention_conclusion_trans_threshold) and (completed_traj_min_idx >= self.recover_index0) and (completed_traj_min_idx <= self.recover_index1)) and (not self.forever_no_window_intervention):
            self.intervened_slide_idx = -1
            self.intervened_slide_idx_buffer[self.recover_index0].append(self.recover_index1)
            self.stagnation_pose = copy.deepcopy(self.env.currpos)
        
        if (self.intervened_slide_idx != -1):
            expert_a = self.compute_delta_pose(copy.deepcopy(self.env.currpos), copy.deepcopy(self.current_demo_tcp_list[self.intervened_slide_idx]))[:6]
            intervened = True
            
        if (len(self.recover_action_list) > 0) and (self.intervened_slide_idx_buffer[self.before_intervened_completed_traj_min_idx] == []):
            expert_a = self.transform_action(self.recover_action_list.pop(0))
            intervened = True
            if len(self.recover_action_list) == 0:
                self.before_intervened_completed_traj_min_idx = -1
                self.stagnation_pose = np.array([100, 100, 100, 0, 0, 0, 1])
        if intervened:
            return expert_a, True
        return action, False

    def step(self, action):
        _, buttons = self.expert.get_action()
        self.left, self.right = tuple(buttons)

        new_action, replaced = self.cal_action(action)
        if replaced:
            self.intervention_cnt += 1
            new_action = self.transform_action_inv(new_action)
        self.prev_currpos = copy.deepcopy(self.env.currpos)
        obs, rew, done, truncated, info = self.env.step(new_action)
        rew = (self.left)
        
        done = (done or rew) or self.right
        
        # Intervention Termination
        if (self.intervention_cnt < self.intervention_termination_step_threshold) and (rew == 1) and done:
            self.forever_no_window_intervention = True
        
        self.current_step += 1
        
        if replaced:
            info["intervene_action"] = new_action
        if (self.intervened_slide_idx == -1):
            self.slide_window.pop(0)
            self.slide_window.append(min(self.slide_window[-1]+1, len(self.current_demo_tcp_list)-1))
        
        return obs, rew, done, truncated, info

    def reset(self, **kwargs):
        self.total_episode_cnt += 1
        self.intervened_slide_idx = -1
        obs, info = self.env.reset(**kwargs)
        self.prev_currpos = copy.deepcopy(self.env.currpos)
        self.slide_window = [i for i in range(self.window_length)]
        
        self.recover_action_list = []
        self.current_step = 0
        self.detect_nomove_window = [np.array([100, 100, 100, 0, 0, 0, 1]) for i in range(self.continued_control_step_cnt_threshold)]
        self.stagnation_pose = np.array([100, 100, 100, 0, 0, 0, 1])
        self.before_intervened_completed_traj_min_idx = -1
        self.intervention_cnt = 0
        self.total_intervention_cnt = 0
        self.intervened_slide_idx_buffer = {i: [] for i in range(len(self.current_demo_tcp_list))}
        self.intervened_slide_idx_buffer[-1] = []
        return obs, info
    
    
class DualSpacemouseIntervention(gym.ActionWrapper):
    def __init__(self, env, action_indices=None, gripper_enabled=True):
        super().__init__(env)

        self.gripper_enabled = gripper_enabled

        self.expert = SpaceMouseExpert()
        self.left1, self.left2, self.right1, self.right2 = False, False, False, False
        self.action_indices = action_indices

    def action(self, action: np.ndarray) -> np.ndarray:
        """
        Input:
        - action: policy action
        Output:
        - action: spacemouse action if nonezero; else, policy action
        """
        intervened = False
        expert_a, buttons = self.expert.get_action()
        self.left1, self.left2, self.right1, self.right2 = tuple(buttons)


        if self.gripper_enabled:
            if self.left1:  # close gripper
                left_gripper_action = np.random.uniform(-1, -0.9, size=(1,))
                intervened = True
            elif self.left2:  # open gripper
                left_gripper_action = np.random.uniform(0.9, 1, size=(1,))
                intervened = True
            else:
                left_gripper_action = np.zeros((1,))

            if self.right1:  # close gripper
                right_gripper_action = np.random.uniform(-1, -0.9, size=(1,))
                intervened = True
            elif self.right2:  # open gripper
                right_gripper_action = np.random.uniform(0.9, 1, size=(1,))
                intervened = True
            else:
                right_gripper_action = np.zeros((1,))
            expert_a = np.concatenate(
                (expert_a[:6], left_gripper_action, expert_a[6:], right_gripper_action),
                axis=0,
            )

        if self.action_indices is not None:
            filtered_expert_a = np.zeros_like(expert_a)
            filtered_expert_a[self.action_indices] = expert_a[self.action_indices]
            expert_a = filtered_expert_a

        if np.linalg.norm(expert_a) > 0.001:
            intervened = True

        if intervened:
            return expert_a, True
        return action, False

    def step(self, action):

        new_action, replaced = self.action(action)

        obs, rew, done, truncated, info = self.env.step(new_action)
        if replaced:
            info["intervene_action"] = new_action
        info["left1"] = self.left1
        info["left2"] = self.left2
        info["right1"] = self.right1
        info["right2"] = self.right2
        return obs, rew, done, truncated, info
    
    def reset(self, **kwargs):
        return self.env.reset(**kwargs)


class GripperPenaltyWrapper(gym.RewardWrapper):
    def __init__(self, env, penalty=0.1):
        super().__init__(env)
        assert env.action_space.shape == (7,)
        self.penalty = penalty
        self.last_gripper_pos = None

    def reset(self, **kwargs):
        obs, info = self.env.reset(**kwargs)
        self.last_gripper_pos = obs["state"][0, 0]
        return obs, info

    def reward(self, reward: float, action) -> float:
        if (action[6] < -0.5 and self.last_gripper_pos > 0.95) or (
            action[6] > 0.5 and self.last_gripper_pos < 0.95
        ):
            return reward - self.penalty
        else:
            return reward

    def step(self, action):
        """Modifies the :attr:`env` :meth:`step` reward using :meth:`self.reward`."""
        observation, reward, terminated, truncated, info = self.env.step(action)
        if "intervene_action" in info:
            action = info["intervene_action"]
        reward = self.reward(reward, action)
        self.last_gripper_pos = observation["state"][0, 0]
        return observation, reward, terminated, truncated, info

class DualGripperPenaltyWrapper(gym.RewardWrapper):
    def __init__(self, env, penalty=0.1):
        super().__init__(env)
        assert env.action_space.shape == (14,)
        self.penalty = penalty
        self.last_gripper_pos_left = 0 
        self.last_gripper_pos_right = 0 
    
    def reward(self, reward: float, action) -> float:
        if (action[6] < -0.5 and self.last_gripper_pos_left==0):
            reward -= self.penalty
            self.last_gripper_pos_left = 1
        elif (action[6] > 0.5 and self.last_gripper_pos_left==1):
            reward -= self.penalty
            self.last_gripper_pos_left = 0
        if (action[13] < -0.5 and self.last_gripper_pos_right==0):
            reward -= self.penalty
            self.last_gripper_pos_right = 1
        elif (action[13] > 0.5 and self.last_gripper_pos_right==1):
            reward -= self.penalty
            self.last_gripper_pos_right = 0
        return reward
    
    def step(self, action):
        """Modifies the :attr:`env` :meth:`step` reward using :meth:`self.reward`."""
        observation, reward, terminated, truncated, info = self.env.step(action)
        if "intervene_action" in info:
            action = info["intervene_action"]
        reward = self.reward(reward, action)
        return observation, reward, terminated, truncated, info

