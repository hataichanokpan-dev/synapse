"use client";

import { useState } from "react";
import {
  RefreshCw,
  Brain,
  Clock,
  User,
  BookOpen,
  MessageSquare,
  Zap,
  Layers,
  CheckCircle,
  Eye,
  TrendingDown,
  Trash2,
  Combine,
  Sparkles,
  Search,
  Plus,
} from "lucide-react";
import { FeedList } from "./feed-list";
import { FeedFilters, LayerFilter } from "./feed-filters";
import { useFeed } from "../../lib/hooks/use-feed";
import { FeedOfflineState, FeedSkeleton } from "@/components/ui/empty-states";
import clsx from "clsx";

export function FeedView() {
  const [filter, setFilter] = useState<LayerFilter>("ALL");
  const { entries, isConnected, isLoading, error, refresh } = useFeed();
  const [isRefreshing, setIsRefreshing] = useState(false);

  // Filter entries
  const filteredEntries =
    filter === "ALL" ? entries : entries.filter((e) => e.layer === filter);

  // Count by layer
  const layerCounts = {
    USER: entries.filter((e) => e.layer === "USER").length,
    PROCEDURAL: entries.filter((e) => e.layer === "PROCEDURAL").length,
    SEMANTIC: entries.filter((e) => e.layer === "SEMANTIC").length,
    EPISODIC: entries.filter((e) => e.layer === "EPISODIC").length,
    WORKING: entries.filter((e) => e.layer === "WORKING").length,
  };

  // Refresh entries
  const handleRefresh = async () => {
    setIsRefreshing(true);
    await refresh();
    setIsRefreshing(false);
  };

  // Determine what to show
  const showOffline = error && !isConnected && entries.length === 0;
  const showLoading = isLoading && entries.length === 0 && !error;
  const showEmpty = !isLoading && !error && entries.length === 0;

  return (
    <div className="h-full flex flex-col bg-gradient-to-b from-bg-primary via-bg-primary to-bg-secondary">
      {/* Header */}
      <div className="px-4 py-3 md:px-5 md:py-4 border-b border-border/50 bg-bg-secondary/30 backdrop-blur-sm">
        {/* Title row */}
        <div className="flex items-center justify-between mb-3">
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 md:w-8 md:h-8 rounded-xl bg-gradient-to-br from-accent-primary via-layer-episodic to-layer-semantic flex items-center justify-center shadow-lg shadow-accent-primary/20">
              <Brain size={18} className="text-white" />
            </div>
            <div>
              <h2 className="text-base md:text-sm font-semibold text-text-primary">
                Memory Feed
              </h2>
              <div className="flex items-center gap-1.5">
                <div
                  className={clsx(
                    "w-1.5 h-1.5 rounded-full",
                    isConnected
                      ? "bg-success animate-pulse"
                      : "bg-warning"
                  )}
                />
                <span className="text-[10px] text-text-muted uppercase tracking-wider">
                  {isConnected ? "Connected" : "Offline"}
                </span>
              </div>
            </div>
          </div>

          <div className="flex items-center gap-1">
            {/* Quick actions - Desktop */}
            <button className="hidden md:flex p-2 text-text-secondary hover:text-text-primary hover:bg-bg-tertiary rounded-lg transition-all">
              <Search size={16} />
            </button>
            <button className="hidden md:flex p-2 text-text-secondary hover:text-text-primary hover:bg-bg-tertiary rounded-lg transition-all">
              <Plus size={16} />
            </button>

            {/* Refresh button */}
            <button
              onClick={handleRefresh}
              disabled={isRefreshing || isLoading}
              className="p-2 text-text-secondary hover:text-text-primary hover:bg-bg-tertiary rounded-lg transition-all disabled:opacity-50 touch-target"
              title="Refresh"
            >
              <RefreshCw
                size={16}
                className={clsx((isRefreshing || isLoading) && "animate-spin")}
              />
            </button>
          </div>
        </div>

        {/* Layer Stats - Scrollable on mobile */}
        <div className="flex items-center gap-1.5 overflow-x-auto pb-1 -mx-1 px-1 scrollbar-none">
          <LayerStat
            icon={<Layers size={12} />}
            label="All"
            count={entries.length}
            active={filter === "ALL"}
            onClick={() => setFilter("ALL")}
          />
          <LayerStat
            icon={<User size={12} />}
            label="User"
            count={layerCounts.USER}
            color="violet"
            active={filter === "USER"}
            onClick={() => setFilter("USER")}
          />
          <LayerStat
            icon={<BookOpen size={12} />}
            label="Procedural"
            count={layerCounts.PROCEDURAL}
            color="amber"
            active={filter === "PROCEDURAL"}
            onClick={() => setFilter("PROCEDURAL")}
          />
          <LayerStat
            icon={<Brain size={12} />}
            label="Semantic"
            count={layerCounts.SEMANTIC}
            color="emerald"
            active={filter === "SEMANTIC"}
            onClick={() => setFilter("SEMANTIC")}
          />
          <LayerStat
            icon={<MessageSquare size={12} />}
            label="Episodic"
            count={layerCounts.EPISODIC}
            color="blue"
            active={filter === "EPISODIC"}
            onClick={() => setFilter("EPISODIC")}
          />
          <LayerStat
            icon={<Zap size={12} />}
            label="Working"
            count={layerCounts.WORKING}
            color="rose"
            active={filter === "WORKING"}
            onClick={() => setFilter("WORKING")}
          />
        </div>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-hidden">
        {showOffline ? (
          <FeedOfflineState onRetry={handleRefresh} loading={isRefreshing} />
        ) : showLoading ? (
          <FeedSkeleton />
        ) : showEmpty ? (
          <div className="h-full flex flex-col items-center justify-center p-6 md:p-8 text-center">
            <div className="w-16 h-16 md:w-20 md:h-20 rounded-2xl bg-gradient-to-br from-bg-tertiary to-bg-secondary flex items-center justify-center mb-4 shadow-xl border border-border/50">
              <Sparkles size={32} className="text-text-muted" />
            </div>
            <h3 className="text-base md:text-lg font-semibold text-text-primary mb-2">
              No memories yet
            </h3>
            <p className="text-sm text-text-muted max-w-sm mb-5 leading-relaxed">
              Start building your knowledge graph by adding memories through the command bar below.
            </p>
            <div className="flex flex-col sm:flex-row items-center gap-2">
              <div className="text-xs text-text-muted bg-bg-tertiary px-3 py-2 rounded-lg border border-border/50">
                Press <kbd className="px-1.5 py-0.5 bg-bg-secondary rounded text-text-primary font-mono mx-1">⌘K</kbd> to open command bar
              </div>
            </div>
          </div>
        ) : (
          <>
            {/* Error banner - non-blocking */}
            {error && (
              <div className="mx-3 md:mx-4 mt-3 px-3 py-2.5 bg-warning/10 border border-warning/20 rounded-xl flex items-center gap-2 text-warning text-xs">
                <div className="w-1.5 h-1.5 rounded-full bg-warning flex-shrink-0" />
                <span>{error}</span>
              </div>
            )}
            {/* Feed list */}
            <FeedList entries={filteredEntries} />
          </>
        )}
      </div>

      {/* Footer */}
      <div className="px-4 py-2.5 md:px-5 md:py-3 border-t border-border/50 bg-bg-secondary/30 text-xs text-text-muted flex items-center justify-between">
        <span className="font-medium">
          {filteredEntries.length}
          {filter !== "ALL" ? ` ${filter.toLowerCase()}` : ""} memories
        </span>
        <span className="flex items-center gap-1.5 text-text-muted">
          <Clock size={10} />
          <span className="hidden sm:inline">Auto-refresh:</span>
          <span>30s</span>
        </span>
      </div>
    </div>
  );
}

