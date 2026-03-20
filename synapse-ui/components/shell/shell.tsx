"use client";

import { ReactNode, useState, useCallback, useEffect } from "react";
import { Sidebar } from "./sidebar";
import { TopBar } from "./top-bar";
import { CommandBar } from "./command-bar";
import { Menu, X } from "lucide-react";
import clsx from "clsx";
import { api } from "../../lib/api-client";

interface ShellProps {
  children: ReactNode;
}

export function Shell({ children }: ShellProps) {
  const [commandResult, setCommandResult] = useState<string | null>(null);
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);

  // Close mobile menu on route change
  useEffect(() => {
    const handleRouteChange = () => setMobileMenuOpen(false);
    window.addEventListener("popstate", handleRouteChange);
    return () => window.removeEventListener("popstate", handleRouteChange);
  }, []);

  // Close on escape
  useEffect(() => {
    const handleEscape = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        setMobileMenuOpen(false);
      }
    };
    window.addEventListener("keydown", handleEscape);
    return () => window.removeEventListener("keydown", handleEscape);
  }, []);

  const handleCommand = useCallback(async (command: string) => {
    const parts = command.split(" ");
    const cmd = parts[0].toLowerCase();

    if (cmd === "status") {
      try {
        const data = await api.getStatus();
        setCommandResult(JSON.stringify(data, null, 2));
      } catch {
        setCommandResult("Error: Could not fetch status");
      }
    } else if (cmd === "add") {
      const content = parts.slice(1).join(" ").trim();
      if (!content) {
        setCommandResult("Usage: add <content>");
      } else {
        try {
          const data = await api.addMemory({
            name: content.slice(0, 50),
            content,
            source: "shell",
          });
          setCommandResult(JSON.stringify(data, null, 2));
        } catch {
          setCommandResult("Error: Add failed");
        }
      }
    } else if (cmd === "search") {
      const query = parts.slice(1).join(" ").trim();
      if (!query) {
        setCommandResult("Usage: search <query>");
      } else {
        try {
          const data = await api.searchMemory(query);
          setCommandResult(JSON.stringify(data, null, 2));
        } catch {
          setCommandResult("Error: Search failed");
        }
      }
    } else {
      setCommandResult(`Unknown command: ${cmd}`);
    }

    setTimeout(() => setCommandResult(null), 5000);
  }, []);

  return (
    <div className="h-screen w-screen flex overflow-hidden bg-bg-primary">
      {/* Desktop Sidebar */}
      <div className="hidden md:block">
        <Sidebar />
      </div>

      {/* Mobile Menu Overlay */}
      {mobileMenuOpen && (
        <div className="md:hidden fixed inset-0 z-50">
          {/* Backdrop */}
          <div
            className="absolute inset-0 bg-black/60 backdrop-blur-sm"
            onClick={() => setMobileMenuOpen(false)}
          />

          {/* Drawer */}
          <div
            className={clsx(
              "absolute left-0 top-0 bottom-0 w-72 bg-bg-secondary",
              "transform transition-transform duration-300 ease-out",
              "shadow-2xl border-r border-border",
              mobileMenuOpen ? "translate-x-0" : "-translate-x-full"
            )}
          >
            {/* Close button */}
            <button
              onClick={() => setMobileMenuOpen(false)}
              className="absolute top-4 right-4 p-2 text-text-secondary hover:text-text-primary rounded-lg hover:bg-bg-tertiary transition-colors"
            >
              <X size={20} />
            </button>

            <Sidebar
              mobile
              onNavigate={() => setMobileMenuOpen(false)}
            />
          </div>
        </div>
      )}

      {/* Main content area */}
      <div className="flex-1 flex flex-col min-w-0">
        {/* Top bar */}
        <TopBar
          onMenuClick={() => setMobileMenuOpen(true)}
        />

        {/* Content */}
        <main className="flex-1 overflow-hidden relative">
          {children}

          {/* Command result overlay */}
          {commandResult && (
            <div className="absolute bottom-0 left-0 right-0 bg-bg-secondary border-t border-border p-4 max-h-64 overflow-auto animate-fade-in shadow-lg">
              <pre className="text-xs text-text-secondary whitespace-pre-wrap font-mono">
                {commandResult}
              </pre>
            </div>
          )}
        </main>

        {/* Command bar */}
        <CommandBar onCommand={handleCommand} />
      </div>
    </div>
  );
}
