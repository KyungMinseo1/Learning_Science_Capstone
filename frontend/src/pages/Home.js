import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { Plus, Brain, Database, Link as LinkIcon } from 'lucide-react';

const HomePage = () => {
  const [stats, setStats] = useState({ paperCount: 0, linkCount: 0, username: '' });
  const [title, setTitle] = useState('');
  const [text, setText] = useState('');
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState('');

  useEffect(() => {
    fetchStats();
  }, []);

  const fetchStats = async () => {
    try {
      const res = await axios.get('/api/user/stats');
      setStats(res.data);
    } catch (err) {
      console.error("Failed to fetch stats", err);
    }
  };

  const handleUpload = async (e) => {
    e.preventDefault();
    setLoading(true);
    setMessage('');
    try {
      await axios.post('/api/papers', { title, text });
      setTitle('');
      setText('');
      setMessage('Paper uploaded and analyzed successfully!');
      fetchStats();
    } catch (err) {
      setMessage('Failed to upload paper');
    } finally {
      setLoading(false);
    }
  };

  const statCards = [
    { label: 'Total Papers', value: stats.paperCount, icon: <Database className="text-blue-500" />, color: 'bg-blue-50' },
    { label: 'Knowledge Links', value: stats.linkCount, icon: <LinkIcon className="text-green-500" />, color: 'bg-green-50' },
    { label: 'Retention Level', value: 'High', icon: <Brain className="text-purple-500" />, color: 'bg-purple-50' },
  ];

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-2xl font-bold text-slate-900">Welcome back, {stats.username}!</h1>
        <p className="text-slate-500">Here's an overview of your knowledge base.</p>
      </div>

      {/* Stats Grid */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        {statCards.map((card, i) => (
          <div key={i} className="bg-white p-6 rounded-2xl shadow-sm border border-slate-100 flex items-center gap-4">
            <div className={`p-4 rounded-xl ${card.color}`}>{card.icon}</div>
            <div>
              <p className="text-sm font-medium text-slate-500">{card.label}</p>
              <p className="text-2xl font-bold text-slate-900">{card.value}</p>
            </div>
          </div>
        ))}
      </div>

      {/* Upload Section */}
      <div className="bg-white rounded-2xl shadow-sm border border-slate-100 overflow-hidden">
        <div className="p-6 border-b border-slate-100 flex items-center gap-3">
          <Plus className="text-blue-600" />
          <h2 className="text-lg font-bold text-slate-900">Add New Research</h2>
        </div>
        <form onSubmit={handleUpload} className="p-6 space-y-4">
          {message && (
            <div className={`p-3 rounded-lg text-sm ${message.includes('success') ? 'bg-green-50 text-green-600' : 'bg-red-50 text-red-600'}`}>
              {message}
            </div>
          )}
          <div>
            <label className="block text-sm font-medium text-slate-700 mb-1">Paper Title</label>
            <input 
              className="w-full p-3 border border-slate-200 rounded-lg outline-none focus:ring-2 focus:ring-blue-500"
              placeholder="Enter paper title..."
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              required
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-slate-700 mb-1">Content (Abstract/Full Text)</label>
            <textarea 
              className="w-full p-3 border border-slate-200 rounded-lg outline-none focus:ring-2 focus:ring-blue-500 h-48"
              placeholder="Paste the paper content here for AI analysis..."
              value={text}
              onChange={(e) => setText(e.target.value)}
              required
            />
          </div>
          <button 
            type="submit"
            disabled={loading}
            className={`w-full py-3 rounded-lg font-semibold text-white transition-all ${loading ? 'bg-slate-400 cursor-not-allowed' : 'bg-blue-600 hover:bg-blue-700 shadow-lg shadow-blue-100'}`}
          >
            {loading ? 'Analyzing with AI...' : 'Upload & Integrate'}
          </button>
        </form>
      </div>
    </div>
  );
};

export default HomePage;
