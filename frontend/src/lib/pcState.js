// Display metadata and helpers for PC and lab states.
// The server decides every state; nothing here computes one from telemetry.

export const PC_STATES = {
  AVAILABLE: { label: 'Available', tone: 'available' },
  IN_USE: { label: 'In use', tone: 'in-use' },
  AVAILABLE_SLEEP: { label: 'Asleep', tone: 'sleep' },
  MAINTENANCE: { label: 'Maintenance', tone: 'maintenance' },
}

// Order used for filters, legends and stacked bars.
export const PC_STATE_ORDER = ['AVAILABLE', 'IN_USE', 'AVAILABLE_SLEEP', 'MAINTENANCE']

export const LAB_STATES = {
  OPEN: { label: 'Open', tone: 'available' },
  OCCUPIED: { label: 'Occupied', tone: 'in-use' },
  CLOSED: { label: 'Closed', tone: 'neutral' },
}

export const normalizeState = (state) => (state || '').toString().toUpperCase()

export const pcStateMeta = (state) =>
  PC_STATES[normalizeState(state)] || { label: state || 'Unknown', tone: 'neutral' }

export const labStateMeta = (state) =>
  LAB_STATES[normalizeState(state)] || { label: state || 'Unknown', tone: 'neutral' }

const pick = (live, key, fallback) => (live && live[key] !== undefined ? live[key] : fallback)

// Overlay the live WebSocket entry (if any) on a PC row from REST.
export const mergeLivePc = (pc, live) => {
  const merged = {
    ...pc,
    current_state: normalizeState((live && live.status) || pc.current_state) || 'AVAILABLE',
    session_active: pick(live, 'session_active', pc.session_active),
    screen_locked: pick(live, 'screen_locked', pc.screen_locked),
    cpu_percent: pick(live, 'cpu_percent', pc.cpu_percent),
    idle_seconds: pick(live, 'idle_seconds', pc.idle_seconds),
    last_heartbeat_at: (live && live.last_heartbeat_at) || pc.last_heartbeat_at,
  }
  // REST returns null telemetry for PCs that have not reported since the
  // backend started. Show that as "waiting", not as an idle PC at 0% CPU.
  merged.has_telemetry = typeof merged.cpu_percent === 'number'
  return merged
}

export const mergeLivePcs = (pcs, pcStates) => pcs.map((pc) => mergeLivePc(pc, pcStates[pc.pc_id]))

export const summarizePcs = (pcs) => {
  const counts = { total: pcs.length, AVAILABLE: 0, IN_USE: 0, AVAILABLE_SLEEP: 0, MAINTENANCE: 0 }
  pcs.forEach((pc) => {
    const s = normalizeState(pc.current_state)
    if (counts[s] !== undefined) counts[s] += 1
  })
  // A sleeping PC is free to use once woken, so it counts as available.
  counts.free = counts.AVAILABLE + counts.AVAILABLE_SLEEP
  return counts
}
