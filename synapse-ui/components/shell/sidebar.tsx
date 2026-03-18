"use client";

import { useRouter, usePathname } from "next/navigation";
import {
  LayoutGrid,
  GitBranch,
  ListChecks,
  User,
  Settings,
  Brain,
  Sparkles,
} from "lucide-react";
import clsx from "clsx";

const navItems = [
  { icon: LayoutGrid, label: "Feed", path: "/", description: "Memory stream" },
  { icon: GitBranch, label: "Graph", path: "/graph", description: "Knowledge graph" },
  { icon: ListChecks, label: "Procedures", path: "/procedures", description: "How-to patterns" },
  { icon: User, label: "Identity", path: "/identity", description: "User context" },
  { icon: Settings, label: "System", path: "/system", description: "System settings" },
];

interface SidebarProps {
  mobile?: boolean;
  onNavigate?: () => void;
}

export function Sidebar({ mobile = false, onNavigate }: SidebarProps) {
  const router = useRouter();
  const pathname = usePathname();

  const handleNavigate = (path: string) => {
    router.push(path);
    onNavigate?.();
  };

  // Mobile drawer version
  if (mobile) {
    return (
      <div className="h-full flex flex-col pt-16 pb-4">
        {/* Logo */}
        <div className="px-5 mb-6">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-accent-primary to-layer-episodic flex items-center justify-center shadow-lg">
              <Brain size={20} className="text-white" />
            </div>
            <div>
              <h1 className="text-lg font-semibold text-text-primary">Synapse</h1>
              <p className="text-xs text-text-muted">Memory System</p>
            </div>
          </div>
        </div>

        {/* Navigation */}
        <nav className="flex-1 px-3">
          <div className="space-y-1">
            {navItems.map((item) => {
              const isActive = pathname === item.path;
              const Icon = item.icon;

              return (
                <button
                  key={item.path}
                  onClick={() => handleNavigate(item.path)}
                  className={clsx(
                    "w-full flex items-center gap-3 px-3 py-3 rounded-xl transition-all",
                    "text-left",
                    isActive
                      ? "bg-accent-primary/15 text-accent-primary"
                      : "text-text-secondary hover:bg-bg-tertiary hover:text-text-primary"
                  )}
                >
                  <div
                    className={clsx(
                      "w-9 h-9 rounded-lg flex items-center justify-center",
                      isActive
                        ? "bg-accent-primary/20"
                        : "bg-bg-tertiary"
                    )}
                  >
                    <Icon size={18} />
                  </div>
                  <div>
                    <span className="block text-sm font-medium">{item.label}</span>
                    <span className="block text-xs text-text-muted">{item.description}</span>
                  </div>
                </button>
              );
            })}
          </div>
        </nav>

        {/* Footer */}
        <div className="px-5 pt-4 border-t border-border">
          <div className="flex items-center gap-2 text-xs text-text-muted">
            <Sparkles size={12} />
            <span>v1.0 • Five-Layer Memory</span>
          </div>
        </div>
      </div>
    );
  }

  // Desktop sidebar
  return (
    <aside className="w-16 h-full bg-bg-secondary border-r border-border flex flex-col items-center py-4">
      {/* Logo */}
      <div className="w-11 h-11 mb-6 flex items-center justify-center rounded-xl bg-gradient-to-br from-accent-primary to-layer-episodic shadow-lg shadow-accent-primary/20">
        <Brain size={20} className="text-white" />
      </div>

      {/* Navigation */}
      <nav className="flex-1 flex flex-col gap-1.5">
        {navItems.map((item) => {
          const isActive = pathname === item.path;
          const Icon = item.icon;

          return (
            <button
              key={item.path}
              onClick={() => handleNavigate(item.path)}
              className={clsx(
                "w-11 h-11 flex items-center justify-center rounded-xl transition-all relative group",
                isActive
                  ? "bg-accent-primary/15 text-accent-primary"
                  : "text-text-secondary hover:bg-bg-tertiary hover:text-text-primary"
              )}
              title={item.label}
            >
              <Icon size={20} />

              {/* Active indicator */}
              {isActive && (
                <div className="absolute left-0 w-1 h-6 bg-accent-primary rounded-r-full" />
              )}

              {/* Tooltip */}
              <div className="absolute left-full ml-3 px-2.5 py-1.5 bg-bg-tertiary rounded-lg text-xs text-text-primary whitespace-nowrap opacity-0 pointer-events-none group-hover:opacity-100 transition-opacity shadow-lg border border-border z-50">
                {item.label}
              </div>
            </button>
          );
        })}
      </nav>

      {/* Version */}
      <div className="text-[10px] text-text-muted mt-2 font-mono">v1.0</div>
    </aside>
  );
}
