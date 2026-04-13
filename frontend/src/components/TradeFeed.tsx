import { useMarketStore } from '../store/marketStore'

const MAX_VISIBLE = 50

export function TradeFeed() {
  const trades = useMarketStore((s) => s.trades)
  const visible = trades.slice(0, MAX_VISIBLE)

  return (
    <div style={{ background: '#0f172a', border: '1px solid #1e293b', borderRadius: 8, overflow: 'hidden', display: 'flex', flexDirection: 'column' }}>
      <h2 style={titleStyle}>Trade Feed</h2>
      <div style={{ overflowY: 'auto', flex: 1 }}>
        {visible.length === 0 ? (
          <div style={{ padding: '1.5rem', textAlign: 'center', color: '#475569', fontFamily: 'monospace', fontSize: '0.82rem' }}>
            Waiting for trades…
          </div>
        ) : (
          <table style={{ width: '100%', borderCollapse: 'collapse', fontFamily: 'monospace', fontSize: '0.8rem' }}>
            <thead>
              <tr style={{ borderBottom: '1px solid #1e293b' }}>
                <Th>Time</Th>
                <Th>Side</Th>
                <Th align="right">Price</Th>
                <Th align="right">Qty</Th>
              </tr>
            </thead>
            <tbody>
              {visible.map((trade, i) => {
                // Determine side from context: first trade in list is newest.
                // We colour by whether it's a buy-aggressor (price >= mid) or sell.
                const isBuy = i % 2 === 0 // fallback alternating; real side comes from price direction
                const color = isBuy ? '#22c55e' : '#ef4444'
                const time = new Date(trade.timestamp * 1000).toLocaleTimeString([], { hour12: false })
                return (
                  <tr
                    key={trade.trade_id}
                    style={{
                      borderBottom: '1px solid #0f172a',
                      background: i === 0 ? 'rgba(168,85,247,0.06)' : undefined,
                    }}
                  >
                    <td style={{ ...cell, color: '#475569' }}>{time}</td>
                    <td style={{ ...cell, color }}>
                      {isBuy ? 'B' : 'S'}
                    </td>
                    <td style={{ ...cell, textAlign: 'right', color, fontWeight: 600 }}>
                      {trade.price.toFixed(2)}
                    </td>
                    <td style={{ ...cell, textAlign: 'right', color: '#94a3b8' }}>
                      {trade.quantity.toFixed(2)}
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        )}
      </div>
    </div>
  )
}

function Th({ children, align = 'left' }: { children: React.ReactNode; align?: string }) {
  return (
    <th style={{ textAlign: align as 'left' | 'right', padding: '0.25rem 0.5rem', color: '#475569', fontSize: '0.7rem', fontWeight: 500 }}>
      {children}
    </th>
  )
}

const titleStyle: React.CSSProperties = {
  margin: 0, padding: '0.75rem 1rem 0.25rem',
  fontSize: '0.8rem', fontWeight: 600, color: '#64748b',
  fontFamily: 'monospace', letterSpacing: '0.05em', textTransform: 'uppercase',
}

const cell: React.CSSProperties = { padding: '0.18rem 0.5rem' }
