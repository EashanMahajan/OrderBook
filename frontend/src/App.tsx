import { useMarketFeed } from './hooks/useMarketFeed'
import { StatusBar } from './components/StatusBar'
import { OrderBook } from './components/OrderBook'
import { DepthChart } from './components/DepthChart'
import { PriceChart } from './components/PriceChart'
import { TradeFeed } from './components/TradeFeed'
import { OrderEntry } from './components/OrderEntry'
import { SimControl } from './components/SimControl'
import { NLOrderEntry } from './components/NLOrderEntry'

export default function App() {
  useMarketFeed()

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
        {/* Left column: order book spans both rows */}
        <div style={{ gridRow: '1 / 3', overflow: 'auto' }}>
          <OrderBook />
        </div>

        {/* Center top: depth chart */}
        <DepthChart />

        {/* Right column top: sim control */}
        <div style={{ overflow: 'auto' }}>
          <SimControl />
        </div>

        {/* Center bottom: price chart + trade feed split */}
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 220px', gap: '0.75rem', minHeight: 0 }}>
          <PriceChart />
          <TradeFeed />
        </div>

        {/* Right column bottom: AI order entry stacked above manual entry */}
        <div style={{ overflow: 'auto', display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
          <NLOrderEntry />
          <OrderEntry />
        </div>
      </div>
    </div>
  )
}
