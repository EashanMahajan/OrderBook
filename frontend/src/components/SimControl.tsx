import { useEffect, useState } from 'react'
import { useMarketStore } from '../store/marketStore'
import type { SimStatus } from '../lib/types'

const POLL_INTERVAL = 2000

const defaultConfig = {
  target_price: 100,
  market_makers: 1,
  noise_traders: 2,
  momentum_traders: 1,
  rl_agents: 0,
  mm_spread: 0.004,
  mm_quote_qty: 10,
  noise_qty_max: 15,
  momentum_cooldown: 3,
  momentum_drift_tolerance: 0.03,
}

export function SimControl() {
  const { simStatus, setSimStatus } = useMarketStore()
  const [config, setConfig] = useState(defaultConfig)
  const [showAdvanced, setShowAdvanced] = useState(false)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  // Poll simulation status every 2 seconds
  useEffect(() => {
    async function poll() {
      try {
        const res = await fetch('/simulation/status')
        const data: SimStatus = await res.json()
        setSimStatus(data)
      } catch {
        // server unreachable — leave status unchanged
      }
    }
    poll()
    const id = setInterval(poll, POLL_INTERVAL)
    return () => clearInterval(id)
  }, [setSimStatus])

  async function startSim() {
    setLoading(true)
    setError(null)
    try {
      const res = await fetch('/simulation/start', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(config),
      })
      const data = await res.json()
      if (!res.ok) throw new Error(data.detail ?? 'Start failed')
      setSimStatus(data)
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Request failed')
    } finally {
      setLoading(false)
    }
  }

  async function stopSim() {
    setLoading(true)
    setError(null)
    try {
      const res = await fetch('/simulation/stop', { method: 'POST' })
      const data = await res.json()
      if (!res.ok) throw new Error(data.detail ?? 'Stop failed')
      setSimStatus({ running: false, agent_count: 0, agents: [] })
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Request failed')
    } finally {
      setLoading(false)
    }
  }

  const isRunning = simStatus?.running ?? false

  return (
    <div style={{ background: '#0f172a', border: '1px solid #1e293b', borderRadius: 8, padding: '1rem', fontFamily: 'monospace' }}>
      <h2 style={titleStyle}>Simulation</h2>

      {!isRunning ? (
        <>
          {/* Config form */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
            <Field label="Target Price $">
              <input
                type="number" step="0.01" min="0.01"
                value={config.target_price}
                onChange={(e) => setConfig((c) => ({ ...c, target_price: parseFloat(e.target.value) }))}
                style={inputStyle}
              />
            </Field>

            <div style={{ display: 'flex', gap: '0.5rem' }}>
              <Field label="Market Makers">
                <input type="number" min="0" max="5" value={config.market_makers}
                  onChange={(e) => setConfig((c) => ({ ...c, market_makers: parseInt(e.target.value) }))}
                  style={{ ...inputStyle, width: 60 }} />
              </Field>
              <Field label="Noise Traders">
                <input type="number" min="0" max="10" value={config.noise_traders}
                  onChange={(e) => setConfig((c) => ({ ...c, noise_traders: parseInt(e.target.value) }))}
                  style={{ ...inputStyle, width: 60 }} />
              </Field>
              <Field label="Momentum">
                <input type="number" min="0" max="5" value={config.momentum_traders}
                  onChange={(e) => setConfig((c) => ({ ...c, momentum_traders: parseInt(e.target.value) }))}
                  style={{ ...inputStyle, width: 60 }} />
              </Field>
            </div>

            {/* RL agent toggle */}
            <label style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', cursor: 'pointer' }}>
              <div
                onClick={() => setConfig((c) => ({ ...c, rl_agents: c.rl_agents ? 0 : 1 }))}
                style={{
                  width: 36, height: 20, borderRadius: 10, position: 'relative', cursor: 'pointer',
                  background: config.rl_agents ? '#7c3aed' : '#1e293b',
                  border: '1px solid #334155', transition: 'background 0.2s',
                }}
              >
                <div style={{
                  position: 'absolute', top: 2, left: config.rl_agents ? 16 : 2,
                  width: 14, height: 14, borderRadius: '50%',
                  background: config.rl_agents ? '#fff' : '#475569',
                  transition: 'left 0.2s',
                }} />
              </div>
              <span style={{ fontSize: '0.72rem', color: config.rl_agents ? '#c4b5fd' : '#475569' }}>
                RL Agent {config.rl_agents ? '(requires checkpoint)' : ''}
              </span>
            </label>

            {/* Advanced */}
            <button
              type="button"
              onClick={() => setShowAdvanced((v) => !v)}
              style={{ ...linkBtn, textAlign: 'left', marginTop: '0.25rem' }}
            >
              {showAdvanced ? '▾' : '▸'} Advanced
            </button>

            {showAdvanced && (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '0.4rem', paddingLeft: '0.5rem', borderLeft: '2px solid #1e293b' }}>
                <Field label="MM Spread %">
                  <input type="number" step="0.001" min="0.001" max="0.5"
                    value={(config.mm_spread * 100).toFixed(1)}
                    onChange={(e) => setConfig((c) => ({ ...c, mm_spread: parseFloat(e.target.value) / 100 }))}
                    style={{ ...inputStyle, width: 80 }} />
                </Field>
                <Field label="MM Quote Qty">
                  <input type="number" step="1" min="1"
                    value={config.mm_quote_qty}
                    onChange={(e) => setConfig((c) => ({ ...c, mm_quote_qty: parseFloat(e.target.value) }))}
                    style={{ ...inputStyle, width: 80 }} />
                </Field>
                <Field label="Noise Max Qty">
                  <input type="number" step="1" min="1"
                    value={config.noise_qty_max}
                    onChange={(e) => setConfig((c) => ({ ...c, noise_qty_max: parseFloat(e.target.value) }))}
                    style={{ ...inputStyle, width: 80 }} />
                </Field>
                <Field label="Mom. Cooldown (s)">
                  <input type="number" step="0.5" min="0.5"
                    value={config.momentum_cooldown}
                    onChange={(e) => setConfig((c) => ({ ...c, momentum_cooldown: parseFloat(e.target.value) }))}
                    style={{ ...inputStyle, width: 80 }} />
                </Field>
                <Field label="Mom. Drift Tol %">
                  <input type="number" step="0.5" min="0.5" max="50"
                    value={(config.momentum_drift_tolerance * 100).toFixed(1)}
                    onChange={(e) => setConfig((c) => ({ ...c, momentum_drift_tolerance: parseFloat(e.target.value) / 100 }))}
                    style={{ ...inputStyle, width: 80 }} />
                </Field>
              </div>
            )}

            <button
              onClick={startSim} disabled={loading}
              style={{ ...actionBtn, background: '#7c3aed', marginTop: '0.25rem' }}
            >
              {loading ? 'Starting…' : '▶ Start Simulation'}
            </button>
          </div>
        </>
      ) : (
        <>
          {/* Agent stats */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem', marginBottom: '0.75rem' }}>
            {simStatus?.agents.map((agent) => (
              <div key={agent.name} style={{ background: '#1e293b', borderRadius: 4, padding: '0.5rem 0.75rem' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '0.2rem' }}>
                  <span style={{ color: '#c4b5fd', fontWeight: 600, fontSize: '0.78rem' }}>{agent.name}</span>
                  <span style={{ color: '#475569', fontSize: '0.72rem' }}>{agent.type}</span>
                </div>
                <div style={{ color: '#64748b', fontSize: '0.72rem', display: 'flex', gap: '1rem', flexWrap: 'wrap' }}>
                  <span>ticks: <span style={{ color: '#94a3b8' }}>{agent.tick_count.toLocaleString()}</span></span>
                  {agent.half_spread_pct !== undefined && (
                    <span>spread: <span style={{ color: '#94a3b8' }}>{agent.half_spread_pct * 2}%</span></span>
                  )}
                  {agent.cooldown_remaining_s !== undefined && (
                    <span>cooldown: <span style={{ color: '#94a3b8' }}>{agent.cooldown_remaining_s}s</span></span>
                  )}
                  {agent.bid_id && (
                    <span>bid: <span style={{ color: '#22c55e' }}>active</span></span>
                  )}
                  {agent.ask_id && (
                    <span>ask: <span style={{ color: '#ef4444' }}>active</span></span>
                  )}
                  {/* RL agent extras */}
                  {(agent as any).last_action !== undefined && (
                    <span>action: <span style={{ color: '#a78bfa' }}>{(agent as any).last_action}</span></span>
                  )}
                  {(agent as any).position !== undefined && (
                    <span>pos: <span style={{
                      color: (agent as any).position > 0 ? '#4ade80' : (agent as any).position < 0 ? '#f87171' : '#94a3b8'
                    }}>{(agent as any).position}</span></span>
                  )}
                  {(agent as any).episode_pnl !== undefined && (
                    <span>ep PnL: <span style={{
                      color: (agent as any).episode_pnl >= 0 ? '#4ade80' : '#f87171'
                    }}>{(agent as any).episode_pnl.toFixed(2)}</span></span>
                  )}
                  {(agent as any).ready === false && (
                    <span style={{ color: '#f59e0b' }}>⚠ no checkpoint</span>
                  )}
                </div>
              </div>
            ))}
          </div>
          <button
            onClick={stopSim} disabled={loading}
            style={{ ...actionBtn, background: '#7f1d1d', width: '100%' }}
          >
            {loading ? 'Stopping…' : '■ Stop Simulation'}
          </button>
        </>
      )}

      {error && (
        <div style={{ marginTop: '0.5rem', color: '#ef4444', fontSize: '0.75rem' }}>{error}</div>
      )}
    </div>
  )
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '0.2rem' }}>
      <label style={{ fontSize: '0.7rem', color: '#475569' }}>{label}</label>
      {children}
    </div>
  )
}

const titleStyle: React.CSSProperties = {
  margin: '0 0 0.75rem', fontSize: '0.8rem', fontWeight: 600, color: '#64748b',
  letterSpacing: '0.05em', textTransform: 'uppercase',
}

const inputStyle: React.CSSProperties = {
  padding: '0.35rem 0.5rem', background: '#0f172a', border: '1px solid #334155',
  borderRadius: 4, color: '#e2e8f0', fontFamily: 'monospace', fontSize: '0.8rem', outline: 'none',
}

const actionBtn: React.CSSProperties = {
  padding: '0.5rem', border: 'none', borderRadius: 4, cursor: 'pointer',
  color: '#fff', fontWeight: 700, fontFamily: 'monospace', fontSize: '0.82rem',
}

const linkBtn: React.CSSProperties = {
  background: 'none', border: 'none', cursor: 'pointer',
  color: '#475569', fontFamily: 'monospace', fontSize: '0.75rem', padding: 0,
}
