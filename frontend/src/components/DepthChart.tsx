import { useEffect, useRef } from 'react'
import * as d3 from 'd3'
import { useMarketStore } from '../store/marketStore'
import type { PriceLevel } from '../lib/types'

interface CumulativePoint { price: number; qty: number }

function buildCumulative(levels: PriceLevel[], side: 'bid' | 'ask'): CumulativePoint[] {
  // Bids: sorted descending (highest first); asks: ascending
  const sorted = side === 'bid'
    ? [...levels].sort((a, b) => b.price - a.price)
    : [...levels].sort((a, b) => a.price - b.price)

  let running = 0
  return sorted.map((l) => {
    running += l.total_quantity
    return { price: l.price, qty: running }
  })
}

export function DepthChart() {
  const svgRef = useRef<SVGSVGElement>(null)
  const snapshot = useMarketStore((s) => s.snapshot)

  useEffect(() => {
    if (!svgRef.current || !snapshot) return

    const el = svgRef.current
    const { width } = el.getBoundingClientRect()
    const height = 200
    const margin = { top: 10, right: 20, bottom: 30, left: 50 }
    const innerW = width - margin.left - margin.right
    const innerH = height - margin.top - margin.bottom

    const bidCurve = buildCumulative(snapshot.bids, 'bid')
    const askCurve = buildCumulative(snapshot.asks, 'ask')

    if (bidCurve.length === 0 && askCurve.length === 0) return

    const allPrices = [...bidCurve, ...askCurve].map((p) => p.price)
    const allQtys = [...bidCurve, ...askCurve].map((p) => p.qty)

    const xScale = d3.scaleLinear()
      .domain([d3.min(allPrices)! * 0.998, d3.max(allPrices)! * 1.002])
      .range([0, innerW])

    const yScale = d3.scaleLinear()
      .domain([0, d3.max(allQtys)! * 1.05])
      .range([innerH, 0])

    const svg = d3.select(el)
    svg.selectAll('*').remove()
    svg.attr('height', height)

    const g = svg.append('g').attr('transform', `translate(${margin.left},${margin.top})`)

    // Grid lines
    g.append('g')
      .call(d3.axisLeft(yScale).ticks(4).tickSize(-innerW).tickFormat(() => ''))
      .call((g) => g.select('.domain').remove())
      .call((g) => g.selectAll('line').attr('stroke', '#1e293b'))

    // Bid area
    const bidArea = d3.area<CumulativePoint>()
      .x((d) => xScale(d.price))
      .y0(innerH)
      .y1((d) => yScale(d.qty))
      .curve(d3.curveStepAfter)

    g.append('path')
      .datum(bidCurve)
      .attr('fill', 'rgba(34,197,94,0.2)')
      .attr('stroke', '#22c55e')
      .attr('stroke-width', 1.5)
      .attr('d', bidArea)

    // Ask area
    const askArea = d3.area<CumulativePoint>()
      .x((d) => xScale(d.price))
      .y0(innerH)
      .y1((d) => yScale(d.qty))
      .curve(d3.curveStepBefore)

    g.append('path')
      .datum(askCurve)
      .attr('fill', 'rgba(239,68,68,0.2)')
      .attr('stroke', '#ef4444')
      .attr('stroke-width', 1.5)
      .attr('d', askArea)

    // Mid-price line
    if (snapshot.bids[0] && snapshot.asks[0]) {
      const mid = (snapshot.bids[0].price + snapshot.asks[0].price) / 2
      g.append('line')
        .attr('x1', xScale(mid)).attr('x2', xScale(mid))
        .attr('y1', 0).attr('y2', innerH)
        .attr('stroke', '#475569')
        .attr('stroke-dasharray', '4 3')
        .attr('stroke-width', 1)
    }

    // Axes
    g.append('g')
      .attr('transform', `translate(0,${innerH})`)
      .call(d3.axisBottom(xScale).ticks(5).tickFormat((d) => `$${d}`))
      .call((g) => g.select('.domain').attr('stroke', '#334155'))
      .call((g) => g.selectAll('text').attr('fill', '#64748b').attr('font-size', '10px'))
      .call((g) => g.selectAll('line').attr('stroke', '#334155'))

    g.append('g')
      .call(d3.axisLeft(yScale).ticks(4))
      .call((g) => g.select('.domain').attr('stroke', '#334155'))
      .call((g) => g.selectAll('text').attr('fill', '#64748b').attr('font-size', '10px'))
      .call((g) => g.selectAll('line').attr('stroke', '#334155'))
  }, [snapshot])

  return (
    <div style={{ background: '#0f172a', border: '1px solid #1e293b', borderRadius: 8, overflow: 'hidden' }}>
      <h2 style={titleStyle}>Market Depth</h2>
      <svg ref={svgRef} style={{ width: '100%', display: 'block' }} />
    </div>
  )
}

const titleStyle: React.CSSProperties = {
  margin: 0, padding: '0.75rem 1rem 0.25rem',
  fontSize: '0.8rem', fontWeight: 600, color: '#64748b',
  fontFamily: 'monospace', letterSpacing: '0.05em', textTransform: 'uppercase',
}
