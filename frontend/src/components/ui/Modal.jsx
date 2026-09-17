import React, { useEffect, useRef } from 'react'
import { createPortal } from 'react-dom'
import { FiX } from 'react-icons/fi'

const Modal = ({ open, onClose, onSubmit, title, description, children, footer, size, busy = false }) => {
  const dialogRef = useRef(null)
  // Callers usually pass inline functions; keep the latest in a ref so the
  // open/close effect runs once per opening rather than on every render.
  const closeRef = useRef(onClose)
  const busyRef = useRef(busy)
  closeRef.current = onClose
  busyRef.current = busy

  useEffect(() => {
    if (!open) return undefined

    const previouslyFocused = document.activeElement
    const onKey = (e) => {
      if (e.key === 'Escape' && !busyRef.current) closeRef.current()
    }
    document.addEventListener('keydown', onKey)
    const { overflow } = document.body.style
    document.body.style.overflow = 'hidden'

    // Focus the first form control, else an explicit target, else the dialog.
    const frame = requestAnimationFrame(() => {
      const root = dialogRef.current
      const target = root?.querySelector('input, select, textarea') || root?.querySelector('[data-autofocus]')
      ;(target || root)?.focus()
    })

    return () => {
      cancelAnimationFrame(frame)
      document.removeEventListener('keydown', onKey)
      document.body.style.overflow = overflow
      previouslyFocused?.focus?.()
    }
  }, [open])

  if (!open) return null

  return createPortal(
    <div className="modal-backdrop" onMouseDown={(e) => e.target === e.currentTarget && !busy && onClose()}>
      <div
        ref={dialogRef}
        className={`modal ${size === 'sm' ? 'modal--sm' : ''}`}
        role="dialog"
        aria-modal="true"
        aria-labelledby="modal-title"
        tabIndex={-1}
      >
        <div className="modal__head">
          <div>
            <h2 id="modal-title" className="modal__title">
              {title}
            </h2>
            {description && <p className="modal__desc">{description}</p>}
          </div>
          <button type="button" className="btn btn--ghost btn--icon btn--sm" onClick={onClose} disabled={busy} aria-label="Close">
            <FiX size={16} />
          </button>
        </div>
        {onSubmit ? (
          // Wrapping body and footer in one form lets Enter submit and a
          // footer button use type="submit".
          <form onSubmit={onSubmit} noValidate={false}>
            {children && <div className="modal__body">{children}</div>}
            {footer && <div className="modal__foot">{footer}</div>}
          </form>
        ) : (
          <>
            {children && <div className="modal__body">{children}</div>}
            {footer && <div className="modal__foot">{footer}</div>}
          </>
        )}
      </div>
    </div>,
    document.body
  )
}

export default Modal
