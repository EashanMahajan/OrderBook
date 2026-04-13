import { useEffect, useRef } from 'react'
import { useMarketStore } from '../store/marketStore'
import type { BookSnapshot } from '../lib/types'

const BASE_DELAY = 500
const MAX_DELAY = 16_000
// Prevent the seen-set from growing without bound across reconnects
const MAX_SEEN = 500

export function useMarketFeed() {
  const { applySnapshot, appendTrade, setConnectionStatus } = useMarketStore()
  const wsRef = useRef<WebSocket | null>(null)
  const delayRef = useRef(BASE_DELAY)
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  // Tracks trade IDs we've already surfaced to the store so we don't duplicate
  // them across consecutive snapshots.
  const seenTradeIds = useRef<Set<string>>(new Set())

  useEffect(() => {
    function connect() {
      setConnectionStatus('connecting')
      const protocol = window.location.protocol === 'https:' ? 'wss' : 'ws'
      const ws = new WebSocket(`${protocol}://${window.location.host}/ws`)
      wsRef.current = ws

      ws.onopen = () => {
        delayRef.current = BASE_DELAY
        setConnectionStatus('live')
      }

      ws.onmessage = (ev) => {
        try {
          const msg = JSON.parse(ev.data)
          if (msg.type !== 'snapshot') return

          const snap = msg.data as BookSnapshot
          applySnapshot(snap)

          // Derive new trade events from the snapshot's recent_trades list.
          // The backend sends snapshots at 10 Hz; each snapshot already contains
          // up to 20 recent trades. We only forward trades with IDs we haven't
          // seen before, so each trade appears in the feed exactly once.
          for (const trade of snap.recent_trades ?? []) {
            if (!seenTradeIds.current.has(trade.trade_id)) {
              seenTradeIds.current.add(trade.trade_id)
              appendTrade(trade)
            }
          }

          // Trim the seen-set so it doesn't grow without bound over long sessions
          if (seenTradeIds.current.size > MAX_SEEN) {
            seenTradeIds.current.clear()
          }
        } catch {
          // malformed message — ignore
        }
      }

      ws.onclose = () => {
        setConnectionStatus('reconnecting')
        timerRef.current = setTimeout(() => {
          delayRef.current = Math.min(delayRef.current * 2, MAX_DELAY)
          connect()
        }, delayRef.current)
      }

      ws.onerror = () => {
        ws.close()
      }
    }

    connect()

    return () => {
      if (timerRef.current) clearTimeout(timerRef.current)
      wsRef.current?.close()
      setConnectionStatus('disconnected')
    }
  }, [applySnapshot, appendTrade, setConnectionStatus])
}
