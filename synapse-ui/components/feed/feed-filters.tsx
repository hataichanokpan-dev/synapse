"use client";

import clsx from "clsx";

export type LayerFilter =
  | "ALL"
  | "USER"
  | "PROCEDURAL"
  | "SEMANTIC"
  | "EPISODIC"
  | "WORKING";

interface FeedFiltersProps {
  active: LayerFilter;
  onChange: (filter: LayerFilter) => void;
}

const filters: { label: string; value: LayerFilter; color: string }[] = [
  { label: "ALL", value: "ALL", color: "bg-text-muted" },
  { label: "USER", value: "USER", color: "bg-layer-user" },
  { label: "PROCEDURAL", value: "PROCEDURAL", color: "bg-layer-procedural" },
  { label: "SEMANTIC", value: "SEMANTIC", color: "bg-layer-semantic" },
  { label: "EPISODIC", value: "EPISODIC", color: "bg-layer-episodic" },
  { label: "WORKING", value: "WORKING", color: "bg-layer-working" },
];

export function FeedFilters({ active, onChange }: FeedFiltersProps) {
  return (
    <div className="flex items-center gap-2">
      {filters.map((filter) => (
        <button
          key={filter.value}
          onClick={() => onChange(filter.value)}
          className={clsx(
            "flex items-center gap-1.5 px-2 py-1 rounded text-xs transition-all",
            active === filter.value
              ? "bg-bg-tertiary text-text-primary"
              : "text-text-secondary hover:text-text-primary"
          )}
        >
          <div className={clsx("w-2 h-2 rounded-full", filter.color)} />
          {filter.label}
        </button>
      ))}
    </div>
  );
}
