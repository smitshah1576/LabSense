import React, { useEffect, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { FiInfo } from 'react-icons/fi'
import SearchBar from '../components/Software/SearchBar'
import SoftwareResults from '../components/Software/SoftwareResults'
import PageHeader from '../components/ui/PageHeader'
import { useSoftwareSearch } from '../hooks/useSoftwareSearch'
import { apiError, useDocumentTitle } from '../lib/hooks'

// Real package names as dpkg / pip report them, so each suggestion can match.
const SUGGESTIONS = ['python3', 'gcc', 'git', 'openjdk', 'code', 'docker', 'wireshark', 'numpy', 'postgresql', 'blender']

const SoftwarePage = () => {
  useDocumentTitle('Software')
  const [params, setParams] = useSearchParams()
  const [query, setQuery] = useState(params.get('q') || '')
  const search = useSoftwareSearch(query)

  // Keep ?q= in the URL so a search can be shared or bookmarked.
  useEffect(() => {
    const q = search.query
    if ((params.get('q') || '') !== q) setParams(q ? { q } : {}, { replace: true })
  }, [search.query]) // eslint-disable-line react-hooks/exhaustive-deps

  return (
    <>
      <PageHeader title="Software" description="Find which workstations have a package installed, across every lab." />

      <div className="card search-hero">
        <SearchBar
          size="lg"
          value={query}
          onChange={setQuery}
          loading={search.loading}
          placeholder="Search packages, e.g. python3, gcc, wireshark"
          autoFocus
        />
        <div className="chips" style={{ marginTop: 14 }}>
          <span className="subtle" style={{ fontSize: 12.5, marginRight: 4 }}>
            Try
          </span>
          {SUGGESTIONS.map((s) => (
            <button key={s} type="button" className="chip" aria-pressed={query.trim() === s} onClick={() => setQuery(s)}>
              {s}
            </button>
          ))}
        </div>
      </div>

      <div className="section" style={{ marginTop: 20 }}>
        {search.error ? (
          <div className="alert alert--error">{apiError(search.error, 'Search failed')}</div>
        ) : (
          <SoftwareResults results={search.results} query={search.query} loading={search.loading} minLength={search.minLength} />
        )}
      </div>

      <div className="note" style={{ marginTop: 20 }}>
        <FiInfo size={15} />
        <div>
          <strong>What is indexed.</strong> System packages from <span className="mono">dpkg</span> and globally installed{' '}
          <span className="mono">pip</span> packages, rescanned every few minutes by each workstation's agent. Packages inside
          virtual environments are not included.
        </div>
      </div>
    </>
  )
}

export default SoftwarePage
