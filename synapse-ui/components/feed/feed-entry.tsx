"use client";

import clsx from "clsx";
import {
  Brain,
  User,
  BookOpen,
  MessageSquare,
  Zap,
  CheckCircle,
  Eye,
  TrendingDown,
  Trash2,
  Combine,
  Clock,
  Tag,
  MoreVertical,
  ExternalLink,
  Copy,
} from "lucide-react";
import { useState } from "react";
import { formatDate, formatTimestamp } from "@/lib/utils";

export interface FeedEntry {
  id: string;
  timestamp: string;
  layer: "USER" | "PROCEDURAL" | "SEMANTIC" | "EPISODIC" | "WORKING";
  action: "ADD" | "ACCESS" | "DECAY" | "DELETE" | "CONSOLIDATE";
  summary: string;
  title?: string;
  source?: string;
  metadata?: {
    topics?: string[];
    accessCount?: number;
    [key: string]: unknown;
  };
}

interface FeedEntryRowProps {
  entry: FeedEntry;
}

const layerConfig = {
  USER: {
    icon: User,
    gradient: "from-violet-500 to-purple-600",
    bg: "bg-violet-500/10",
    border: "border-violet-500/20",
    text: "text-violet-400",
    badge: "bg-violet-500/15 text-violet-400 border-violet-500/30",
    label: "User Model",
  },
  PROCEDURAL: {
    icon: BookOpen,
    gradient: "from-amber-500 to-orange-600",
    bg: "bg-amber-500/10",
    border: "border-amber-500/20",
    text: "text-amber-400",
    badge: "bg-amber-500/15 text-amber-400 border-amber-500/30",
    label: "Procedural",
  },
  SEMANTIC: {
    icon: Brain,
    gradient: "from-emerald-500 to-teal-600",
    bg: "bg-emerald-500/10",
    border: "border-emerald-500/20",
    text: "text-emerald-400",
    badge: "bg-emerald-500/15 text-emerald-400 border-emerald-500/30",
    label: "Semantic",
  },
  EPISODIC: {
    icon: MessageSquare,
    gradient: "from-blue-500 to-indigo-600",
    bg: "bg-blue-500/10",
    border: "border-blue-500/20",
    text: "text-blue-400",
    badge: "bg-blue-500/15 text-blue-400 border-blue-500/30",
    label: "Episodic",
  },
  WORKING: {
    icon: Zap,
    gradient: "from-rose-500 to-pink-600",
    bg: "bg-rose-500/10",
    border: "border-rose-500/20",
    text: "text-rose-400",
    badge: "bg-rose-500/15 text-rose-400 border-rose-500/30",
    label: "Working",
  },
};

const actionConfig = {
  ADD: {
    icon: CheckCircle,
    color: "text-emerald-400",
    bg: "bg-emerald-500/10",
    label: "Added",
  },
  ACCESS: {
    icon: Eye,
    color: "text-blue-400",
    bg: "bg-blue-500/10",
    label: "Accessed",
  },
  DECAY: {
    icon: TrendingDown,
    color: "text-amber-400",
    bg: "bg-amber-500/10",
    label: "Decayed",
  },
  DELETE: {
    icon: Trash2,
    color: "text-rose-400",
    bg: "bg-rose-500/10",
    label: "Deleted",
  },
  CONSOLIDATE: {
    icon: Combine,
    color: "text-violet-400",
    bg: "bg-violet-500/10",
    label: "Consolidated",
  },
};

