import { useQuery } from "@tanstack/react-query";
import { useEffect, useMemo, useRef, useState } from "react";
import type { FormEvent } from "react";
import { Link, useNavigate } from "react-router-dom";

import { searchApi } from "../lib/api";
import type { SearchSuggestItem } from "../types";

const DEBOUNCE_MS = 300;

export function SearchHeader() {
  const navigate = useNavigate();
  const rootRef = useRef<HTMLDivElement | null>(null);
  const [keyword, setKeyword] = useState("");
  const [debouncedKeyword, setDebouncedKeyword] = useState("");
  const [dropdownOpen, setDropdownOpen] = useState(false);

  useEffect(() => {
    const timer = window.setTimeout(() => {
      setDebouncedKeyword(keyword.trim());
    }, DEBOUNCE_MS);
    return () => window.clearTimeout(timer);
  }, [keyword]);

  useEffect(() => {
    const onPointerDown = (event: MouseEvent) => {
      if (!rootRef.current?.contains(event.target as Node)) {
        setDropdownOpen(false);
      }
    };
    document.addEventListener("mousedown", onPointerDown);
    return () => document.removeEventListener("mousedown", onPointerDown);
  }, []);

  const suggestQuery = useQuery({
    queryKey: ["search-suggest", debouncedKeyword],
    queryFn: () => searchApi.suggest(debouncedKeyword),
    enabled: dropdownOpen && debouncedKeyword.length > 0,
    staleTime: 1000 * 60,
  });

  const suggestions = useMemo(() => suggestQuery.data ?? [], [suggestQuery.data]);
  const showDropdown =
    dropdownOpen &&
    debouncedKeyword.length > 0 &&
    (suggestQuery.isFetching || suggestions.length > 0);

  const searchByText = (raw: string) => {
    const value = raw.trim();
    if (!value) {
      return;
    }
    setDropdownOpen(false);
    navigate(`/words/${encodeURIComponent(value)}`);
  };

  const goToSuggestion = (item: SearchSuggestItem) => {
    setDropdownOpen(false);
    setKeyword(item.text);
    navigate(item.type === "phrase" ? `/phrases/${item.id}` : `/words/${item.id}`);
  };

  const onSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    searchByText(keyword);
  };

  return (
    <header className="site-header">
      <div className="header-inner" ref={rootRef}>
        <Link to="/" className="site-title">
          <img src="/rootmap-logo.svg" alt="" className="site-logo" aria-hidden="true" />
          <span>My Own Rootmap</span>
        </Link>
        <form className="search-form" onSubmit={onSubmit}>
          <div className="suggest-container">
            <input
              value={keyword}
              onChange={(event) => {
                setKeyword(event.target.value);
                setDropdownOpen(true);
              }}
              onFocus={() => setDropdownOpen(true)}
              placeholder="単語・熟語を検索"
              aria-label="単語・熟語を検索"
            />
            {showDropdown && (
              <div className="suggest-dropdown">
                {suggestQuery.isFetching ? (
                  <div className="suggest-loading">検索中...</div>
                ) : (
                  suggestions.map((item) => (
                    <button
                      key={`${item.type}-${item.id}`}
                      type="button"
                      className="suggest-item"
                      onClick={() => goToSuggestion(item)}
                    >
                      <span className={`suggest-item-type suggest-item-type--${item.type}`}>
                        {item.type === "phrase" ? "熟語" : "単語"}
                      </span>
                      <span className="suggest-item-text">{item.text}</span>
                    </button>
                  ))
                )}
              </div>
            )}
          </div>
          <button type="submit">検索</button>
        </form>
      </div>
    </header>
  );
}
