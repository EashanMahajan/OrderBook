import { useEffect, useRef, useState } from 'react'

interface RLStatus {
  running: boolean
  episode: number
  total_steps: number
  last_episode_reward: number
  best_reward: number | null
  last_loss: number
  epsilon: number
  buffer_size: number
  checkpoint_exists: boolean
}

const CARD: React.CSSProperties = {
  background: '#0d1424',
  border: '1px solid #1e2d45',
  borderRadius: '0.5rem',
  padding: '0.75rem',
  display: 'flex',
  flexDirection: 'column',
  gap: '0.5rem',
}

const LABEL: React.CSSProperties = {
  fontSize: '0.6rem',
  fontWeight: 700,
  letterSpacing: '0.08em',
  color: '#64748b',
  textTransform: 'uppercase',
}

const STAT_ROW: React.CSSProperties = {
  display: 'flex',
  justifyContent: 'space-between',
  fontSize: '0.72rem',
  color: '#94a3b8',
}

const STAT_VAL: React.CSSProperties = {
  color: '#e2e8f0',
  fontFamily: 'monospace',
  fontWeight: 600,
}

const BTN_BASE: React.CSSProperties = {
  border: 'none',
  borderRadius: '0.375rem',
  cursor: 'pointer',
  fontSize: '0.72rem',
  fontWeight: 600,
  padding: '0.4rem 0',
  width: '100%',
}

const EMPTY: RLStatus = {
  running: false,
  episode: 0,
  total_steps: 0,
  last_episode_reward: 0,
  best_reward: null,
  last_loss: 0,
  epsilon: 1.0,
  buffer_size: 0,
  checkpoint_exists: false,
}

function EpsilonBar({ value }: { value: number }) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '0.2rem' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.65rem', color: '#64748b' }}>
        <span>ε explore</span>
        <span style={{ color: '#e2e8f0', fontFamily: 'monospace' }}>{value.toFixed(3)}</span>
      </div>
      <div style={{ background: '#0a1628', borderRadius: '2px', height: '4px', overflow: 'hidden' }}>
        <div
          style={{
            background: value > 0.5 ? '#f59e0b' : value > 0.2 ? '#3b82f6' : '#22c55e',
            height: '100%',
            width: `${value * 100}%`,
            transition: 'width 0.5s ease',
          }}
        />
      </div>
    </div>
  )
}

export function RLAgentPanel() {
  const [status, setStatus] = useState<RLStatus>(EMPTY)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null)

  async function fetchStatus() {
    try {
      const res = await fetch('/rl/status')
      if (res.ok) setStatus(await res.json())
    } catch {
      // ignore network blips
    }
  }

  useEffect(() => {
    fetchStatus()
    intervalRef.current = setInterval(fetchStatus, 2000)
    return () => {
      if (intervalRef.current) clearInterval(intervalRef.current)
    }
  }, [])

  async function toggleTraining() {
    setBusy(true)
    setError(null)
    const url = status.running ? '/rl/train/stop' : '/rl/train/start'
    try {
      const res = await fetch(url, { method: 'POST' })
      const data = await res.json()
      if (!res.ok) throw new Error(data.detail ?? `HTTP ${res.status}`)
      setStatus((prev) => ({ ...prev, ...data }))
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : String(err))
    } finally {
      setBusy(false)
    }
  }

  const btnColor = status.running ? '#dc2626' : '#2563eb'
  const btnLabel = busy ? '…' : status.running ? 'Stop Training' : 'Start Training'

  const rewardColor = (v: number) =>
    v > 0 ? '#4ade80' : v < 0 ? '#f87171' : '#94a3b8'

  return (
    <div style={CARD}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <div style={LABEL}>RL Agent (DQN)</div>
        {status.checkpoint_exists && (
          <span style={{ fontSize: '0.6rem', color: '#4ade80' }}>✓ checkpoint</span>
        )}
      </div>

      {/* Status indicator */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
        <div style={{
          width: '6px', height: '6px', borderRadius: '50%',
          background: status.running ? '#4ade80' : '#475569',
          boxShadow: status.running ? '0 0 4px #4ade80' : 'none',
        }} />
        <span style={{ fontSize: '0.68rem', color: status.running ? '#4ade80' : '#475569' }}>
          {status.running ? 'Training' : 'Idle'}
        </span>
      </div>

      {/* Stats */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: '0.25rem' }}>
        <div style={STAT_ROW}>
          <span>Episodes</span>
          <span style={STAT_VAL}>{status.episode.toLocaleString()}</span>
        </div>
        <div style={STAT_ROW}>
          <span>Steps</span>
          <span style={STAT_VAL}>{status.total_steps.toLocaleString()}</span>
        </div>
        <div style={STAT_ROW}>
          <span>Last reward</span>
          <span style={{ ...STAT_VAL, color: rewardColor(status.last_episode_reward) }}>
            {status.last_episode_reward.toFixed(2)}
          </span>
        </div>
        <div style={STAT_ROW}>
          <span>Best reward</span>
          <span style={{ ...STAT_VAL, color: status.best_reward !== null ? rewardColor(status.best_reward) : '#475569' }}>
            {status.best_reward !== null ? status.best_reward.toFixed(2) : '—'}
          </span>
        </div>
        <div style={STAT_ROW}>
          <span>Loss</span>
          <span style={STAT_VAL}>{status.last_loss > 0 ? status.last_loss.toFixed(5) : '—'}</span>
        </div>
        <div style={STAT_ROW}>
          <span>Buffer</span>
          <span style={STAT_VAL}>{status.buffer_size.toLocaleString()}</span>
        </div>
      </div>

      <EpsilonBar value={status.epsilon} />

      <button
        onClick={toggleTraining}
        disabled={busy}
        style={{ ...BTN_BASE, background: btnColor, color: '#fff', opacity: busy ? 0.6 : 1 }}
      >
        {btnLabel}
      </button>

      {error && (
        <div style={{ color: '#f87171', fontSize: '0.68rem', wordBreak: 'break-word' }}>
          {error}
        </div>
      )}
    </div>
  )
}
