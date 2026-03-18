"use client";

import { useRef, useEffect, useCallback } from "react";
import type { GraphNode, GraphEdge } from "../../lib/types/graph";

interface GraphCanvasProps {
  nodes: GraphNode[];
  edges: GraphEdge[];
  zoom: number;
  selectedNodeId: string | null;
  onNodeSelect: (nodeId: string | null) => void;
}

// Color palette for node types
const NODE_COLORS: Record<string, string> = {
  person: "#60a5fa", // blue
  concept: "#a78bfa", // purple
  event: "#f472b6", // pink
  object: "#34d399", // green
  location: "#fbbf24", // yellow
  organization: "#f87171", // red
  technology: "#2dd4bf", // teal
  default: "#6b7280", // gray
};

function getNodeColor(entityType: string): string {
  const normalized = entityType.toLowerCase();
  for (const [key, color] of Object.entries(NODE_COLORS)) {
    if (normalized.includes(key)) {
      return color;
    }
  }
  return NODE_COLORS.default;
}

interface SimulatedNode extends GraphNode {
  x: number;
  y: number;
  vx: number;
  vy: number;
}

export function GraphCanvas({
  nodes,
  edges,
  zoom,
  selectedNodeId,
  onNodeSelect,
}: GraphCanvasProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const nodesRef = useRef<SimulatedNode[]>([]);
  const animationRef = useRef<number | null>(null);
  const offsetRef = useRef({ x: 0, y: 0 });
  const isDraggingRef = useRef(false);
  const dragStartRef = useRef({ x: 0, y: 0 });

  // Initialize node positions
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    // Defensive check: ensure nodes is an array
    const safeNodes = Array.isArray(nodes) ? nodes : [];

    const centerX = canvas.width / 2;
    const centerY = canvas.height / 2;

    nodesRef.current = safeNodes.map((node, i) => ({
      ...node,
      x: centerX + (Math.random() - 0.5) * 400,
      y: centerY + (Math.random() - 0.5) * 400,
      vx: 0,
      vy: 0,
    }));
  }, [nodes]);

  // Simple force-directed simulation
  const simulate = useCallback(() => {
    const simulatedNodes = nodesRef.current;
    const nodeMap = new Map(simulatedNodes.map((n) => [n.uuid, n]));

    // Defensive check: ensure edges is an array
    const safeEdges = Array.isArray(edges) ? edges : [];

    // Apply forces
    for (const node of simulatedNodes) {
      // Center gravity
      const canvas = canvasRef.current;
      if (canvas) {
        const dx = canvas.width / 2 - node.x;
        const dy = canvas.height / 2 - node.y;
        node.vx += dx * 0.0001;
        node.vy += dy * 0.0001;
      }

      // Repulsion between nodes
      for (const other of simulatedNodes) {
        if (node.uuid === other.uuid) continue;
        const dx = node.x - other.x;
        const dy = node.y - other.y;
        const dist = Math.sqrt(dx * dx + dy * dy) || 1;
        if (dist < 150) {
          const force = (150 - dist) / dist * 0.5;
          node.vx += dx * force * 0.01;
          node.vy += dy * force * 0.01;
        }
      }
    }

    // Edge attraction
    for (const edge of safeEdges) {
      const source = nodeMap.get(edge.source_id);
      const target = nodeMap.get(edge.target_id);
      if (!source || !target) continue;

      const dx = target.x - source.x;
      const dy = target.y - source.y;
      const dist = Math.sqrt(dx * dx + dy * dy) || 1;
      const targetDist = 120;
      const force = (dist - targetDist) / dist * 0.01;

      source.vx += dx * force;
      source.vy += dy * force;
      target.vx -= dx * force;
      target.vy -= dy * force;
    }

    // Apply velocity with damping
    for (const node of simulatedNodes) {
      node.vx *= 0.9;
      node.vy *= 0.9;
      node.x += node.vx;
      node.y += node.vy;
    }
  }, [edges]);

  // Render function
  const render = useCallback(() => {
    const canvas = canvasRef.current;
    const ctx = canvas?.getContext("2d");
    if (!canvas || !ctx) return;

    const { width, height } = canvas;
    const offset = offsetRef.current;

    // Clear canvas
    ctx.fillStyle = "#0a0a0a";
    ctx.fillRect(0, 0, width, height);

    // Draw grid
    ctx.strokeStyle = "#1a1a1a";
    ctx.lineWidth = 1;
    const gridSize = 50 * zoom;
    const offsetX = (offset.x % gridSize);
    const offsetY = (offset.y % gridSize);

    for (let x = offsetX; x < width; x += gridSize) {
      ctx.beginPath();
      ctx.moveTo(x, 0);
      ctx.lineTo(x, height);
      ctx.stroke();
    }
    for (let y = offsetY; y < height; y += gridSize) {
      ctx.beginPath();
      ctx.moveTo(0, y);
      ctx.lineTo(width, y);
      ctx.stroke();
    }

    ctx.save();
    ctx.translate(offset.x, offset.y);
    ctx.scale(zoom, zoom);

    const simulatedNodes = nodesRef.current;
    const nodeMap = new Map(simulatedNodes.map((n) => [n.uuid, n]));

    // Defensive check: ensure edges is an array
    const safeEdges = Array.isArray(edges) ? edges : [];

    // Draw edges
    ctx.strokeStyle = "#333";
    ctx.lineWidth = 1 / zoom;
    for (const edge of safeEdges) {
      const source = nodeMap.get(edge.source_id);
      const target = nodeMap.get(edge.target_id);
      if (!source || !target) continue;

      const isHighlighted =
        selectedNodeId === source.uuid || selectedNodeId === target.uuid;

      ctx.beginPath();
      ctx.moveTo(source.x, source.y);
      ctx.lineTo(target.x, target.y);
      ctx.strokeStyle = isHighlighted ? "#60a5fa" : "#333";
      ctx.lineWidth = isHighlighted ? 2 / zoom : 1 / zoom;
      ctx.stroke();
    }

    // Draw nodes
    for (const node of simulatedNodes) {
      const isSelected = selectedNodeId === node.uuid;
      const color = getNodeColor(node.entity_type);

      // Node circle
      const radius = isSelected ? 12 : 8;
      ctx.beginPath();
      ctx.arc(node.x, node.y, radius, 0, Math.PI * 2);
      ctx.fillStyle = isSelected ? "#fff" : color;
      ctx.fill();

      if (isSelected) {
        ctx.strokeStyle = color;
        ctx.lineWidth = 3 / zoom;
        ctx.stroke();
      }

      // Node label
      ctx.fillStyle = "#fff";
      ctx.font = `${10 / zoom}px monospace`;
      ctx.textAlign = "center";
      ctx.fillText(node.name, node.x, node.y + radius + 12 / zoom);
    }

    ctx.restore();
  }, [edges, selectedNodeId, zoom]);

  // Animation loop
  useEffect(() => {
    const animate = () => {
      simulate();
      render();
      animationRef.current = requestAnimationFrame(animate);
    };

    animate();

    return () => {
      if (animationRef.current) {
        cancelAnimationFrame(animationRef.current);
      }
    };
  }, [simulate, render]);

  // Handle resize
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    const handleResize = () => {
      const parent = canvas.parentElement;
      if (parent) {
        canvas.width = parent.clientWidth;
        canvas.height = parent.clientHeight;
      }
    };

    handleResize();
    window.addEventListener("resize", handleResize);
    return () => window.removeEventListener("resize", handleResize);
  }, []);

  // Mouse interactions
  const handleMouseDown = useCallback((e: React.MouseEvent) => {
    isDraggingRef.current = true;
    dragStartRef.current = { x: e.clientX, y: e.clientY };
  }, []);

  const handleMouseMove = useCallback((e: React.MouseEvent) => {
    if (isDraggingRef.current) {
      const dx = e.clientX - dragStartRef.current.x;
      const dy = e.clientY - dragStartRef.current.y;
      offsetRef.current.x += dx;
      offsetRef.current.y += dy;
      dragStartRef.current = { x: e.clientX, y: e.clientY };
    }
  }, []);

  const handleMouseUp = useCallback(() => {
    isDraggingRef.current = false;
  }, []);

  const handleClick = useCallback(
    (e: React.MouseEvent) => {
      const canvas = canvasRef.current;
      if (!canvas) return;

      const rect = canvas.getBoundingClientRect();
      const x = (e.clientX - rect.left - offsetRef.current.x) / zoom;
      const y = (e.clientY - rect.top - offsetRef.current.y) / zoom;

      // Find clicked node
      for (const node of nodesRef.current) {
        const dx = x - node.x;
        const dy = y - node.y;
        const dist = Math.sqrt(dx * dx + dy * dy);
        if (dist < 15) {
          onNodeSelect(node.uuid);
          return;
        }
      }

      onNodeSelect(null);
    },
    [onNodeSelect, zoom]
  );

  return (
    <canvas
      ref={canvasRef}
      className="flex-1 cursor-grab active:cursor-grabbing"
      onMouseDown={handleMouseDown}
      onMouseMove={handleMouseMove}
      onMouseUp={handleMouseUp}
      onMouseLeave={handleMouseUp}
      onClick={handleClick}
    />
  );
}
