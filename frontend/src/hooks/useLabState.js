import { useContext } from 'react'
import { WebSocketContext } from '../context/WebSocketContext'

export const useLabState = () => {
  const context = useContext(WebSocketContext)
  if (!context) {
    throw new Error('useLabState must be used within a WebSocketProvider')
  }
  return context
}
