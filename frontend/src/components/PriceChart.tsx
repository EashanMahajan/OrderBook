import { useEffect, useRef } from 'react'
import * as d3 from 'd3'
import { useMarketStore } from '../store/marketStore'
import type { Trade } from '../lib/types'

const WINDOW_SECONDS = 60

export function PriceChart() {
  const svgRef = useRef<SVGSVGElement>(null)
  const trades = useMarketStore((s) => s.trades)
  const simStatus = useMarketStore((s) => s.simStatus)

  useEffect(() => {
    if (!svgRef.current || trades.length === 0) return

    const el = svgRef.current
    const { width } = el.getBoundingClientRect()
    const height = 200
    const margin = { top: 10, right: 20, bottom: 30, left: 60 }
    const innerW = width - margin.left - margin.right
    const innerH = height - margin.top - margin.bottom

    // Filter to rolling 60-second window
    const now = Date.now() / 1000
    const windowStart = now - WINDOW_SECONDS
    const visible: Trade[] = [...trades]
      .filter((t) => t.timestamp >= windowStart)
      .sort((a, b) => a.timestamp - b.timestamp)

    if (visible.length < 2) return

    const xScale = d3.scaleLinear()
      .domain([windowStart, now])
      .range([0, innerW])

    const prices = visible.map((t) => t.price)
    const minP = d3.min(prices)!
    const maxP = d3.max(prices)!
    const pad = (maxP - minP) * 0.1 || 1

    const yScale = d3.scaleLinear()
      .domain([minP - pad, maxP + pad])
      .range([innerH, 0])

    const svg = d3.select(el)
    svg.selectAll('*').remove()
    svg.attr('height', height)

    const g = svg.append('g').attr('transform', `translate(${margin.left},${margin.top})`)

    // Grid
    g.append('g')
      .call(d3.axisLeft(yScale).ticks(4).tickSize(-innerW).tickFormat(() => ''))
      .call((g) => g.select('.domain').remove())
      .call((g) => g.selectAll('line').attr('stroke', '#1e293b'))

    // target_price dashed line (when sim is running)
    const targetPrice = simStatus?.agents[0]?.target_price
    if (simStatus?.running && targetPrice !== undefined) {
      g.append('line')
        .attr('x1', 0).attr('x2', innerW)
        .attr('y1', yScale(targetPrice)).attr('y2', yScale(targetPrice))
        .attr('stroke', '#a855f7')
        .attr('stroke-dasharray', '6 4')
        .attr('stroke-width', 1)

      g.append('text')
        .attr('x', innerW - 4).attr('y', yScale(targetPrice) - 4)
        .attr('text-anchor', 'end')
        .attr('fill', '#a855f7')
        .attr('font-size', '10px')
        .attr('font-family', 'monospace')
        .text(`target $${targetPrice}`)
    }

    // Price line
    const line = d3.line<Trade>()
      .x((d) => xScale(d.timestamp))
      .y((d) => yScale(d.price))
      .curve(d3.curveMonotoneX)

    g.append('path')
      .datum(visible)
      .attr('fill', 'none')
      .attr('stroke', '#38bdf8')
      .attr('stroke-width', 1.5)
      .attr('d', line)

    // Trade dots (sparse — only every Nth to avoid clutter)
    const step = Math.max(1, Math.floor(visible.length / 30))
    g.selectAll('circle')
      .data(visible.filter((_, i) => i % step === 0))
      .join('circle')
      .attr('cx', (d) => xScale(d.timestamp))
      .attr('cy', (d) => yScale(d.price))
      .attr('r', 2)
      .attr('fill', '#38bdf8')
      .attr('opacity', 0.6)

    // Axes
    const xAxis = d3.axisBottom(xScale)
      .ticks(5)
      .tickFormat((d) => {
        const date = new Date(Number(d) * 1000)
        return date.toLocaleTimeString([], { hour12: false, hour: '2-digit', minute: '2-digit', second: '2-digit' })
      })

    g.append('g')
      .attr('transform', `translate(0,${innerH})`)
      .call(xAxis)
      .call((g) => g.select('.domain').attr('stroke', '#334155'))
      .call((g) => g.selectAll('text').attr('fill', '#64748b').attr('font-size', '9px'))
      .call((g) => g.selectAll('line').attr('stroke', '#334155'))

    g.append('g')
      .call(d3.axisLeft(yScale).ticks(4).tickFormat((d) => `$${d}`))
      .call((g) => g.select('.domain').attr('stroke', '#334155'))
      .call((g) => g.selectAll('text').attr('fill', '#64748b').attr('font-size', '10px'))
      .call((g) => g.selectAll('line').attr('stroke', '#334155'))
  }, [trades, simStatus])

  return (
    <div style={{ background: '#0f172a', border: '1px solid #1e293b', borderRadius: 8, overflow: 'hidden' }}>
      <h2 style={titleStyle}>Price (60s window)</h2>
      {trades.length === 0
        ? <div style={{ height: 200, display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#475569', fontFamily: 'monospace', fontSize: '0.82rem' }}>Waiting for trades…</div>
        : <svg ref={svgRef} style={{ width: '100%', display: 'block' }} />
      }
    </div>
  )
}

const titleStyle: React.CSSProperties = {
  margin: 0, padding: '0.75rem 1rem 0.25rem',
  fontSize: '0.8rem', fontWeight: 600, color: '#64748b',
  fontFamily: 'monospace', letterSpacing: '0.05em', textTransform: 'uppercase',
}
