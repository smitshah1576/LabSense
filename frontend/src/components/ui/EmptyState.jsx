import React from 'react'

const EmptyState = ({ icon: Icon, title, description, action }) => (
  <div className="empty">
    {Icon && (
      <div className="empty__icon">
        <Icon size={18} />
      </div>
    )}
    {title && <div className="empty__title">{title}</div>}
    {description && <div className="empty__desc">{description}</div>}
    {action && <div className="empty__action">{action}</div>}
  </div>
)

export default EmptyState
