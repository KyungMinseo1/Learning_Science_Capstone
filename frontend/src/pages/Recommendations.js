import React, { useEffect, useState, useCallback } from 'react';
import axios from 'axios';
import GraphComponent from '../components/GraphComponent';

const CATEGORY_STORAGE_KEY = 'papermind.recommendations.selectedCategory';

const Recommendations = () => {
  const [graph, setGraph] = useState({ nodes: [], links: [] });
  const [availableCategories, setAvailableCategories] = useState([]);
  const [selectedCategory, setSelectedCategory] = useState(() => window.sessionStorage.getItem(CATEGORY_STORAGE_KEY) || '');
  const [selected, setSelected] = useState([]);
  const [loading, setLoading] = useState(false);
  const [results, setResults] = useState([]);
  const [selectedResultId, setSelectedResultId] = useState(null);
  const [detailOverlay, setDetailOverlay] = useState(null);
  const [notice, setNotice] = useState('');
  const [userSettings, setUserSettings] = useState({ final_k: 10 });
  const [addModal, setAddModal] = useState(null);
  const [addCategories, setAddCategories] = useState('');
  const [manualKeywords, setManualKeywords] = useState([{ keyword: '', importance: '' }]);

  const normalizeKeywords = (value) => {
    if (Array.isArray(value)) return value.filter(Boolean).map((v) => String(v));
    if (typeof value === 'string') {
      try {
        const parsed = JSON.parse(value);
        if (Array.isArray(parsed)) return parsed.filter(Boolean).map((v) => String(v));
      } catch (e) {}
      return value.split(',').map((v) => v.trim()).filter(Boolean);
    }
    return [];
  };

  const fetchCategories = useCallback(async () => {
    try {
      const res = await axios.get('/api/user/categories');
      setAvailableCategories(res.data?.categories || []);
    } catch (e) {
      console.error('Failed to load categories', e);
    }
  }, []);

  const fetchGraph = useCallback(async (category = selectedCategory) => {
    try {
      if (!category) {
        setGraph({ nodes: [], links: [], available_categories: [], selected_category: '' });
        return;
      }
      const res = await axios.get('/api/graph', { params: { category } });
      const raw = res.data || { nodes: [], links: [] };
      const nodeIds = new Set((raw.nodes || []).map(n => n.id));
      const safeLinks = (raw.links || []).filter(l => {
        const src = typeof l.source === 'object' ? l.source?.id : l.source;
        const tgt = typeof l.target === 'object' ? l.target?.id : l.target;
        return nodeIds.has(src) && nodeIds.has(tgt);
      });
      setGraph({ ...raw, links: safeLinks });
      setAvailableCategories(prev => raw.available_categories || prev);
    } catch (e) {
      console.error('Failed to load graph', e);
    }
  }, [selectedCategory]);

  const fetchUserSettings = useCallback(async () => {
    try {
      const res = await axios.get('/api/user/settings');
      setUserSettings((prev) => ({ ...prev, ...(res.data || {}) }));
    } catch (e) {
      console.error('Failed to load user settings', e);
    }
  }, []);

  useEffect(() => {
    fetchCategories();
    fetchUserSettings();
  }, [fetchCategories, fetchUserSettings]);

  useEffect(() => {
    window.sessionStorage.setItem(CATEGORY_STORAGE_KEY, selectedCategory || '');
    setSelected([]);
    setSelectedResultId(null);
    setDetailOverlay(null);
    setNotice('');
    fetchGraph(selectedCategory);
  }, [selectedCategory, fetchGraph]);

  useEffect(() => {
    const handleSettingsUpdated = () => fetchUserSettings();
    window.addEventListener('app-settings-updated', handleSettingsUpdated);
    return () => window.removeEventListener('app-settings-updated', handleSettingsUpdated);
  }, [fetchUserSettings]);

  const loadLatestRecommendation = useCallback(async (paperId) => {
    if (!paperId) return false;
    try {
      const res = await axios.get('/api/recommend/latest', {
        params: { paper_id: paperId, method: 'single' },
      });
      const candidates = res.data?.candidates || [];
      if (!candidates.length) {
        setResults([]);
        setSelectedResultId(null);
        return false;
      }
      setResults(candidates);
      setSelectedResultId(null);
      return true;
    } catch (e) {
      setResults([]);
      setSelectedResultId(null);
      return false;
    }
  }, []);

  const onNodeClick = (node, shift) => {
    setNotice('');
    setSelectedResultId(null);
    setDetailOverlay(null);
    if (shift) {
      setSelected((prev) => {
        if (prev.find((p) => p.id === node.id)) return prev.filter((p) => p.id !== node.id);
        return [...prev, node];
      });
    } else {
      setSelected([node]);
    }
  };

  useEffect(() => {
    let cancelled = false;
    const run = async () => {
      if (selected.length !== 1) return;
      const paperId = selected[0]?.id;
      if (!paperId) return;
      const loaded = await loadLatestRecommendation(paperId);
      if (cancelled) return;
      if (!loaded) {
        setResults([]);
        setSelectedResultId(null);
      }
    };
    run();
    return () => {
      cancelled = true;
    };
  }, [selected, loadLatestRecommendation]);

  const clearSelection = () => {
    setSelected([]);
    setSelectedResultId(null);
    setDetailOverlay(null);
    setNotice('');
  };

  const runRecommend = async () => {
    if (!selected.length) return;
    setNotice('');
    setLoading(true);
    try {
      if (selected.length === 1) {
        const res = await axios.post('/api/recommend/single', {
          paper_id: selected[0].id,
          final_k: userSettings.final_k || 10,
        });
        const candidates = res.data.candidates || [];
        setResults(candidates);
        setSelectedResultId(null);
      } else {
        setNotice('Dual recommendation is still being implemented.');
      }
    } catch (e) {
      console.error('Recommend failed', e);
      setNotice('추천 실행에 실패했습니다.');
    } finally {
      setLoading(false);
    }
  };

  const activeDetailItem = selected.length === 1 ? selected[0] : null;

  const addKeywordRow = () => {
    if (manualKeywords.length >= 5) return;
    setManualKeywords(prev => [...prev, { keyword: '', importance: '' }]);
  };

  const removeKeywordRow = (index) => {
    setManualKeywords(prev => prev.filter((_, i) => i !== index));
  };

  const updateKeywordRow = (index, field, value) => {
    setManualKeywords(prev => prev.map((item, i) => i === index ? { ...item, [field]: value } : item));
  };

  const openAddModal = (paper) => {
    setAddModal(paper);
    setAddCategories('');
    setManualKeywords([{ keyword: '', importance: '' }]);
  };

  const addRecommendedPaper = async () => {
    if (!addModal) return;
    try {
      setNotice('');
      const validKeywords = manualKeywords.filter(k => k.keyword.trim());
      const payload = {
        title: addModal.title,
        text: addModal.abstract || addModal.tldr || '',
        categories: addCategories
          ? addCategories.split(',').map(c => c.trim()).filter(Boolean)
          : [],
        manual_keywords: validKeywords.map(k => k.keyword.trim()),
        manual_keyword_importance: validKeywords.map(k => parseFloat(k.importance) || 0.5),
      };
      await axios.post('/api/papers', payload);
      setNotice('Added paper to your graph. Refreshing...');
      setAddModal(null);
      await fetchGraph();
    } catch (e) {
      console.error('Failed to add recommended paper', e);
      setNotice('Failed to add paper.');
    }
  };

  const openDetailOverlay = (paper) => {
    setSelectedResultId(paper?.paper_id || null);
    setDetailOverlay(paper || null);
  };

  const closeDetailOverlay = () => {
    setDetailOverlay(null);
  };

  return (
    <div className="space-y-6 relative">
      <style>{`
        @keyframes softPulse {
          0%, 100% {
            box-shadow: 0 0 0 0 rgba(37, 99, 235, 0.00), 0 0 0 0 rgba(59, 130, 246, 0.00);
            transform: translateY(0) scale(1);
          }
          50% {
            box-shadow: 0 0 0 8px rgba(37, 99, 235, 0.18), 0 0 18px rgba(59, 130, 246, 0.28);
            transform: translateY(-1px) scale(1.02);
          }
        }
        @keyframes edgePulse {
          0%, 100% { opacity: 0.38; }
          50% { opacity: 1; }
        }
        .links line.edge-pulse,
        .quiz-hover-overlay line.edge-pulse {
          stroke: #4f83d1;
          animation: edgePulse 1.2s ease-in-out infinite;
          will-change: opacity;
        }
      `}</style>

      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-2xl font-bold text-slate-900">Recommendations</h1>
          <p className="text-slate-500">Select a node in the graph to load previous recommendations. Click the Recommend button to run a new recommendation.</p>
        </div>
        <div className="flex items-center gap-3">
          <button
            onClick={() => fetchGraph(selectedCategory)}
            className="rounded-xl bg-blue-500 px-4 py-2 text-sm font-medium text-white shadow-md transition-all hover:scale-[1.02] hover:bg-blue-600 hover:shadow-lg"
          >
            Refresh Graph
          </button>

          <button
            onClick={clearSelection}
            className="rounded-xl border border-slate-200 bg-white px-4 py-2 text-sm font-medium text-slate-700 transition-all hover:border-blue-300 hover:text-blue-600"
          >
            Clear Selection
          </button>
        </div>
      </div>

      {notice && (
        <div className="rounded-xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-800">
          {notice}
        </div>
      )}

      <div className="flex flex-col xl:flex-row gap-6 items-stretch h-full min-h-0" style={{ height: 'min(80vh, 860px)' }}>
        <div className="flex-[1.35] min-w-0 h-full min-h-0">
          <div className="bg-white rounded-2xl shadow-sm border border-slate-100 overflow-hidden h-full min-h-0 flex items-stretch justify-center">
            {selectedCategory && graph.nodes.length > 0 ? (
              <div className="w-full h-full min-h-0">
                <GraphComponent
                  data={graph}
                  onNodeClick={onNodeClick}
                  selectedNodes={selected}
                  availableCategories={availableCategories}
                  selectedCategory={selectedCategory}
                  onCategoryChange={setSelectedCategory}
                  height={620}
                />
              </div>
            ) : (
              <div className="text-center p-8 flex flex-col items-center justify-center gap-3">
                <p className="text-slate-500 italic">
                  {selectedCategory
                    ? 'No nodes yet for this category. Add papers to this category to display its graph.'
                    : 'Select a category to display its graph.'}
                </p>
                {!selectedCategory && availableCategories.length > 0 && (
                  <div className="flex flex-wrap justify-center gap-2 max-w-xl">
                    {availableCategories.slice(0, 6).map((category) => (
                      <button
                        key={category}
                        onClick={() => setSelectedCategory(category)}
                        className="rounded-full border border-slate-200 bg-white px-3 py-1.5 text-sm font-medium text-slate-700 hover:bg-slate-50"
                      >
                        {category}
                      </button>
                    ))}
                  </div>
                )}
              </div>
            )}
          </div>
        </div>

        <div className="shrink-0 h-full min-h-0 transition-all duration-300 ease-in-out" style={{ width: 320, maxHeight: '100%' }}>
          <div className="space-y-3 h-full min-h-0 flex flex-col">
            <div className="rounded-2xl border border-slate-200 bg-white p-2.5 shadow-sm flex-shrink-0">
              {activeDetailItem ? (
                <div className="flex flex-col gap-2">
                <div className="min-w-0">
                  <p className="text-[11px] font-semibold text-blue-600 uppercase tracking-wider">Paper Info</p>
                  <p className="mt-1 text-base font-semibold text-slate-900 leading-snug">{activeDetailItem.title}</p>
                  {(activeDetailItem.keywords || []).length > 0 && (
                  <p className="mt-1 text-[11px] leading-5 text-blue-700">
                    {(activeDetailItem.keywords || []).slice(0, 8).join(', ')}
                  </p>
                  )}
                </div>
                <div className="flex items-center justify-center gap-2">
                  {activeDetailItem.paper_id && (
                  <button onClick={() => openAddModal(activeDetailItem)} className="rounded-full border border-slate-200 bg-white px-3 py-1.5 text-xs font-semibold text-slate-700 hover:bg-slate-50">
                    Add
                  </button>
                  )}
                  <button
                  onClick={runRecommend}
                  disabled={!selected.length || loading}
                  className="rounded-full bg-blue-600 px-3 py-1.5 text-xs font-semibold text-white hover:bg-blue-700 disabled:cursor-not-allowed disabled:bg-slate-300"
                  >
                  {loading ? 'Running...' : 'Recommend'}
                  </button>
                  </div>
                  </div>
              ) : (
                <div className="text-sm text-slate-500">
                Select a node or recommendation to see paper info.
                </div>
              )}
            </div>

            <div className="rounded-2xl bg-white border border-slate-100 p-3 shadow-sm h-full min-h-0 overflow-hidden flex flex-col">
              <div className="flex items-center justify-between gap-3 pb-3 border-b border-slate-100">
                <div className="min-w-0">
                  <h2 className="text-lg font-bold text-slate-900">Recommended Papers</h2>
                  <p className="text-xs text-slate-400 mt-1 truncate">Latest candidate set for the selected paper</p>
                </div>
                <span className="rounded-full bg-blue-50 px-2.5 py-1 text-xs font-medium text-blue-700">
                  {results.length}
                </span>
              </div>

              <div className="mt-3 flex-1 min-h-0 overflow-hidden">
              {results.length === 0 ? (
                <div className="h-full rounded-2xl border border-dashed border-slate-200 bg-slate-50 p-4 flex items-center justify-center text-center">
                  <p className="text-sm font-medium text-slate-600">No recommendations yet.</p>
                </div>
              ) : (
                <div className="space-y-2.5 h-full min-h-0 overflow-y-auto pr-1 pb-1">
                  {results.map((r) => (
                    <div
                      key={r.paper_id}
                      className="w-full text-left rounded-2xl border border-slate-200 bg-white p-2.5 shadow-sm hover:border-blue-500 hover:shadow-md transition-all"
                    >
                      <div className="flex items-start justify-between gap-3">
                        <div className="min-w-0 flex-1">
                          <p className="text-[11px] font-semibold text-blue-600 uppercase tracking-wider">#{r.rank}</p>
                          <p className="font-semibold text-slate-900 mt-1 leading-snug truncate">{r.title}</p>
                          <p className="text-[11px] text-slate-500 mt-1.5">{r.year || 'Unknown year'} · score {r.score}</p>
                          <p className="text-[11px] text-blue-700 mt-1.5 leading-5 truncate">{normalizeKeywords(r.keywords).slice(0, 6).join(', ') || 'No keywords available'}</p>
                        </div>
                        <div className="flex shrink-0 flex-col items-end gap-2">
                          <button
                            onClick={() => openDetailOverlay(r)}
                            className={`rounded-full px-2.5 py-1 text-xs font-medium ${selectedResultId === r.paper_id ? 'bg-blue-600 text-white' : 'bg-blue-50 text-blue-700 hover:bg-blue-100'}`}
                          >
                            Detail
                          </button>
                          <button
                            onClick={() => openAddModal(r)}
                            className="rounded-full border border-slate-200 bg-white px-2.5 py-1 text-xs font-semibold text-slate-700 hover:bg-slate-50"
                          >
                            Add
                          </button>
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              )}
              </div>
            </div>
          </div>
        </div>
      </div>

      {detailOverlay && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center p-4"
          style={{ background: 'rgba(0, 0, 0, 0.58)' }}
          onClick={closeDetailOverlay}
        >
          <div
            className="w-full max-w-3xl rounded-2xl bg-white border border-slate-200 shadow-2xl overflow-hidden"
            onClick={(event) => event.stopPropagation()}
          >
            <div className="flex items-start justify-between gap-4 px-6 py-5 border-b border-slate-100 bg-slate-50">
              <div className="min-w-0">
                <p className="text-xs font-semibold uppercase tracking-widest text-blue-600">Paper Details</p>
                <h3 className="mt-1 text-xl font-bold text-slate-900 break-words">{detailOverlay.title}</h3>
              </div>
              <button
                onClick={closeDetailOverlay}
                className="shrink-0 rounded-full border border-slate-200 bg-white px-3 py-1.5 text-sm font-medium text-slate-700 hover:border-blue-300 hover:text-blue-700 transition-colors"
              >
                Close
              </button>
            </div>

            <div className="px-6 py-5 space-y-5 max-h-[72vh] overflow-y-auto">
              <div>
                <p className="text-xs font-semibold uppercase tracking-widest text-slate-400">Keywords</p>
                <div className="mt-2 flex flex-wrap gap-2">
                  {normalizeKeywords(detailOverlay.keywords).length > 0 ? (
                    normalizeKeywords(detailOverlay.keywords).map((keyword) => (
                      <span key={keyword} className="rounded-full bg-blue-50 px-3 py-1 text-sm font-medium text-blue-700">
                        {keyword}
                      </span>
                    ))
                  ) : (
                    <span className="text-sm text-slate-500">No keywords available.</span>
                  )}
                </div>
              </div>

              <div>
                <p className="text-xs font-semibold uppercase tracking-widest text-slate-400">Summary</p>
                <p className="mt-2 text-sm leading-7 text-slate-700 whitespace-pre-wrap">
                  {detailOverlay.abstract || detailOverlay.tldr || detailOverlay.summary || 'No summary available.'}
                </p>
              </div>
            </div>
          </div>
        </div>
      )}

      {addModal && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center p-4"
          style={{ background: 'rgba(0,0,0,0.58)' }}
          onClick={() => setAddModal(null)}
        >
          <div
            className="w-full max-w-md rounded-2xl bg-white border border-slate-200 shadow-2xl overflow-hidden"
            onClick={e => e.stopPropagation()}
          >
            <div className="px-6 py-5 border-b border-slate-100 bg-slate-50">
              <p className="text-xs font-semibold uppercase tracking-widest text-blue-600">Add Paper</p>
              <h3 className="mt-1 text-base font-bold text-slate-900 break-words">{addModal.title}</h3>
            </div>
            <div className="px-6 py-5 space-y-5">
              {/* Categories */}
              <div>
                <label className="block text-xs font-semibold text-slate-500 uppercase tracking-wider mb-1.5">
                  Categories <span className="normal-case font-normal">(comma-separated)</span>
                </label>
                <input
                  className="w-full rounded-xl border border-slate-200 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-300"
                  placeholder="e.g. NLP, Reinforcement Learning"
                  value={addCategories}
                  onChange={e => setAddCategories(e.target.value)}
                />
              </div>

              {/* Manual Keywords */}
              <div>
                <div className="flex items-center justify-between gap-3 mb-2">
                  <label className="block text-sm font-medium text-slate-700">Manual Keywords</label>
                  <button
                    type="button"
                    onClick={addKeywordRow}
                    disabled={manualKeywords.length >= 5}
                    className="text-xs font-semibold text-blue-600 hover:text-blue-700 disabled:text-slate-300"
                  >
                    Add keyword
                  </button>
                </div>
                <div className="space-y-3">
                  {manualKeywords.map((item, index) => (
                    <div key={index} className="grid grid-cols-[minmax(0,1fr)_120px_auto] gap-2">
                      <input
                        className="w-full p-2.5 border border-slate-200 rounded-lg text-sm outline-none focus:ring-2 focus:ring-blue-300"
                        placeholder="Keyword"
                        value={item.keyword}
                        onChange={e => updateKeywordRow(index, 'keyword', e.target.value)}
                      />
                      <input
                        type="number" step="0.01" min="0" max="1"
                        className="w-full p-2.5 border border-slate-200 rounded-lg text-sm outline-none focus:ring-2 focus:ring-blue-300"
                        placeholder="Importance"
                        value={item.importance}
                        onChange={e => updateKeywordRow(index, 'importance', e.target.value)}
                      />
                      <button
                        type="button"
                        onClick={() => removeKeywordRow(index)}
                        className="rounded-lg border border-slate-200 px-3 py-2 text-sm text-slate-600 hover:bg-slate-50"
                      >
                        ✕
                      </button>
                    </div>
                  ))}
                </div>
                <p className="text-xs text-slate-500 mt-2">
                  Up to 5 keyword/importance pairs. AI will generate the remaining keywords after these.
                </p>
              </div>
            </div>
            <div className="flex justify-end gap-2 px-6 py-4 border-t border-slate-100">
              <button
                onClick={() => setAddModal(null)}
                className="rounded-full border border-slate-200 px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50"
              >
                Cancel
              </button>
              <button
                onClick={addRecommendedPaper}
                className="rounded-full bg-blue-600 px-4 py-2 text-sm font-semibold text-white hover:bg-blue-700"
              >
                Add to Graph
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default Recommendations;
