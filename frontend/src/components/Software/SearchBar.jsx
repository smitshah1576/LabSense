import React, { useState, useEffect, useRef } from 'react'
import { FiSearch, FiX, FiLoader } from 'react-icons/fi'

const SearchBar = ({ onSearch, placeholder = 'Search software (e.g., Python, MATLAB, Docker, VS Code)...', loading = false, initialValue = '' }) => {
  const [query, setQuery] = useState(initialValue)
  const isFirstRender = useRef(true)

  useEffect(() => {
    if (isFirstRender.current) {
      isFirstRender.current = false
      if (initialValue) {
        onSearch(initialValue)
      }
      return
    }

    const handler = setTimeout(() => {
      onSearch(query.trim())
    }, 300)

    return () => {
      clearTimeout(handler)
    }
  }, [query])

  const handleClear = () => {
    setQuery('')
    onSearch('')
  }

  return (
    <div className="search-input-wrapper">
      <span className="search-input-icon">
        {loading ? (
          <FiLoader className="spin" size={18} style={{ animation: 'spin 1s linear infinite' }} />
        ) : (
          <FiSearch size={18} />
        )}
      </span>
      <input
        type="text"
        className="search-input"
        placeholder={placeholder}
        value={query}
        onChange={(e) => setQuery(e.target.value)}
      />
      {query && (
        <button
          type="button"
          className="search-clear-btn"
          onClick={handleClear}
          title="Clear search"
        >
          <FiX size={16} />
        </button>
      )}
      <style>{`
        @keyframes spin {
          from { transform: rotate(0deg); }
          to { transform: rotate(360deg); }
        }
      `}</style>
    </div>
  )
}

export default SearchBar
