import { useEffect, useMemo, useRef, useState } from 'react';

type EventPayload = {
  ts: string;
  kind: string;
  payload: Record<string, unknown>;
};

const eventMeta: Record<
  string,
  { icon: string; label: string; classes: string }
> = {
  tool_call: { icon: '🛠️', label: 'Tool Call', classes: 'bg-yellow-100/80 text-amber-900' },
  tool_result: { icon: '🔧', label: 'Tool Result', classes: 'bg-amber-100/80 text-amber-900' },
  validator_decision: { icon: '⚠️', label: 'Validator', classes: 'bg-red-100/80 text-red-900' },
  transcript: { icon: '💬', label: 'Transcript', classes: 'bg-emerald-100/80 text-emerald-900' },
  server_status: { icon: '🔎', label: 'Backend', classes: 'bg-slate-100/80 text-slate-900' },
};

function makeSessionId() {
  return Math.random().toString(36).slice(2, 10);
}

function App() {
  const [sessionId, setSessionId] = useState(() => makeSessionId());
  const [utterance, setUtterance] = useState('');
  const [events, setEvents] = useState<EventPayload[]>([]);
  const sourceRef = useRef<EventSource | null>(null);
  const eventsContainerRef = useRef<HTMLDivElement | null>(null);
  const [status, setStatus] = useState('Ready');
  const [backendInfo, setBackendInfo] = useState<{ backend: string; modelId?: string } | null>(null);
  const backendText = backendInfo
    ? backendInfo.backend.toLowerCase() === 'fake'
      ? 'FakeBedrock returns canned tool calls; ZIPs and account IDs in canned responses may not match what you typed. Set BEDROCK_MODEL_ID_TEXT to use real Bedrock.'
      : backendInfo.backend.toLowerCase() === 'real'
      ? `Real Bedrock active: ${backendInfo.modelId ?? 'unknown model'}`
      : ''
    : '';

  useEffect(() => {
    return () => {
      sourceRef.current?.close();
    };
  }, []);

  useEffect(() => {
    const el = eventsContainerRef.current;
    if (!el) return;
    // scroll to bottom to keep latest event in view
    try {
      window.requestAnimationFrame(() => {
        el.scrollTop = el.scrollHeight;
      });
    } catch {
      // ignore in non-browser environments
      setTimeout(() => {
        el.scrollTop = el.scrollHeight;
      }, 0);
    }
  }, [events.length]);

  const clearSession = () => {
    sourceRef.current?.close();
    setSessionId(makeSessionId());
    setEvents([]);
    setUtterance('');
    setStatus('Ready');
    setBackendInfo(null);
  };

  const startTurn = () => {
    if (!utterance.trim()) {
      return;
    }

    sourceRef.current?.close();
    setEvents((prev) => [
      ...prev,
      {
        ts: new Date().toISOString(),
        kind: 'system',
        payload: { message: 'Sending turn to backend...' },
      },
    ]);

      const eventSource = new EventSource(
      `/turn?session_id=${encodeURIComponent(sessionId)}&utterance=${encodeURIComponent(utterance)}`
    );
    sourceRef.current = eventSource;
    setStatus('Streaming');

    eventSource.onmessage = (event) => {
      try {
        const payload = JSON.parse(event.data) as EventPayload;
          if (payload.kind === 'server_status') {
            setBackendInfo({
              backend: payload.payload.backend as string,
              modelId: payload.payload.model_id as string,
            });
          }
          setEvents((prev) => [...prev, payload]);
        } catch {
          setEvents((prev) => [
            ...prev,
            {
              ts: new Date().toISOString(),
              kind: 'error',
              payload: { message: event.data },
            },
          ]);
        }
      };

    eventSource.onerror = () => {
      setStatus('Complete');
      eventSource.close();
    };
  };

  const renderedEvents = useMemo(
    () =>
      events.map((event, index) => {
        const meta = eventMeta[event.kind] ?? {
          icon: 'ℹ️',
          label: event.kind,
          classes: 'bg-slate-100/80 text-slate-900',
        };
        return (
          <div key={`${event.ts}-${index}`} className={`rounded-2xl border border-slate-700 p-4 ${meta.classes} mb-3`}>
            <div className="flex items-center gap-3 text-sm font-semibold">
              <span>{meta.icon}</span>
              <span>{meta.label}</span>
              <span className="text-slate-500">{new Date(event.ts).toLocaleTimeString()}</span>
            </div>
            <pre className="mt-2 max-h-40 overflow-auto whitespace-pre-wrap text-xs text-slate-800">
              {JSON.stringify(event.payload, null, 2)}
            </pre>
          </div>
        );
      }),
    [events]
  );

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100">
      <div className="mx-auto flex min-h-screen max-w-7xl flex-col gap-6 p-6 sm:p-10">
        <header className="rounded-3xl border border-slate-800 bg-slate-900/80 p-6 shadow-xl shadow-slate-900/10">
          <h1 className="text-3xl font-bold text-white">Carrier Voice Agent</h1>
          <p className="mt-2 text-slate-400">Live developer demo with SSE event logging and in-memory session state.</p>
        </header>

        <div className="grid flex-1 gap-6 lg:grid-cols-[360px_1fr]">
          <section className="rounded-3xl border border-slate-800 bg-slate-900/80 p-6 shadow-xl shadow-slate-900/10">
            <div className="flex items-center justify-between gap-4">
              <div>
                <p className="text-sm uppercase tracking-[0.2em] text-slate-500">Session</p>
                <p className="mt-2 break-all text-lg font-semibold text-white">{sessionId}</p>
              </div>
              <button
                type="button"
                onClick={clearSession}
                className="rounded-full bg-slate-700 px-4 py-2 text-sm font-semibold text-slate-100 transition hover:bg-slate-600"
              >
                New session
              </button>
            </div>

            <div className="mt-8 space-y-4">
              <label className="block text-sm font-semibold text-slate-300">Turn text</label>
              <textarea
                rows={6}
                value={utterance}
                onChange={(event) => setUtterance(event.target.value)}
                className="w-full rounded-3xl border border-slate-700 bg-slate-950/90 px-4 py-3 text-sm text-slate-100 outline-none transition focus:border-cyan-500 focus:ring-2 focus:ring-cyan-500/20"
                placeholder="Ask the agent about an outage, account, appointment, or escalation."
              />
              {backendText ? (
                <p className="text-xs text-slate-400">{backendText}</p>
              ) : null}
            </div>

            <div className="mt-6 flex flex-col gap-3 sm:flex-row">
              <button
                type="button"
                onClick={startTurn}
                className="inline-flex items-center justify-center rounded-full bg-cyan-500 px-6 py-3 text-sm font-semibold text-slate-950 transition hover:bg-cyan-400"
              >
                Send turn
              </button>
              <div className="rounded-full border border-slate-700 bg-slate-950/80 px-4 py-3 text-sm text-slate-400">
                {status}
              </div>
            </div>
          </section>

          <section className="rounded-3xl border border-slate-800 bg-slate-900/80 p-6 shadow-xl shadow-slate-900/10">
            <div className="mb-6 flex items-center justify-between gap-4">
              <div>
                <p className="text-sm uppercase tracking-[0.2em] text-slate-500">Event log</p>
                <p className="mt-2 text-lg font-semibold text-white">{events.length} entries</p>
              </div>
              <button
                type="button"
                onClick={() => setEvents([])}
                className="rounded-full border border-slate-700 bg-slate-950/80 px-4 py-2 text-sm text-slate-300 transition hover:bg-slate-800"
              >
                Clear
              </button>
            </div>
            <div ref={eventsContainerRef} className="space-y-3 overflow-y-auto max-h-[70vh] pr-1">{renderedEvents}</div>
          </section>
        </div>
      </div>
    </div>
  );
}

export default App;
