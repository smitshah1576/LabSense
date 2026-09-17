import React, { useEffect, useState } from 'react'
import { Outlet, useLocation } from 'react-router-dom'
import Navbar from './Navbar'
import Sidebar from './Sidebar'

const Layout = () => {
  const [menuOpen, setMenuOpen] = useState(false)
  const location = useLocation()

  // Close the mobile drawer whenever the route changes.
  useEffect(() => {
    setMenuOpen(false)
  }, [location.pathname])

  return (
    <div className="shell">
      <Sidebar open={menuOpen} />
      {menuOpen && <div className="sidebar-scrim" onClick={() => setMenuOpen(false)} aria-hidden="true" />}
      <div className="shell__main">
        <Navbar onMenu={() => setMenuOpen(true)} />
        <main className="content" id="main">
          <Outlet />
        </main>
      </div>
    </div>
  )
}

export default Layout
