import React, { useCallback, useEffect, useMemo, useState } from 'react';
import axios from 'axios';
import GraphComponent from '../components/GraphComponent';
import QuizComponent from '../components/QuizComponent';
import { Sparkles } from 'lucide-react';

const normalizePairKey = (paper1Id, paper2Id) => [paper1Id, paper2Id].filter(Boolean).sort().join('::');
const CATEGORY_STORAGE_KEY = 'papermind.graph.selectedCategory';
const QUIZ_STORAGE_KEY = 'papermind.graph.quizBundle';

const GraphPage = () => {
  const [data, setData] = useState({ nodes: [], links: [] });
  const [quizBundle, setQuizBundle] = useState({ anchor: null, items: [] });
  const [availableCategories, setAvailableCategories] = useState([]);
  const [selectedCategory, setSelectedCategory] = useState(() => window.sessionStorage.getItem(CATEGORY_STORAGE_KEY) || '');
  const [loading, setLoading] = useState(true);
  const [activeQuiz, setActiveQuiz] = useState(null);
  const [question, setQuestion] = useState('');
  const [loadingQuestion, setLoadingQuestion] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [now, setNow] = useState(Date.now());
  const [selectedNodes, setSelectedNodes] = useState([]);
  const [pairSimilarity, setPairSimilarity] = useState(null);
  const [connectionPair, setConnectionPair] = useState(null);
  const [connectionQuestion, setConnectionQuestion] = useState('');
  const [connectionOpen, setConnectionOpen] = useState(false);
  const [connectionInitialValues, setConnectionInitialValues] = useState(null);
  const [selectedRelationship, setSelectedRelationship] = useState(null);
  const [quizCollapsed, setQuizCollapsed] = useState(false);
  const [paperOverlay, setPaperOverlay] = useState(null);
  const [suggestedNeuronConnectionEnabled, setSuggestedNeuronConnectionEnabled] = useState(true);
  const [hoveredQuizPairKey, setHoveredQuizPairKey] = useState(null);

  const fetchCategories = useCallback(async () => {
    try {
      const res = await axios.get('/api/user/categories');
      const categories = res.data?.categories || [];
      setAvailableCategories(categories);
      return categories;
    } catch (err) {
      console.error('Failed to fetch categories', err);
      return [];
    }
  }, []);

  const fetchGraphData = useCallback(async (category = selectedCategory) => {
    try {
      if (!category) {
        setData({ nodes: [], links: [], available_categories: [], selected_category: '' });
        return;
      }
      const graphRes = await axios.get('/api/graph', {
        params: { category },
      });
      const raw = graphRes.data || { nodes: [], links: [] };
      const nodeIds = new Set((raw.nodes || []).map(n => n.id));
      const safeLinks = (raw.links || []).filter(l => {
        const src = typeof l.source === 'object' ? l.source?.id : l.source;
        const tgt = typeof l.target === 'object' ? l.target?.id : l.target;
        return nodeIds.has(src) && nodeIds.has(tgt);
      });
      setData({ ...raw, links: safeLinks });
      setAvailableCategories(raw.available_categories || []);
    } catch (err) {
      console.error('Failed to fetch graph data', err);
    }
  }, [selectedCategory]);

  const fetchQuizBundle = useCallback(async () => {
    try {
      const quizRes = await axios.get('/api/quiz');
      const nextBundle = quizRes.data || { anchor: null, items: [] };
      setQuizBundle(nextBundle);
      window.sessionStorage.setItem(QUIZ_STORAGE_KEY, JSON.stringify(nextBundle));
      return nextBundle;
    } catch (err) {
      console.error('Failed to fetch quiz bundle', err);
      return { anchor: null, items: [] };
    }
  }, []);

  const refreshAndOpenQuiz = async () => {
    try {
      await axios.post('/api/quiz/refresh');
      await fetchGraphData();
      await fetchQuizBundle(true);
    } catch (err) {
      console.error('Failed to refresh and open quiz', err);
    }
  };

  useEffect(() => {
    const boot = async () => {
      await fetchCategories();
      await fetchQuizBundle();
      setLoading(false);
    };

    boot();
    const timer = setInterval(() => setNow(Date.now()), 1000);
    const handleSettingsUpdated = () => {
      fetchCategories();
    };
    window.addEventListener('app-settings-updated', handleSettingsUpdated);
    return () => {
      clearInterval(timer);
      window.removeEventListener('app-settings-updated', handleSettingsUpdated);
    };
  }, [fetchCategories, fetchQuizBundle]);

  useEffect(() => {
    window.sessionStorage.setItem(CATEGORY_STORAGE_KEY, selectedCategory || '');
    setSelectedNodes([]);
    setPairSimilarity(null);
    setSelectedRelationship(null);
    setPaperOverlay(null);
    if (selectedCategory) {
      fetchGraphData(selectedCategory);
    } else {
      setData({ nodes: [], links: [], available_categories: [], selected_category: '' });
    }
  }, [fetchGraphData, selectedCategory]);

  const openQuiz = async (quiz) => {
    setActiveQuiz(quiz);
    setQuestion('');
    setLoadingQuestion(true);
    try {
      const res = await axios.post('/api/quiz/question', {
        paper1_id: quiz.paper1_id,
        paper2_id: quiz.paper2_id,
      });
      setQuestion(res.data?.question || 'What are the commonalities and differences between these two papers, and how would you define their relationship?');
    } catch (err) {
      console.error('Failed to generate quiz question', err);
      setQuestion('What are the commonalities and differences between these two papers, and how would you define their relationship?');
    } finally {
      setLoadingQuestion(false);
    }
  };

  const handleNodeClick = (node, shiftKey) => {
    if (shiftKey) {
      setSelectedNodes(prev => {
        const ids = Array.from(prev);
        if (ids.includes(node.id)) {
          return ids.filter(x => x !== node.id);
        }
        ids.push(node.id);
        return ids.slice(-2);
      });
    } else {
      setSelectedNodes([node.id]);
    }
  };

  useEffect(() => {
    let cancelled = false;

    const loadSimilarity = async () => {
      if (selectedNodes.length !== 2) {
        setPairSimilarity(null);
        return;
      }

      try {
        const res = await axios.get('/api/graph/similarity', {
          params: {
            paper1_id: selectedNodes[0],
            paper2_id: selectedNodes[1],
          },
        });
        if (!cancelled) {
          setPairSimilarity(res.data || null);
        }
      } catch (err) {
        console.error('Failed to load pair similarity', err);
        if (!cancelled) setPairSimilarity(null);
      }
    };

    loadSimilarity();

    return () => {
      cancelled = true;
    };
  }, [selectedNodes]);

  useEffect(() => {
    let cancelled = false;

    const loadRelationship = async () => {
      if (selectedNodes.length !== 2) {
        setSelectedRelationship(null);
        return;
      }

      try {
        const res = await axios.get('/api/graph/relationship', {
          params: {
            paper1_id: selectedNodes[0],
            paper2_id: selectedNodes[1],
          },
        });
        if (!cancelled) {
          setSelectedRelationship(res.data && Object.keys(res.data).length ? res.data : null);
        }
      } catch (err) {
        console.error('Failed to load existing relationship', err);
        if (!cancelled) setSelectedRelationship(null);
      }
    };

    loadRelationship();

    return () => {
      cancelled = true;
    };
  }, [selectedNodes]);

  const handleBackgroundClick = () => {
    setSelectedNodes([]);
    setPairSimilarity(null);
    setSelectedRelationship(null);
  };

  const handleQuizHover = (paper1Id, paper2Id) => {
    setHoveredQuizPairKey(normalizePairKey(paper1Id, paper2Id));
  };

  const clearQuizHover = () => {
    setHoveredQuizPairKey(null);
  };

  const handleNodeDelete = async (node) => {
    if (!window.confirm(`Delete paper "${node.title}"? This will remove relations and related quiz slots.`)) return;
    try {
      await axios.delete(`/api/papers/${node.id}`);
      await fetchGraphData();
      setSelectedNodes([]);
    } catch (err) {
      console.error('Failed to delete paper', err);
      alert('Delete failed');
    }
  };

  const handleSummaryClick = (node) => {
    if (!node) return;
    setPaperOverlay(node);
  };

  const closePaperOverlay = () => {
    setPaperOverlay(null);
  };

  const handleConnectSelected = async (nodeA, nodeB) => {
    if (!nodeA || !nodeB) return;
    setConnectionPair({ nodeA, nodeB });
    setConnectionQuestion('');
    setConnectionOpen(true);
    setLoadingQuestion(true);
    setConnectionInitialValues(null);

    const pairMatchesSelected = selectedRelationship && (
      (selectedRelationship.paper1_id === nodeA.id && selectedRelationship.paper2_id === nodeB.id) ||
      (selectedRelationship.paper1_id === nodeB.id && selectedRelationship.paper2_id === nodeA.id)
    );

    if (pairMatchesSelected) {
      setConnectionQuestion(selectedRelationship.question || 'How would you define the relationship between these two papers?');
      setConnectionInitialValues({
        commonalities: selectedRelationship.commonalities || '',
        differences: selectedRelationship.differences || '',
        description: selectedRelationship.description || '',
        relType: selectedRelationship.rel_type || 'RELATED_TO',
        question: selectedRelationship.question || '',
      });
      setLoadingQuestion(false);
      return;
    }

    try {
      const relationshipRes = await axios.get('/api/graph/relationship', {
        params: {
          paper1_id: nodeA.id,
          paper2_id: nodeB.id,
        },
      });
      const existingRelationship = relationshipRes.data || null;
      if (existingRelationship) {
        setSelectedRelationship(existingRelationship);
        setConnectionQuestion(existingRelationship.question || 'How would you define the relationship between these two papers?');
        setConnectionInitialValues({
          commonalities: existingRelationship.commonalities || '',
          differences: existingRelationship.differences || '',
          description: existingRelationship.description || '',
          relType: existingRelationship.rel_type || 'RELATED_TO',
          question: existingRelationship.question || '',
        });
      } else {
        setSelectedRelationship(null);
        const questionRes = await axios.post('/api/quiz/question', {
          paper1_id: nodeA.id,
          paper2_id: nodeB.id,
        });
        setConnectionQuestion(questionRes.data?.question || 'How would you define the relationship between these two papers?');
        setConnectionInitialValues({
          commonalities: '',
          differences: '',
          description: '',
          relType: 'RELATED_TO',
          question: '',
        });
      }
    } catch (err) {
      console.error('Failed to generate connection question', err);
      setSelectedRelationship(null);
      setConnectionQuestion('How would you define the relationship between these two papers?');
      setConnectionInitialValues({
        commonalities: '',
        differences: '',
        description: '',
        relType: 'RELATED_TO',
          question: '',
      });
    } finally {
      setLoadingQuestion(false);
    }
  };

  const regenerateConnectionQuestion = async () => {
    if (!connectionPair) return;
    setLoadingQuestion(true);
    try {
      const res = await axios.post('/api/quiz/question', {
        paper1_id: connectionPair.nodeA.id,
        paper2_id: connectionPair.nodeB.id,
      });
      setConnectionQuestion(res.data?.question || 'How would you define the relationship between these two papers?');
      setConnectionInitialValues((current) => ({
        commonalities: current?.commonalities || '',
        differences: current?.differences || '',
        description: current?.description || '',
        relType: current?.relType || 'RELATED_TO',
        question: res.data?.question || '',
      }));
    } catch (err) {
      console.error('Failed to regenerate connection question', err);
    } finally {
      setLoadingQuestion(false);
    }
  };

  const closeQuiz = () => {
    setActiveQuiz(null);
    setQuestion('');
    setLoadingQuestion(false);
  };

  const submitQuiz = async (payload) => {
    if (!activeQuiz) return;

    setSubmitting(true);
    try {
      await axios.post('/api/quiz/confirm', {
        paper1_id: activeQuiz.paper1_id,
        paper2_id: activeQuiz.paper2_id,
        description: payload.description,
        rel_type: payload.relType,
        commonalities: payload.commonalities,
        differences: payload.differences,
        question,
      });
      closeQuiz();
      await fetchGraphData();
      await fetchQuizBundle(true);
    } catch (err) {
      console.error('Failed to confirm quiz', err);
    } finally {
      setSubmitting(false);
    }
  };

  const closeConnection = () => {
    setConnectionOpen(false);
    setConnectionPair(null);
    setConnectionQuestion('');
    setLoadingQuestion(false);
    setConnectionInitialValues(null);
  };

  const submitConnection = async (payload) => {
    if (!connectionPair) return;

    setSubmitting(true);
    try {
      await axios.post('/api/quiz/confirm', {
        paper1_id: connectionPair.nodeA.id,
        paper2_id: connectionPair.nodeB.id,
        description: payload.description,
        rel_type: payload.relType,
        commonalities: payload.commonalities,
        differences: payload.differences,
        question: connectionQuestion,
      });
      closeConnection();
      await fetchGraphData();
      await fetchQuizBundle(true);
      setSelectedNodes([]);
      setPairSimilarity(null);
    } catch (err) {
      console.error('Failed to confirm connection', err);
    } finally {
      setSubmitting(false);
    }
  };

  const hasRemainingQuizzes = (quizBundle.items || []).some((item) => item && item.status !== 'empty');
  const activeQuizCount = (quizBundle.items || []).filter((item) => item && item.status === 'active').length;
  const hasActiveQuizzes = activeQuizCount > 0;
  const quizItems = useMemo(() => quizBundle.items || [], [quizBundle.items]);
  const activeQuizPairKeys = useMemo(() => {
    return new Set(
      quizItems
        .filter((item) => item && item.status === 'active' && item.paper1_id && item.paper2_id)
        .map((item) => normalizePairKey(item.paper1_id, item.paper2_id))
    );
  }, [quizItems]);
  const selectedConnectionLabel = selectedRelationship ? 'View Connection' : 'Create connection';
  const connectionQuiz = useMemo(() => {
    if (!connectionOpen || !connectionPair) return null;
    return {
      paper1_title: connectionPair.nodeA.title,
      paper2_title: connectionPair.nodeB.title,
      paper1_summary: connectionPair.nodeA.summary,
      paper2_summary: connectionPair.nodeB.summary,
      paper1_id: connectionPair.nodeA.id,
      paper2_id: connectionPair.nodeB.id,
    };
  }, [connectionOpen, connectionPair]);

  if (loading) return <div className="text-center p-12 text-slate-500">Loading your knowledge graph...</div>;

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
          <h1 className="text-2xl font-bold text-slate-900">Knowledge Graph</h1>
          <p className="text-slate-500">Latest paper-driven relation quizzes appear as instant toasts.</p>
        </div>
        <div className="flex flex-col items-end gap-3">
          <button
            onClick={() => setSuggestedNeuronConnectionEnabled((value) => !value)}
            className={`flex items-center justify-between rounded-2xl border px-3 py-2 text-sm font-semibold transition-all duration-200 ${suggestedNeuronConnectionEnabled ? 'border-blue-200 bg-blue-50 text-blue-800 hover:bg-blue-100' : 'border-slate-200 bg-white text-slate-600 hover:bg-slate-50'}`}
            title={suggestedNeuronConnectionEnabled ? 'Hide suggested neuron connections' : 'Show suggested neuron connections'}
          >
            <span className="truncate">Suggested Neuron Connection</span>
            <span className={`ml-3 rounded-full px-2.5 py-1 text-[10px] uppercase tracking-wide ${suggestedNeuronConnectionEnabled ? 'bg-blue-600 text-white' : 'bg-slate-200 text-slate-600'}`}>
              {suggestedNeuronConnectionEnabled ? 'On' : 'Off'}
            </span>
          </button>
        </div>
      </div>

      <div className="flex flex-col xl:flex-row gap-6 items-stretch h-full min-h-0" style={{ height: 'min(80vh, 860px)' }}>
        <div className="flex-[1.35] min-w-0 h-full min-h-0">
          <div className="bg-white rounded-2xl shadow-sm border border-slate-100 overflow-hidden h-full min-h-0 flex items-stretch justify-center">
            <div className="w-full h-full min-h-0">
              <GraphComponent
                data={data}
                onNodeClick={handleNodeClick}
                onNodeDelete={handleNodeDelete}
                onBackgroundClick={handleBackgroundClick}
                onConnectSelected={handleConnectSelected}
                connectionButtonLabel={selectedConnectionLabel}
                onSummaryClick={handleSummaryClick}
                pairSimilarity={pairSimilarity}
                selectedNodes={selectedNodes}
                highlightedPairKeys={activeQuizPairKeys}
                hoveredQuizPairKey={hoveredQuizPairKey}
                suggestedNeuronConnectionEnabled={suggestedNeuronConnectionEnabled}
                availableCategories={availableCategories}
                selectedCategory={selectedCategory}
                onCategoryChange={setSelectedCategory}
                height={620}
              />
            </div>
          </div>
        </div>

        <div
          className="shrink-0 h-full min-h-0 transition-all duration-300 ease-in-out"
          style={{ width: quizCollapsed ? 76 : 320, maxHeight: '100%' }}
        >
          <div className="rounded-2xl bg-white border border-slate-100 p-3 shadow-sm h-full min-h-0 overflow-hidden flex flex-col">
            <div className={`flex items-center gap-3 ${quizCollapsed ? 'justify-center' : 'justify-between'} pb-3 border-b border-slate-100`}>
              {!quizCollapsed && (
                <div className="flex items-center gap-3 min-w-0">
                  <Sparkles className="text-blue-600 shrink-0" />
                  <div className="min-w-0">
                    <h2 className="text-lg font-bold text-slate-900">Active Recall Quizzes</h2>
                    <p className="text-xs text-slate-400 mt-1 truncate">
                      {activeQuizCount > 0 ? `${activeQuizCount} active slot${activeQuizCount > 1 ? 's' : ''}` : 'No active quizzes right now'}
                    </p>
                  </div>
                </div>
              )}
              <button
                onClick={() => setQuizCollapsed((value) => !value)}
                title={quizCollapsed ? 'Expand quizzes' : 'Collapse quizzes'}
                className={`rounded-full border transition-all duration-200 ${quizCollapsed ? 'border-blue-200 bg-blue-50 text-blue-700 hover:bg-blue-100 hover:border-blue-300' : 'border-blue-100 bg-blue-50 text-blue-700 hover:bg-blue-100 hover:border-blue-300'}`}
                style={{
                  width: quizCollapsed ? 44 : 40,
                  height: 40,
                  boxShadow: hasActiveQuizzes ? '0 0 0 1px rgba(59, 130, 246, 0.08)' : 'none',
                  animation: hasActiveQuizzes && quizCollapsed ? 'softPulse 2.1s ease-in-out infinite' : 'none',
                }}
              >
                <span className="text-sm font-semibold drop-shadow-sm">{quizCollapsed ? '◀' : '▶'}</span>
              </button>
            </div>

            {!quizCollapsed && (
              <>
                <p className="text-sm text-slate-500 mt-3">
                  Latest anchor: {quizBundle.anchor ? quizBundle.anchor.title : 'No paper available'}
                </p>
                <p className="mt-2 text-xs text-slate-400">Click on a quiz to generate an immediate question. Check the slots below.</p>

                <div className="mt-3 flex-1 min-h-0 overflow-hidden">
                  {!hasRemainingQuizzes ? (
                    <div className="h-full rounded-2xl border border-dashed border-slate-200 bg-slate-50 p-4 flex items-center justify-center text-center">
                      <p className="text-sm font-medium text-slate-600">
                        No active quizzes right now. The sidebar will refill when relationships become available.
                      </p>
                    </div>
                  ) : (
                    <div className="space-y-2.5 h-full min-h-0 overflow-y-auto pr-1 pb-1">
                      {Array.from({ length: (quizBundle.quiz_frequency || quizItems.length || 3) }).map((_, idx) => {
                        const item = quizItems[idx] || null;
                        if (item && item.status === 'active') {
                          return (
                            <button
                              key={`${item.paper1_id}-${item.paper2_id}`}
                              onClick={() => openQuiz(item)}
                              onMouseEnter={() => handleQuizHover(item.paper1_id, item.paper2_id)}
                              onMouseLeave={clearQuizHover}
                              className="w-full text-left rounded-2xl border border-slate-200 bg-white p-2.5 shadow-sm hover:border-blue-500 hover:shadow-md transition-all"
                            >
                              <div className="flex items-start justify-between gap-3">
                                <div>
                                  <p className="text-[11px] font-semibold text-blue-600 uppercase tracking-wider">#{item.rank}</p>
                                  <p className="font-semibold text-slate-900 mt-1 leading-snug">{item.paper1_title?.slice(0, 18)}... ↔ {item.paper2_title?.slice(0, 18)}...</p>
                                  <p className="text-[11px] text-slate-500 mt-1.5">{item.selection_source === 'random_top5' ? 'Random top-5 pick' : 'Ranked by similarity'} · score {(Number(item.score) || 0).toFixed(3)}</p>
                                </div>
                                <span className="rounded-full bg-blue-50 px-2.5 py-1 text-xs font-medium text-blue-700">Open</span>
                              </div>
                            </button>
                          );
                        }

                        if (item && item.status === 'cooldown') {
                          const expiresAt = item.expiresAt ? new Date(item.expiresAt) : null;
                          const remainingMs = expiresAt ? Math.max(0, expiresAt - now) : 0;
                          const totalSeconds = Math.floor(remainingMs / 1000);
                          const hours = Math.floor(totalSeconds / 3600);
                          const minutes = Math.floor((totalSeconds % 3600) / 60);
                          const seconds = totalSeconds % 60;
                          const remainingLabel = expiresAt ? `${hours}h ${minutes}m ${seconds}s` : 'Waiting';

                          return (
                            <div key={`cooldown-${item.id || idx}`} className="w-full rounded-2xl border border-dashed border-slate-200 bg-white p-2.5 shadow-sm flex items-center justify-between gap-2">
                              <div>
                                <p className="text-sm text-slate-600">Blank Slot</p>
                                <p className="text-xs text-slate-400 mt-1">Time until auto-fill: <span className="font-semibold text-slate-800">{remainingLabel}</span></p>
                              </div>
                              <div className="flex flex-col items-end gap-2">
                                <button
                                  onClick={refreshAndOpenQuiz}
                                  className="px-3 py-1 rounded-md bg-blue-600 text-white text-sm"
                                >
                                  Generate Now
                                </button>
                              </div>
                            </div>
                          );
                        }

                        const expiresAt = null;
                        const remainingMs = expiresAt ? Math.max(0, expiresAt - new Date()) : 0;
                        const remainingLabel = expiresAt ? `${Math.floor(remainingMs / 3600000)}h ${Math.floor((remainingMs % 3600000) / 60000)}m` : 'Waiting';

                        return (
                            <div key={`placeholder-${idx}`} className="w-full rounded-2xl border border-dashed border-slate-200 bg-white p-2.5 shadow-sm flex items-center justify-between gap-2">
                            <div>
                              <p className="text-sm text-slate-600">Blank Slot</p>
                              <p className="text-xs text-slate-400 mt-1">Time until auto-fill: <span className="font-semibold text-slate-800">{remainingLabel}</span></p>
                            </div>
                            <div className="flex flex-col items-end gap-2">
                              <button
                                onClick={refreshAndOpenQuiz}
                                className="px-3 py-1 rounded-md bg-blue-600 text-white text-sm"
                              >
                                Generate Now
                              </button>
                            </div>
                          </div>
                        );
                      })}
                    </div>
                  )}
                </div>
              </>
            )}
          </div>
        </div>
      </div>

      <QuizComponent
        quiz={activeQuiz}
        question={question}
        loadingQuestion={loadingQuestion}
        submitting={submitting}
        onClose={closeQuiz}
        onSubmit={submitQuiz}
      />

      <QuizComponent
        quiz={connectionQuiz}
        question={connectionQuestion}
        loadingQuestion={loadingQuestion}
        submitting={submitting}
        onClose={closeConnection}
        onSubmit={submitConnection}
        initialValues={connectionInitialValues}
        onRegenerateQuestion={regenerateConnectionQuestion}
        modeLabel={selectedRelationship ? 'View Connection' : 'Create Connection'}
      />

      {paperOverlay && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center p-4"
          style={{ background: 'rgba(0, 0, 0, 0.58)' }}
          onClick={closePaperOverlay}
        >
          <div
            className="w-full max-w-3xl rounded-2xl bg-white border border-slate-200 shadow-2xl overflow-hidden"
            onClick={(event) => event.stopPropagation()}
          >
            <div className="flex items-start justify-between gap-4 px-6 py-5 border-b border-slate-100 bg-slate-50">
              <div className="min-w-0">
                <p className="text-xs font-semibold uppercase tracking-widest text-blue-600">Paper Details</p>
                <h3 className="mt-1 text-xl font-bold text-slate-900 break-words">{paperOverlay.title}</h3>
              </div>
              <button
                onClick={closePaperOverlay}
                className="shrink-0 rounded-full border border-slate-200 bg-white px-3 py-1.5 text-sm font-medium text-slate-700 hover:border-blue-300 hover:text-blue-700 transition-colors"
              >
                Close
              </button>
            </div>

            <div className="px-6 py-5 space-y-5 max-h-[72vh] overflow-y-auto">
              <div>
                <p className="text-xs font-semibold uppercase tracking-widest text-slate-400">Keywords</p>
                <div className="mt-2 flex flex-wrap gap-2">
                  {(paperOverlay.keywords || []).length > 0 ? (
                    paperOverlay.keywords.map((keyword) => (
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
                  {paperOverlay.summary || 'No summary available.'}
                </p>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default GraphPage;
