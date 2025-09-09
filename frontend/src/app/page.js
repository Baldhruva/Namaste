"use client";

import { useState, useEffect, useRef } from "react";
import { Search } from "lucide-react";
import axios from "axios";

export default function HomePage() {
  const [query, setQuery] = useState("");
  const [results, setResults] = useState([]);
  const typingTimeout = useRef(null);

  const handleChange = (e) => {
    const value = e.target.value;
    setQuery(value);

    // clear previous timer if still typing
    if (typingTimeout.current) {
      clearTimeout(typingTimeout.current);
    }

    // set new timer (200–300ms delay)
    typingTimeout.current = setTimeout(() => {
      fetchResults(value);
    }, 300);
  };

  const fetchResults = async (value) => {
    if (value.trim() === "") {
      setResults([]);
      return;
    }

    try {
      const res = await axios.get(process.env.NEXT_PUBLIC_AUTOFILL_API, {
        params: { q: value }, 
      });
      console.log(res.data.bruh)

      if (res.status === 200) {
        setResults(["true"]);
      } else {
        setResults([]);
      }
    } catch (err) {
      console.error("API error:", err);
      setResults([]);
    }
  };

  const handleSelect = (word) => {
    setQuery(word);
    setResults([]);
  };

  return (
    <main className="flex flex-col items-center justify-center min-h-screen bg-gray-50">
      <h1 className="text-3xl font-bold mb-6">Search Stuff</h1>

      {/* Search Bar */}
      <div className="relative w-80">
        <input
          type="text"
          placeholder="Type to search..."
          value={query}
          onChange={handleChange}
          className="w-full border border-gray-300 rounded-full pl-4 pr-12 py-3 shadow-md focus:outline-none focus:ring-2 focus:ring-green-400 transition"
        />
        <Search className="absolute right-4 top-1/2 -translate-y-1/2 text-gray-500 w-5 h-5" />
      </div>

      {/* Suggestions */}
      {results.length > 0 && (
        <ul className="mt-4 w-80 bg-white shadow rounded-lg">
          {results.map((word, i) => (
            <li
              key={i}
              onClick={() => handleSelect(word)}
              className="border-b last:border-b-0 px-4 py-2 hover:bg-green-100 cursor-pointer rounded-md transition"
            >
              {word}
            </li>
          ))}
        </ul>
      )}
    </main>
  );
}
