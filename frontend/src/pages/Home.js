import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { Plus, Brain, Database, Link as LinkIcon } from 'lucide-react';

const HomePage = () => {
  const [stats, setStats] = useState({ paperCount: 0, linkCount: 0, username: '' });
  const [title, setTitle] = useState('');
  const [categories, setCategories] = useState([]);
  const [categoryInput, setCategoryInput] = useState('');
  const [showSuggestions, setShowSuggestions] = useState(false);
  const [manualKeywords, setManualKeywords] = useState([{ keyword: '', importance: '' }]);
  const [text, setText] = useState('');
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState('');
  const [categoryOptions, setCategoryOptions] = useState([]);

  useEffect(() => {
    fetchStats();
    fetchCategoryOptions();
  }, []);

  const fetchStats = async () => {
    try {
      const res = await axios.get('/api/user/stats');
      setStats(res.data);
    } catch (err) {
      console.error("Failed to fetch stats", err);
    }
  };

  const fetchCategoryOptions = async () => {
    try {
      const res = await axios.get('/api/user/categories');
      setCategoryOptions(res.data?.categories || []);
    } catch (err) {
      console.error('Failed to fetch categories', err);
    }
  };

  const handleCategorySelect = (category) => {
    if (categories.includes(category)) return;
    setCategories(prev => [...prev, category]);
    setCategoryInput('');
    setShowSuggestions(false);
  };

  const removeCategory = (cat) => {
    setCategories(prev => prev.filter(c => c !== cat));
  };

  const filtered = categoryOptions.filter(c =>
    !categories.includes(c) &&
    c.toLowerCase().includes(categoryInput.toLowerCase())
  );

  const normalizeManualKeywords = () => {
    return manualKeywords
      .map((item) => ({
        keyword: (item.keyword || '').trim(),
        importance: item.importance === '' || item.importance === null || item.importance === undefined ? '' : Number(item.importance),
      }))
      .filter((item) => item.keyword)
      .slice(0, 5);
  };

  const addKeywordRow = () => {
    setManualKeywords((prev) => (prev.length >= 5 ? prev : [...prev, { keyword: '', importance: '' }]));
  };

  const updateKeywordRow = (index, field, value) => {
    setManualKeywords((prev) => prev.map((item, itemIndex) => (itemIndex === index ? { ...item, [field]: value } : item)));
  };

  const removeKeywordRow = (index) => {
    setManualKeywords((prev) => (prev.length === 1 ? prev : prev.filter((_, itemIndex) => itemIndex !== index)));
  };

  const handleUpload = async (e) => {
    e.preventDefault();
    setLoading(true);
    setMessage('');
    try {
      const payload = {
        title,
        text,
        categories: categories.slice(0, 10),
        manual_keywords: normalizeManualKeywords().map((item) => ({ keyword: item.keyword, importance: item.importance === '' ? 1.0 : item.importance })),
        manual_keyword_importance: normalizeManualKeywords().map((item) => item.importance === '' ? 1.0 : item.importance),
      };

      await axios.post('/api/papers', payload);
      setTitle('');
      setCategories([]);
      setManualKeywords([{ keyword: '', importance: '' }]);
      setText('');
      setMessage('Paper uploaded and analyzed successfully!');
      fetchStats();
      fetchCategoryOptions();
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
            <label className="block text-sm font-medium text-slate-700 mb-1">Categories</label>
            {categories.length > 0 && (
              <div className="flex flex-wrap gap-1.5 mb-2">
                {categories.map((cat) => (
                  <span key={cat} className="flex items-center gap-1 rounded-full bg-blue-50 px-2.5 py-1 text-xs font-medium text-blue-700">
                    {cat}
                    <button
                      type="button"
                      onClick={() => removeCategory(cat)}
                      className="text-blue-400 hover:text-blue-700"
                    >✕</button>
                  </span>
                ))}
              </div>
            )}
            <div className="relative">
              <input
                className="w-full p-3 border border-slate-200 rounded-lg outline-none focus:ring-2 focus:ring-blue-500"
                placeholder="Type or select a category"
                value={categoryInput}
                onChange={(e) => { setCategoryInput(e.target.value); setShowSuggestions(true); }}
                onFocus={() => setShowSuggestions(true)}
                onBlur={() => setTimeout(() => setShowSuggestions(false), 150)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter') {
                    e.preventDefault();
                    const val = categoryInput.trim();
                    if (val) handleCategorySelect(val);
                  }
                }}
              />
              {showSuggestions && filtered.length > 0 && (
                <div className="absolute z-20 w-full mt-1 rounded-xl border border-slate-200 bg-white shadow-lg max-h-48 overflow-y-auto">
                  {filtered.map((category) => (
                    <button
                      key={category}
                      type="button"
                      onMouseDown={() => handleCategorySelect(category)}
                      className="w-full text-left px-3 py-2 text-sm text-slate-700 hover:bg-slate-50"
                    >
                      {category}
                    </button>
                  ))}
                </div>
              )}
            </div>
            <p className="text-xs text-slate-500 mt-2">You can reuse existing categories or create new ones. Multiple categories are supported.</p>
          </div>
          <div>
            <div className="flex items-center justify-between gap-3 mb-2">
              <label className="block text-sm font-medium text-slate-700">Manual Keywords (Optional)</label>
              <button type="button" onClick={addKeywordRow} className="text-xs font-semibold text-blue-600 hover:text-blue-700">Add keyword</button>
            </div>
            <div className="space-y-3">
              {manualKeywords.map((item, index) => (
                <div key={index} className="grid grid-cols-1 md:grid-cols-[minmax(0,1fr)_160px_auto] gap-3">
                  <input
                    className="w-full p-3 border border-slate-200 rounded-lg outline-none focus:ring-2 focus:ring-blue-500"
                    placeholder="Keyword"
                    value={item.keyword}
                    onChange={(e) => updateKeywordRow(index, 'keyword', e.target.value)}
                  />
                  <input
                    type="number"
                    step="0.01"
                    min="0"
                    max="1"
                    className="w-full p-3 border border-slate-200 rounded-lg outline-none focus:ring-2 focus:ring-blue-500"
                    placeholder="Importance"
                    value={item.importance}
                    onChange={(e) => updateKeywordRow(index, 'importance', e.target.value)}
                  />
                  <button
                    type="button"
                    onClick={() => removeKeywordRow(index)}
                    className="rounded-lg border border-slate-200 px-3 py-2 text-sm font-medium text-slate-600 hover:bg-slate-50"
                  >
                    Remove
                  </button>
                </div>
              ))}
            </div>
            <p className="text-xs text-slate-500 mt-2">Enter up to 5 keyword/importance pairs. The AI will generate the remaining keywords after these are excluded.</p>
          </div>
          <div>
            <label className="block text-sm font-medium text-slate-700 mb-1">Content (Optional)</label>
            <textarea 
              className="w-full p-3 border border-slate-200 rounded-lg outline-none focus:ring-2 focus:ring-blue-500 h-48"
              placeholder="Paste the paper content here if you want to help keyword extraction..."
              value={text}
              onChange={(e) => setText(e.target.value)}
            />
            <p className="text-xs text-slate-500 mt-2">Title is required. If content is omitted, Semantic Scholar metadata will be used as the summary source when available.</p>
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
