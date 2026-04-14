import { useState } from 'react'
import { useMarketFeed } from './hooks/useMarketFeed'
import { StatusBar } from './components/StatusBar'
import { OrderBook } from './components/OrderBook'
import { DepthChart } from './components/DepthChart'
import { PriceChart } from './components/PriceChart'
import { TradeFeed } from './components/TradeFeed'
import { OrderEntry } from './components/OrderEntry'
import { SimControl } from './components/SimControl'
import { NLOrderEntry } from './components/NLOrderEntry'
import { RLAgentPanel } from './components/RLAgentPanel'

type RightTab = 'rl' | 'ai'

const TAB_LABELS: { key: RightTab; label: string }[] = [
  { key: 'rl', label: 'RL Agent' },
  { key: 'ai', label: 'AI Orders' },
]

export default function App() {
  useMarketFeed()
  const [rightTab, setRightTab] = useState<RightTab>('rl')

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100vh', background: '#020917', color: '#e2e8f0' }}>
      <StatusBar />

      <div style={{
        flex: 1,
        display: 'grid',
        gridTemplateColumns: '280px 1fr 240px',
        gridTemplateRows: '1fr 1fr',
        gap: '0.75rem',
        padding: '0.75rem',
        overflow: 'hidden',
        minHeight: 0,
      }}>
        {/* Left top: order book */}
        <div style={{ overflow: 'auto' }}>
          <OrderBook />
        </div>

        {/* Center top: depth chart */}
        <DepthChart />

        {/* Right top: sim control */}
        <div style={{ overflow: 'auto' }}>
          <SimControl />
        </div>

        {/* Left bottom: order entry */}
        <div style={{ overflow: 'auto' }}>
          <OrderEntry />
        </div>

        {/* Center bottom: price chart + trade feed */}
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 220px', gap: '0.75rem', minHeight: 0 }}>
          <PriceChart />
          <TradeFeed />
        </div>

        {/* Right bottom: tabbed panel (RL Agent | AI Orders) */}
        <div style={{ display: 'flex', flexDirection: 'column', minHeight: 0 }}>
          {/* Tab bar */}
          <div style={{
            display: 'flex',
            borderBottom: '1px solid #1e2d45',
            marginBottom: '0.5rem',
            flexShrink: 0,
          }}>
            {TAB_LABELS.map(({ key, label }) => (
              <button
                key={key}
                onClick={() => setRightTab(key)}
                style={{
                  flex: 1,
                  background: 'none',
                  border: 'none',
                  borderBottom: rightTab === key ? '2px solid #7c3aed' : '2px solid transparent',
                  color: rightTab === key ? '#e2e8f0' : '#475569',
                  cursor: 'pointer',
                  fontSize: '0.72rem',
                  fontWeight: rightTab === key ? 700 : 400,
                  fontFamily: 'monospace',
                  letterSpacing: '0.04em',
                  padding: '0.35rem 0',
                  transition: 'color 0.15s, border-color 0.15s',
                }}
              >
                {label}
              </button>
            ))}
          </div>

          {/* Tab content */}
          <div style={{ flex: 1, overflow: 'auto' }}>
            {rightTab === 'rl'  && <RLAgentPanel />}
            {rightTab === 'ai'  && <NLOrderEntry />}
          </div>
        </div>
      </div>
    </div>
  )
}