// Layer stat component
interface LayerStatProps {
  icon: React.ReactNode;
  label: string;
  count: number;
  color?: "violet" | "blue" | "emerald" | "amber" | "rose" | "gray";
  active: boolean;
  onClick: () => void;
}

function LayerStat({
  icon,
  label,
  count,
  color = "gray",
  active,
  onClick,
}: LayerStatProps) {
  const colorClasses = {
    violet: "bg-violet-500/15 text-violet-400 border-violet-500/30",
    blue: "bg-blue-500/15 text-blue-400 border-blue-500/30",
    emerald: "bg-emerald-500/15 text-emerald-400 border-emerald-500/30",
    amber: "bg-amber-500/15 text-amber-400 border-amber-500/30",
    rose: "bg-rose-500/15 text-rose-400 border-rose-500/30",
    gray: "bg-bg-tertiary text-text-secondary border-border",
  };

  return (
    <button
      onClick={onClick}
      className={clsx(
        "flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg text-[11px] font-medium transition-all border whitespace-nowrap touch-target",
        active
          ? colorClasses[color]
          : "bg-transparent text-text-muted border-transparent hover:bg-bg-tertiary/50 hover:text-text-secondary"
      )}
    >
      {icon}
      <span className="hidden sm:inline">{label}</span>
      <span
        className={clsx(
          "px-1.5 py-0.5 rounded-md text-[10px] font-mono",
          active ? "bg-black/20" : "bg-bg-tertiary"
        )}
      >
        {count}
      </span>
    </button>
  );
}
