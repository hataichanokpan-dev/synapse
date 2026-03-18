"use client";

import { useState, useEffect, useCallback } from "react";
import {
  Search,
  Plus,
  Trash2,
  CheckCircle,
  AlertCircle,
  Loader2,
  ChevronDown,
  ChevronRight,
} from "lucide-react";
import { api, Procedure, AddProcedureRequest } from "../../lib/api-client";
import { ProceduresOfflineState, TableSkeleton } from "@/components/ui/empty-states";
import clsx from "clsx";

export function ProceduresView() {
  const [procedures, setProcedures] = useState<Procedure[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState("");
  const [expandedTrigger, setExpandedTrigger] = useState<string | null>(null);
  const [isAddingNew, setIsAddingNew] = useState(false);
  const [newProcedure, setNewProcedure] = useState<AddProcedureRequest>({
    trigger: "",
    steps: [""],
    topics: [],
  });

  // Load procedures
  const loadProcedures = useCallback(async () => {
    setIsLoading(true);
    setError(null);

    try {
      const data = await api.getProcedures();
      // Handle both { items: [] } and [] response formats
      setProcedures(Array.isArray(data) ? data : (data.items || []));
    } catch (err) {
      const message = err instanceof Error ? err.message : "Failed to load procedures";
      setError(message);
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    loadProcedures();
  }, [loadProcedures]);

  // Determine states
  const showOffline = error && procedures.length === 0;
  const showLoading = isLoading && procedures.length === 0 && !error;
  const showEmpty = !isLoading && !error && procedures.length === 0;

  // Filter by search
  const filteredProcedures = procedures.filter((p) =>
    p.trigger.toLowerCase().includes(searchQuery.toLowerCase())
  );

  // Toggle expansion
  const toggleExpand = (trigger: string) => {
    setExpandedTrigger((current) =>
      current === trigger ? null : trigger
    );
  };

  // Add new procedure
  const handleAddProcedure = async () => {
    if (!newProcedure.trigger.trim()) return;

    try {
      await api.addProcedure({
        trigger: newProcedure.trigger.trim(),
        steps: newProcedure.steps.filter((s) => s.trim()),
        topics: newProcedure.topics,
      });
      setNewProcedure({ trigger: "", steps: [""], topics: [] });
      setIsAddingNew(false);
      loadProcedures();
    } catch (err) {
      const message = err instanceof Error ? err.message : "Failed to add procedure";
      setError(message);
    }
  };

  // Delete procedure
  const handleDeleteProcedure = async (trigger: string) => {
    if (!confirm(`Delete procedure "${trigger}"?`)) return;

    try {
      await api.deleteProcedure(trigger);
      loadProcedures();
    } catch (err) {
      const message = err instanceof Error ? err.message : "Failed to delete procedure";
      setError(message);
    }
  };

  // Record success
  const handleRecordSuccess = async (trigger: string) => {
    try {
      await api.recordProcedureSuccess(trigger);
      loadProcedures();
    } catch (err) {
      const message = err instanceof Error ? err.message : "Failed to record success";
      setError(message);
    }
  };

  // Add step input
  const addStep = () => {
    setNewProcedure((prev) => ({
      ...prev,
      steps: [...prev.steps, ""],
    }));
  };

  // Update step
  const updateStep = (index: number, value: string) => {
    setNewProcedure((prev) => ({
      ...prev,
      steps: prev.steps.map((s, i) => (i === index ? value : s)),
    }));
  };

  // Remove step
  const removeStep = (index: number) => {
    setNewProcedure((prev) => ({
      ...prev,
      steps: prev.steps.filter((_, i) => i !== index),
    }));
  };

  return (
    <div className="h-full flex flex-col">
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3 border-b border-border">
        <div className="flex items-center gap-3">
          <h2 className="text-sm font-medium text-text-primary">Procedures</h2>
          <span className="text-[11px] text-text-muted">
            {filteredProcedures.length} total
          </span>
        </div>

        <div className="flex items-center gap-3">
          {/* Search */}
          <div className="relative">
            <Search
              size={14}
              className="absolute left-2.5 top-1/2 -translate-y-1/2 text-text-muted"
            />
            <input
              type="text"
              placeholder="Search by trigger..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="pl-8 pr-3 py-1.5 text-xs bg-bg-secondary border border-border rounded-md
                text-text-primary placeholder:text-text-muted
                focus:outline-none focus:ring-1 focus:ring-accent"
            />
          </div>

          {/* Add button */}
          <button
            onClick={() => setIsAddingNew(!isAddingNew)}
            className={clsx(
              "px-3 py-1.5 text-xs rounded-md flex items-center gap-1.5 transition-colors",
              isAddingNew
                ? "bg-error/20 text-error"
                : "bg-accent/20 text-accent hover:bg-accent/30"
            )}
          >
            {isAddingNew ? (
              <>
                <span>Cancel</span>
              </>
            ) : (
              <>
                <Plus size={14} />
                <span>Add</span>
              </>
            )}
          </button>
        </div>
      </div>

      {/* Error banner */}
      {error && (
        <div className="px-4 py-2 bg-error/10 border-b border-error/20 flex items-center gap-2 text-error text-xs">
          <AlertCircle size={14} />
          <span>{error}</span>
        </div>
      )}

      {/* Add new procedure form */}
      {isAddingNew && (
        <div className="p-4 border-b border-border bg-bg-secondary">
          <h3 className="text-sm font-medium text-text-primary mb-3">
            New Procedure
          </h3>

          <div className="space-y-3">
            {/* Trigger */}
            <div>
              <label className="text-[11px] text-text-muted mb-1 block">
                Trigger
              </label>
              <input
                type="text"
                placeholder="e.g., deploy to production"
                value={newProcedure.trigger}
                onChange={(e) =>
                  setNewProcedure((prev) => ({ ...prev, trigger: e.target.value }))
                }
                className="w-full px-3 py-1.5 text-xs bg-bg-primary border border-border rounded-md
                  text-text-primary placeholder:text-text-muted
                  focus:outline-none focus:ring-1 focus:ring-accent"
              />
            </div>

            {/* Steps */}
            <div>
              <label className="text-[11px] text-text-muted mb-1 block">
                Steps
              </label>
              <div className="space-y-2">
                {newProcedure.steps.map((step, i) => (
                  <div key={i} className="flex items-center gap-2">
                    <span className="text-[10px] text-text-muted w-4">{i + 1}.</span>
                    <input
                      type="text"
                      placeholder="Step description"
                      value={step}
                      onChange={(e) => updateStep(i, e.target.value)}
                      className="flex-1 px-3 py-1.5 text-xs bg-bg-primary border border-border rounded-md
                        text-text-primary placeholder:text-text-muted
                        focus:outline-none focus:ring-1 focus:ring-accent"
                    />
                    {newProcedure.steps.length > 1 && (
                      <button
                        onClick={() => removeStep(i)}
                        className="p-1 text-text-muted hover:text-error transition-colors"
                      >
                        <Trash2 size={14} />
                      </button>
                    )}
                  </div>
                ))}
                <button
                  onClick={addStep}
                  className="text-[11px] text-accent hover:text-accent/80 transition-colors"
                >
                  + Add step
                </button>
              </div>
            </div>

            {/* Topics */}
            <div>
              <label className="text-[11px] text-text-muted mb-1 block">
                Topics (comma-separated)
              </label>
              <input
                type="text"
                placeholder="e.g., deployment, production, ci/cd"
                value={(newProcedure.topics || []).join(", ")}
                onChange={(e) =>
                  setNewProcedure((prev) => ({
                    ...prev,
                    topics: e.target.value
                      .split(",")
                      .map((t) => t.trim())
                      .filter(Boolean),
                  }))
                }
                className="w-full px-3 py-1.5 text-xs bg-bg-primary border border-border rounded-md
                  text-text-primary placeholder:text-text-muted
                  focus:outline-none focus:ring-1 focus:ring-accent"
              />
            </div>

            {/* Submit */}
            <button
              onClick={handleAddProcedure}
              disabled={!newProcedure.trigger.trim()}
              className="px-4 py-1.5 text-xs bg-accent text-white rounded-md
                hover:bg-accent/90 disabled:opacity-50 disabled:cursor-not-allowed
                transition-colors"
            >
              Save Procedure
            </button>
          </div>
        </div>
      )}

      {/* Procedures list */}
      <div className="flex-1 overflow-y-auto">
        {showOffline ? (
          <ProceduresOfflineState onRetry={loadProcedures} loading={isLoading} />
        ) : showLoading ? (
          <TableSkeleton rows={5} />
        ) : showEmpty ? (
          <div className="flex-1 flex flex-col items-center justify-center p-8 text-center">
            <div className="w-12 h-12 rounded-full bg-bg-tertiary flex items-center justify-center mb-3">
              <Plus size={24} className="text-text-muted" />
            </div>
            <h3 className="text-sm font-medium text-text-secondary mb-1">
              No procedures yet
            </h3>
            <p className="text-xs text-text-muted max-w-xs mb-4">
              Create reusable procedures to automate common workflows and tasks.
            </p>
            <button
              onClick={() => setIsAddingNew(true)}
              className="px-4 py-1.5 text-xs bg-accent/20 text-accent rounded-md
                hover:bg-accent/30 transition-colors flex items-center gap-1.5"
            >
              <Plus size={14} />
              <span>Add your first procedure</span>
            </button>
          </div>
        ) : (
          <div className="divide-y divide-border">
            {filteredProcedures.map((procedure) => (
              <div key={procedure.uuid} className="group">
                {/* Trigger row */}
                <div
                  className="flex items-center gap-3 px-4 py-3 hover:bg-bg-secondary cursor-pointer"
                  onClick={() => toggleExpand(procedure.trigger)}
                >
                  {expandedTrigger === procedure.trigger ? (
                    <ChevronDown size={14} className="text-text-muted" />
                  ) : (
                    <ChevronRight size={14} className="text-text-muted" />
                  )}

                  <div className="flex-1 min-w-0">
                    <div className="text-sm text-text-primary font-medium truncate">
                      {procedure.trigger}
                    </div>
                    <div className="text-[11px] text-text-muted">
                      {procedure.steps.length} steps
                      {procedure.topics.length > 0 &&
                        ` • ${procedure.topics.slice(0, 3).join(", ")}${
                          procedure.topics.length > 3 ? "..." : ""
                        }`}
                    </div>
                  </div>

                  {/* Success count */}
                  <div className="flex items-center gap-1.5 text-[11px] text-success">
                    <CheckCircle size={12} />
                    <span>{procedure.success_count}</span>
                  </div>

                  {/* Actions */}
                  <div className="flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        handleRecordSuccess(procedure.trigger);
                      }}
                      className="p-1 text-success hover:bg-success/20 rounded transition-colors"
                      title="Record success"
                    >
                      <CheckCircle size={14} />
                    </button>
                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        handleDeleteProcedure(procedure.trigger);
                      }}
                      className="p-1 text-error hover:bg-error/20 rounded transition-colors"
                      title="Delete"
                    >
                      <Trash2 size={14} />
                    </button>
                  </div>
                </div>

                {/* Expanded content */}
                {expandedTrigger === procedure.trigger && (
                  <div className="px-4 pb-3 pl-10 space-y-2">
                    {procedure.steps.map((step, i) => (
                      <div
                        key={i}
                        className="flex items-start gap-2 text-xs text-text-secondary"
                      >
                        <span className="text-text-muted w-4">{i + 1}.</span>
                        <span>{step}</span>
                      </div>
                    ))}

                    {procedure.topics.length > 0 && (
                      <div className="flex flex-wrap gap-1.5 pt-2">
                        {procedure.topics.map((topic) => (
                          <span
                            key={topic}
                            className="px-2 py-0.5 text-[10px] bg-bg-tertiary text-text-muted rounded"
                          >
                            {topic}
                          </span>
                        ))}
                      </div>
                    )}

                    {procedure.success_count > 0 && (
                      <div className="text-[10px] text-text-muted pt-2">
                        Success count: {procedure.success_count}
                      </div>
                    )}
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
