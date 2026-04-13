import { useMarketStore } from '../store/marketStore'
import type { ConnectionStatus } from '../lib/types'

const statusLabel: Record<ConnectionStatus, string> = {
  connecting: 'Connecting…',
  live: 'Live',
  reconnecting: 'Reconnecting…',
  disconnected: 'Disconnected',
}

const statusColor: Record<ConnectionStatus, string> = {
  connecting: '#f59e0b',
  live: '#22c55e',
  reconnecting: '#f59e0b',
  disconnected: '#ef4444',
}

export function StatusBar() {
  const connectionStatus = useMarketStore((s) => s.connectionStatus)
  const snapshot = useMarketStore((s) => s.snapshot)
  const trades = useMarketStore((s) => s.trades)
  const simStatus = useMarketStore((s) => s.simStatus)

  const lastPrice = trades.length > 0 ? trades[0].price : null
  const bestBid = snapshot?.bids[0]?.price ?? null
  const bestAsk = snapshot?.asks[0]?.price ?? null
  const spread = snapshot?.spread ?? null

  return (
    <div style={{
      display: 'flex',
      alignItems: 'center',
      gap: '2rem',
      padding: '0.5rem 1.5rem',
      background: '#0f172a',
      borderBottom: '1px solid #1e293b',
      fontFamily: 'monospace',
      fontSize: '0.8rem',
      color: '#94a3b8',
      flexWrap: 'wrap',
    }}>
      {/* Connection indicator */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
        <span style={{
          width: 8, height: 8, borderRadius: '50%',
          background: statusColor[connectionStatus],
          display: 'inline-block',
          boxShadow: connectionStatus === 'live' ? `0 0 6px ${statusColor['live']}` : undefined,
        }} />
        <span style={{ color: statusColor[connectionStatus] }}>
          {statusLabel[connectionStatus]}
        </span>
      </div>

      {lastPrice !== null && (
        <Stat label="Last" value={`$${lastPrice.toFixed(2)}`} highlight />
      )}
      {bestBid !== null && (
        <Stat label="Bid" value={`$${bestBid.toFixed(2)}`} color="#22c55e" />
      )}
      {bestAsk !== null && (
        <Stat label="Ask" value={`$${bestAsk.toFixed(2)}`} color="#ef4444" />
      )}
      {spread !== null && (
        <Stat label="Spread" value={`$${spread.toFixed(2)}`} />
      )}
      {snapshot && (
        <Stat label="Trades" value={snapshot.total_trades.toLocaleString()} />
      )}

      <div style={{ marginLeft: 'auto', display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
        <span style={{
          width: 8, height: 8, borderRadius: '50%',
          background: simStatus?.running ? '#a855f7' : '#334155',
          display: 'inline-block',
        }} />
        <span style={{ color: simStatus?.running ? '#a855f7' : '#475569' }}>
          {simStatus?.running ? `Sim running (${simStatus.agent_count} agents)` : 'Sim off'}
        </span>
      </div>
    </div>
  )
}

function Stat({ label, value, color, highlight }: {
  label: string
  value: string
  color?: string
  highlight?: boolean
}) {
  return (
    <div>
      <span style={{ color: '#475569', marginRight: '0.3rem' }}>{label}</span>
      <span style={{ color: highlight ? '#f8fafc' : (color ?? '#94a3b8'), fontWeight: highlight ? 600 : 400 }}>
        {value}
      </span>
    </div>
  )
}
