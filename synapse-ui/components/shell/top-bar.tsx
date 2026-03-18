"use client";

import { useRouter, usePathname } from "next/navigation";
import { Menu, Command, User, Brain, Activity } from "lucide-react";
import clsx from "clsx";

interface TopBarProps {
  onMenuClick?: () => void;
}

// Page titles mapping
const pageTitles: Record<string, string> = {
  "/": "Memory Feed",
  "/graph": "Knowledge Graph",
  "/procedures": "Procedures",
  "/identity": "Identity",
  "/system": "System",
};

export function TopBar({ onMenuClick }: TopBarProps) {
  const pathname = usePathname();
  const title = pageTitles[pathname] || "Synapse";

  return (
    <header className="h-12 md:h-10 bg-bg-secondary/80 backdrop-blur-sm border-b border-border flex items-center justify-between px-3 md:px-4 sticky top-0 z-40">
      {/* Left: Menu + Title */}
      <div className="flex items-center gap-2 md:gap-3">
        {/* Mobile menu button */}
        <button
          onClick={onMenuClick}
          className="md:hidden p-2 -ml-2 text-text-secondary hover:text-text-primary hover:bg-bg-tertiary rounded-lg transition-colors touch-target"
          aria-label="Open menu"
        >
          <Menu size={20} />
        </button>

        {/* Logo for mobile */}
        <div className="flex md:hidden items-center gap-2">
          <div className="w-7 h-7 rounded-lg bg-gradient-to-br from-accent-primary to-layer-episodic flex items-center justify-center">
            <Brain size={14} className="text-white" />
          </div>
          <span className="text-text-primary font-semibold">{title}</span>
        </div>

        {/* Desktop title */}
        <span className="hidden md:block text-text-primary font-medium">
          {title}
        </span>
      </div>

      {/* Center: Keyboard shortcut hint (desktop only) */}
      <div className="hidden md:flex items-center gap-1.5 text-text-muted text-xs">
        <Command size={11} />
        <span className="text-[11px]">K</span>
      </div>

      {/* Right: Status + Identity */}
      <div className="flex items-center gap-2 md:gap-3">
        {/* Status indicator */}
        <div className="flex items-center gap-1.5 px-2 py-1 rounded-lg bg-bg-tertiary/50">
          <Activity size={12} className="text-success" />
          <span className="text-[11px] text-text-secondary hidden sm:inline">
            Online
          </span>
        </div>

        {/* Identity badge */}
        <div className="flex items-center gap-2 px-2 py-1.5 md:py-1 rounded-lg bg-bg-tertiary hover:bg-bg-tertiary/80 transition-colors cursor-pointer">
          <div className="w-2 h-2 rounded-full bg-layer-semantic animate-pulse" />
          <span className="text-xs text-text-secondary font-medium">
            alice
          </span>
          <User size={14} className="text-text-muted hidden sm:block" />
        </div>
      </div>
    </header>
  );
}
