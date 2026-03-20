"use client";

import { useState, useEffect, useCallback } from "react";
import {
  Save,
  Loader2,
  AlertCircle,
  CheckCircle,
  Trash2,
} from "lucide-react";
import { api, type UpdatePreferencesRequest } from "../../lib/api-client";
import type { UserContext, UserPreferences } from "../../lib/types";
import { IdentityOfflineState, FormSkeleton } from "@/components/ui/empty-states";
import clsx from "clsx";

export default function IdentityPage() {
  const [context, setContext] = useState<UserContext>({});
  const [preferences, setPreferences] = useState<UserPreferences>({});
  const [isLoading, setIsLoading] = useState(true);
  const [isSaving, setIsSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  // Load identity data
  const loadData = useCallback(async () => {
    setIsLoading(true);
    setError(null);

    try {
      const [identityData, prefsResponse] = await Promise.all([
        api.getIdentity(),
        api.getPreferences(),
      ]);
      setContext(identityData);
      // Handle { user_id, preferences } response format
      setPreferences(prefsResponse.preferences || prefsResponse);
    } catch (err) {
      const message = err instanceof Error ? err.message : "Failed to load identity";
      setError(message);
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    loadData();
  }, [loadData]);

  // Save identity
  const handleSaveIdentity = async () => {
    setIsSaving(true);
    setError(null);
    setSuccess(null);

    try {
      await api.setIdentity(context);
      setSuccess("Identity saved successfully");
      setTimeout(() => setSuccess(null), 3000);
    } catch (err) {
      const message = err instanceof Error ? err.message : "Failed to save identity";
      setError(message);
    } finally {
      setIsSaving(false);
    }
  };

  // Save preferences
  const handleSavePreferences = async () => {
    setIsSaving(true);
    setError(null);
    setSuccess(null);

    try {
      const request: UpdatePreferencesRequest = {
        ...(preferences.language ? { language: preferences.language } : {}),
        ...(preferences.timezone ? { timezone: preferences.timezone } : {}),
        ...(preferences.response_style ? { response_style: preferences.response_style } : {}),
        ...(preferences.expertise?.length ? { add_expertise: preferences.expertise } : {}),
        ...(preferences.topics?.length ? { add_topics: preferences.topics } : {}),
        ...(preferences.notes ? { notes: preferences.notes } : {}),
      };
      await api.updatePreferences(request);
      setSuccess("Preferences saved successfully");
      setTimeout(() => setSuccess(null), 3000);
    } catch (err) {
      const message = err instanceof Error ? err.message : "Failed to save preferences";
      setError(message);
    } finally {
      setIsSaving(false);
    }
  };

  // Clear identity
  const handleClearIdentity = async () => {
    if (!confirm("Clear all identity data?")) return;

    try {
      await api.clearIdentity();
      setContext({});
      setSuccess("Identity cleared");
      setTimeout(() => setSuccess(null), 3000);
    } catch (err) {
      const message = err instanceof Error ? err.message : "Failed to clear identity";
      setError(message);
    }
  };

  if (isLoading) {
    return (
      <div className="h-full flex items-center justify-center">
        <div className="flex items-center gap-2 text-text-muted">
          <Loader2 size={24} className="animate-spin" />
          <span className="text-sm">Loading identity...</span>
        </div>
      </div>
    );
  }

  return (
    <div className="h-full flex flex-col">
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3 border-b border-border">
        <h2 className="text-sm font-medium text-text-primary">Identity</h2>

        <div className="flex items-center gap-2">
          {success && (
            <div className="flex items-center gap-1.5 text-success text-xs">
              <CheckCircle size={14} />
              <span>{success}</span>
            </div>
          )}
        </div>
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
        {/* User Context */}
        <section className="bg-bg-secondary rounded-lg p-4">
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-sm font-medium text-text-primary">User Context</h3>
            <button
              onClick={handleClearIdentity}
              className="p-1.5 text-error hover:bg-error/20 rounded transition-colors"
              title="Clear identity"
            >
              <Trash2 size={14} />
            </button>
          </div>

          <div className="space-y-4">
            <div>
              <label className="text-[11px] text-text-muted mb-1 block">
                User ID
              </label>
              <input
                type="text"
                placeholder="e.g., user_123"
                value={context.user_id || ""}
                onChange={(e) =>
                  setContext((prev) => ({ ...prev, user_id: e.target.value || undefined }))
                }
                className="w-full px-3 py-1.5 text-xs bg-bg-primary border border-border rounded-md
                  text-text-primary placeholder:text-text-muted
                  focus:outline-none focus:ring-1 focus:ring-accent"
              />
            </div>

            <div>
              <label className="text-[11px] text-text-muted mb-1 block">
                Agent ID
              </label>
              <input
                type="text"
                placeholder="e.g., claude-sonnet"
                value={context.agent_id || ""}
                onChange={(e) =>
                  setContext((prev) => ({ ...prev, agent_id: e.target.value || undefined }))
                }
                className="w-full px-3 py-1.5 text-xs bg-bg-primary border border-border rounded-md
                  text-text-primary placeholder:text-text-muted
                  focus:outline-none focus:ring-1 focus:ring-accent"
              />
            </div>

            <div>
              <label className="text-[11px] text-text-muted mb-1 block">
                Chat ID
              </label>
              <input
                type="text"
                placeholder="e.g., session_abc123"
                value={context.chat_id || ""}
                onChange={(e) =>
                  setContext((prev) => ({ ...prev, chat_id: e.target.value || undefined }))
                }
                className="w-full px-3 py-1.5 text-xs bg-bg-primary border border-border rounded-md
                  text-text-primary placeholder:text-text-muted
                  focus:outline-none focus:ring-1 focus:ring-accent"
              />
            </div>

            <button
              onClick={handleSaveIdentity}
              disabled={isSaving}
              className="px-4 py-1.5 text-xs bg-accent text-white rounded-md
                hover:bg-accent/90 disabled:opacity-50 transition-colors
                flex items-center gap-1.5"
            >
              {isSaving ? (
                <Loader2 size={14} className="animate-spin" />
              ) : (
                <Save size={14} />
              )}
              <span>Save Identity</span>
            </button>
          </div>
        </section>

        {/* User Preferences */}
        <section className="bg-bg-secondary rounded-lg p-4">
          <h3 className="text-sm font-medium text-text-primary mb-4">
            User Preferences
          </h3>

          <div className="space-y-4">
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="text-[11px] text-text-muted mb-1 block">
                  Language
                </label>
                <input
                  type="text"
                  placeholder="e.g., th, en"
                  value={preferences.language || ""}
                  onChange={(e) =>
                    setPreferences((prev) => ({
                      ...prev,
                      language: e.target.value || undefined,
                    }))
                  }
                  className="w-full px-3 py-1.5 text-xs bg-bg-primary border border-border rounded-md
                    text-text-primary placeholder:text-text-muted
                    focus:outline-none focus:ring-1 focus:ring-accent"
                />
              </div>

              <div>
                <label className="text-[11px] text-text-muted mb-1 block">
                  Timezone
                </label>
                <input
                  type="text"
                  placeholder="e.g., Asia/Bangkok"
                  value={preferences.timezone || ""}
                  onChange={(e) =>
                    setPreferences((prev) => ({
                      ...prev,
                      timezone: e.target.value || undefined,
                    }))
                  }
                  className="w-full px-3 py-1.5 text-xs bg-bg-primary border border-border rounded-md
                    text-text-primary placeholder:text-text-muted
                    focus:outline-none focus:ring-1 focus:ring-accent"
                />
              </div>
            </div>

            <div>
              <label className="text-[11px] text-text-muted mb-1 block">
                Response Style
              </label>
              <select
                value={preferences.response_style || ""}
                onChange={(e) =>
                  setPreferences((prev) => ({
                    ...prev,
                    response_style: (e.target.value || undefined) as UserPreferences["response_style"],
                  }))
                }
                className="w-full px-3 py-1.5 text-xs bg-bg-primary border border-border rounded-md
                  text-text-primary
                  focus:outline-none focus:ring-1 focus:ring-accent"
              >
                <option value="">Select style</option>
                <option value="balanced">Balanced</option>
                <option value="concise">Concise</option>
                <option value="detailed">Detailed</option>
              </select>
            </div>

            <div>
              <label className="text-[11px] text-text-muted mb-1 block">
                Expertise Areas (comma-separated)
              </label>
              <input
                type="text"
                placeholder="e.g., frontend, backend, devops"
                value={preferences.expertise?.join(", ") || ""}
                onChange={(e) =>
                  setPreferences((prev) => ({
                    ...prev,
                    expertise: e.target.value
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

            <div>
              <label className="text-[11px] text-text-muted mb-1 block">
                Topics of Interest (comma-separated)
              </label>
              <input
                type="text"
                placeholder="e.g., AI, machine learning, web development"
                value={preferences.topics?.join(", ") || ""}
                onChange={(e) =>
                  setPreferences((prev) => ({
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

            <div>
              <label className="text-[11px] text-text-muted mb-1 block">
                Notes
              </label>
              <textarea
                placeholder="Additional notes..."
                value={preferences.notes || ""}
                onChange={(e) =>
                  setPreferences((prev) => ({
                    ...prev,
                    notes: e.target.value || undefined,
                  }))
                }
                rows={3}
                className="w-full px-3 py-1.5 text-xs bg-bg-primary border border-border rounded-md
                  text-text-primary placeholder:text-text-muted resize-none
                  focus:outline-none focus:ring-1 focus:ring-accent"
              />
            </div>

            <button
              onClick={handleSavePreferences}
              disabled={isSaving}
              className="px-4 py-1.5 text-xs bg-accent text-white rounded-md
                hover:bg-accent/90 disabled:opacity-50 transition-colors
                flex items-center gap-1.5"
            >
              {isSaving ? (
                <Loader2 size={14} className="animate-spin" />
              ) : (
                <Save size={14} />
              )}
              <span>Save Preferences</span>
            </button>
          </div>
        </section>
      </div>
    </div>
  );
}
