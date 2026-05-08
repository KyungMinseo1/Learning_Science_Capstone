import React, { useState, useEffect } from 'react';
import axios from 'axios';
import GraphComponent from '../components/GraphComponent';
import QuizComponent from '../components/QuizComponent';
import { Info } from 'lucide-react';

const GraphPage = () => {
  const [data, setData] = useState({ nodes: [], links: [] });
  const [quiz, setQuiz] = useState(null);
  const [loading, setLoading] = useState(true);

  const fetchData = async () => {
    try {
      const [graphRes, quizRes] = await Promise.all([
        axios.get('/api/graph'),
        axios.get('/api/quiz')
      ]);
      setData(graphRes.data);
      if (quizRes.data.link_id) {
        setQuiz(quizRes.data);
      } else {
        setQuiz(null);
      }
    } catch (err) {
      console.error("Failed to fetch graph data", err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
  }, []);

  if (loading) return <div className="text-center p-12 text-slate-500">Loading your knowledge graph...</div>;

  return (
    <div className="space-y-6">
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-2xl font-bold text-slate-900">Knowledge Graph</h1>
          <p className="text-slate-500">Visualizing the connections between your research.</p>
        </div>
        <div className="flex items-center gap-4 text-sm text-slate-500">
          <div className="flex items-center gap-1">
            <div className="w-3 h-3 bg-blue-500 rounded-full"></div>
            <span>Confirmed</span>
          </div>
          <div className="flex items-center gap-1">
            <div className="w-3 h-3 bg-slate-300 rounded-full"></div>
            <span>Shadow (AI)</span>
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 xl:grid-cols-3 gap-8">
        <div className="xl:col-span-2">
          <div className="bg-white rounded-2xl shadow-sm border border-slate-100 overflow-hidden min-h-[600px] flex items-center justify-center">
            {data.nodes.length > 0 ? (
              <GraphComponent data={data} />
            ) : (
              <div className="text-center p-8">
                <Info size={48} className="mx-auto text-slate-300 mb-4" />
                <p className="text-slate-500 italic">No nodes yet. Upload at least 5 papers to start generating connections.</p>
              </div>
            )}
          </div>
        </div>

        <div className="space-y-6">
          <h2 className="text-lg font-bold text-slate-900">Active Recall Quizzes</h2>
          {quiz ? (
            <QuizComponent quiz={quiz} onConfirm={fetchData} />
          ) : (
            <div className="bg-slate-50 border border-dashed border-slate-200 rounded-2xl p-8 text-center">
              <p className="text-slate-500 text-sm">All set! No pending connections to confirm at the moment.</p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

export default GraphPage;
