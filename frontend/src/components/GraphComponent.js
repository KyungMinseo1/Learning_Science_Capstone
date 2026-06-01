import React, { useCallback, useEffect, useRef, useState } from 'react';
import * as d3 from 'd3';

const truncate = (s, n = 20) => (s && s.length > n ? s.slice(0, n) + '...' : s || '');

const normalizePairKey = (paper1Id, paper2Id) => [paper1Id, paper2Id].filter(Boolean).sort().join('::');

const getEndpointId = (endpoint) => {
  if (!endpoint && endpoint !== 0) return endpoint;
  if (typeof endpoint === 'object') return endpoint.id || endpoint?.toString();
  return endpoint;
};

const ACTIVE_EDGE_BASE = '#4f83d1';

const GraphComponent = ({
  data,
  onNodeClick,
  onNodeDelete,
  onBackgroundClick,
  onConnectSelected,
  onSummaryClick,
  selectedNodes = [],
  pairSimilarity = null,
  height = 600,
  connectionButtonLabel = 'Create connection',
  suggestedNeuronConnectionEnabled = true,
  onSuggestedNeuronConnectionToggle,
  highlightedPairKeys = new Set(),
  hoveredQuizPairKey = null,
  availableCategories = [],
  selectedCategory = '',
  onCategoryChange,
}) => {
  const svgRef = useRef();
  const containerRef = useRef();
  const [zoomBehavior, setZoomBehavior] = useState(null);
  const [hoverConnection, setHoverConnection] = useState(null);
  const transformRef = useRef(d3.zoomIdentity);
  const hoverTimerRef = useRef(null);
  const hoverClearTimerRef = useRef(null);
  const hoverPointRef = useRef(null);
  const hoverConnectionRef = useRef(null);
  const nodeOpacityMapRef = useRef(new Map());
  const nodePositionMapRef = useRef(new Map());
  const suggestedNeuronConnectionEnabledRef = useRef(suggestedNeuronConnectionEnabled);
  const highlightedPairKeysRef = useRef(highlightedPairKeys);
  const onNodeClickRef = useRef(onNodeClick);
  useEffect(() => { onNodeClickRef.current = onNodeClick; }, [onNodeClick]);
  const onBackgroundClickRef = useRef(onBackgroundClick);
  useEffect(() => { onBackgroundClickRef.current = onBackgroundClick; }, [onBackgroundClick]);
  suggestedNeuronConnectionEnabledRef.current = suggestedNeuronConnectionEnabled;
  highlightedPairKeysRef.current = highlightedPairKeys;
  useEffect(() => { hoverConnectionRef.current = hoverConnection; }, [hoverConnection]);

  const clearHoverConnection = useCallback(() => {
    if (hoverTimerRef.current) {
      clearTimeout(hoverTimerRef.current);
      hoverTimerRef.current = null;
    }
    if (hoverClearTimerRef.current) {
      clearTimeout(hoverClearTimerRef.current);
      hoverClearTimerRef.current = null;
    }
    hoverPointRef.current = null;
    setHoverConnection(null);
  }, []);

  const scheduleClearHoverConnection = useCallback(() => {
    if (hoverClearTimerRef.current) {
      clearTimeout(hoverClearTimerRef.current);
    }
    hoverClearTimerRef.current = window.setTimeout(() => {
      clearHoverConnection();
    }, 350);
  }, [clearHoverConnection]);

  useEffect(() => () => clearHoverConnection(), [clearHoverConnection]);

  useEffect(() => {
    if (!data || !data.nodes) return;

    const width = containerRef.current ? containerRef.current.clientWidth || 900 : 900;
    const measuredHeight = containerRef.current ? containerRef.current.clientHeight || 0 : 0;
    const svgHeight = Math.max(420, measuredHeight || Number(height) || 600);

    const svg = d3.select(svgRef.current)
      .attr('width', width)
      .attr('height', svgHeight)
      .style('cursor', 'grab');

    svg.selectAll('*').remove();

    // groups for zooming
    const g = svg.append('g').attr('class', 'viewport');

    const nodeBaseRadius = 17;
    const nodeDegree = new Map();
    const nodeScoreTotal = new Map();
    for (const link of data.links) {
      const sourceId = link.source?.id || link.source;
      const targetId = link.target?.id || link.target;
      const score = typeof link.score === 'number' ? link.score : 0.25;
      nodeDegree.set(sourceId, (nodeDegree.get(sourceId) || 0) + 1);
      nodeDegree.set(targetId, (nodeDegree.get(targetId) || 0) + 1);
      nodeScoreTotal.set(sourceId, (nodeScoreTotal.get(sourceId) || 0) + score);
      nodeScoreTotal.set(targetId, (nodeScoreTotal.get(targetId) || 0) + score);
    }
    const maxDegree = Math.max(1, ...nodeDegree.values());
    const maxScoreTotal = Math.max(1, ...nodeScoreTotal.values());
    nodeOpacityMapRef.current = new Map();
    for (const node of data.nodes) {
      const degree = nodeDegree.get(node.id) || 0;
      const scoreTotal = nodeScoreTotal.get(node.id) || 0;
      const degreeFactor = Math.min(1, degree / maxDegree);
      const scoreFactor = Math.min(1, scoreTotal / maxScoreTotal);
      const opacity = degree === 0 ? 0.2 : 0.24 + (0.76 * (degreeFactor * 0.45 + scoreFactor * 0.55));
      nodeOpacityMapRef.current.set(node.id, Math.max(0.18, Math.min(1, opacity)));
    }

    const isHighlightedLink = (link) => {
      if (!suggestedNeuronConnectionEnabledRef.current || !highlightedPairKeysRef.current || !highlightedPairKeysRef.current.size) {
        return false;
      }
      const sourceId = getEndpointId(link.source);
      const targetId = getEndpointId(link.target);
      return highlightedPairKeysRef.current.has(normalizePairKey(sourceId, targetId));
    };

    const baseLinkOpacity = (link) => {
      const score = Number(link.score);
      const normalizedScore = Number.isFinite(score) ? Math.max(0, Math.min(1, score)) : 0.25;
      const statusBoost = link.status === 'confirmed' ? 0.16 : 0;
      return Math.max(0.18, Math.min(1, 0.22 + (normalizedScore * 0.62) + statusBoost));
    };

    const simulation = d3.forceSimulation(data.nodes)
      .force('link', d3.forceLink(data.links).id(d => d.id).distance(d => {
        // Keep distance driven only by similarity score, regardless of link status.
        const score = (d && d.score != null) ? d.score : 0.5;
        const baseMin = 140;
        const baseMax = 410;
        const stretch = baseMax - baseMin;
        return baseMax - (score * stretch);
      }))
      .force('charge', d3.forceManyBody().strength(-420))
      .force('collide', d3.forceCollide().radius(nodeBaseRadius + 26).iterations(2))
      .force('center', d3.forceCenter(width / 2, svgHeight / 2));

    const link = g.append('g')
      .attr('class', 'links')
      .selectAll('line')
      .data(data.links)
      .enter().append('line')
      .attr('stroke', d => (suggestedNeuronConnectionEnabledRef.current && isHighlightedLink(d)) ? ACTIVE_EDGE_BASE : (d.status === 'confirmed' ? '#7f97ad' : (d.type === 'SHADOW_LINK' ? '#9ca3af' : '#64748b')))
      .attr('stroke-dasharray', d => (suggestedNeuronConnectionEnabledRef.current && isHighlightedLink(d)) ? '1 7' : (d.status === 'confirmed' ? '0' : (d.type === 'SHADOW_LINK' ? '1 7' : '0')))
      .attr('stroke-linecap', 'round')
      .attr('stroke-linejoin', 'round')
      .attr('vector-effect', 'non-scaling-stroke')
      .attr('stroke-width', d => Math.max(1.25, 1.3 + (Number(d.score) || 0.2) * 2.1 + ((suggestedNeuronConnectionEnabledRef.current && isHighlightedLink(d)) ? 1.15 : 0)))
      .style('opacity', d => (suggestedNeuronConnectionEnabledRef.current && isHighlightedLink(d)) ? 0.8 : baseLinkOpacity(d))
      .style('filter', d => (suggestedNeuronConnectionEnabledRef.current && isHighlightedLink(d)) ? 'drop-shadow(0 0 10px rgba(79, 131, 209, 0.42))' : 'none')

      .style('pointer-events', d => d.status === 'confirmed' ? 'stroke' : 'none')
      .style('cursor', d => d.status === 'confirmed' ? 'pointer' : 'default');

    const resolveNode = (endpoint) => {
      if (endpoint && typeof endpoint === 'object' && endpoint.id) {
        return endpoint;
      }
      return data.nodes.find((node) => node.id === endpoint) || null;
    };

    const handleLinkMouseEnter = (event, d) => {
      if (d.status !== 'confirmed') return;
      clearHoverConnection();
      const source = resolveNode(d.source);
      const target = resolveNode(d.target);
      if (!source || !target) return;

      const clientX = event.clientX;
      const clientY = event.clientY;

      hoverPointRef.current = { source, target };
      hoverTimerRef.current = window.setTimeout(() => {
        const rect = containerRef.current?.getBoundingClientRect();
        if (!rect || !hoverPointRef.current) return;
        setHoverConnection({
          source: hoverPointRef.current.source,
          target: hoverPointRef.current.target,
          x: clientX - rect.left,
          y: clientY - rect.top,
        });
      }, 500);
    };

    const handleLinkMouseMove = (event) => {
      if (!hoverTimerRef.current && !hoverConnectionRef.current) return;
      const rect = containerRef.current?.getBoundingClientRect();
      if (!rect || !hoverPointRef.current) return;

      const nextPoint = {
        source: hoverPointRef.current.source,
        target: hoverPointRef.current.target,
        x: event.clientX - rect.left,
        y: event.clientY - rect.top,
      };

      hoverPointRef.current = nextPoint;
      setHoverConnection((current) => {
        if (!current) return current;
        if (current.source?.id !== nextPoint.source?.id || current.target?.id !== nextPoint.target?.id) {
          return current;
        }
        return { ...current, x: nextPoint.x, y: nextPoint.y };
      });
    };

    const handleLinkMouseLeave = () => {
      scheduleClearHoverConnection();
    };

    link
      .on('mouseenter', handleLinkMouseEnter)
      .on('mousemove', handleLinkMouseMove)
      .on('mouseleave', handleLinkMouseLeave);

    const nodeGroup = g.append('g').attr('class', 'nodes');

    const node = nodeGroup.selectAll('g.node')
      .data(data.nodes)
      .enter().append('g')
      .attr('class', 'node')
      .attr('opacity', d => nodeOpacityMapRef.current.get(d.id) || 0.4);

    node.append('circle')
      .attr('r', nodeBaseRadius)
      .attr('fill', '#60a5fa')
      .attr('stroke', '#f8fafc')
      .attr('stroke-width', 1.5);

    // ensure clicks on the group (including text) select the node
    node.on('click', (event, d) => {
      try { event.stopPropagation(); } catch (e) {}
      event.preventDefault();
      if (onNodeClickRef.current) {
        onNodeClickRef.current(d, event.shiftKey);
      }
    });

    node.append('text')
      .attr('x', 0)
      .attr('y', nodeBaseRadius + 20)
      .attr('text-anchor', 'middle')
      .attr('font-size', 13)
      .attr('font-weight', 600)
      .attr('fill', '#0f172a')
      .text(d => truncate(d.title, 30));

    node.append('title').text(d => d.title);

    // Run simulation for a number of iterations to stabilize positions, then stop.
    try {
      for (let i = 0; i < 350; i++) simulation.tick();
    } catch (e) {}

    try {
      simulation.force('charge', null);
      simulation.alpha(0);
      simulation.stop();
    } catch (e) {}

    // apply final positions once
    const offsetLine = (source, target, radiusOffset) => {
      const dx = (target.x || 0) - (source.x || 0);
      const dy = (target.y || 0) - (source.y || 0);
      const distance = Math.max(1, Math.sqrt(dx * dx + dy * dy));
      const offsetX = (dx / distance) * radiusOffset;
      const offsetY = (dy / distance) * radiusOffset;
      return {
        x1: (source.x || width / 2) + offsetX,
        y1: (source.y || svgHeight / 2) + offsetY,
        x2: (target.x || width / 2) - offsetX,
        y2: (target.y || svgHeight / 2) - offsetY,
      };
    };

    link
      .attr('x1', d => offsetLine(d.source, d.target, nodeBaseRadius).x1)
      .attr('y1', d => offsetLine(d.source, d.target, nodeBaseRadius).y1)
      .attr('x2', d => offsetLine(d.source, d.target, nodeBaseRadius).x2)
      .attr('y2', d => offsetLine(d.source, d.target, nodeBaseRadius).y2);

    node
      .attr('transform', d => `translate(${d.x || width/2},${d.y || svgHeight/2})`);

    nodePositionMapRef.current = new Map(
      data.nodes.map((nodeItem) => [
        nodeItem.id,
        {
          x: nodeItem.x || width / 2,
          y: nodeItem.y || svgHeight / 2,
        },
      ])
    );

    // removed drag handlers to keep nodes static after initial layout

    // Zoom behavior
    const zoom = d3.zoom()
      .scaleExtent([0.2, 4])
      .on('zoom', (event) => {
        g.attr('transform', event.transform);
        transformRef.current = event.transform;
        // keep text size stable by adjusting font-size inversely to zoom
        const k = event.transform.k || 1;
        g.selectAll('text').attr('font-size', k < 0.72 ? 0 : 13 / k);
      });

    svg.call(zoom);
    // restore previous transform if present
    if (transformRef.current && transformRef.current.k !== 1) {
      try { svg.call(zoom.transform, transformRef.current); } catch (e) { /* ignore */ }
    }
    setZoomBehavior(() => zoom);

    // ctrl + wheel for zoom (less sensitive)
    const svgEl = svgRef.current;
    const wheelHandler = (e) => {
      // allow plain wheel to zoom (not requiring ctrl); make sensitivity gentle
      e.preventDefault();
      const factor = e.deltaY > 0 ? 0.985 : 1.015;
        d3.select(svgEl).transition().duration(120).call(zoom.scaleBy, factor);
    };
    if (svgEl) svgEl.addEventListener('wheel', wheelHandler, { passive: false });

    // background click to clear selection
    const bgClick = (event) => {
      try {
        // ignore clicks on nodes (or their children)
        const closestNode = event.target && event.target.closest && event.target.closest('.node');
        if (closestNode) return;
      } catch (e) {}
      if (onBackgroundClickRef.current) {
        onBackgroundClickRef.current();
      }
    };
    if (svgEl) svgEl.addEventListener('click', bgClick);

    return () => {
      if (svgEl) {
        svgEl.removeEventListener('wheel', wheelHandler);
        svgEl.removeEventListener('click', bgClick);
      }
      simulation.stop();
      clearHoverConnection();
    };
  }, [data, height, clearHoverConnection, scheduleClearHoverConnection]);

  useEffect(() => {
    if (!svgRef.current) return;

    const links = d3.select(svgRef.current).selectAll('.links line');
    if (links.empty()) return;

    const isHighlightedLink = (link) => {
      if (!suggestedNeuronConnectionEnabledRef.current || !highlightedPairKeysRef.current || !highlightedPairKeysRef.current.size) {
        return false;
      }
      const sourceId = getEndpointId(link.source);
      const targetId = getEndpointId(link.target);
      return highlightedPairKeysRef.current.has(normalizePairKey(sourceId, targetId));
    };

    const baseLinkOpacity = (link) => {
      const score = Number(link.score);
      const normalizedScore = Number.isFinite(score) ? Math.max(0, Math.min(1, score)) : 0.25;
      const statusBoost = link.status === 'confirmed' ? 0.16 : 0;
      return Math.max(0.18, Math.min(1, 0.22 + (normalizedScore * 0.62) + statusBoost));
    };

    links
      .attr('stroke', d => (suggestedNeuronConnectionEnabledRef.current && isHighlightedLink(d)) ? ACTIVE_EDGE_BASE : (d.status === 'confirmed' ? '#7f97ad' : (d.type === 'SHADOW_LINK' ? '#9ca3af' : '#64748b')))
      .attr('stroke-dasharray', d => (suggestedNeuronConnectionEnabledRef.current && isHighlightedLink(d)) ? '1 7' : (d.status === 'confirmed' ? '0' : (d.type === 'SHADOW_LINK' ? '1 7' : '0')))
      .attr('stroke-width', d => Math.max(1.25, 1.3 + (Number(d.score) || 0.2) * 2.1 + ((suggestedNeuronConnectionEnabledRef.current && isHighlightedLink(d)) ? 1.15 : 0)))
      .style('opacity', d => (suggestedNeuronConnectionEnabledRef.current && isHighlightedLink(d)) ? 0.8 : baseLinkOpacity(d))
      .style('filter', d => (suggestedNeuronConnectionEnabledRef.current && isHighlightedLink(d)) ? 'drop-shadow(0 0 10px rgba(79, 131, 209, 0.42))' : 'none')
      .style('pointer-events', d => d.status === 'confirmed' ? 'stroke' : 'none')
      .style('cursor', d => d.status === 'confirmed' ? 'pointer' : 'default');
  }, [highlightedPairKeys, data, suggestedNeuronConnectionEnabled]);

  useEffect(() => {
    if (!svgRef.current) return;
    const links = d3.select(svgRef.current).selectAll('.links line');
    if (links.empty()) return;

    links.classed('edge-pulse', d => {
      if (!suggestedNeuronConnectionEnabled || !hoveredQuizPairKey) return false;
      const sourceId = getEndpointId(d.source);
      const targetId = getEndpointId(d.target);
      return normalizePairKey(sourceId, targetId) === hoveredQuizPairKey;
    });
  }, [hoveredQuizPairKey, suggestedNeuronConnectionEnabled]);

  useEffect(() => {
    if (!svgRef.current) return;

    const svg = d3.select(svgRef.current);
    const viewport = svg.select('g.viewport');
    const overlayHost = viewport.empty() ? svg : viewport;
    const overlay = overlayHost.selectAll('g.quiz-hover-overlay').data([null]).join('g').attr('class', 'quiz-hover-overlay');
    overlay.selectAll('*').remove();

    if (!suggestedNeuronConnectionEnabled || !highlightedPairKeys || !highlightedPairKeys.size) return;

    const existingPairs = new Set(
      data.links.map((link) => normalizePairKey(getEndpointId(link.source), getEndpointId(link.target)))
    );

    const shortenLine = (source, target, radiusOffset) => {
      const dx = (target.x || 0) - (source.x || 0);
      const dy = (target.y || 0) - (source.y || 0);
      const distance = Math.max(1, Math.sqrt(dx * dx + dy * dy));
      const offsetX = (dx / distance) * radiusOffset;
      const offsetY = (dy / distance) * radiusOffset;
      return {
        x1: (source.x || 0) + offsetX,
        y1: (source.y || 0) + offsetY,
        x2: (target.x || 0) - offsetX,
        y2: (target.y || 0) - offsetY,
      };
    };

    [...highlightedPairKeys].forEach((pairKey) => {
      if (!pairKey || existingPairs.has(pairKey)) return;

      const [sourceId, targetId] = pairKey.split('::');
      const source = nodePositionMapRef.current.get(sourceId) || null;
      const target = nodePositionMapRef.current.get(targetId) || null;
      if (!source || !target) return;
      const line = shortenLine(source, target, 18);

      const isHovered = hoveredQuizPairKey === pairKey;

      overlay.append('line')
        .attr('class', `edge-pulse-phantom${isHovered ? ' edge-pulse' : ''}`)
        .attr('x1', line.x1)
        .attr('y1', line.y1)
        .attr('x2', line.x2)
        .attr('y2', line.y2)
        .attr('stroke', ACTIVE_EDGE_BASE)
        .attr('stroke-dasharray', '1 7')
        .attr('stroke-width', 3.2)
        .attr('stroke-linecap', 'round')
        .attr('vector-effect', 'non-scaling-stroke')
        .style('opacity', isHovered ? 0.8 : 0.8)
        .style('filter', 'drop-shadow(0 0 10px rgba(79, 131, 209, 0.42))')
        .style('pointer-events', 'none');
    });
  }, [data, highlightedPairKeys, hoveredQuizPairKey, suggestedNeuronConnectionEnabled]);

  useEffect(() => {
    if (!svgRef.current) return;
    d3.select(svgRef.current)
      .selectAll('g.node')
      .attr('opacity', d => selectedNodes.includes(d.id) ? 1 : (nodeOpacityMapRef.current.get(d.id) || 0.4))
      .select('circle')
      .attr('fill', d => selectedNodes.includes(d.id) ? '#1d4ed8' : '#60a5fa');
  }, [selectedNodes]);

  const doZoom = (factor) => {
    if (!svgRef.current || !zoomBehavior) return;
    const svg = d3.select(svgRef.current);
    svg.transition().duration(200).call(zoomBehavior.scaleBy, factor);
  };

  const selectedNodeA = selectedNodes && selectedNodes.length >= 1 ? data.nodes.find(n => n.id === selectedNodes[0]) : null;
  const selectedNodeB = selectedNodes && selectedNodes.length >= 2 ? data.nodes.find(n => n.id === selectedNodes[1]) : null;
  const selectedSimilarity = pairSimilarity ? pairSimilarity.score.toFixed(3) : '...';
  const hasGraphNodes = Boolean(data?.nodes?.length);

  return (
    <div ref={containerRef} className="border rounded shadow-lg p-0 bg-white relative h-full">
      <div className="absolute right-4 top-4 z-30 w-40 max-w-[calc(100%-2rem)]">
        <details className="relative">
          <summary className="list-none cursor-pointer rounded-2xl border border-slate-200 bg-white px-4 py-2 text-sm font-semibold text-slate-700 shadow-sm hover:bg-slate-50">
            {selectedCategory || 'Select category'}
          </summary>
          <div className="absolute right-0 mt-2 w-40 rounded-2xl border border-slate-200 bg-white p-2 shadow-xl z-30">
            <button
              type="button"
              onClick={() => onCategoryChange?.('')}
              className="mb-2 w-full rounded-xl border border-dashed border-slate-200 px-3 py-2 text-left text-sm text-slate-500 hover:bg-slate-50"
            >
              Hide graph
            </button>
            <div className="max-h-64 overflow-y-auto space-y-1">
              {availableCategories.length > 0 ? availableCategories.map((category) => (
                <button
                  key={category}
                  type="button"
                  onClick={() => onCategoryChange?.(category)}
                  className={`w-full rounded-xl px-3 py-2 text-left text-sm transition-colors ${selectedCategory === category ? 'bg-blue-50 text-blue-700' : 'hover:bg-slate-50 text-slate-700'}`}
                >
                  {category}
                </button>
              )) : (
                <p className="px-3 py-2 text-sm text-slate-500">No categories yet. Add papers with categories first.</p>
              )}
            </div>
          </div>
        </details>
      </div>

      {!selectedCategory && (
        <div className="absolute inset-0 z-10 flex items-center justify-center pointer-events-none px-6">
          <div className="rounded-3xl border border-dashed border-slate-200 bg-white/90 px-6 py-5 text-center shadow-sm backdrop-blur-sm max-w-md">
            <p className="text-sm font-semibold text-slate-800">Select a category to display its graph</p>
            <p className="mt-2 text-xs text-slate-500">Use the selector in the top-right corner to switch categories.</p>
          </div>
        </div>
      )}

      {selectedCategory && !hasGraphNodes && (
        <div className="absolute inset-0 z-10 flex items-center justify-center pointer-events-none px-6">
          <div className="rounded-3xl border border-dashed border-slate-200 bg-white/90 px-6 py-5 text-center shadow-sm backdrop-blur-sm max-w-md">
            <p className="text-sm font-semibold text-slate-800">No nodes yet for this category</p>
            <p className="mt-2 text-xs text-slate-500">Add papers to this category to populate the graph.</p>
          </div>
        </div>
      )}

      <div className="absolute right-4 bottom-4 flex flex-col gap-2 z-20">
        <button onClick={() => doZoom(1.2)} className="bg-white p-2 rounded shadow">+</button>
        <button onClick={() => doZoom(0.8)} className="bg-white p-2 rounded shadow">-</button>
      </div>

      {hoverConnection && (
        <button
          onMouseEnter={() => {
            if (hoverClearTimerRef.current) {
              clearTimeout(hoverClearTimerRef.current);
              hoverClearTimerRef.current = null;
            }
          }}
          onMouseLeave={() => {
            scheduleClearHoverConnection();
          }}
          onClick={() => {
            onConnectSelected?.(hoverConnection.source, hoverConnection.target);
            clearHoverConnection();
          }}
          className="absolute z-40 rounded-full border border-blue-200 bg-white px-3 py-2 text-xs font-semibold text-blue-700 shadow-lg hover:border-blue-300 hover:bg-blue-50"
          style={{
            left: Math.max(12, hoverConnection.x),
            top: Math.max(12, hoverConnection.y),
            transform: 'translate(12px, -100%)',
          }}
        >
          View Connection
        </button>
      )}

      {(selectedNodeA || selectedNodeB) && (
      <div
      className="absolute left-4 top-4 z-30"
      style={{
        background: '#ffffff',
        border: '1px solid #cbd5e1',
        borderRadius: 12,
        padding: '12px 14px',
        boxShadow: '0 4px 12px rgba(2,6,23,0.06)',
        minWidth: selectedNodeB ? 420 : 260,
        maxWidth: selectedNodeB ? 560 : 420,
        width: selectedNodeB ? 420 : 320,
        resize: 'horizontal',
        overflow: 'hidden',
      }}>

        {!selectedNodeB && selectedNodeA && (
          <>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 5 }}>
              <span style={{ fontSize: 11, fontWeight: 500, color: 'var(--color-text-info)', letterSpacing: '0.05em' }}>Paper Info</span>
            </div>
            <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: 8 }}>
              <div style={{ minWidth: 0 }}>
                <div style={{ fontSize: 15, fontWeight: 700, color: 'var(--color-text-primary)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                  {selectedNodeA.title}
                </div>
                <div style={{ fontSize: 11, color: '#2563eb', marginTop: 3, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                  {(selectedNodeA.keywords || []).join(', ')}
                </div>
              </div>
              <button onClick={() => onNodeDelete?.(selectedNodeA)}
                style={{ fontSize: 11, fontWeight: 600, padding: '4px 12px', borderRadius: 99,
                        background: '#fff1f2', color: '#e11d48', border: '1px solid #fecdd3', cursor: 'pointer' }}>
                Delete
              </button>
            </div>
            <div
              onClick={() => onSummaryClick?.(selectedNodeA)}
              style={{
                marginTop: 5,
                fontSize: 13,
                color: '#334155',
                lineHeight: 1.6,
                display: '-webkit-box',
                WebkitLineClamp: 3,
                WebkitBoxOrient: 'vertical',
                overflow: 'hidden',
                cursor: onSummaryClick ? 'pointer' : 'default',
              }}
            >
              {selectedNodeA.summary}
            </div>
          </>
        )}

        {selectedNodeA && selectedNodeB && (
          <>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 5 }}>
              <span style={{ fontSize: 11, fontWeight: 500, color: 'var(--color-text-info)', letterSpacing: '0.05em' }}>Connection</span>
              <span style={{ fontSize: 11, color: 'var(--color-text-secondary)' }}>Similarity {selectedSimilarity}</span>
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: '1fr auto 1fr', gap: 8, alignItems: 'start' }}>
              <div style={{ minWidth: 0 }}>
                <div style={{ fontSize: 15, fontWeight: 700, color: 'var(--color-text-primary)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{selectedNodeA.title}</div>
                <div style={{ fontSize: 11, color: '#2563eb', marginTop: 2, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{(selectedNodeA.keywords || []).join(', ')}</div>
                <div
                  onClick={() => onSummaryClick?.(selectedNodeA)}
                  style={{
                    marginTop: 5,
                    fontSize: 12,
                    color: 'var(--color-text-secondary)',
                    lineHeight: 1.6,
                    display: '-webkit-box',
                    WebkitLineClamp: 3,
                    WebkitBoxOrient: 'vertical',
                    overflow: 'hidden',
                    cursor: onSummaryClick ? 'pointer' : 'default',
                  }}
                >
                  {selectedNodeA.summary}
                </div>
              </div>

              <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', paddingTop: 14, gap: 4 }}>
                <div style={{ width: 1, height: 12, background: 'var(--color-border-secondary)' }}></div>
                <span style={{ fontSize: 10, color: 'var(--color-text-tertiary)' }}>vs</span>
                <div style={{ width: 1, height: 12, background: 'var(--color-border-secondary)' }}></div>
              </div>

              <div style={{ minWidth: 0, textAlign: 'right' }}>
                <div style={{ fontSize: 15, fontWeight: 700, color: 'var(--color-text-primary)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{selectedNodeB.title}</div>
                <div style={{ fontSize: 11, color: '#2563eb', marginTop: 2, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{(selectedNodeB.keywords || []).join(', ')}</div>
                <div
                  onClick={() => onSummaryClick?.(selectedNodeB)}
                  style={{
                    marginTop: 5,
                    fontSize: 12,
                    color: 'var(--color-text-secondary)',
                    lineHeight: 1.6,
                    display: '-webkit-box',
                    WebkitLineClamp: 3,
                    WebkitBoxOrient: 'vertical',
                    overflow: 'hidden',
                    cursor: onSummaryClick ? 'pointer' : 'default',
                  }}
                >
                  {selectedNodeB.summary}
                </div>
              </div>
            </div>

            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginTop: 12, gap: 6 }}>
              <button onClick={() => onNodeDelete?.(selectedNodeA)}
                style={{ fontSize: 11, fontWeight: 600, padding: '4px 12px', borderRadius: 99,
                        background: '#fff1f2', color: '#e11d48', border: '1px solid #fecdd3', cursor: 'pointer' }}>
                Delete A
              </button>
              <button onClick={() => onConnectSelected?.(selectedNodeA, selectedNodeB)}
                style={{ fontSize: 13, fontWeight: 600, padding: '4px 16px', borderRadius: 99, background: '#eff6ff', color: '#2563eb', border: '1px solid #bfdbfe', cursor: 'pointer' }}>
                {connectionButtonLabel}
              </button>
              <button onClick={() => onNodeDelete?.(selectedNodeB)}
                style={{ fontSize: 11, fontWeight: 600, padding: '4px 12px', borderRadius: 99,
                        background: '#fff1f2', color: '#e11d48', border: '1px solid #fecdd3', cursor: 'pointer' }}>
                Delete B
              </button>
            </div>
          </>
        )}
      </div>
    )}

      <svg ref={svgRef} style={{ width: '100%', height: '100%' }}></svg>
    </div>
  );
};

export default GraphComponent;
