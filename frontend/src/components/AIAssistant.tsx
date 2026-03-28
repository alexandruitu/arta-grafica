import { useState, useRef } from 'react';
import { Bot, RefreshCw, ChevronDown, ChevronUp } from 'lucide-react';

const QUESTIONS: Record<string, { id: string; label: string }[]> = {
  dashboard: [
    { id: 'dashboard_summary',  label: 'Rezumă situația de azi' },
    { id: 'dashboard_urgent',   label: 'Care sunt comenzile urgente?' },
    { id: 'dashboard_blocaje',  label: 'Unde sunt principalele blocaje?' },
  ],
  planificare: [
    { id: 'plan_blocate',       label: 'De ce sunt comenzi blocate?' },
    { id: 'plan_aprovizionare', label: 'Ce materiale să aprovizionez?' },
    { id: 'plan_quickwins',     label: 'Care sunt quick wins?' },
  ],
};

interface Props {
  tab: 'dashboard' | 'planificare';
}

export default function AIAssistant({ tab }: Props) {
  const [activeId, setActiveId]   = useState<string | null>(null);
  const [response, setResponse]   = useState('');
  const [loading, setLoading]     = useState(false);
  const [collapsed, setCollapsed] = useState(false);
  const abortRef                  = useRef<AbortController | null>(null);
  const questions                 = QUESTIONS[tab];

  const handleQuestion = async (questionId: string) => {
    // If already loading, abort and reset
    if (loading) {
      abortRef.current?.abort();
      setLoading(false);
      setActiveId(null);
      return;
    }

    setActiveId(questionId);
    setResponse('');
    setCollapsed(false);
    setLoading(true);

    const controller = new AbortController();
    abortRef.current = controller;

    try {
      const res = await fetch(`/api/ai/analyze?question_id=${encodeURIComponent(questionId)}`, {
        signal: controller.signal,
      });

      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      if (!res.body) throw new Error('No response body');

      const reader  = res.body.getReader();
      const decoder = new TextDecoder();
      let buffer    = '';

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const parts = buffer.split('\n\n');
        buffer = parts.pop() ?? '';

        for (const part of parts) {
          if (!part.startsWith('data: ')) continue;
          const raw = part.slice(6).trim();
          if (raw === '[DONE]') break;
          try {
            const { text } = JSON.parse(raw) as { text: string };
            setResponse(prev => prev + text);
          } catch {
            setResponse(prev => prev + raw);
          }
        }
      }
    } catch (e: any) {
      if (e.name !== 'AbortError') {
        setResponse(prev => prev + `\n\n[Eroare: ${e.message}]`);
      }
    }

    setLoading(false);
  };

  const handleReset = () => {
    abortRef.current?.abort();
    setLoading(false);
    setResponse('');
    setActiveId(null);
    setCollapsed(false);
  };

  const activeLabel = questions.find(q => q.id === activeId)?.label ?? '';
  const showPanel   = loading || !!response;

  return (
    <div className="bg-gradient-to-r from-blue-50 to-indigo-50 border border-blue-200 rounded-lg p-4">

      {/* Header row */}
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          <div className="p-1.5 bg-blue-600 rounded-lg">
            <Bot size={15} className="text-white" />
          </div>
          <span className="font-semibold text-slate-700 text-sm">Asistent AI Producție</span>
          <span className="text-xs text-slate-400 bg-white/70 border border-blue-100 px-2 py-0.5 rounded-full">
            Claude
          </span>
        </div>
        {showPanel && (
          <div className="flex items-center gap-1">
            <button
              onClick={() => setCollapsed(c => !c)}
              className="p-1 text-slate-400 hover:text-slate-600 rounded"
              title={collapsed ? 'Extinde' : 'Restrânge'}
            >
              {collapsed ? <ChevronDown size={15} /> : <ChevronUp size={15} />}
            </button>
            <button
              onClick={handleReset}
              className="p-1 text-slate-400 hover:text-slate-600 rounded"
              title="Resetează"
            >
              <RefreshCw size={14} />
            </button>
          </div>
        )}
      </div>

      {/* Question buttons */}
      <div className="flex flex-wrap gap-2">
        {questions.map(q => (
          <button
            key={q.id}
            onClick={() => handleQuestion(q.id)}
            className={[
              'px-3 py-1.5 rounded-full text-xs font-medium transition-all',
              activeId === q.id
                ? loading
                  ? 'bg-blue-400 text-white cursor-wait'
                  : 'bg-blue-600 text-white'
                : 'bg-white border border-blue-200 text-blue-700 hover:bg-blue-50 hover:border-blue-400',
            ].join(' ')}
          >
            {activeId === q.id && loading ? (
              <span className="flex items-center gap-1.5">
                <span className="w-3 h-3 border-2 border-white border-t-transparent rounded-full animate-spin inline-block" />
                {q.label}
              </span>
            ) : q.label}
          </button>
        ))}
      </div>

      {/* Response panel */}
      {showPanel && !collapsed && (
        <div className="mt-3 bg-white rounded-lg border border-blue-100 overflow-hidden">
          {activeLabel && (
            <div className="px-4 py-2 bg-blue-600 text-white text-xs font-medium">
              {activeLabel}
            </div>
          )}
          <div className="px-4 py-3 text-sm text-slate-700 whitespace-pre-wrap leading-relaxed min-h-[60px]">
            {response || (
              <span className="text-slate-400 italic">Se analizează datele...</span>
            )}
            {loading && (
              <span
                className="inline-block w-1.5 h-4 bg-blue-500 rounded-sm align-middle ml-0.5 animate-pulse"
                aria-hidden
              />
            )}
          </div>
        </div>
      )}
    </div>
  );
}
