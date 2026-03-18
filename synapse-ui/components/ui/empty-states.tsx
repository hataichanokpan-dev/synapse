"use client";

import { motion } from "framer-motion";
import {
  WifiOff,
  Database,
  GitBranch,
  ListChecks,
  User,
  Settings,
  Search,
  Inbox,
  AlertCircle,
  RefreshCw,
} from "lucide-react";
import clsx from "clsx";

interface EmptyStateProps {
  icon?: React.ReactNode;
  title: string;
  description?: string;
  action?: {
    label: string;
    onClick: () => void;
    loading?: boolean;
  };
  variant?: "default" | "offline" | "empty" | "error";
  size?: "sm" | "md" | "lg";
}

const variantStyles = {
  default: {
    icon: "text-text-muted",
    title: "text-text-secondary",
    description: "text-text-muted",
  },
  offline: {
    icon: "text-warning",
    title: "text-text-secondary",
    description: "text-text-muted",
  },
  empty: {
    icon: "text-text-muted",
    title: "text-text-secondary",
    description: "text-text-muted",
  },
  error: {
    icon: "text-error",
    title: "text-error",
    description: "text-text-muted",
  },
};

const sizeStyles = {
  sm: {
    container: "py-6",
    icon: 32,
    title: "text-xs",
    description: "text-[11px]",
  },
  md: {
    container: "py-12",
    icon: 48,
    title: "text-sm",
    description: "text-xs",
  },
  lg: {
    container: "py-20",
    icon: 64,
    title: "text-base",
    description: "text-sm",
  },
};

export function EmptyState({
  icon,
  title,
  description,
  action,
  variant = "default",
  size = "md",
}: EmptyStateProps) {
  const vStyle = variantStyles[variant];
  const sStyle = sizeStyles[size];

  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.3 }}
      className={clsx("flex flex-col items-center justify-center text-center", sStyle.container)}
    >
      <div className={clsx("mb-3 opacity-60", vStyle.icon)}>
        {icon}
      </div>
      <h3 className={clsx("font-medium mb-1", vStyle.title, sStyle.title)}>
        {title}
      </h3>
      {description && (
        <p className={clsx("max-w-xs", vStyle.description, sStyle.description)}>
          {description}
        </p>
      )}
      {action && (
        <button
          onClick={action.onClick}
          disabled={action.loading}
          className={clsx(
            "mt-4 px-4 py-1.5 text-xs rounded-md flex items-center gap-2 transition-all",
            variant === "error"
              ? "bg-error/20 text-error hover:bg-error/30"
              : "bg-accent/20 text-accent hover:bg-accent/30",
            action.loading && "opacity-50"
          )}
        >
          {action.loading ? (
            <RefreshCw size={14} className="animate-spin" />
          ) : (
            <RefreshCw size={14} />
          )}
          <span>{action.label}</span>
        </button>
      )}
    </motion.div>
  );
}

// Pre-built empty states for common use cases
export function OfflineState({ onRetry, loading }: { onRetry?: () => void; loading?: boolean }) {
  return (
    <EmptyState
      icon={<WifiOff size={48} />}
      title="Unable to connect"
      description="The memory server is not responding. Please check if the backend is running."
      variant="offline"
      action={onRetry ? { label: "Retry connection", onClick: onRetry, loading } : undefined}
    />
  );
}

export function NoDataState({
  icon,
  title,
  description,
  action
}: {
  icon?: React.ReactNode;
  title: string;
  description?: string;
  action?: { label: string; onClick: () => void };
}) {
  return (
    <EmptyState
      icon={icon || <Inbox size={48} />}
      title={title}
      description={description}
      variant="empty"
      action={action}
    />
  );
}

export function ErrorState({
  message,
  onRetry,
  loading
}: {
  message: string;
  onRetry?: () => void;
  loading?: boolean;
}) {
  return (
    <EmptyState
      icon={<AlertCircle size={48} />}
      title="Something went wrong"
      description={message}
      variant="error"
      action={onRetry ? { label: "Try again", onClick: onRetry, loading } : undefined}
    />
  );
}

// Skeleton components for loading states
export function Skeleton({ className }: { className?: string }) {
  return (
    <div
      className={clsx(
        "animate-pulse bg-gradient-to-r from-bg-tertiary via-bg-secondary to-bg-tertiary bg-[length:200%_100%] rounded",
        className
      )}
    />
  );
}

export function FeedSkeleton() {
  return (
    <div className="p-4 space-y-3">
      {[...Array(5)].map((_, i) => (
        <div key={i} className="p-3 bg-bg-secondary rounded-lg space-y-2">
          <div className="flex items-center gap-2">
            <Skeleton className="w-16 h-4" />
            <Skeleton className="w-20 h-4" />
          </div>
          <Skeleton className="w-full h-3" />
          <Skeleton className="w-3/4 h-3" />
        </div>
      ))}
    </div>
  );
}

