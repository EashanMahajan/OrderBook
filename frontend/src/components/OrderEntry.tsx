import { useState } from 'react'

interface OrderResult {
  order: {
    order_id: string
    status: string
    side: string
    price: number | null
    quantity: number
    remaining: number
  }
  trades: { price: number; quantity: number }[]
}

export function OrderEntry() {
  const [side, setSide] = useState<'buy' | 'sell'>('buy')
  const [orderType, setOrderType] = useState<'limit' | 'market'>('limit')
  const [price, setPrice] = useState('')
  const [qty, setQty] = useState('')
  const [result, setResult] = useState<OrderResult | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)

  const [cancelId, setCancelId] = useState('')
  const [cancelMsg, setCancelMsg] = useState<string | null>(null)
  const [cancelErr, setCancelErr] = useState<string | null>(null)

  async function submit(e: React.FormEvent) {
    e.preventDefault()
    setResult(null)
    setError(null)
    setLoading(true)
    try {
      const body: Record<string, unknown> = {
        side,
        order_type: orderType,
        quantity: parseFloat(qty),
      }
      if (orderType === 'limit') body.price = parseFloat(price)

      const res = await fetch('/orders', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      })
      const data = await res.json()
      if (!res.ok) throw new Error(data.detail ?? 'Unknown error')
      setResult(data)
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Request failed')
    } finally {
      setLoading(false)
    }
  }

  async function cancelOrder(e: React.FormEvent) {
    e.preventDefault()
    setCancelMsg(null)
    setCancelErr(null)
    try {
      const res = await fetch(`/orders/${encodeURIComponent(cancelId)}`, { method: 'DELETE' })
      const data = await res.json()
      if (!res.ok) throw new Error(data.detail ?? 'Unknown error')
      setCancelMsg(`Cancelled order ${cancelId.slice(-8)}… (status: ${data.order.status})`)
      setCancelId('')
    } catch (err: unknown) {
      setCancelErr(err instanceof Error ? err.message : 'Request failed')
    }
  }

  const accentColor = side === 'buy' ? '#22c55e' : '#ef4444'

  return (
    <div style={{ background: '#0f172a', border: '1px solid #1e293b', borderRadius: 8, padding: '1rem', fontFamily: 'monospace' }}>
      <h2 style={titleStyle}>Order Entry</h2>

      <form onSubmit={submit} style={{ display: 'flex', flexDirection: 'column', gap: '0.6rem' }}>
        {/* Side */}
        <div style={{ display: 'flex', gap: '0.5rem' }}>
          {(['buy', 'sell'] as const).map((s) => (
            <button
              key={s}
              type="button"
              onClick={() => setSide(s)}
              style={{
                flex: 1, padding: '0.4rem', border: 'none', borderRadius: 4, cursor: 'pointer',
                fontFamily: 'monospace', fontWeight: 600, fontSize: '0.85rem',
                background: side === s ? (s === 'buy' ? '#15803d' : '#b91c1c') : '#1e293b',
                color: side === s ? '#fff' : '#475569',
              }}
            >{s.toUpperCase()}</button>
          ))}
        </div>

        {/* Type */}
        <div style={{ display: 'flex', gap: '0.5rem' }}>
          {(['limit', 'market'] as const).map((t) => (
            <button
              key={t}
              type="button"
              onClick={() => setOrderType(t)}
              style={{
                flex: 1, padding: '0.3rem', border: `1px solid ${orderType === t ? accentColor : '#1e293b'}`,
                borderRadius: 4, cursor: 'pointer', fontFamily: 'monospace', fontSize: '0.78rem',
                background: orderType === t ? 'rgba(255,255,255,0.04)' : 'transparent',
                color: orderType === t ? accentColor : '#475569',
              }}
            >{t}</button>
          ))}
        </div>

        {/* Price (limit only) */}
        {orderType === 'limit' && (
          <input
            type="number" step="0.01" min="0.01" placeholder="Price"
            value={price} onChange={(e) => setPrice(e.target.value)}
            required
            style={inputStyle}
          />
        )}

        {/* Quantity */}
        <input
          type="number" step="0.01" min="0.01" placeholder="Quantity"
          value={qty} onChange={(e) => setQty(e.target.value)}
          required
          style={inputStyle}
        />

        <button
          type="submit" disabled={loading}
          style={{
            padding: '0.5rem', border: 'none', borderRadius: 4, cursor: loading ? 'not-allowed' : 'pointer',
            background: accentColor, color: '#fff', fontWeight: 700, fontFamily: 'monospace', fontSize: '0.85rem',
            opacity: loading ? 0.6 : 1,
          }}
        >
          {loading ? 'Submitting…' : `Submit ${side.toUpperCase()}`}
        </button>
      </form>

      {/* Result */}
      {result && (
        <div style={{ marginTop: '0.6rem', padding: '0.5rem', background: '#0a1628', borderRadius: 4, fontSize: '0.75rem' }}>
          <div style={{ color: '#22c55e', marginBottom: '0.25rem' }}>
            Order {result.order.order_id.slice(-8)}… — {result.order.status}
          </div>
          {result.trades.length > 0 && (
            <div style={{ color: '#94a3b8' }}>
              {result.trades.length} fill(s): avg ${
                (result.trades.reduce((s, t) => s + t.price * t.quantity, 0) /
                 result.trades.reduce((s, t) => s + t.quantity, 0)).toFixed(2)
              }
            </div>
          )}
        </div>
      )}
      {error && (
        <div style={{ marginTop: '0.6rem', padding: '0.5rem', background: '#1a0a0a', borderRadius: 4, color: '#ef4444', fontSize: '0.75rem' }}>
          {error}
        </div>
      )}

      {/* Cancel */}
      <div style={{ marginTop: '1rem', borderTop: '1px solid #1e293b', paddingTop: '0.75rem' }}>
        <form onSubmit={cancelOrder} style={{ display: 'flex', gap: '0.4rem' }}>
          <input
            placeholder="Order ID to cancel"
            value={cancelId} onChange={(e) => setCancelId(e.target.value)}
            required
            style={{ ...inputStyle, flex: 1 }}
          />
          <button
            type="submit"
            style={{ padding: '0.4rem 0.75rem', border: '1px solid #ef4444', borderRadius: 4, background: 'transparent', color: '#ef4444', cursor: 'pointer', fontFamily: 'monospace', fontSize: '0.78rem' }}
          >Cancel</button>
        </form>
        {cancelMsg && <div style={{ marginTop: '0.4rem', color: '#22c55e', fontSize: '0.75rem' }}>{cancelMsg}</div>}
        {cancelErr && <div style={{ marginTop: '0.4rem', color: '#ef4444', fontSize: '0.75rem' }}>{cancelErr}</div>}
      </div>
    </div>
  )
}

const titleStyle: React.CSSProperties = {
  margin: '0 0 0.75rem', fontSize: '0.8rem', fontWeight: 600, color: '#64748b',
  letterSpacing: '0.05em', textTransform: 'uppercase',
}

const inputStyle: React.CSSProperties = {
  width: '100%', padding: '0.4rem 0.5rem', boxSizing: 'border-box',
  background: '#1e293b', border: '1px solid #334155', borderRadius: 4,
  color: '#e2e8f0', fontFamily: 'monospace', fontSize: '0.82rem', outline: 'none',
}
