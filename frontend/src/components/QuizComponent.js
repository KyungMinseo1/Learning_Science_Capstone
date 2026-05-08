import React, { useState } from 'react';
import axios from 'axios';

const QuizComponent = ({ quiz, onConfirm }) => {
  const [description, setDescription] = useState('');
  const [relType, setRelType] = useState('RELATED_TO');

  const handleSubmit = async () => {
    try {
      await axios.post('/api/quiz/confirm', {
        link_id: quiz.link_id,
        description: description,
        rel_type: relType
      });
      onConfirm();
    } catch (error) {
      console.error("Failed to confirm quiz", error);
    }
  };

  return (
    <div className="p-6 bg-blue-50 rounded-lg shadow-md mt-4">
      <h3 className="text-xl font-bold mb-4">Memory Recall Quiz</h3>
      <p className="mb-2">How is <strong>{quiz.paper1}</strong> related to <strong>{quiz.paper2}</strong>?</p>
      
      <div className="grid grid-cols-2 gap-4 mb-4 text-sm text-gray-600">
        <div className="p-2 bg-white rounded border">{quiz.summary1}</div>
        <div className="p-2 bg-white rounded border">{quiz.summary2}</div>
      </div>

      <textarea 
        className="w-full p-2 border rounded mb-4" 
        placeholder="Explain the relationship..."
        value={description}
        onChange={(e) => setDescription(e.target.value)}
      />

      <div className="flex items-center gap-4">
        <select 
          className="p-2 border rounded"
          value={relType}
          onChange={(e) => setRelType(e.target.value)}
        >
          <option value="RELATED_TO">Related To</option>
          <option value="SUPPORTS">Supports</option>
          <option value="CONTRADICTS">Contradicts</option>
          <option value="EXTENDS">Extends</option>
        </select>
        <button 
          className="px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700"
          onClick={handleSubmit}
        >
          Confirm Relationship
        </button>
      </div>
    </div>
  );
};

export default QuizComponent;
