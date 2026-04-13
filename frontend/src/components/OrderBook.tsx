import { useMarketStore } from '../store/marketStore'
import type { PriceLevel } from '../lib/types'

const MAX_LEVELS = 15

export function OrderBook() {
  const snapshot = useMarketStore((s) => s.snapshot)

  if (!snapshot) {
    return <Panel><Empty>Waiting for data…</Empty></Panel>
  }

  const bids = snapshot.bids.slice(0, MAX_LEVELS)
  const asks = snapshot.asks.slice(0, MAX_LEVELS)

  const maxBidQty = Math.max(...bids.map((l) => l.total_quantity), 1)
  const maxAskQty = Math.max(...asks.map((l) => l.total_quantity), 1)

  return (
    <Panel>
      <h2 style={titleStyle}>Order Book</h2>
      <table style={tableStyle}>
        <thead>
          <tr>
            <Th align="right">Qty</Th>
            <Th align="right" color="#22c55e">Bid</Th>
            <Th align="left" color="#ef4444">Ask</Th>
            <Th align="left">Qty</Th>
          </tr>
        </thead>
        <tbody>
          {Array.from({ length: Math.max(bids.length, asks.length) }).map((_, i) => {
            const bid = bids[i] ?? null
            const ask = asks[i] ?? null
            return (
              <tr key={i}>
                <BidCell level={bid} maxQty={maxBidQty} />
                <PriceCell price={bid?.price ?? null} side="bid" />
                <PriceCell price={ask?.price ?? null} side="ask" />
                <AskCell level={ask} maxQty={maxAskQty} />
              </tr>
            )
          })}
        </tbody>
      </table>

      {snapshot.spread !== null && (
        <div style={{ textAlign: 'center', padding: '0.4rem', color: '#64748b', fontSize: '0.75rem' }}>
          Spread: ${snapshot.spread.toFixed(2)}
          {' '}({snapshot.bid_count}B / {snapshot.ask_count}A orders)
        </div>
      )}
    </Panel>
  )
}

function BidCell({ level, maxQty }: { level: PriceLevel | null; maxQty: number }) {
  if (!level) return <td style={cellStyle} />
  const pct = (level.total_quantity / maxQty) * 100
  return (
    <td style={{ ...cellStyle, textAlign: 'right', position: 'relative' }}>
      <div style={{
        position: 'absolute', right: 0, top: 0, bottom: 0,
        width: `${pct}%`, background: 'rgba(34,197,94,0.12)',
      }} />
      <span style={{ position: 'relative', color: '#94a3b8' }}>
        {level.total_quantity.toFixed(2)}
      </span>
    </td>
  )
}

function AskCell({ level, maxQty }: { level: PriceLevel | null; maxQty: number }) {
  if (!level) return <td style={cellStyle} />
  const pct = (level.total_quantity / maxQty) * 100
  return (
    <td style={{ ...cellStyle, position: 'relative' }}>
      <div style={{
        position: 'absolute', left: 0, top: 0, bottom: 0,
        width: `${pct}%`, background: 'rgba(239,68,68,0.12)',
      }} />
      <span style={{ position: 'relative', color: '#94a3b8' }}>
        {level.total_quantity.toFixed(2)}
      </span>
    </td>
  )
}

function PriceCell({ price, side }: { price: number | null; side: 'bid' | 'ask' }) {
  const color = side === 'bid' ? '#22c55e' : '#ef4444'
  return (
    <td style={{ ...cellStyle, textAlign: side === 'bid' ? 'right' : 'left', color, fontWeight: 600 }}>
      {price !== null ? price.toFixed(2) : '—'}
    </td>
  )
}

function Th({ children, align, color }: { children: React.ReactNode; align: 'left' | 'right'; color?: string }) {
  return (
    <th style={{ textAlign: align, padding: '0.25rem 0.5rem', color: color ?? '#475569', fontSize: '0.7rem', fontWeight: 500 }}>
      {children}
    </th>
  )
}

function Panel({ children }: { children: React.ReactNode }) {
  return <div style={{ background: '#0f172a', border: '1px solid #1e293b', borderRadius: 8, overflow: 'hidden' }}>{children}</div>
}

function Empty({ children }: { children: React.ReactNode }) {
  return <div style={{ padding: '2rem', textAlign: 'center', color: '#475569', fontFamily: 'monospace' }}>{children}</div>
}

const titleStyle: React.CSSProperties = {
  margin: 0, padding: '0.75rem 1rem 0.25rem',
  fontSize: '0.8rem', fontWeight: 600, color: '#64748b',
  fontFamily: 'monospace', letterSpacing: '0.05em', textTransform: 'uppercase',
}

const tableStyle: React.CSSProperties = {
  width: '100%', borderCollapse: 'collapse', fontFamily: 'monospace', fontSize: '0.82rem',
}

const cellStyle: React.CSSProperties = {
  padding: '0.18rem 0.5rem', overflow: 'hidden',
}
