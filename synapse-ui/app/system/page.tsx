"use client";

import { useState, useEffect, useCallback } from "react";
import {
  RefreshCw,
  Loader2,
  AlertCircle,
  CheckCircle,
  Database,
  Server,
  HardDrive,
} from "lucide-react";
import { api } from "../../lib/api-client";
import type { StatusResponse, StatsResponse } from "../../lib/types/system";
import clsx from "clsx";

export default function SystemPage() {
  const [status, setStatus] = useState<StatusResponse | null>(null);
  const [stats, setStats] = useState<StatsResponse | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Load system data
  const loadData = useCallback(async () => {
    setError(null);

    try {
      const [statusData, statsData] = await Promise.all([
        api.getStatus(),
        api.getStats(),
      ]);
      setStatus(statusData);
      setStats(statsData);
    } catch (err) {
      const message = err instanceof Error ? err.message : "Failed to load system data";
      setError(message);
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    loadData();
  }, [loadData]);

  // Refresh
  const handleRefresh = async () => {
    setIsRefreshing(true);
    await loadData();
    setIsRefreshing(false);
  };

  // Format MB
  const formatMB = (mb: number): string => {
    if (mb < 1) return `${(mb * 1024).toFixed(0)} KB`;
    if (mb < 1024) return `${mb.toFixed(1)} MB`;
    return `${(mb / 1024).toFixed(1)} GB`;
  };

  // Status badge color
  const getStatusColor = (statusStr: string) => {
    switch (statusStr) {
      case "healthy":
        return "text-success bg-success/20";
      case "degraded":
        return "text-warning bg-warning/20";
      case "unhealthy":
        return "text-error bg-error/20";
      default:
        return "text-text-muted bg-bg-tertiary";
    }
  };

  if (isLoading) {
    return (
      <div className="h-full flex items-center justify-center">
        <div className="flex items-center gap-2 text-text-muted">
          <Loader2 size={24} className="animate-spin" />
          <span className="text-sm">Loading system status...</span>
        </div>
      </div>
    );
  }

  return (
    <div className="h-full flex flex-col">
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3 border-b border-border">
        <div className="flex items-center gap-3">
          <h2 className="text-sm font-medium text-text-primary">System</h2>
          {status && (
            <span
              className={clsx(
                "px-2 py-0.5 text-[10px] rounded-full font-medium",
                getStatusColor(status.status)
              )}
            >
              {status.status.toUpperCase()}
            </span>
          )}
        </div>

        <button
          onClick={handleRefresh}
          disabled={isRefreshing}
          className="p-1.5 text-text-secondary hover:text-text-primary transition-colors
            disabled:opacity-50"
        >
          <RefreshCw
            size={14}
            className={clsx(isRefreshing && "animate-spin")}
          />
        </button>
      </div>

      {/* Error banner */}
      {error && (
        <div className="px-4 py-2 bg-error/10 border-b border-error/20 flex items-center gap-2 text-error text-xs">
          <AlertCircle size={14} />
          <span>{error}</span>
        </div>
      )}

      {/* Content */}
      <div className="flex-1 overflow-y-auto p-4 space-y-6">
        {/* Components */}
        {status && (
          <section className="bg-bg-secondary rounded-lg p-4">
            <h3 className="text-sm font-medium text-text-primary mb-4 flex items-center gap-2">
              <Server size={16} />
              <span>Components</span>
            </h3>

            <div className="space-y-2">
              {status.components.map((component) => (
                <div
                  key={component.name}
                  className="flex items-center justify-between p-2 bg-bg-tertiary rounded"
                >
                  <div className="flex items-center gap-2">
                    <div
                      className={clsx(
                        "w-2 h-2 rounded-full",
                        component.status === "healthy"
                          ? "bg-success"
                          : component.status === "degraded"
                          ? "bg-warning"
                          : "bg-error"
                      )}
                    />
                    <span className="text-xs text-text-primary">{component.name}</span>
                  </div>

                  <span
                    className={clsx(
                      "px-1.5 py-0.5 text-[10px] rounded",
                      getStatusColor(component.status)
                    )}
                  >
                    {component.status}
                  </span>
                </div>
              ))}
            </div>
          </section>
        )}

        {/* Memory Stats */}
        {stats && (
          <section className="bg-bg-secondary rounded-lg p-4">
            <h3 className="text-sm font-medium text-text-primary mb-4 flex items-center gap-2">
              <Database size={16} />
              <span>Memory Stats</span>
            </h3>

            <div className="grid grid-cols-2 gap-4">
              <div className="p-3 bg-bg-tertiary rounded">
                <div className="text-[10px] text-text-muted mb-1">Entities</div>
                <div className="text-lg font-medium text-text-primary">
                  {stats.memory.entities.toLocaleString()}
                </div>
              </div>

              <div className="p-3 bg-bg-tertiary rounded">
                <div className="text-[10px] text-text-muted mb-1">Edges</div>
                <div className="text-lg font-medium text-text-primary">
                  {stats.memory.edges.toLocaleString()}
                </div>
              </div>

              <div className="p-3 bg-bg-tertiary rounded">
                <div className="text-[10px] text-text-muted mb-1">Episodes</div>
                <div className="text-lg font-medium text-text-primary">
                  {stats.memory.episodes.toLocaleString()}
                </div>
              </div>

              <div className="p-3 bg-bg-tertiary rounded">
                <div className="text-[10px] text-text-muted mb-1">Procedures</div>
                <div className="text-lg font-medium text-text-primary">
                  {stats.memory.procedures.toLocaleString()}
                </div>
              </div>

              <div className="p-3 bg-bg-tertiary rounded">
                <div className="text-[10px] text-text-muted mb-1">Episodic Items</div>
                <div className="text-lg font-medium text-text-primary">
                  {stats.memory.episodic_items.toLocaleString()}
                </div>
              </div>

              <div className="p-3 bg-bg-tertiary rounded">
                <div className="text-[10px] text-text-muted mb-1">Working Keys</div>
                <div className="text-lg font-medium text-text-primary">
                  {stats.memory.working_keys.toLocaleString()}
                </div>
              </div>
            </div>
          </section>
        )}

        {/* Storage Stats */}
        {stats && (
          <section className="bg-bg-secondary rounded-lg p-4">
            <h3 className="text-sm font-medium text-text-primary mb-4 flex items-center gap-2">
              <HardDrive size={16} />
              <span>Storage</span>
            </h3>

            <div className="space-y-3">
              <div className="flex items-center justify-between p-2 bg-bg-tertiary rounded">
                <span className="text-xs text-text-secondary">FalkorDB</span>
                <span className="text-xs text-text-primary font-mono">
                  {formatMB(stats.storage.falkordb_mb)}
                </span>
              </div>

              <div className="flex items-center justify-between p-2 bg-bg-tertiary rounded">
                <span className="text-xs text-text-secondary">Qdrant</span>
                <span className="text-xs text-text-primary font-mono">
                  {formatMB(stats.storage.qdrant_mb)}
                </span>
              </div>

              <div className="flex items-center justify-between p-2 bg-bg-tertiary rounded">
                <span className="text-xs text-text-secondary">SQLite</span>
                <span className="text-xs text-text-primary font-mono">
                  {formatMB(stats.storage.sqlite_mb)}
                </span>
              </div>
            </div>
          </section>
        )}

        {/* Message */}
        {status?.message && (
          <section className="bg-bg-secondary rounded-lg p-4">
            <h3 className="text-sm font-medium text-text-primary mb-2">Status</h3>
            <p className="text-xs text-text-secondary">{status.message}</p>
          </section>
        )}
      </div>
    </div>
  );
}