export function FeedEntryRow({ entry }: FeedEntryRowProps) {
  // API returns lowercase, convert to uppercase for config lookup
  const layerKey = entry.layer?.toUpperCase() as keyof typeof layerConfig;
  const actionKey = entry.action?.toUpperCase() as keyof typeof actionConfig;
  const layer = layerConfig[layerKey] || layerConfig.SEMANTIC; // fallback to SEMANTIC
  const action = actionConfig[actionKey] || actionConfig.ADD; // fallback to ADD
  const LayerIcon = layer.icon;
  const ActionIcon = action.icon;
  const [showActions, setShowActions] = useState(false);
  const timestampDate = formatDate(entry.timestamp);
  const timestampTime = formatTimestamp(entry.timestamp);
  const localizedTimestamp = `${timestampDate} ${timestampTime}`;

  return (
    <div
      className="group px-3 py-3 md:px-4 md:py-3.5 border-b border-border/30 hover:bg-bg-hover transition-all duration-200"
      onMouseLeave={() => setShowActions(false)}
    >
      <div className="flex items-start gap-3">
        {/* Layer indicator */}
        <div
          className={clsx(
            "w-10 h-10 md:w-9 md:h-9 rounded-xl flex items-center justify-center shrink-0",
            "bg-gradient-to-br",
            layer.gradient,
            "shadow-lg"
          )}
        >
          <LayerIcon size={18} className="text-white" />
        </div>

        {/* Content */}
        <div className="flex-1 min-w-0">
          {/* Header row */}
          <div className="flex items-start justify-between gap-2 mb-1.5">
            <div className="flex items-center gap-2 flex-wrap min-w-0">
              {/* Title */}
              {entry.title && (
                <span className="text-sm font-semibold text-text-primary truncate max-w-[200px] md:max-w-none">
                  {entry.title}
                </span>
              )}

              {/* Layer badge */}
              <span
                className={clsx(
                  "px-2 py-0.5 rounded-md text-[10px] font-medium shrink-0 border",
                  layer.badge
                )}
              >
                {layer.label}
              </span>
            </div>

            {/* Action menu - visible on hover */}
            <div className="relative shrink-0">
              <button
                onClick={() => setShowActions(!showActions)}
                className="p-1.5 text-text-muted hover:text-text-secondary hover:bg-bg-tertiary rounded-lg opacity-0 group-hover:opacity-100 transition-all"
              >
                <MoreVertical size={14} />
              </button>

              {showActions && (
                <div className="absolute right-0 top-full mt-1 w-36 bg-bg-tertiary border border-border rounded-xl shadow-xl overflow-hidden z-10">
                  <button className="w-full px-3 py-2 text-left text-xs text-text-secondary hover:bg-bg-secondary flex items-center gap-2">
                    <ExternalLink size={12} />
                    View details
                  </button>
                  <button className="w-full px-3 py-2 text-left text-xs text-text-secondary hover:bg-bg-secondary flex items-center gap-2">
                    <Copy size={12} />
                    Copy content
                  </button>
                </div>
              )}
            </div>
          </div>

          {/* Summary */}
          <p className="text-sm text-text-secondary leading-relaxed line-clamp-2 md:line-clamp-3 mb-2.5">
            {entry.summary}
          </p>

          {/* Footer row */}
          <div className="flex items-center gap-3 md:gap-4 text-[11px] text-text-muted flex-wrap">
            {/* Action indicator */}
            <div
              className={clsx(
                "flex items-center gap-1.5 px-2 py-1 rounded-lg shrink-0",
                action.bg,
                action.color
              )}
            >
              <ActionIcon size={11} />
              <span className="font-medium">{action.label}</span>
            </div>

            {/* Timestamp */}
            <span className="flex items-center gap-1.5">
              <Clock size={11} />
              <span className="font-mono" title={localizedTimestamp}>
                {timestampTime}
              </span>
              <span className="hidden md:inline">{timestampDate}</span>
            </span>

            {/* Topics - Desktop only */}
            {entry.metadata?.topics && entry.metadata.topics.length > 0 && (
              <span className="hidden md:flex items-center gap-1.5">
                <Tag size={11} />
                {entry.metadata.topics.slice(0, 3).map((topic, i) => (
                  <span
                    key={i}
                    className="px-1.5 py-0.5 bg-bg-tertiary rounded-md text-[10px] font-mono"
                  >
                    {topic}
                  </span>
                ))}
                {entry.metadata.topics.length > 3 && (
                  <span className="text-text-muted">
                    +{entry.metadata.topics.length - 3}
                  </span>
                )}
              </span>
            )}

            {/* Access count */}
            {entry.metadata?.accessCount && entry.metadata.accessCount > 1 && (
              <span className="flex items-center gap-1.5">
                <Eye size={11} />
                <span>{entry.metadata.accessCount}×</span>
              </span>
            )}
          </div>

          {/* Topics - Mobile only */}
          {entry.metadata?.topics && entry.metadata.topics.length > 0 && (
            <div className="flex md:hidden items-center gap-1.5 mt-2 flex-wrap">
              <Tag size={10} className="text-text-muted" />
              {entry.metadata.topics.slice(0, 2).map((topic, i) => (
                <span
                  key={i}
                  className="px-1.5 py-0.5 bg-bg-tertiary rounded-md text-[10px] font-mono"
                >
                  {topic}
                </span>
              ))}
              {entry.metadata.topics.length > 2 && (
                <span className="text-[10px] text-text-muted">
                  +{entry.metadata.topics.length - 2}
                </span>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
