import React, { createContext, useCallback, useContext, useRef, useState } from 'react'
import { FiAlertCircle, FiCheckCircle, FiInfo, FiX } from 'react-icons/fi'
import Modal from './Modal'

// Toasts replace alert(); confirm() replaces window.confirm().
const FeedbackContext = createContext(null)

const ICONS = { success: FiCheckCircle, error: FiAlertCircle, info: FiInfo }

export const FeedbackProvider = ({ children }) => {
  const [toasts, setToasts] = useState([])
  const [dialog, setDialog] = useState(null)
  const nextId = useRef(1)

  const dismiss = useCallback((id) => setToasts((list) => list.filter((t) => t.id !== id)), [])

  const push = useCallback(
    (kind, message) => {
      const id = nextId.current++
      setToasts((list) => [...list.slice(-3), { id, kind, message }])
      setTimeout(() => dismiss(id), kind === 'error' ? 6000 : 3500)
    },
    [dismiss]
  )

  const toast = useRef({
    success: (m) => push('success', m),
    error: (m) => push('error', m),
    info: (m) => push('info', m),
  }).current

  const confirm = useCallback(
    (options) =>
      new Promise((resolve) => {
        setDialog({ ...options, resolve })
      }),
    []
  )

  const closeDialog = (result) => {
    dialog?.resolve(result)
    setDialog(null)
  }

  return (
    <FeedbackContext.Provider value={{ toast, confirm }}>
      {children}

      <div className="toasts" role="status" aria-live="polite">
        {toasts.map((t) => {
          const Icon = ICONS[t.kind] || FiInfo
          return (
            <div key={t.id} className={`toast toast--${t.kind}`}>
              <Icon size={16} className="toast__icon" />
              <div className="toast__msg">{t.message}</div>
              <button type="button" className="btn btn--ghost btn--icon btn--sm" onClick={() => dismiss(t.id)} aria-label="Dismiss">
                <FiX size={14} />
              </button>
            </div>
          )
        })}
      </div>

      <Modal
        open={!!dialog}
        size="sm"
        onClose={() => closeDialog(false)}
        title={dialog?.title}
        description={dialog?.message}
        footer={
          <>
            <button type="button" className="btn btn--secondary" onClick={() => closeDialog(false)}>
              {dialog?.cancelLabel || 'Cancel'}
            </button>
            <button
              type="button"
              data-autofocus
              className={`btn ${dialog?.tone === 'danger' ? 'btn--danger' : 'btn--primary'}`}
              onClick={() => closeDialog(true)}
            >
              {dialog?.confirmLabel || 'Confirm'}
            </button>
          </>
        }
      />
    </FeedbackContext.Provider>
  )
}

export const useToast = () => useContext(FeedbackContext).toast
export const useConfirm = () => useContext(FeedbackContext).confirm
