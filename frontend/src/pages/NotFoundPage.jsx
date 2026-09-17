import React from 'react'
import { Link } from 'react-router-dom'
import { FiCompass } from 'react-icons/fi'
import EmptyState from '../components/ui/EmptyState'
import { useDocumentTitle } from '../lib/hooks'

const NotFoundPage = () => {
  useDocumentTitle('Page not found')
  return (
    <div className="card" style={{ marginTop: 40 }}>
      <EmptyState
        icon={FiCompass}
        title="Page not found"
        description="The page you were looking for doesn't exist or has moved."
        action={
          <Link to="/" className="btn btn--primary">
            Go to overview
          </Link>
        }
      />
    </div>
  )
}

export default NotFoundPage
