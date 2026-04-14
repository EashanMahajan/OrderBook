"""
DQN agent: Q-network + target network + experience replay.

Architecture  : MLP  state_dim → 64 → 64 → n_actions
Optimizer     : Adam with gradient clipping (max_norm=10)
Loss          : Huber (smooth L1) — robust to outlier rewards
Exploration   : ε-greedy, multiplicative decay each gradient step
Target update : hard copy every `update_target` gradient steps
"""

from __future__ import annotations

import random
from collections import deque
from typing import Optional

import numpy as np
import torch
import torch.nn as nn
import torch.optim as optim

from rl.env import N_ACTIONS, STATE_DIM


# ---------------------------------------------------------------------------
# Neural network
# ---------------------------------------------------------------------------

class QNetwork(nn.Module):
    """Two-hidden-layer MLP: state → Q-values for each action."""

    def __init__(
        self,
        state_dim: int = STATE_DIM,
        n_actions: int = N_ACTIONS,
        hidden: int = 64,
    ) -> None:
        super().__init__()
        self.net = nn.Sequential(
            nn.Linear(state_dim, hidden),
            nn.ReLU(),
            nn.Linear(hidden, hidden),
            nn.ReLU(),
            nn.Linear(hidden, n_actions),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.net(x)


# ---------------------------------------------------------------------------
# Replay buffer
# ---------------------------------------------------------------------------

class ReplayBuffer:
    """Fixed-capacity circular buffer of (s, a, r, s', done) transitions."""

    def __init__(self, capacity: int = 10_000) -> None:
        self._buf: deque = deque(maxlen=capacity)

    def push(
        self,
        state: np.ndarray,
        action: int,
        reward: float,
        next_state: np.ndarray,
        done: bool,
    ) -> None:
        self._buf.append((
            np.array(state, dtype=np.float32),
            int(action),
            float(reward),
            np.array(next_state, dtype=np.float32),
            bool(done),
        ))

    def sample(self, batch_size: int):
        batch = random.sample(self._buf, batch_size)
        s, a, r, s_, d = zip(*batch)
        return (
            np.array(s,  dtype=np.float32),
            np.array(a,  dtype=np.int64),
            np.array(r,  dtype=np.float32),
            np.array(s_, dtype=np.float32),
            np.array(d,  dtype=np.float32),
        )

    def __len__(self) -> int:
        return len(self._buf)


# ---------------------------------------------------------------------------
# DQN agent
# ---------------------------------------------------------------------------

class DQNAgent:
    """
    Standard DQN with replay buffer and periodic target-network updates.

    Parameters
    ----------
    gamma           Bellman discount factor.
    lr              Adam learning rate.
    batch_size      Mini-batch size for each gradient step.
    buffer_capacity Max transitions stored in replay buffer.
    min_buffer      Minimum buffer fill before training starts.
    update_target   Copy online → target network every N gradient steps.
    eps_start       Initial ε for ε-greedy exploration.
    eps_end         Minimum ε (never fully deterministic during training).
    eps_decay       Multiplicative decay applied after each gradient step.
    """

    def __init__(
        self,
        state_dim: int = STATE_DIM,
        n_actions: int = N_ACTIONS,
        gamma: float = 0.99,
        lr: float = 1e-3,
        batch_size: int = 64,
        buffer_capacity: int = 10_000,
        min_buffer: int = 256,
        update_target: int = 200,
        eps_start: float = 1.0,
        eps_end: float = 0.05,
        eps_decay: float = 0.995,
    ) -> None:
        self.n_actions = n_actions
        self.gamma = gamma
        self.batch_size = batch_size
        self.min_buffer = min_buffer
        self.update_target = update_target
        self.eps = eps_start
        self.eps_end = eps_end
        self.eps_decay = eps_decay

        self.device = torch.device("cpu")

        self.online = QNetwork(state_dim, n_actions).to(self.device)
        self.target = QNetwork(state_dim, n_actions).to(self.device)
        self.target.load_state_dict(self.online.state_dict())
        self.target.eval()

        self.optimizer = optim.Adam(self.online.parameters(), lr=lr)
        self.loss_fn = nn.HuberLoss()
        self.buffer = ReplayBuffer(buffer_capacity)

        self._grad_steps: int = 0

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def select_action(self, state: np.ndarray, exploit: bool = False) -> int:
        """
        ε-greedy action selection.

        exploit=True forces greedy (used during live inference, not training).
        """
        if not exploit and random.random() < self.eps:
            return random.randrange(self.n_actions)

        with torch.no_grad():
            s = torch.tensor(state, dtype=torch.float32, device=self.device).unsqueeze(0)
            return int(self.online(s).argmax(dim=1).item())

    def store(
        self,
        state: np.ndarray,
        action: int,
        reward: float,
        next_state: np.ndarray,
        done: bool,
    ) -> None:
        self.buffer.push(state, action, reward, next_state, done)

    def train_step(self) -> Optional[float]:
        """
        One gradient update using a random mini-batch.

        Returns the loss value, or None if the buffer is not yet large
        enough to sample from.
        """
        if len(self.buffer) < self.min_buffer:
            return None

        states, actions, rewards, next_states, dones = self.buffer.sample(self.batch_size)

        s  = torch.tensor(states,     device=self.device)
        a  = torch.tensor(actions,    device=self.device)
        r  = torch.tensor(rewards,    device=self.device)
        s_ = torch.tensor(next_states, device=self.device)
        d  = torch.tensor(dones,      device=self.device)

        # Q(s, a) from online network
        q_vals = self.online(s).gather(1, a.unsqueeze(1)).squeeze(1)

        # Bellman target using target network
        with torch.no_grad():
            q_next = self.target(s_).max(dim=1).values
            q_target = r + self.gamma * q_next * (1.0 - d)

        loss = self.loss_fn(q_vals, q_target)
        self.optimizer.zero_grad()
        loss.backward()
        nn.utils.clip_grad_norm_(self.online.parameters(), max_norm=10.0)
        self.optimizer.step()

        self._grad_steps += 1
        self.eps = max(self.eps_end, self.eps * self.eps_decay)

        if self._grad_steps % self.update_target == 0:
            self.target.load_state_dict(self.online.state_dict())

        return float(loss.item())

    # ------------------------------------------------------------------
    # Checkpoint I/O
    # ------------------------------------------------------------------

    def save(self, path: str) -> None:
        torch.save(
            {
                "online": self.online.state_dict(),
                "target": self.target.state_dict(),
                "optimizer": self.optimizer.state_dict(),
                "eps": self.eps,
                "grad_steps": self._grad_steps,
            },
            path,
        )

    def load(self, path: str) -> None:
        ckpt = torch.load(path, map_location=self.device, weights_only=True)
        self.online.load_state_dict(ckpt["online"])
        self.target.load_state_dict(ckpt["target"])
        self.optimizer.load_state_dict(ckpt["optimizer"])
        self.eps = ckpt["eps"]
        self._grad_steps = ckpt["grad_steps"]
