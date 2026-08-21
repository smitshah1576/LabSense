import React, { useState, useEffect, useContext } from 'react'
import { labsApi, softwareApi, adminApi } from '../api/endpoints'
import { AuthContext } from '../context/AuthContext'
import { useLabState } from '../hooks/useLabState'
import LabCard from '../components/Dashboard/LabCard'
import SearchBar from '../components/Software/SearchBar'
import SoftwareResults from '../components/Software/SoftwareResults'
import {
  FiGrid,
  FiLayers,
  FiMonitor,
  FiActivity,
  FiRefreshCw,
  FiCheckCircle,
  FiPlus,
} from 'react-icons/fi'

const DashboardPage = () => {
  const [labs, setLabs] = useState([])
  const [loading, setLoading] = useState(true)
  const [refreshing, setRefreshing] = useState(false)
  const [searchQuery, setSearchQuery] = useState('')
  const [searchResults, setSearchResults] = useState([])
  const [searchLoading, setSearchLoading] = useState(false)

  const { isAdmin } = useContext(AuthContext)
  const [showCreateModal, setShowCreateModal] = useState(false)
  const [newLabData, setNewLabData] = useState({ lab_id: '', lab_name: '', operating_start_time: '08:00', operating_end_time: '20:00' })

  const { labStates, pcStates } = useLabState()

  const fetchLabs = async (isManualRefresh = false) => {
    if (isManualRefresh) setRefreshing(true)
    try {
      const res = await labsApi.getLabs()
      if (Array.isArray(res.data)) {
        setLabs(res.data)
      }
    } catch (err) {
      console.error('Error fetching labs:', err)
    } finally {
      setLoading(false)
      if (isManualRefresh) setRefreshing(false)
    }
  }

  useEffect(() => {
    fetchLabs()
  }, [])

  // Sync labs with real-time websocket updates
  const mergedLabs = labs.map((lab) => {
    const liveLabState = labStates[lab.lab_id]
    return {
      ...lab,
      state: liveLabState || lab.state,
    }
  })

  // Handle global software search from dashboard
  const handleSearch = async (q) => {
    setSearchQuery(q)
    if (!q || q.length < 2) {
      setSearchResults([])
      return
    }
    setSearchLoading(true)
    try {
      const res = await softwareApi.searchGlobal(q)
      if (Array.isArray(res.data)) {
        setSearchResults(res.data)
      }
    } catch (err) {
      console.error('Software search error:', err)
    } finally {
      setSearchLoading(false)
    }
  }

  const handleCreateLab = async (e) => {
    e.preventDefault()
    try {
      await adminApi.createLab(newLabData)
      setShowCreateModal(false)
      setNewLabData({ lab_id: '', lab_name: '', operating_start_time: '08:00', operating_end_time: '20:00' })
      fetchLabs()
    } catch (err) {
      alert(err.response?.data?.detail || 'Failed to create lab')
    }
  }

  const handleDeleteLab = async (labId) => {
    try {
      await adminApi.deleteLab(labId)
      fetchLabs()
    } catch (err) {
      alert(err.response?.data?.detail || 'Failed to delete lab')
    }
  }

  // Calculate high level campus statistics
  const totalLabs = mergedLabs.length
  const totalCapacity = mergedLabs.reduce((acc, l) => acc + (l.capacity || 0), 0)
  const totalAvailablePcs = mergedLabs.reduce((acc, l) => acc + (l.available_pcs || 0), 0)
  const openLabsCount = mergedLabs.filter((l) => (l.state || '').toUpperCase() === 'OPEN').length

  return (
    <div className="page-container">
      {/* Page Header */}
      <div className="page-header">
        <div className="page-title-group">
          <h1 className="page-title">
            <FiGrid style={{ color: 'var(--color-primary)' }} />
            Campus Lab Overview
          </h1>
          <p className="page-subtitle">
            Live occupancy, real-time workstation status, and software locator
          </p>
        </div>

        <div className="page-actions">
          {isAdmin() && (
            <button
              onClick={() => setShowCreateModal(true)}
              className="btn btn-primary btn-sm"
              style={{ marginRight: '0.5rem' }}
            >
              <FiPlus size={14} />
              <span>Add Lab</span>
            </button>
          )}
          <button
            onClick={() => fetchLabs(true)}
            className="btn btn-secondary btn-sm"
            disabled={refreshing}
          >
            <FiRefreshCw size={14} className={refreshing ? 'spin' : ''} />
            <span>{refreshing ? 'Refreshing...' : 'Refresh'}</span>
          </button>
        </div>
      </div>

      {showCreateModal && (
        <div className="glass-panel" style={{ padding: '1.25rem', marginBottom: '1.25rem' }}>
          <h3>Add New Lab</h3>
          <form onSubmit={handleCreateLab} style={{ display: 'flex', gap: '1rem', alignItems: 'flex-end', flexWrap: 'wrap', marginTop: '1rem' }}>
            <div>
              <label style={{ display: 'block', fontSize: '0.8rem', marginBottom: '0.25rem' }}>Lab ID</label>
              <input required value={newLabData.lab_id} onChange={e => setNewLabData({...newLabData, lab_id: e.target.value})} className="form-control" placeholder="e.g. 408" />
            </div>
            <div>
              <label style={{ display: 'block', fontSize: '0.8rem', marginBottom: '0.25rem' }}>Lab Name</label>
              <input required value={newLabData.lab_name} onChange={e => setNewLabData({...newLabData, lab_name: e.target.value})} className="form-control" placeholder="e.g. Computer Lab 408" />
            </div>
            <div>
              <label style={{ display: 'block', fontSize: '0.8rem', marginBottom: '0.25rem' }}>Start Time</label>
              <input required type="time" value={newLabData.operating_start_time} onChange={e => setNewLabData({...newLabData, operating_start_time: e.target.value})} className="form-control" />
            </div>
            <div>
              <label style={{ display: 'block', fontSize: '0.8rem', marginBottom: '0.25rem' }}>End Time</label>
              <input required type="time" value={newLabData.operating_end_time} onChange={e => setNewLabData({...newLabData, operating_end_time: e.target.value})} className="form-control" />
            </div>
            <div style={{ display: 'flex', gap: '0.5rem' }}>
              <button type="submit" className="btn btn-primary">Create</button>
              <button type="button" className="btn btn-secondary" onClick={() => setShowCreateModal(false)}>Cancel</button>
            </div>
          </form>
        </div>
      )}

      {/* Summary KPI Cards */}
      <div className="grid-container grid-4">
        <div className="glass-card" style={{ padding: '1.25rem' }}>
          <div className="flex-between">
            <span style={{ fontSize: '0.8rem', color: 'var(--text-secondary)' }}>Total Labs</span>
            <div style={{ color: 'var(--color-primary)' }}>
              <FiLayers size={18} />
            </div>
          </div>
          <div style={{ fontSize: '1.75rem', fontWeight: 700, color: 'var(--text-primary)', marginTop: '0.5rem' }}>
            {totalLabs}
          </div>
          <div style={{ fontSize: '0.72rem', color: 'var(--text-muted)', marginTop: '0.25rem' }}>
            {openLabsCount} open for walk-in use
          </div>
        </div>

        <div className="glass-card" style={{ padding: '1.25rem' }}>
          <div className="flex-between">
            <span style={{ fontSize: '0.8rem', color: 'var(--text-secondary)' }}>Available PCs</span>
            <div style={{ color: 'var(--color-success)' }}>
              <FiCheckCircle size={18} />
            </div>
          </div>
          <div style={{ fontSize: '1.75rem', fontWeight: 700, color: 'var(--color-success)', marginTop: '0.5rem' }}>
            {totalAvailablePcs}
          </div>
          <div style={{ fontSize: '0.72rem', color: 'var(--text-muted)', marginTop: '0.25rem' }}>
            Out of {totalCapacity} total workstations
          </div>
        </div>

        <div className="glass-card" style={{ padding: '1.25rem' }}>
          <div className="flex-between">
            <span style={{ fontSize: '0.8rem', color: 'var(--text-secondary)' }}>Campus Capacity</span>
            <div style={{ color: 'var(--color-cyan)' }}>
              <FiMonitor size={18} />
            </div>
          </div>
          <div style={{ fontSize: '1.75rem', fontWeight: 700, color: 'var(--text-primary)', marginTop: '0.5rem' }}>
            {totalCapacity}
          </div>
          <div style={{ fontSize: '0.72rem', color: 'var(--text-muted)', marginTop: '0.25rem' }}>
            Monitored in real-time
          </div>
        </div>

        <div className="glass-card" style={{ padding: '1.25rem' }}>
          <div className="flex-between">
            <span style={{ fontSize: '0.8rem', color: 'var(--text-secondary)' }}>Live Telemetry</span>
            <div style={{ color: 'var(--color-purple)' }}>
              <FiActivity size={18} />
            </div>
          </div>
          <div style={{ fontSize: '1.75rem', fontWeight: 700, color: 'var(--color-purple)', marginTop: '0.5rem' }}>
            100%
          </div>
          <div style={{ fontSize: '0.72rem', color: 'var(--text-muted)', marginTop: '0.25rem' }}>
            Async heartbeat sync active
          </div>
        </div>
      </div>

      {/* Global Quick Search Bar */}
      <div className="glass-panel" style={{ padding: '1.25rem' }}>
        <h3 style={{ fontSize: '0.95rem', fontWeight: 600, marginBottom: '0.75rem', color: 'var(--text-secondary)' }}>
          Looking for specific software? Search campus-wide:
        </h3>
        <SearchBar
          onSearch={handleSearch}
          placeholder="Search software (e.g. VS Code, Wireshark, Blender, Python 3.11)..."
          loading={searchLoading}
        />

        {searchQuery.length >= 2 && (
          <div style={{ marginTop: '1.25rem' }}>
            <SoftwareResults
              results={searchResults}
              searchQuery={searchQuery}
              loading={searchLoading}
            />
          </div>
        )}
      </div>

      {/* Labs Grid */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: '0.85rem' }}>
        <h2 style={{ fontSize: '1.25rem', fontWeight: 600 }}>All Computer Labs</h2>

        {loading ? (
          <div className="grid-container grid-3">
            {[1, 2, 3].map((n) => (
              <div key={n} className="glass-card skeleton" style={{ height: '180px' }} />
            ))}
          </div>
        ) : mergedLabs.length === 0 ? (
          <div className="glass-panel" style={{ textAlign: 'center', padding: '3rem 1rem', color: 'var(--text-muted)' }}>
            <FiLayers size={36} style={{ opacity: 0.4, marginBottom: '0.5rem' }} />
            <p>No labs configured yet in the campus database.</p>
          </div>
        ) : (
          <div className="grid-container grid-3">
            {mergedLabs.map((lab) => (
              <LabCard key={lab.lab_id} lab={lab} isAdmin={isAdmin()} onDelete={handleDeleteLab} />
            ))}
          </div>
        )}
      </div>
    </div>
  )
}

export default DashboardPage
