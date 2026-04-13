export interface PriceLevel {
  price: number
  total_quantity: number
  order_count: number
}

export interface Trade {
  trade_id: string
  buy_order_id: string
  sell_order_id: string
  price: number
  quantity: number
  timestamp: number
}

export interface BookSnapshot {
  bids: PriceLevel[]
  asks: PriceLevel[]
  spread: number | null
  bid_count: number
  ask_count: number
  total_trades: number
  recent_trades: Trade[]
}

export interface AgentStatus {
  name: string
  type: string
  tick_count: number
  target_price: number
  tick_interval_ms: number
  // MarketMaker extras
  bid_id?: string | null
  ask_id?: string | null
  half_spread_pct?: number
  quote_qty?: number
  // MomentumTrader extras
  cooldown_remaining_s?: number
  drift_tolerance_pct?: number
}

export interface SimStatus {
  running: boolean
  agent_count: number
  agents: AgentStatus[]
}

export type ConnectionStatus = 'connecting' | 'live' | 'reconnecting' | 'disconnected'