export function GraphSkeleton() {
  return (
    <div className="flex-1 flex items-center justify-center">
      <div className="relative">
        {/* Animated nodes */}
        {[...Array(6)].map((_, i) => (
          <motion.div
            key={i}
            className="absolute w-4 h-4 rounded-full bg-accent/30"
            style={{
              left: `${Math.cos((i * Math.PI * 2) / 6) * 60}px`,
              top: `${Math.sin((i * Math.PI * 2) / 6) * 60}px`,
            }}
            animate={{
              scale: [1, 1.2, 1],
              opacity: [0.3, 0.6, 0.3],
            }}
            transition={{
              duration: 2,
              repeat: Infinity,
              delay: i * 0.2,
            }}
          />
        ))}
        {/* Center node */}
        <motion.div
          className="w-6 h-6 rounded-full bg-accent/50"
          animate={{ scale: [1, 1.3, 1] }}
          transition={{ duration: 2, repeat: Infinity }}
        />
      </div>
    </div>
  );
}

export function TableSkeleton({ rows = 5 }: { rows?: number }) {
  return (
    <div className="divide-y divide-border">
      {[...Array(rows)].map((_, i) => (
        <div key={i} className="flex items-center gap-4 px-4 py-3">
          <Skeleton className="w-8 h-8 rounded" />
          <div className="flex-1 space-y-2">
            <Skeleton className="w-1/3 h-3" />
            <Skeleton className="w-1/2 h-2" />
          </div>
          <Skeleton className="w-16 h-6 rounded" />
        </div>
      ))}
    </div>
  );
}

export function FormSkeleton() {
  return (
    <div className="p-4 space-y-4">
      {[...Array(4)].map((_, i) => (
        <div key={i} className="space-y-2">
          <Skeleton className="w-20 h-3" />
          <Skeleton className="w-full h-8 rounded-md" />
        </div>
      ))}
      <Skeleton className="w-24 h-8 rounded-md" />
    </div>
  );
}

// Page-specific offline states
export function FeedOfflineState({ onRetry, loading }: { onRetry?: () => void; loading?: boolean }) {
  return (
    <div className="flex-1 flex flex-col items-center justify-center p-8">
      <motion.div
        initial={{ opacity: 0, scale: 0.9 }}
        animate={{ opacity: 1, scale: 1 }}
        className="text-center"
      >
        <div className="relative mb-4">
          <Database size={48} className="mx-auto text-text-muted opacity-40" />
          <motion.div
            className="absolute -top-1 -right-1 w-4 h-4 bg-warning rounded-full"
            animate={{ scale: [1, 1.2, 1] }}
            transition={{ duration: 1.5, repeat: Infinity }}
          />
        </div>
        <h3 className="text-sm font-medium text-text-secondary mb-1">
          Memory Feed Unavailable
        </h3>
        <p className="text-xs text-text-muted max-w-xs mx-auto mb-4">
          Connect to the Synapse server to view your memory feed and live updates.
        </p>
        {onRetry && (
          <button
            onClick={onRetry}
            disabled={loading}
            className="px-4 py-1.5 text-xs bg-accent/20 text-accent rounded-md
              hover:bg-accent/30 transition-colors flex items-center gap-2 mx-auto
              disabled:opacity-50"
          >
            <RefreshCw size={14} className={clsx(loading && "animate-spin")} />
            <span>Connect</span>
          </button>
        )}
      </motion.div>
    </div>
  );
}

export function GraphOfflineState({ onRetry, loading }: { onRetry?: () => void; loading?: boolean }) {
  return (
    <div className="flex-1 flex flex-col items-center justify-center p-8">
      <motion.div
        initial={{ opacity: 0, scale: 0.9 }}
        animate={{ opacity: 1, scale: 1 }}
        className="text-center"
      >
        <div className="relative mb-4">
          <GitBranch size={48} className="mx-auto text-text-muted opacity-40" />
          <motion.div
            className="absolute -top-1 -right-1 w-4 h-4 bg-warning rounded-full"
            animate={{ scale: [1, 1.2, 1] }}
            transition={{ duration: 1.5, repeat: Infinity }}
          />
        </div>
        <h3 className="text-sm font-medium text-text-secondary mb-1">
          Knowledge Graph Unavailable
        </h3>
        <p className="text-xs text-text-muted max-w-xs mx-auto mb-4">
          Connect to the Synapse server to explore your knowledge graph and entity relationships.
        </p>
        {onRetry && (
          <button
            onClick={onRetry}
            disabled={loading}
            className="px-4 py-1.5 text-xs bg-accent/20 text-accent rounded-md
              hover:bg-accent/30 transition-colors flex items-center gap-2 mx-auto
              disabled:opacity-50"
          >
            <RefreshCw size={14} className={clsx(loading && "animate-spin")} />
            <span>Connect</span>
          </button>
        )}
      </motion.div>
    </div>
  );
}

