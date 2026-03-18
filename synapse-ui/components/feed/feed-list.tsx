"use client";

import { useRef } from "react";
import { useVirtualizer } from "@tanstack/react-virtual";
import { FeedEntry, FeedEntryRow } from "./feed-entry";
import { Layers } from "lucide-react";

interface FeedListProps {
  entries: FeedEntry[];
}

export function FeedList({ entries }: FeedListProps) {
  const parentRef = useRef<HTMLDivElement>(null);

  const virtualizer = useVirtualizer({
    count: entries.length,
    getScrollElement: () => parentRef.current,
    estimateSize: () => 100, // Approximate height of each entry
    overscan: 5,
  });

  const items = virtualizer.getVirtualItems();

  if (entries.length === 0) {
    return (
      <div className="flex-1 flex items-center justify-center p-6 md:p-8">
        <div className="text-center">
          <div className="w-14 h-14 md:w-12 md:h-12 rounded-xl bg-bg-tertiary flex items-center justify-center mx-auto mb-3 border border-border/50">
            <Layers size={24} className="text-text-muted" />
          </div>
          <p className="text-sm text-text-secondary mb-1 font-medium">
            No memories in this layer
          </p>
          <p className="text-xs text-text-muted">
            Try selecting a different filter
          </p>
        </div>
      </div>
    );
  }

  return (
    <div
      ref={parentRef}
      className="flex-1 overflow-auto scrollbar-thin scrollbar-thumb-border scrollbar-track-transparent"
    >
      <div
        style={{
          height: `${virtualizer.getTotalSize()}px`,
          width: "100%",
          position: "relative",
        }}
      >
        {items.map((virtualRow) => (
          <div
            key={virtualRow.key}
            style={{
              position: "absolute",
              top: 0,
              left: 0,
              width: "100%",
              height: `${virtualRow.size}px`,
              transform: `translateY(${virtualRow.start}px)`,
            }}
          >
            <FeedEntryRow entry={entries[virtualRow.index]} />
          </div>
        ))}
      </div>
    </div>
  );
}
