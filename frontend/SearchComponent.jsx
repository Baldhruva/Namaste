import React, { useEffect, useMemo, useRef, useState } from 'react';

// Single-file component using Tailwind CSS classes
// Props:
//   - apiBaseUrl (default: '/api')
//
// This component is self-contained: it handles input, debounced API calls,
// loading and error states, and displays results.

const useDebouncedCallback = (callback, delay) => {
  const timer = useRef(null);
  return useMemo(() => {
    return (...args) => {
      if (timer.current) clearTimeout(timer.current);
      timer.current = setTimeout(() => callback(...args), delay);
    };
  }, [callback, delay]);
};

export default function SearchComponent({ apiBaseUrl = '/api' }) {
  const [query, setQuery] = useState('');
  const [module, setModule] = useState('MMS');
  const [limit, setLimit] = useState(10);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [results, setResults] = useState([]);
  const [meta, setMeta] = useState({ source: '', count: 0, query_hash: '', cached_at: null });

  const doSearch = useDebouncedCallback(async (q, module, limit) => {
    if (!q || q.trim().length === 0) {
      setResults([]);
      setMeta({ source: '', count: 0, query_hash: '', cached_at: null });
      setError('');
      setLoading(false);
      return;
    }
    setLoading(true);
    setError('');
    try {
      const resp = await fetch(`${apiBaseUrl}/search`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ q, module, limit }),
      });
      if (!resp.ok) {
        const body = await resp.json().catch(() => ({}));
        throw new Error(body.detail || `HTTP ${resp.status}`);
      }
      const data = await resp.json();
      setResults(data.results || []);
      setMeta({ source: data.source, count: data.count, query_hash: data.query_hash, cached_at: data.cached_at || null });
    } catch (e) {
      setError(e.message || 'Search failed');
      setResults([]);
      setMeta({ source: '', count: 0, query_hash: '', cached_at: null });
    } finally {
      setLoading(false);
    }
  }, 400);

  useEffect(() => {
    doSearch(query, module, limit);
  }, [query, module, limit]);

  return (
    <div className="max-w-3xl mx-auto p-4">
      <h1 className="text-2xl font-semibold mb-4">ICD-11 Search</h1>

      <div className="flex flex-col md:flex-row gap-3 items-stretch md:items-end mb-4">
        <div className="flex-1">
          <label className="block text-sm font-medium text-gray-700 mb-1">Search Query</label>
          <input
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Type a diagnosis or concept..."
            className="w-full rounded border border-gray-300 p-2 focus:outline-none focus:ring-2 focus:ring-blue-500"
          />
        </div>
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">Module</label>
          <select
            value={module}
            onChange={(e) => setModule(e.target.value)}
            className="rounded border border-gray-300 p-2"
          >
            <option value="MMS">MMS</option>
            <option value="TM2">TM2</option>
          </select>
        </div>
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">Limit</label>
          <input
            type="number"
            min={1}
            max={50}
            value={limit}
            onChange={(e) => setLimit(parseInt(e.target.value, 10) || 10)}
            className="w-24 rounded border border-gray-300 p-2"
          />
        </div>
      </div>

      {loading && (
        <div className="text-blue-600 mb-2">Searching...</div>
      )}

      {error && (
        <div className="text-red-600 mb-2">{error}</div>
      )}

      {!loading && !error && results.length === 0 && query && (
        <div className="text-gray-600">No results</div>
      )}

      {!error && results.length > 0 && (
        <div className="space-y-3">
          <div className="text-sm text-gray-600">Source: {meta.source}{meta.cached_at ? ` (cached)` : ''} • {meta.count} results</div>
          <ul className="divide-y divide-gray-200 border rounded">
            {results.map((r, idx) => (
              <li key={`${r.code}-${idx}`} className="p-3">
                <div className="font-mono text-sm text-gray-800">{r.code}</div>
                <div className="font-semibold">{r.title}</div>
                {r.definition && (
                  <div className="text-sm text-gray-700 mt-1">{r.definition}</div>
                )}
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
