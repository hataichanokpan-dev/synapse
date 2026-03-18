"use client";

import { useState, useRef, useEffect, useCallback } from "react";
import { ChevronRight, Search, Command, Sparkles } from "lucide-react";
import clsx from "clsx";

interface CommandBarProps {
  onCommand?: (command: string) => void;
}

const COMMANDS = [
  { cmd: "search", desc: "Search memories", example: "search <query>" },
  { cmd: "add", desc: "Add memory", example: "add <content>" },
  { cmd: "status", desc: "System status", example: "status" },
  { cmd: "consult", desc: "Ask for guidance", example: "consult <query>" },
  { cmd: "reflect", desc: "Get random insight", example: "reflect" },
];

export function CommandBar({ onCommand }: CommandBarProps) {
  const [input, setInput] = useState("");
  const [history, setHistory] = useState<string[]>([]);
  const [historyIndex, setHistoryIndex] = useState(-1);
  const [suggestions, setSuggestions] = useState<typeof COMMANDS>([]);
  const [focused, setFocused] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  // Load history from localStorage
  useEffect(() => {
    const saved = localStorage.getItem("synapse-command-history");
    if (saved) {
      try {
        setHistory(JSON.parse(saved));
      } catch {
        setHistory([]);
      }
    }
  }, []);

  // Save history to localStorage
  const saveHistory = useCallback((newHistory: string[]) => {
    const trimmed = newHistory.slice(-50);
    setHistory(trimmed);
    localStorage.setItem("synapse-command-history", JSON.stringify(trimmed));
  }, []);

  // Autocomplete
  useEffect(() => {
    if (input.length > 0 && focused) {
      const firstWord = input.toLowerCase().split(" ")[0];
      const matching = COMMANDS.filter((c) =>
        c.cmd.startsWith(firstWord)
      );
      setSuggestions(matching);
    } else {
      setSuggestions([]);
    }
  }, [input, focused]);

  // Global keyboard shortcut
  useEffect(() => {
    const handleGlobalKeyDown = (e: KeyboardEvent) => {
      // Cmd/Ctrl + K to focus
      if ((e.metaKey || e.ctrlKey) && e.key === "k") {
        e.preventDefault();
        inputRef.current?.focus();
      }
    };

    window.addEventListener("keydown", handleGlobalKeyDown);
    return () => window.removeEventListener("keydown", handleGlobalKeyDown);
  }, []);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!input.trim()) return;

    const cmd = input.trim();
    saveHistory([...history, cmd]);
    setHistoryIndex(-1);
    setInput("");
    setSuggestions([]);
    onCommand?.(cmd);
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "ArrowUp") {
      e.preventDefault();
      if (history.length > 0) {
        const newIndex = historyIndex < history.length - 1 ? historyIndex + 1 : historyIndex;
        setHistoryIndex(newIndex);
        setInput(history[history.length - 1 - newIndex] || "");
      }
    } else if (e.key === "ArrowDown") {
      e.preventDefault();
      if (historyIndex > 0) {
        const newIndex = historyIndex - 1;
        setHistoryIndex(newIndex);
        setInput(history[history.length - 1 - newIndex] || "");
      } else {
        setHistoryIndex(-1);
        setInput("");
      }
    } else if (e.key === "Tab" && suggestions.length > 0) {
      e.preventDefault();
      setInput(suggestions[0].cmd + " ");
      setSuggestions([]);
    } else if (e.key === "Escape") {
      setInput("");
      setSuggestions([]);
      inputRef.current?.blur();
    }
  };

  return (
    <div className="h-14 md:h-10 bg-bg-secondary/95 backdrop-blur-sm border-t border-border flex items-center px-3 md:px-4 safe-bottom">
      <div className="flex-1 relative">
        <div className="flex items-center gap-2 md:gap-2">
          {/* Prompt */}
          <div className="flex items-center gap-1.5 text-accent-primary">
            <ChevronRight size={14} className="hidden sm:block" />
            <Sparkles size={14} className="sm:hidden" />
          </div>

          {/* Input form */}
          <form onSubmit={handleSubmit} className="flex-1">
            <input
              ref={inputRef}
              type="text"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              onFocus={() => setFocused(true)}
              onBlur={() => setTimeout(() => setFocused(false), 200)}
              placeholder="search, add, consult..."
              className="w-full bg-transparent text-text-primary text-sm outline-none placeholder:text-text-muted font-mono"
              autoComplete="off"
              autoCapitalize="off"
              spellCheck={false}
            />
          </form>

          {/* Search icon */}
          <Search size={14} className="text-text-muted hidden sm:block" />

          {/* Keyboard shortcut hint */}
          <div className="hidden md:flex items-center gap-1 text-text-muted text-[11px]">
            <Command size={10} />
            <span>K</span>
          </div>
        </div>

        {/* Autocomplete suggestions */}
        {suggestions.length > 0 && (
          <div className="absolute bottom-full left-0 right-0 mb-1 bg-bg-tertiary border border-border rounded-xl overflow-hidden shadow-lg">
            {suggestions.map((suggestion, i) => (
              <button
                key={i}
                onMouseDown={() => {
                  setInput(suggestion.cmd + " ");
                  setSuggestions([]);
                  inputRef.current?.focus();
                }}
                className="w-full px-3 py-2.5 text-left hover:bg-bg-secondary transition-colors flex items-center justify-between"
              >
                <div>
                  <span className="text-sm text-text-primary font-mono">
                    {suggestion.cmd}
                  </span>
                  <span className="text-xs text-text-muted ml-2">
                    {suggestion.desc}
                  </span>
                </div>
                <span className="text-[10px] text-text-muted bg-bg-secondary px-1.5 py-0.5 rounded">
                  Tab
                </span>
              </button>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
