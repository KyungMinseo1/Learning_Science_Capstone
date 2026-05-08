import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { Save, Cpu, Cloud, Bell } from 'lucide-react';

const SettingsPage = () => {
  const [settings, setSettings] = useState({ ai_provider: 'openai', quiz_frequency: 3 });
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState('');

  useEffect(() => {
    fetchSettings();
  }, []);

  const fetchSettings = async () => {
    try {
      const res = await axios.get('/api/user/settings');
      setSettings(res.data);
    } catch (err) {
      console.error("Failed to fetch settings", err);
    }
  };

  const handleSave = async () => {
    setLoading(true);
    setMessage('');
    try {
      await axios.post('/api/user/settings', settings);
      setMessage('Settings updated successfully!');
    } catch (err) {
      setMessage('Failed to update settings');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="max-w-2xl space-y-8">
      <div>
        <h1 className="text-2xl font-bold text-slate-900">System Settings</h1>
        <p className="text-slate-500">Configure your AI providers and memory consolidation preferences.</p>
      </div>

      <div className="bg-white rounded-2xl shadow-sm border border-slate-100 divide-y divide-slate-100">
        {/* AI Provider Section */}
        <div className="p-6">
          <div className="flex items-center gap-3 mb-6">
            <Cpu className="text-blue-600" />
            <h2 className="text-lg font-bold text-slate-900">AI Intelligence Mode</h2>
          </div>
          
          <div className="grid grid-cols-2 gap-4">
            <button 
              onClick={() => setSettings({...settings, ai_provider: 'openai'})}
              className={`p-4 rounded-xl border-2 text-left transition-all ${settings.ai_provider === 'openai' ? 'border-blue-600 bg-blue-50' : 'border-slate-100 hover:border-slate-200'}`}
            >
              <div className="flex justify-between items-start mb-2">
                <Cloud className={settings.ai_provider === 'openai' ? 'text-blue-600' : 'text-slate-400'} />
                {settings.ai_provider === 'openai' && <div className="w-4 h-4 bg-blue-600 rounded-full flex items-center justify-center text-[10px] text-white">✓</div>}
              </div>
              <p className="font-bold text-slate-900">OpenAI (Cloud)</p>
              <p className="text-xs text-slate-500 mt-1">Highest accuracy, requires internet & API key.</p>
            </button>

            <button 
              onClick={() => setSettings({...settings, ai_provider: 'ollama'})}
              className={`p-4 rounded-xl border-2 text-left transition-all ${settings.ai_provider === 'ollama' ? 'border-blue-600 bg-blue-50' : 'border-slate-100 hover:border-slate-200'}`}
            >
              <div className="flex justify-between items-start mb-2">
                <Cpu className={settings.ai_provider === 'ollama' ? 'text-blue-600' : 'text-slate-400'} />
                {settings.ai_provider === 'ollama' && <div className="w-4 h-4 bg-blue-600 rounded-full flex items-center justify-center text-[10px] text-white">✓</div>}
              </div>
              <p className="font-bold text-slate-900">Ollama (Local SLM)</p>
              <p className="text-xs text-slate-500 mt-1">Full privacy, runs on your machine.</p>
            </button>
          </div>
        </div>

        {/* Consolidation Settings */}
        <div className="p-6">
          <div className="flex items-center gap-3 mb-6">
            <Bell className="text-blue-600" />
            <h2 className="text-lg font-bold text-slate-900">Consolidation Strategy</h2>
          </div>
          
          <div className="space-y-4">
            <label className="block">
              <span className="text-sm font-medium text-slate-700">Quiz Frequency (papers per quiz)</span>
              <input 
                type="number"
                className="mt-1 w-full p-3 border border-slate-200 rounded-lg outline-none focus:ring-2 focus:ring-blue-500"
                value={settings.quiz_frequency}
                onChange={(e) => setSettings({...settings, quiz_frequency: parseInt(e.target.value)})}
              />
              <p className="text-xs text-slate-500 mt-2 italic">* Note: Memory consolidation only starts after 5 papers are integrated.</p>
            </label>
          </div>
        </div>

        {/* Save Button */}
        <div className="p-6 bg-slate-50 flex items-center justify-between">
          <p className="text-sm text-slate-500">
            {message && <span className={message.includes('success') ? 'text-green-600 font-medium' : 'text-red-600 font-medium'}>{message}</span>}
          </p>
          <button 
            onClick={handleSave}
            disabled={loading}
            className="flex items-center gap-2 bg-slate-900 text-white px-6 py-2 rounded-lg hover:bg-slate-800 transition-colors disabled:bg-slate-400"
          >
            <Save size={18} />
            {loading ? 'Saving...' : 'Save Settings'}
          </button>
        </div>
      </div>
    </div>
  );
};

export default SettingsPage;
