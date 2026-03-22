"use client";

import { useState, useEffect, useCallback, useMemo } from "react";
import { Search, ZoomIn, ZoomOut, Maximize2, AlertCircle } from "lucide-react";
import { GraphCanvas } from "./graph-canvas";
import { api } from "../../lib/api-client";
import type { GraphNode, GraphEdge, GraphData } from "../../lib/types/graph";
import { GraphOfflineState, GraphSkeleton } from "@/components/ui/empty-states";
import { formatDate } from "@/lib/utils";
import clsx from "clsx";

interface SelectedNode {
  node: GraphNode;
  connections: { edge: GraphEdge; neighbor: GraphNode }[];
}

export function GraphView() {
  const [graphData, setGraphData] = useState<GraphData>({ nodes: [], edges: [] });
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState("");
  const [selectedNode, setSelectedNode] = useState<SelectedNode | null>(null);
  const [zoom, setZoom] = useState(1);

  // Load graph data
  const loadGraph = useCallback(async () => {
    setIsLoading(true);
    setError(null);

    try {
      const data = await api.getGraphData(100);
      setGraphData(data);
    } catch (err) {
      const message = err instanceof Error ? err.message : "Failed to load graph";
      setError(message);
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    loadGraph();
  }, [loadGraph]);

  // Filter nodes by search
  const filteredData = useMemo(() => {
    // Defensive check: ensure nodes and edges are arrays
    const safeNodes = Array.isArray(graphData.nodes) ? graphData.nodes : [];
    const safeEdges = Array.isArray(graphData.edges) ? graphData.edges : [];

    if (!searchQuery.trim()) {
      return { nodes: safeNodes, edges: safeEdges };
    }

    const query = searchQuery.toLowerCase();
    const matchingNodes = safeNodes.filter(
      (n) =>
        n.name.toLowerCase().includes(query) ||
        n.entity_type.toLowerCase().includes(query)
    );
    const matchingIds = new Set(matchingNodes.map((n) => n.uuid));

    // Include edges where both endpoints are in the filtered set
    const matchingEdges = safeEdges.filter(
      (e) => matchingIds.has(e.source_id) && matchingIds.has(e.target_id)
    );

    return { nodes: matchingNodes, edges: matchingEdges };
  }, [graphData, searchQuery]);

  // Handle node selection
  const handleNodeSelect = useCallback(
    (nodeId: string | null) => {
      if (!nodeId) {
        setSelectedNode(null);
        return;
      }

      // Defensive check: ensure nodes and edges are arrays
      const safeNodes = Array.isArray(graphData.nodes) ? graphData.nodes : [];
      const safeEdges = Array.isArray(graphData.edges) ? graphData.edges : [];

      const node = safeNodes.find((n) => n.uuid === nodeId);
      if (!node) {
        setSelectedNode(null);
        return;
      }

      // Find connected nodes and edges
      const connections = safeEdges
        .filter((e) => e.source_id === nodeId || e.target_id === nodeId)
        .map((edge) => {
          const neighborId = edge.source_id === nodeId ? edge.target_id : edge.source_id;
          const neighbor = safeNodes.find((n) => n.uuid === neighborId);
          return neighbor ? { edge, neighbor } : null;
        })
        .filter((c): c is { edge: GraphEdge; neighbor: GraphNode } => c !== null);

      setSelectedNode({ node, connections });
    },
    [graphData]
  );

  // Zoom controls
  const handleZoomIn = () => setZoom((z) => Math.min(z * 1.2, 3));
  const handleZoomOut = () => setZoom((z) => Math.max(z / 1.2, 0.3));
  const handleZoomReset = () => setZoom(1);

  // Determine state
  const safeNodes = Array.isArray(graphData.nodes) ? graphData.nodes : [];
  const showOffline = error && safeNodes.length === 0;
  const showLoading = isLoading && safeNodes.length === 0 && !error;
  const showEmpty = !isLoading && !error && safeNodes.length === 0;

  return (
    <div className="h-full flex">
      {/* Main canvas area */}
      <div className="flex-1 flex flex-col">
        {/* Header */}
        <div className="flex items-center justify-between px-4 py-3 border-b border-border">
          <div className="flex items-center gap-3">
            <h2 className="text-sm font-medium text-text-primary">Knowledge Graph</h2>
            <span className="text-[11px] text-text-muted">
              {filteredData.nodes.length} nodes / {filteredData.edges.length} edges
            </span>
          </div>

          {/* Search */}
          <div className="relative">
            <Search
              size={14}
              className="absolute left-2.5 top-1/2 -translate-y-1/2 text-text-muted"
            />
            <input
              type="text"
              placeholder="Search nodes..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="pl-8 pr-3 py-1.5 text-xs bg-bg-secondary border border-border rounded-md
                text-text-primary placeholder:text-text-muted
                focus:outline-none focus:ring-1 focus:ring-accent"
            />
          </div>

          {/* Zoom controls */}
          <div className="flex items-center gap-1">
            <button
              onClick={handleZoomOut}
              className="p-1.5 text-text-secondary hover:text-text-primary transition-colors"
              title="Zoom out"
            >
              <ZoomOut size={16} />
            </button>
            <span className="text-[11px] text-text-muted w-12 text-center">
              {Math.round(zoom * 100)}%
            </span>
            <button
              onClick={handleZoomIn}
              className="p-1.5 text-text-secondary hover:text-text-primary transition-colors"
              title="Zoom in"
            >
              <ZoomIn size={16} />
            </button>
            <button
              onClick={handleZoomReset}
              className="p-1.5 text-text-secondary hover:text-text-primary transition-colors"
              title="Reset zoom"
            >
              <Maximize2 size={16} />
            </button>
          </div>
        </div>

        {/* Content */}
        {showOffline ? (
          <GraphOfflineState onRetry={loadGraph} loading={isLoading} />
        ) : showLoading ? (
          <GraphSkeleton />
        ) : showEmpty ? (
          <div className="flex-1 flex flex-col items-center justify-center p-8 text-center">
            <div className="w-12 h-12 rounded-full bg-bg-tertiary flex items-center justify-center mb-3">
              <Search size={24} className="text-text-muted" />
            </div>
            <h3 className="text-sm font-medium text-text-secondary mb-1">
              Graph is empty
            </h3>
            <p className="text-xs text-text-muted max-w-xs">
              Add episodes to your memory to populate the knowledge graph with entities and relationships.
            </p>
          </div>
        ) : (
          <>
            {/* Error banner - non-blocking */}
            {error && (
              <div className="px-4 py-2 bg-warning/10 border-b border-warning/20 flex items-center gap-2 text-warning text-xs">
                <AlertCircle size={14} />
                <span>Using cached data: {error}</span>
              </div>
            )}
            <GraphCanvas
              nodes={filteredData.nodes}
              edges={filteredData.edges}
              zoom={zoom}
              selectedNodeId={selectedNode?.node.uuid || null}
              onNodeSelect={handleNodeSelect}
            />
          </>
        )}
      </div>

      {/* Node detail drawer */}
      {selectedNode && (
        <div className="w-80 border-l border-border bg-bg-secondary overflow-y-auto">
          <div className="p-4">
            <div className="flex items-center justify-between mb-3">
              <h3 className="text-sm font-medium text-text-primary">
                {selectedNode.node.name}
              </h3>
              <span
                className={clsx(
                  "px-2 py-0.5 text-[10px] rounded-full",
                  "bg-accent/20 text-accent"
                )}
              >
                {selectedNode.node.entity_type}
              </span>
            </div>

            {selectedNode.node.summary && (
              <p className="text-xs text-text-secondary mb-4">
                {selectedNode.node.summary}
              </p>
            )}

            <div className="space-y-2 text-[11px] text-text-muted">
              <div className="flex justify-between">
                <span>Access count:</span>
                <span className="text-text-primary">
                  {selectedNode.node.access_count}
                </span>
              </div>
              {selectedNode.node.decay_score !== undefined && (
                <div className="flex justify-between">
                  <span>Decay score:</span>
                  <span className="text-text-primary">
                    {selectedNode.node.decay_score.toFixed(2)}
                  </span>
                </div>
              )}
              <div className="flex justify-between">
                <span>Created:</span>
                <span className="text-text-primary">
                  {formatDate(selectedNode.node.created_at)}
                </span>
              </div>
            </div>

            {/* Connections */}
            {selectedNode.connections.length > 0 && (
              <div className="mt-4 pt-4 border-t border-border">
                <h4 className="text-xs font-medium text-text-primary mb-2">
                  Connections ({selectedNode.connections.length})
                </h4>
                <div className="space-y-2">
                  {selectedNode.connections.map(({ edge, neighbor }, i) => (
                    <div
                      key={i}
                      className="p-2 bg-bg-tertiary rounded text-[11px]"
                    >
                      <div className="text-text-muted mb-1">{edge.relation}</div>
                      <div className="text-text-primary font-medium">
                        {neighbor.name}
                      </div>
                      <div className="text-text-muted text-[10px]">
                        {neighbor.entity_type}
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
