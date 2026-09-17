import React from 'react'
import { FiLoader, FiSearch, FiX } from 'react-icons/fi'

// Controlled search input. Debouncing is the caller's job (useDebouncedValue).
const SearchBar = ({ value, onChange, placeholder = 'Search software…', loading = false, size, autoFocus, label = 'Search software' }) => {
  const large = size === 'lg'
  return (
    <div className={`input-icon ${large ? 'input-icon--lg' : ''}`}>
      <input
        type="search"
        className={`input ${large ? 'input--lg' : ''}`}
        placeholder={placeholder}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        aria-label={label}
        autoFocus={autoFocus}
        spellCheck={false}
        autoComplete="off"
        style={{ paddingRight: value ? 40 : undefined }}
      />
      {loading ? <FiLoader size={large ? 17 : 15} className="spin" /> : <FiSearch size={large ? 17 : 15} />}
      {value && (
        <button type="button" className="input-clear" onClick={() => onChange('')} aria-label="Clear search">
          <FiX size={15} />
        </button>
      )}
    </div>
  )
}

export default SearchBar
