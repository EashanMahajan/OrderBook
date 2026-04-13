import { create } from 'zustand'
import type { BookSnapshot, ConnectionStatus, SimStatus, Trade } from '../lib/types'

const TRADE_BUFFER = 200

interface MarketState {
  // Book
  snapshot: BookSnapshot | null
  // Rolling trade ring-buffer (newest first)
  trades: Trade[]
  // WS health
  connectionStatus: ConnectionStatus
  // Simulation
  simStatus: SimStatus | null

  // Actions
  applySnapshot: (snap: BookSnapshot) => void
  appendTrade: (trade: Trade) => void
  setConnectionStatus: (s: ConnectionStatus) => void
  setSimStatus: (s: SimStatus | null) => void
}

export const useMarketStore = create<MarketState>((set) => ({
  snapshot: null,
  trades: [],
  connectionStatus: 'connecting',
  simStatus: null,

  applySnapshot: (snap) =>
    set({ snapshot: snap }),

  appendTrade: (trade) =>
    set((state) => ({
      trades: [trade, ...state.trades].slice(0, TRADE_BUFFER),
    })),

  setConnectionStatus: (connectionStatus) => set({ connectionStatus }),

  setSimStatus: (simStatus) => set({ simStatus }),
}))
