import { useQuery } from "@tanstack/react-query";
import { useEffect, useMemo, useRef, useState } from "react";
import type { FormEvent } from "react";
import { Link, useNavigate } from "react-router-dom";

import { wordApi } from "../lib/api";

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
    queryKey: ["word-suggest", debouncedKeyword],
    queryFn: () => wordApi.suggest(debouncedKeyword),
    enabled: dropdownOpen && debouncedKeyword.length > 0,
    staleTime: 1000 * 60,
  });

  const suggestions = useMemo(() => suggestQuery.data ?? [], [suggestQuery.data]);
  const showDropdown =
    dropdownOpen &&
    debouncedKeyword.length > 0 &&
    (suggestQuery.isFetching || suggestions.length > 0);

  const search = (raw: string) => {
    const value = raw.trim();
    if (!value) {
      return;
    }
    setDropdownOpen(false);
    navigate(`/words/${encodeURIComponent(value)}`);
  };

  const onSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    search(keyword);
  };

  return (
    <header className="site-header">
      <div className="header-inner" ref={rootRef}>
        <Link to="/" className="site-title">
          個人用 英語語源辞書
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
              placeholder="単語を検索"
              aria-label="単語を検索"
            />
            {showDropdown && (
              <div className="suggest-dropdown">
                {suggestQuery.isFetching ? (
                  <div className="suggest-loading">検索中...</div>
                ) : (
                  suggestions.map((item) => (
                    <button
                      key={item}
                      type="button"
                      className="suggest-item"
                      onClick={() => {
                        setKeyword(item);
                        search(item);
                      }}
                    >
                      {item}
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