export function ProceduresOfflineState({ onRetry, loading }: { onRetry?: () => void; loading?: boolean }) {
  return (
    <div className="flex-1 flex flex-col items-center justify-center p-8">
      <motion.div
        initial={{ opacity: 0, scale: 0.9 }}
        animate={{ opacity: 1, scale: 1 }}
        className="text-center"
      >
        <div className="relative mb-4">
          <ListChecks size={48} className="mx-auto text-text-muted opacity-40" />
          <motion.div
            className="absolute -top-1 -right-1 w-4 h-4 bg-warning rounded-full"
            animate={{ scale: [1, 1.2, 1] }}
            transition={{ duration: 1.5, repeat: Infinity }}
          />
        </div>
        <h3 className="text-sm font-medium text-text-secondary mb-1">
          Procedures Unavailable
        </h3>
        <p className="text-xs text-text-muted max-w-xs mx-auto mb-4">
          Connect to the Synapse server to manage your saved procedures and workflows.
        </p>
        {onRetry && (
          <button
            onClick={onRetry}
            disabled={loading}
            className="px-4 py-1.5 text-xs bg-accent/20 text-accent rounded-md
              hover:bg-accent/30 transition-colors flex items-center gap-2 mx-auto
              disabled:opacity-50"
          >
            <RefreshCw size={14} className={clsx(loading && "animate-spin")} />
            <span>Connect</span>
          </button>
        )}
      </motion.div>
    </div>
  );
}

export function IdentityOfflineState({ onRetry, loading }: { onRetry?: () => void; loading?: boolean }) {
  return (
    <div className="flex-1 flex flex-col items-center justify-center p-8">
      <motion.div
        initial={{ opacity: 0, scale: 0.9 }}
        animate={{ opacity: 1, scale: 1 }}
        className="text-center"
      >
        <div className="relative mb-4">
          <User size={48} className="mx-auto text-text-muted opacity-40" />
          <motion.div
            className="absolute -top-1 -right-1 w-4 h-4 bg-warning rounded-full"
            animate={{ scale: [1, 1.2, 1] }}
            transition={{ duration: 1.5, repeat: Infinity }}
          />
        </div>
        <h3 className="text-sm font-medium text-text-secondary mb-1">
          Identity Unavailable
        </h3>
        <p className="text-xs text-text-muted max-w-xs mx-auto mb-4">
          Connect to the Synapse server to manage your identity and preferences.
        </p>
        {onRetry && (
          <button
            onClick={onRetry}
            disabled={loading}
            className="px-4 py-1.5 text-xs bg-accent/20 text-accent rounded-md
              hover:bg-accent/30 transition-colors flex items-center gap-2 mx-auto
              disabled:opacity-50"
          >
            <RefreshCw size={14} className={clsx(loading && "animate-spin")} />
            <span>Connect</span>
          </button>
        )}
      </motion.div>
    </div>
  );
}

export function SystemOfflineState({ onRetry, loading }: { onRetry?: () => void; loading?: boolean }) {
  return (
    <div className="flex-1 flex flex-col items-center justify-center p-8">
      <motion.div
        initial={{ opacity: 0, scale: 0.9 }}
        animate={{ opacity: 1, scale: 1 }}
        className="text-center"
      >
        <div className="relative mb-4">
          <Settings size={48} className="mx-auto text-text-muted opacity-40" />
          <motion.div
            className="absolute -top-1 -right-1 w-4 h-4 bg-warning rounded-full"
            animate={{ scale: [1, 1.2, 1] }}
            transition={{ duration: 1.5, repeat: Infinity }}
          />
        </div>
        <h3 className="text-sm font-medium text-text-secondary mb-1">
          System Status Unavailable
        </h3>
        <p className="text-xs text-text-muted max-w-xs mx-auto mb-4">
          Connect to the Synapse server to view system health, memory stats, and configuration.
        </p>
        {onRetry && (
          <button
            onClick={onRetry}
            disabled={loading}
            className="px-4 py-1.5 text-xs bg-accent/20 text-accent rounded-md
              hover:bg-accent/30 transition-colors flex items-center gap-2 mx-auto
              disabled:opacity-50"
          >
            <RefreshCw size={14} className={clsx(loading && "animate-spin")} />
            <span>Connect</span>
          </button>
        )}
      </motion.div>
    </div>
  );
}
