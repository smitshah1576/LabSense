import React, { createContext, useState, useEffect, useRef, useContext } from 'react'
import { AuthContext } from './AuthContext'

export const WebSocketContext = createContext(null)

export const WebSocketProvider = ({ children }) => {
  const { token, isAuthenticated } = useContext(AuthContext)
  const [pcStates, setPcStates] = useState({})
  const [labStates, setLabStates] = useState({})
  const [connected, setConnected] = useState(false)
  const socketRef = useRef(null)
  const reconnectTimeoutRef = useRef(null)

  useEffect(() => {
    if (!isAuthenticated || !token) {
      if (socketRef.current) {
        socketRef.current.close()
        socketRef.current = null
      }
      setConnected(false)
      return
    }

    const getWsUrl = () => {
      const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
      const host = import.meta.env.VITE_WS_URL || 'localhost:8000'
      const cleanHost = host.replace(/^wss?:\/\//, '')
      return `${protocol}//${cleanHost}/ws?token=${token}`
    }

    let isUnmounted = false

    const connect = () => {
      if (isUnmounted) return

      try {
        const url = getWsUrl()
        const ws = new WebSocket(url)
        socketRef.current = ws

        ws.onopen = () => {
          if (!isUnmounted) {
            setConnected(true)
          }
        }

        ws.onmessage = (event) => {
          if (isUnmounted) return
          try {
            const data = JSON.parse(event.data)

            if (data.type === 'initial_state' && Array.isArray(data.pcs)) {
              setPcStates((prev) => {
                const next = { ...prev }
                data.pcs.forEach((pc) => {
                  next[pc.pc_id] = {
                    ...(next[pc.pc_id] || {}),
                    status: pc.state,
                    session_active: pc.session_active,
                    screen_locked: pc.screen_locked,
                    cpu_percent: pc.cpu_percent,
                    idle_seconds: pc.idle_seconds,
                    last_heartbeat_at: new Date().toISOString(),
                  }
                })
                return next
              })
            } else if (data.type === 'pc_update' && data.pc_id) {
              setPcStates((prev) => ({
                ...prev,
                [data.pc_id]: {
                  ...(prev[data.pc_id] || {}),
                  status: data.state,
                  session_active: data.session_active !== undefined ? data.session_active : (prev[data.pc_id]?.session_active),
                  screen_locked: data.screen_locked !== undefined ? data.screen_locked : (prev[data.pc_id]?.screen_locked),
                  cpu_percent: data.cpu_percent !== undefined ? data.cpu_percent : (prev[data.pc_id]?.cpu_percent),
                  idle_seconds: data.idle_seconds !== undefined ? data.idle_seconds : (prev[data.pc_id]?.idle_seconds),
                  last_heartbeat_at: new Date().toISOString(),
                },
              }))
            } else if (data.type === 'lab_update' && data.lab_id) {
              setLabStates((prev) => ({
                ...prev,
                [data.lab_id]: data.state,
              }))
            }
          } catch (err) {
            console.error('Error parsing WebSocket message:', err)
          }
        }

        ws.onerror = (err) => {
          console.warn('WebSocket encountered error:', err)
        }

        ws.onclose = () => {
          if (!isUnmounted) {
            setConnected(false)
            // Attempt reconnection after 3 seconds
            reconnectTimeoutRef.current = setTimeout(connect, 3000)
          }
        }
      } catch (err) {
        console.error('Failed to create WebSocket connection:', err)
        if (!isUnmounted) {
          reconnectTimeoutRef.current = setTimeout(connect, 4000)
        }
      }
    }

    connect()

    return () => {
      isUnmounted = true
      if (reconnectTimeoutRef.current) {
        clearTimeout(reconnectTimeoutRef.current)
      }
      if (socketRef.current) {
        socketRef.current.close()
        socketRef.current = null
      }
    }
  }, [token, isAuthenticated])

  return (
    <WebSocketContext.Provider value={{ pcStates, labStates, connected }}>
      {children}
    </WebSocketContext.Provider>
  )
}
