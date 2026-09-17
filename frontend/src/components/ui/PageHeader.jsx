import React from 'react'

const PageHeader = ({ title, description, actions, breadcrumb }) => (
  <>
    {breadcrumb && <nav className="breadcrumb" aria-label="Breadcrumb">{breadcrumb}</nav>}
    <header className="page-header">
      <div>
        <h1 className="page-header__title">{title}</h1>
        {description && <p className="page-header__desc">{description}</p>}
      </div>
      {actions && <div className="page-header__actions">{actions}</div>}
    </header>
  </>
)

export default PageHeader
