import React, { useState } from 'react'
import { softwareApi } from '../api/endpoints'
import SearchBar from '../components/Software/SearchBar'
import SoftwareResults from '../components/Software/SoftwareResults'
import { FiSearch, FiPackage, FiZap } from 'react-icons/fi'

const POPULAR_PACKAGES = [
  'Python',
  'VS Code',
  'Docker',
  'MATLAB',
  'Wireshark',
  'Blender',
  'GCC',
  'PostgreSQL',
  'Git',
  'Java',
]

const SoftwarePage = () => {
  const [query, setQuery] = useState('')
  const [results, setResults] = useState([])
  const [loading, setLoading] = useState(false)

  const handleSearch = async (q) => {
    setQuery(q)
    if (!q || q.length < 2) {
      setResults([])
      return
    }
    setLoading(true)
    try {
      const res = await softwareApi.searchGlobal(q)
      if (Array.isArray(res.data)) {
        setResults(res.data)
      }
    } catch (err) {
      console.error('Failed to search software globally:', err)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="page-container">
      <div className="page-header">
        <div className="page-title-group">
          <h1 className="page-title">
            <FiPackage style={{ color: 'var(--color-primary)' }} />
            Campus Software Locator
          </h1>
          <p className="page-subtitle">
            Find which campus labs and workstations have specific applications, compilers, and IDEs installed
          </p>
        </div>
      </div>

      {/* Search Header Panel */}
      <div className="glass-card" style={{ padding: '1.75rem', display: 'flex', flexDirection: 'column', gap: '1.25rem' }}>
        <SearchBar
          onSearch={handleSearch}
          placeholder="Search any software tool, IDE, package or CLI (e.g. PyTorch, Quartus, CLion, Rust)..."
          loading={loading}
          initialValue={query}
        />

        {/* Popular Tags */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', flexWrap: 'wrap' }}>
          <span style={{ fontSize: '0.78rem', color: 'var(--text-muted)', display: 'flex', alignItems: 'center', gap: '0.3rem' }}>
            <FiZap size={13} style={{ color: 'var(--color-warning)' }} />
            Popular:
          </span>
          {POPULAR_PACKAGES.map((pkg) => (
            <button
              key={pkg}
              onClick={() => handleSearch(pkg)}
              className="btn btn-ghost btn-sm"
              style={{
                fontSize: '0.75rem',
                padding: '0.2rem 0.6rem',
                borderRadius: 'var(--radius-full)',
                background: 'hsla(220, 20%, 14%, 0.6)',
                border: '1px solid var(--border-glass)',
                color: query.toLowerCase() === pkg.toLowerCase() ? 'var(--color-primary)' : 'var(--text-secondary)',
              }}
            >
              {pkg}
            </button>
          ))}
        </div>
      </div>

      {/* Results */}
      <SoftwareResults
        results={results}
        searchQuery={query}
        loading={loading}
      />
    </div>
  )
}

export default SoftwarePage
