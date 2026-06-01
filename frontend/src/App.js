import React from 'react';
import { BrowserRouter as Router, Routes, Route } from 'react-router-dom';
import { AuthProvider } from './AuthContext';
import ProtectedRoute from './components/ProtectedRoute';
import Layout from './components/Layout';
import LoginPage from './pages/Login';
import HomePage from './pages/Home';
import GraphPage from './pages/Graph';
import RecommendationsPage from './pages/Recommendations';
import SettingsPage from './pages/Settings';

function App() {
  return (
    <AuthProvider>
      <Router>
        <Routes>
          <Route path="/login" element={<LoginPage />} />
          
          <Route element={<ProtectedRoute />}>
            <Route path="/" element={<Layout><HomePage /></Layout>} />
            <Route path="/graph" element={<Layout><GraphPage /></Layout>} />
            <Route path="/recommendations" element={<Layout><RecommendationsPage /></Layout>} />
            <Route path="/settings" element={<Layout><SettingsPage /></Layout>} />
          </Route>
        </Routes>
      </Router>
    </AuthProvider>
  );
}

export default App;
