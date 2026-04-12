"""
market_agents.py — Synthetic market participants for simulation mode.

Implements three agent types that generate realistic order flow:
- MarketMaker:     Posts two-sided quotes, provides liquidity
- MomentumTrader:  Follows recent price direction
- NoiseTrader:     Random orders for volume and realism

Built in Phase 6.
"""
