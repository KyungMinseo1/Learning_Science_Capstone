import React, { useEffect, useRef, useState } from 'react';

const QuizComponent = ({
  quiz,
  question,
  loadingQuestion,
  submitting,
  onClose,
  onSubmit,
  initialValues,
  onRegenerateQuestion,
  modeLabel = 'Active Recall Quiz',
}) => {
  const [commonalities, setCommonalities] = useState('');
  const [differences, setDifferences] = useState('');
  const [description, setDescription] = useState('');
  const [relType, setRelType] = useState('RELATED_TO');
  const quizKeyRef = useRef('');
  const dirtyRef = useRef(false);

  useEffect(() => {
    const nextQuizKey = quiz ? `${quiz.paper1_id || quiz.paper1_title || ''}__${quiz.paper2_id || quiz.paper2_title || ''}` : '';
    if (!nextQuizKey) return;

    const pairChanged = quizKeyRef.current !== nextQuizKey;
    const hasInitialValues = Boolean(initialValues);

    if (pairChanged) {
      quizKeyRef.current = nextQuizKey;
      dirtyRef.current = false;
      setCommonalities(initialValues?.commonalities || '');
      setDifferences(initialValues?.differences || '');
      setDescription(initialValues?.description || '');
      setRelType(initialValues?.relType || 'RELATED_TO');
      return;
    }

    if (!dirtyRef.current && hasInitialValues) {
      setCommonalities(initialValues?.commonalities || '');
      setDifferences(initialValues?.differences || '');
      setDescription(initialValues?.description || '');
      setRelType(initialValues?.relType || 'RELATED_TO');
    }
  }, [quiz, initialValues]);

  const markDirty = () => {
    dirtyRef.current = true;
  };

  const handleSubmit = async () => {
    await onSubmit({
      commonalities,
      differences,
      description,
      relType,
    });
  };

  if (!quiz) return null;

  const isConnectionHistory = modeLabel !== 'Active Recall Quiz';

  return (
    <div className="fixed inset-0 z-40 flex items-center justify-center bg-slate-950/50 px-4">
      <div className="w-full max-w-3xl rounded-3xl bg-white shadow-2xl border border-slate-200 overflow-hidden">
        <div className="flex items-start justify-between gap-4 p-6 border-b border-slate-100">
          <div>
            <p className="text-xs uppercase tracking-widest text-blue-600 font-semibold">{modeLabel}</p>
            <h3 className="text-2xl font-bold text-slate-900 mt-2">Paper Relationship Quiz</h3>
            <p className="text-sm text-slate-500 mt-1">The default relationship type is RELATED_TO, and you can change it if needed.</p>
            {isConnectionHistory && (
              <p className="text-sm text-blue-700 mt-2">Previously saved connection history is loaded below. Edit any field and save to update the record.</p>
            )}
          </div>
          <button
            onClick={onClose}
            className="px-3 py-2 rounded-lg text-slate-500 hover:bg-slate-100 hover:text-slate-800"
          >
            Close
          </button>
        </div>

        <div className="p-6 space-y-6 max-h-[80vh] overflow-y-auto">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="rounded-2xl border border-slate-200 bg-slate-50 p-4">
              <p className="text-xs font-semibold text-slate-500 mb-2">Paper A</p>
              <h4 className="font-bold text-slate-900">{quiz.paper1_title}</h4>
              <p className="text-sm text-slate-600 mt-2 leading-6">{quiz.paper1_summary || 'No summary available.'}</p>
            </div>
            <div className="rounded-2xl border border-slate-200 bg-slate-50 p-4">
              <p className="text-xs font-semibold text-slate-500 mb-2">Paper B</p>
              <h4 className="font-bold text-slate-900">{quiz.paper2_title}</h4>
              <p className="text-sm text-slate-600 mt-2 leading-6">{quiz.paper2_summary || 'No summary available.'}</p>
            </div>
          </div>

          <div className="rounded-2xl border border-blue-100 bg-blue-50 p-4">
            <div className="flex items-center justify-between gap-4 mb-2">
              <p className="text-xs font-semibold text-blue-700">AI Generated Question</p>
              {onRegenerateQuestion && (
                <button
                  onClick={onRegenerateQuestion}
                  disabled={loadingQuestion || submitting}
                  className="rounded-full border border-blue-200 bg-white px-3 py-1 text-xs font-semibold text-blue-700 hover:bg-blue-100 disabled:opacity-60"
                >
                  Regenerate
                </button>
              )}
            </div>
            {loadingQuestion ? (
              <p className="text-sm text-blue-700">Generating question...</p>
            ) : (
              <p className="text-lg font-semibold text-slate-900 leading-8">{question || 'Failed to load question.'}</p>
            )}
          </div>

          <div className="grid grid-cols-1 gap-4">
            <label className="block">
              <span className="text-sm font-medium text-slate-700">Commonalities</span>
              <textarea
                className="mt-1 w-full rounded-xl border border-slate-200 p-3 outline-none focus:ring-2 focus:ring-blue-500 min-h-[96px]"
                placeholder="Enter the commonalities between the two papers"
                value={commonalities}
                onChange={(e) => {
                  markDirty();
                  setCommonalities(e.target.value);
                }}
              />
            </label>

            <label className="block">
              <span className="text-sm font-medium text-slate-700">Differences</span>
              <textarea
                className="mt-1 w-full rounded-xl border border-slate-200 p-3 outline-none focus:ring-2 focus:ring-blue-500 min-h-[96px]"
                placeholder="Enter the differences between the two papers"
                value={differences}
                onChange={(e) => {
                  markDirty();
                  setDifferences(e.target.value);
                }}
              />
            </label>

            <label className="block">
              <span className="text-sm font-medium text-slate-700">Relationship Definition</span>
              <textarea
                className="mt-1 w-full rounded-xl border border-slate-200 p-3 outline-none focus:ring-2 focus:ring-blue-500 min-h-[96px]"
                placeholder="Define the relationship between the two papers"
                value={description}
                onChange={(e) => {
                  markDirty();
                  setDescription(e.target.value);
                }}
              />
            </label>
          </div>

          <div className="flex flex-col md:flex-row md:items-center gap-4 justify-between">
            <label className="block w-full md:w-72">
              <span className="text-sm font-medium text-slate-700">Relationship Type</span>
              <select
                className="mt-1 w-full rounded-xl border border-slate-200 p-3 outline-none focus:ring-2 focus:ring-blue-500"
                value={relType}
                onChange={(e) => {
                  markDirty();
                  setRelType(e.target.value);
                }}
              >
                <option value="RELATED_TO">RELATED_TO</option>
                <option value="SUPPORTS">SUPPORTS</option>
                <option value="CONTRADICTS">CONTRADICTS</option>
                <option value="EXTENDS">EXTENDS</option>
              </select>
            </label>

            <button
              onClick={handleSubmit}
              disabled={submitting || loadingQuestion}
              className="inline-flex items-center justify-center rounded-xl bg-slate-900 px-6 py-3 text-white font-semibold hover:bg-slate-800 disabled:bg-slate-400"
            >
              {submitting ? 'Saving...' : 'Save Relationship'}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};

export default QuizComponent;
