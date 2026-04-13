import { useState, useRef, KeyboardEvent } from 'react'
import type { NLOrderResult } from '../lib/types'

const CARD: React.CSSProperties = {
  background: '#0d1424',
  border: '1px solid #1e2d45',
  borderRadius: '0.5rem',
  padding: '0.75rem',
  display: 'flex',
  flexDirection: 'column',
  gap: '0.6rem',
}

const LABEL: React.CSSProperties = {
  fontSize: '0.6rem',
  fontWeight: 700,
  letterSpacing: '0.08em',
  color: '#64748b',
  textTransform: 'uppercase',
}

const TEXTAREA: React.CSSProperties = {
  background: '#020917',
  border: '1px solid #1e2d45',
  borderRadius: '0.375rem',
  color: '#e2e8f0',
  fontSize: '0.78rem',
  padding: '0.5rem 0.6rem',
  resize: 'none',
  outline: 'none',
  fontFamily: 'inherit',
  lineHeight: 1.5,
}

const BTN: React.CSSProperties = {
  background: '#7c3aed',
  border: 'none',
  borderRadius: '0.375rem',
  color: '#fff',
  cursor: 'pointer',
  fontSize: '0.75rem',
  fontWeight: 600,
  padding: '0.45rem 0.75rem',
  width: '100%',
}

const BTN_DISABLED: React.CSSProperties = {
  ...BTN,
  opacity: 0.5,
  cursor: 'not-allowed',
}

const RESULT_ROW: React.CSSProperties = {
  background: '#0a1628',
  border: '1px solid #1e2d45',
  borderRadius: '0.375rem',
  fontSize: '0.72rem',
  padding: '0.45rem 0.6rem',
  display: 'flex',
  flexDirection: 'column',
  gap: '0.25rem',
}

const EXAMPLES = [
  'Buy 5 at market',
  'Sell 10 limit at 102.50',
  'Buy 3 at 1% below mid',
  'Sell 7 at best ask + 0.5',
]

export function NLOrderEntry() {
  const [instruction, setInstruction] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [results, setResults] = useState<NLOrderResult[]>([])
  const textareaRef = useRef<HTMLTextAreaElement>(null)

  async function submit() {
    const text = instruction.trim()
    if (!text || loading) return

    setLoading(true)
    setError(null)
    setResults([])

    try {
      const res = await fetch('/ai/order', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ instruction: text }),
      })

      if (!res.ok) {
        const body = await res.json().catch(() => ({}))
        throw new Error(body.detail ?? `HTTP ${res.status}`)
      }

      const data = await res.json()
      setResults(data.results ?? [])
      setInstruction('')
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : String(err))
    } finally {
      setLoading(false)
      textareaRef.current?.focus()
    }
  }

  function onKeyDown(e: KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      submit()
    }
  }

  return (
    <div style={CARD}>
      <div style={LABEL}>Tasks for AI</div>

      {/* Example pills */}
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.3rem' }}>
        {EXAMPLES.map((ex) => (
          <button
            key={ex}
            onClick={() => setInstruction(ex)}
            style={{
              background: 'transparent',
              border: '1px solid #2d3f5a',
              borderRadius: '999px',
              color: '#94a3b8',
              cursor: 'pointer',
              fontSize: '0.65rem',
              padding: '0.15rem 0.5rem',
            }}
          >
            {ex}
          </button>
        ))}
      </div>

      <textarea
        ref={textareaRef}
        rows={3}
        placeholder={'Describe your trade in plain English…\n(Enter to submit, Shift+Enter for newline)'}
        value={instruction}
        onChange={(e) => setInstruction(e.target.value)}
        onKeyDown={onKeyDown}
        style={TEXTAREA}
        disabled={loading}
      />

      <button
        onClick={submit}
        disabled={loading || !instruction.trim()}
        style={loading || !instruction.trim() ? BTN_DISABLED : BTN}
      >
        {loading ? 'Interpreting…' : 'Submit'}
      </button>

      {/* Error */}
      {error && (
        <div style={{ color: '#f87171', fontSize: '0.72rem', wordBreak: 'break-word' }}>
          {error}
        </div>
      )}

      {/* Results */}
      {results.map((r, i) => (
        <div key={i} style={RESULT_ROW}>
          <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'center' }}>
            <span
              style={{
                color: r.order.side === 'buy' ? '#4ade80' : '#f87171',
                fontWeight: 700,
                textTransform: 'uppercase',
                fontSize: '0.7rem',
              }}
            >
              {r.order.side}
            </span>
            <span style={{ color: '#e2e8f0' }}>
              {r.order.quantity} × {r.order.order_type}
              {r.order.price != null ? ` @ ${r.order.price}` : ''}
            </span>
            <span
              style={{
                marginLeft: 'auto',
                color: '#64748b',
                fontSize: '0.65rem',
              }}
            >
              {r.order.status}
            </span>
          </div>
          {r.trades.length > 0 && (
            <div style={{ color: '#a78bfa', fontSize: '0.68rem' }}>
              Filled {r.trades.reduce((s, t) => s + t.quantity, 0)} in {r.trades.length} trade
              {r.trades.length !== 1 ? 's' : ''}
            </div>
          )}
          {r.reasoning && (
            <div style={{ color: '#475569', fontSize: '0.67rem', fontStyle: 'italic' }}>
              {r.reasoning}
            </div>
          )}
        </div>
      ))}
    </div>
  )
}
