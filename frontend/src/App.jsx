import { Activity, BarChart3, Brain, Circle, Clock3, ShieldCheck, TrendingDown, TrendingUp, WalletCards } from "lucide-react";
import { useEffect, useMemo, useState } from "react";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "/api";
const REFRESH_MS = 3000;

const emptyAnalysis = {
  plain_english_explanation: "No AI analysis is available for this trade yet.",
  why_the_trade_qualified: "Cannot be determined because no analysis has been stored yet.",
  risk_factors: "Cannot be determined because no analysis has been stored yet.",
  watch_after_entry: "Cannot be determined because no analysis has been stored yet.",
  educational_summary: "Cannot be determined because no analysis has been stored yet.",
};

function formatNumber(value, digits = 2) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) {
    return "N/A";
  }

  return Number(value).toLocaleString(undefined, {
    maximumFractionDigits: digits,
    minimumFractionDigits: digits,
  });
}

function formatPercent(value) {
  return `${formatNumber(value, 1)}%`;
}

function formatTime(value) {
  if (!value) {
    return "N/A";
  }

  return new Intl.DateTimeFormat(undefined, {
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
  }).format(new Date(value));
}

function formatDuration(seconds) {
  if (seconds === null || seconds === undefined || Number.isNaN(Number(seconds))) {
    return "N/A";
  }

  const totalSeconds = Math.max(0, Math.round(Number(seconds)));
  const minutes = Math.floor(totalSeconds / 60);
  const remainingSeconds = totalSeconds % 60;
  if (minutes >= 60) {
    const hours = Math.floor(minutes / 60);
    const remainingMinutes = minutes % 60;
    return `${hours}h ${remainingMinutes}m`;
  }
  if (minutes > 0) {
    return `${minutes}m ${remainingSeconds}s`;
  }
  return `${remainingSeconds}s`;
}

function normalizeGrade(grade, confidence = 0) {
  if (!grade) {
    return "D";
  }

  if (grade === "A" && confidence >= 95) {
    return "A+";
  }

  return ["A+", "A", "B", "C", "D"].includes(grade) ? grade : "D";
}

function confidenceClass(score) {
  if (score >= 80) return "bg-emerald-400";
  if (score >= 60) return "bg-lime-300";
  if (score >= 40) return "bg-amber-300";
  return "bg-red-400";
}

function actionStyles(action) {
  return action === "BUY"
    ? "border-emerald-400/40 bg-emerald-400/10 text-emerald-200"
    : "border-red-400/40 bg-red-400/10 text-red-200";
}

function App() {
  const [snapshot, setSnapshot] = useState(null);
  const [selectedTradeId, setSelectedTradeId] = useState(null);
  const [selectedTrade, setSelectedTrade] = useState(null);
  const [backendReachable, setBackendReachable] = useState(false);
  const [lastUpdated, setLastUpdated] = useState(null);
  const [error, setError] = useState("");
  const [botActionPending, setBotActionPending] = useState(false);

  useEffect(() => {
    let cancelled = false;

    async function loadSnapshot() {
      try {
        const response = await fetch(`${API_BASE_URL}/dashboard/snapshot`);
        if (!response.ok) {
          throw new Error("Backend returned an error.");
        }

        const data = await response.json();
        if (cancelled) return;

        setSnapshot(data);
        setBackendReachable(true);
        setLastUpdated(new Date());
        setError("");

        const nextSelectedId = selectedTradeId ?? data.latest_trade?.id ?? null;
        setSelectedTradeId(nextSelectedId);

        if (!selectedTradeId && data.latest_trade) {
          setSelectedTrade(data.latest_trade);
        }
      } catch (caughtError) {
        if (cancelled) return;
        setBackendReachable(false);
        setError(caughtError.message);
      }
    }

    loadSnapshot();
    const intervalId = window.setInterval(loadSnapshot, REFRESH_MS);

    return () => {
      cancelled = true;
      window.clearInterval(intervalId);
    };
  }, [selectedTradeId]);

  useEffect(() => {
    if (!selectedTradeId) {
      return;
    }

    const matchingTrade = snapshot?.trades?.find((trade) => trade.id === selectedTradeId);
    if (matchingTrade) {
      setSelectedTrade(matchingTrade);
    }
  }, [selectedTradeId, snapshot]);

  const account = snapshot?.account;
  const latestTrade = snapshot?.latest_trade;
  const displayTrade = selectedTrade ?? latestTrade;
  const displayAnalysis = displayTrade?.analysis ?? emptyAnalysis;
  const confidence = displayTrade?.analysis?.confidence_score ?? 0;
  const grade = normalizeGrade(displayTrade?.analysis?.trade_grade, confidence);

  const topMetrics = useMemo(
    () => [
      { label: "Trades Today", value: account?.trades_today ?? 0 },
      { label: "Open Positions", value: account?.open_positions ?? 0 },
      { label: "Winning Trades", value: account?.winning_trades ?? 0 },
      { label: "Losing Trades", value: account?.losing_trades ?? 0 },
      { label: "Win Rate", value: formatPercent(account?.win_rate ?? 0) },
      { label: "Average R:R", value: account?.average_reward_risk ? `${formatNumber(account.average_reward_risk, 2)}:1` : "N/A" },
      { label: "Realized P&L", value: formatCurrency(account?.realized_pnl ?? 0) },
      { label: "Profit Factor", value: account?.profit_factor ? formatNumber(account.profit_factor, 2) : "N/A" },
      { label: "Current Equity", value: formatCurrency(account?.current_equity ?? 0) },
      { label: "Max Drawdown", value: `${formatCurrency(account?.max_drawdown ?? 0)} (${formatNumber(account?.max_drawdown_percent ?? 0, 2)}%)` },
    ],
    [account],
  );

  async function setBotRunning(shouldRun) {
    setBotActionPending(true);
    try {
      const response = await fetch(`${API_BASE_URL}/bot/${shouldRun ? "start" : "stop"}`, { method: "POST" });
      if (!response.ok) {
        throw new Error("Bot control request failed.");
      }
      const state = await response.json();
      setSnapshot((current) => current ? { ...current, bot_state: state } : current);
      setError("");
    } catch (caughtError) {
      setError(caughtError.message);
    } finally {
      setBotActionPending(false);
    }
  }

  return (
    <main className="min-h-screen bg-[#07090d] text-zinc-100">
      <div className="mx-auto flex min-h-screen max-w-7xl flex-col px-4 py-4 sm:px-6 lg:px-8">
        <TopBar
          backendReachable={backendReachable}
          currentSymbol={snapshot?.current_symbol ?? "QQQ"}
          currentSession={snapshot?.current_session ?? "Loading"}
          lastUpdated={lastUpdated}
        />

        {error ? (
          <div className="mt-4 rounded border border-red-500/40 bg-red-500/10 px-4 py-3 text-sm text-red-100">
            {error}
          </div>
        ) : null}

        {snapshot?.configuration_warnings?.length ? (
          <div className="mt-4 rounded border border-amber-400/40 bg-amber-400/10 px-4 py-3 text-sm text-amber-100">
            <p className="font-semibold">Runtime configuration warnings</p>
            <ul className="mt-2 list-disc space-y-1 pl-5">
              {snapshot.configuration_warnings.map((warning) => (
                <li key={warning}>{warning}</li>
              ))}
            </ul>
          </div>
        ) : null}

        <section className="grid gap-4 py-4 xl:grid-cols-[0.85fr_1.15fr]">
          <Panel title="Account" icon={BarChart3}>
            <div className="grid grid-cols-2 gap-3 md:grid-cols-3">
              {topMetrics.map((metric) => (
                <Metric key={metric.label} label={metric.label} value={metric.value} />
              ))}
            </div>
          </Panel>

          <BotControlPanel
            botState={snapshot?.bot_state}
            pending={botActionPending}
            onStart={() => setBotRunning(true)}
            onStop={() => setBotRunning(false)}
          />
        </section>

        <section className="pb-4">
          <StrategyWorkerPanel
            strategyState={snapshot?.strategy_state}
            strategySignals={snapshot?.strategy_signals ?? []}
          />
        </section>

        <section className="pb-4">
          <LatestTradePanel trade={latestTrade} />
        </section>

        <section className="grid flex-1 gap-4 pb-4 xl:grid-cols-[1fr_1.15fr]">
          <Panel title="AI Analysis" icon={Brain}>
            <div className="grid gap-4">
              <AnalysisBlock title="Plain English Explanation" text={displayAnalysis.plain_english_explanation} />
              <AnalysisBlock title="Why The Trade Qualified" text={displayAnalysis.why_the_trade_qualified} />
              <AnalysisBlock title="Risk Factors" text={displayAnalysis.risk_factors} />
              <AnalysisBlock title="What To Watch After Entry" text={displayAnalysis.watch_after_entry} />
              <AnalysisBlock title="Educational Summary" text={displayAnalysis.educational_summary} />
            </div>
          </Panel>

          <Panel title="Trade History" icon={Activity}>
            <TradeHistory
              trades={snapshot?.trades ?? []}
              selectedTradeId={displayTrade?.id}
              onSelect={setSelectedTradeId}
            />
          </Panel>
        </section>

        <section className="grid gap-4 pb-4 xl:grid-cols-2">
          <Panel title="Open Positions" icon={WalletCards}>
            <PositionTable positions={snapshot?.open_positions ?? []} emptyText="No paper positions are open." />
          </Panel>
          <Panel title="Closed Positions" icon={Activity}>
            <PositionTable positions={snapshot?.closed_positions ?? []} emptyText="No paper positions have closed yet." />
          </Panel>
        </section>

        <section className="pb-4">
          <Panel title="Equity Curve & Drawdown" icon={TrendingUp}>
            <EquityCurve points={snapshot?.equity_curve ?? []} />
            <div className="mt-4 flex flex-wrap gap-3 text-sm">
              <a className="rounded border border-cyan-400/40 px-3 py-2 text-cyan-200 hover:bg-cyan-400/10" href={`${API_BASE_URL}/reports/trade-journal.csv`}>Export Trade Journal CSV</a>
              <a className="rounded border border-zinc-700 px-3 py-2 text-zinc-200 hover:bg-zinc-800" href={`${API_BASE_URL}/reports/performance.json`}>Export Performance JSON</a>
              <a className="rounded border border-zinc-700 px-3 py-2 text-zinc-200 hover:bg-zinc-800" href={`${API_BASE_URL}/reports/performance.csv`}>Export Performance CSV</a>
            </div>
          </Panel>
        </section>

        <section className="pb-4">
          <Panel title="Webhook Delivery Audit" icon={ShieldCheck}>
            <DeliveryAudit
              deliveries={snapshot?.webhook_deliveries ?? []}
              jobs={snapshot?.analysis_jobs ?? {}}
              queue={snapshot?.analysis_queue}
            />
          </Panel>
        </section>
      </div>
    </main>
  );
}

function StrategyWorkerPanel({ strategyState, strategySignals }) {
  return (
    <Panel title="Standalone Strategy Worker" icon={Activity}>
      <div className="grid gap-3 md:grid-cols-4">
        <Metric label="Status" value={strategyState?.status ?? "UNKNOWN"} />
        <Metric label="Symbol" value={strategyState?.symbol ?? "QQQ"} />
        <Metric label="Last Bar" value={formatTime(strategyState?.last_bar_at)} />
        <Metric label="Latest Signal" value={strategyState?.latest_signal ?? "None"} />
      </div>
      <div className="mt-4 grid gap-3 md:grid-cols-3">
        <Quote label="Opening Range High" value={formatNumber(strategyState?.opening_range_high)} />
        <Quote label="Opening Range Low" value={formatNumber(strategyState?.opening_range_low)} />
        <Quote label="Session Date" value={strategyState?.session_date ?? "N/A"} />
      </div>
      <p className="mt-4 rounded border border-zinc-800 bg-[#0b1017] p-3 text-sm text-zinc-300">
        {strategyState?.message ?? "The Alpaca market-data strategy worker has not reported state yet."}
      </p>
      <div className="mt-4">
        <p className="mb-2 text-xs uppercase tracking-[0.2em] text-zinc-500">Recent Strategy Candidates</p>
        {!strategySignals.length ? <EmptyState text="No selected or rejected strategy candidates have been recorded since reset." /> : (
          <div className="overflow-x-auto">
            <table className="w-full min-w-[760px] text-left text-sm">
              <thead>
                <tr className="border-b border-zinc-800 text-xs uppercase tracking-widest text-zinc-500">
                  <th className="py-3 pr-3">Time</th>
                  <th className="py-3 pr-3">Strategy</th>
                  <th className="py-3 pr-3">Action</th>
                  <th className="py-3 pr-3">Score</th>
                  <th className="py-3 pr-3">Status</th>
                  <th className="py-3">Reason</th>
                </tr>
              </thead>
              <tbody>
                {strategySignals.map((signal) => (
                  <tr key={signal.id} className="border-b border-zinc-900">
                    <td className="py-3 pr-3 text-zinc-300">{formatTime(signal.created_at)}</td>
                    <td className="py-3 pr-3 font-mono text-xs text-zinc-200">{signal.strategy_name}</td>
                    <td className="py-3 pr-3"><ActionBadge action={signal.action} /></td>
                    <td className="py-3 pr-3 font-mono">{signal.score}</td>
                    <td className={`py-3 pr-3 font-semibold ${signal.status === "SELECTED" ? "text-emerald-300" : "text-amber-200"}`}>
                      {signal.status}
                    </td>
                    <td className="py-3 text-zinc-400">{signal.reason}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </Panel>
  );
}

function BotControlPanel({ botState, pending, onStart, onStop }) {
  const running = botState?.status === "RUNNING";
  return (
    <Panel title="Bot Control" icon={ShieldCheck}>
      <div className="grid gap-4 lg:grid-cols-[1fr_auto] lg:items-center">
        <div>
          <p className="text-xs uppercase tracking-[0.2em] text-zinc-500">Execution State</p>
          <p className={`mt-2 text-3xl font-semibold ${running ? "text-emerald-300" : "text-amber-200"}`}>
            {botState?.status ?? "UNKNOWN"}
          </p>
          <p className="mt-2 text-sm text-zinc-400">
            Mode: <span className="font-mono text-zinc-200">{botState?.execution_mode ?? "internal_paper"}</span>
          </p>
          <p className="mt-2 text-sm text-zinc-300">{botState?.message ?? "Bot state is loading."}</p>
          <p className="mt-2 text-xs text-zinc-500">
            Start arms external paper execution. Webhooks are still audited even when the bot is stopped.
          </p>
        </div>
        <div className="flex gap-3">
          <button
            className="rounded border border-emerald-400/50 bg-emerald-400/10 px-4 py-2 text-sm font-semibold text-emerald-100 disabled:cursor-not-allowed disabled:opacity-50"
            disabled={pending || running}
            onClick={onStart}
            type="button"
          >
            Start Bot
          </button>
          <button
            className="rounded border border-red-400/50 bg-red-400/10 px-4 py-2 text-sm font-semibold text-red-100 disabled:cursor-not-allowed disabled:opacity-50"
            disabled={pending || !running}
            onClick={onStop}
            type="button"
          >
            Stop Bot
          </button>
        </div>
      </div>
    </Panel>
  );
}

function DeliveryAudit({ deliveries, jobs, queue }) {
  const queueCounts = queue?.counts ?? jobs;
  const hasQueueIssue = (queue?.stale_running_jobs ?? 0) > 0 || Boolean(queue?.latest_failure);

  return (
    <div>
      <div className={`mb-4 rounded border px-3 py-3 ${hasQueueIssue ? "border-amber-400/40 bg-amber-400/10" : "border-zinc-800 bg-zinc-950/40"}`}>
        <div className="flex flex-col gap-2 md:flex-row md:items-start md:justify-between">
          <div>
            <p className="text-xs uppercase tracking-[0.2em] text-zinc-500">Durable Analysis Worker</p>
            <p className="mt-1 text-sm text-zinc-200">
              Jobs: {Object.entries(queueCounts).map(([status, count]) => `${status} ${count}`).join(" · ") || "none"}
            </p>
          </div>
          <div className="grid gap-1 text-xs text-zinc-400 sm:grid-cols-3 md:text-right">
            <span>Oldest pending: {queue?.oldest_available_at ? formatTime(queue.oldest_available_at) : "none"}</span>
            <span>Pending age: {formatDuration(queue?.pending_age_seconds)}</span>
            <span>Stale locks: {queue?.stale_running_jobs ?? 0}</span>
          </div>
        </div>
        {queue?.latest_failure ? (
          <p className="mt-2 truncate text-xs text-amber-200" title={queue.latest_failure}>
            Latest failure: {queue.latest_failure}
          </p>
        ) : null}
      </div>
      {!deliveries.length ? <EmptyState text="No audited webhook deliveries have been received yet." /> : (
        <div className="overflow-x-auto">
          <table className="w-full min-w-[700px] text-left text-sm">
            <thead><tr className="border-b border-zinc-800 text-xs uppercase tracking-widest text-zinc-500">
              <th className="py-3 pr-3">Received</th><th className="py-3 pr-3">Status</th><th className="py-3 pr-3">HTTP</th><th className="py-3 pr-3">Event ID</th><th className="py-3">Error</th>
            </tr></thead>
            <tbody>{deliveries.map((delivery) => (
              <tr key={delivery.id} className="border-b border-zinc-900">
                <td className="py-3 pr-3 text-zinc-300">{formatTime(delivery.received_at)}</td>
                <td className="py-3 pr-3 font-semibold text-white">{delivery.status}</td>
                <td className="py-3 pr-3 font-mono">{delivery.response_status}</td>
                <td className="py-3 pr-3 font-mono text-xs">{delivery.event_id ?? "N/A"}</td>
                <td className="max-w-sm truncate py-3 text-red-200" title={delivery.error_message ?? ""}>{delivery.error_message?.slice(0, 140) ?? "—"}</td>
              </tr>
            ))}</tbody>
          </table>
        </div>
      )}
    </div>
  );
}

function EquityCurve({ points }) {
  if (!points.length) return <EmptyState text="The equity curve begins after the first recorded position closes." />;
  const width = 900;
  const height = 240;
  const equities = points.map((point) => point.equity);
  const min = Math.min(...equities);
  const max = Math.max(...equities);
  const range = Math.max(max - min, 1);
  const coordinates = points.map((point, index) => {
    const x = points.length === 1 ? width / 2 : (index / (points.length - 1)) * width;
    const y = height - ((point.equity - min) / range) * (height - 32) - 16;
    return `${x},${y}`;
  }).join(" ");
  return (
    <div>
      <svg viewBox={`0 0 ${width} ${height}`} className="h-64 w-full rounded bg-[#0b1017]" role="img" aria-label="Account equity curve">
        <polyline points={coordinates} fill="none" stroke="#67e8f9" strokeWidth="4" strokeLinejoin="round" />
      </svg>
      <div className="mt-2 flex justify-between text-xs text-zinc-500">
        <span>{formatTime(points[0].timestamp)}</span>
        <span>Latest equity: {formatCurrency(points.at(-1).equity)}</span>
        <span>{formatTime(points.at(-1).timestamp)}</span>
      </div>
    </div>
  );
}

function formatCurrency(value) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) return "N/A";
  return new Intl.NumberFormat(undefined, { style: "currency", currency: "USD" }).format(Number(value));
}

function PositionTable({ positions, emptyText }) {
  if (!positions.length) return <EmptyState text={emptyText} />;
  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[620px] border-collapse text-left text-sm">
        <thead>
          <tr className="border-b border-zinc-800 text-xs uppercase tracking-widest text-zinc-500">
            <th className="py-3 pr-3 font-medium">Opened</th>
            <th className="py-3 pr-3 font-medium">Side</th>
            <th className="py-3 pr-3 font-medium">Qty</th>
            <th className="py-3 pr-3 font-medium">Entry</th>
            <th className="py-3 pr-3 font-medium">Exit</th>
            <th className="py-3 font-medium">P&L</th>
          </tr>
        </thead>
        <tbody>
          {positions.map((position) => (
            <tr key={position.id} className="border-b border-zinc-900">
              <td className="py-3 pr-3 text-zinc-300">{formatTime(position.opened_at)}</td>
              <td className="py-3 pr-3 font-semibold text-white">{position.side}</td>
              <td className="py-3 pr-3 font-mono">{formatNumber(position.quantity, 4)}</td>
              <td className="py-3 pr-3 font-mono">{formatNumber(position.entry_price)}</td>
              <td className="py-3 pr-3 font-mono">{formatNumber(position.exit_price)}</td>
              <td className={`py-3 font-mono ${(position.realized_pnl ?? 0) >= 0 ? "text-emerald-300" : "text-red-300"}`}>
                {position.realized_pnl === null ? "Open" : formatCurrency(position.realized_pnl)}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function TopBar({ backendReachable, currentSymbol, currentSession, lastUpdated }) {
  return (
    <header className="flex flex-col gap-3 border-b border-zinc-800/90 pb-4 md:flex-row md:items-center md:justify-between">
      <div>
        <div className="flex items-center gap-3">
          <ShieldCheck className="text-cyan-300" size={24} aria-hidden="true" />
          <h1 className="text-xl font-semibold tracking-wide text-white">Blackout Quant</h1>
        </div>
        <p className="mt-1 text-xs uppercase tracking-[0.22em] text-zinc-500">Paper Trading Workstation</p>
      </div>

      <div className="grid gap-2 text-sm sm:grid-cols-3">
        <StatusPill label="Backend Status" value={backendReachable ? "Reachable" : "Offline"} active={backendReachable} />
        <StatusPill label="Current Symbol" value={currentSymbol} active />
        <StatusPill label="Current Session" value={currentSession} active={currentSession !== "Outside Trading Window"} />
      </div>

      <div className="flex items-center gap-2 text-xs text-zinc-500">
        <Clock3 size={14} aria-hidden="true" />
        <span>Auto refresh 3s</span>
        <span>{lastUpdated ? formatTime(lastUpdated) : "Waiting"}</span>
      </div>
    </header>
  );
}

function StatusPill({ label, value, active }) {
  return (
    <div className="rounded border border-zinc-800 bg-zinc-950 px-3 py-2">
      <p className="text-[10px] uppercase tracking-widest text-zinc-500">{label}</p>
      <div className="mt-1 flex items-center gap-2">
        <Circle className={active ? "fill-emerald-400 text-emerald-400" : "fill-red-400 text-red-400"} size={9} />
        <span className="font-medium text-zinc-100">{value}</span>
      </div>
    </div>
  );
}

function Panel({ title, icon: Icon, children }) {
  return (
    <section className="rounded border border-zinc-800 bg-zinc-950/80 p-4 shadow-2xl shadow-black/20">
      <div className="mb-4 flex items-center gap-2 border-b border-zinc-800 pb-3">
        <Icon size={17} className="text-cyan-300" aria-hidden="true" />
        <h2 className="text-sm font-semibold uppercase tracking-[0.18em] text-zinc-300">{title}</h2>
      </div>
      {children}
    </section>
  );
}

function Metric({ label, value }) {
  return (
    <div className="rounded border border-zinc-800 bg-[#0b1017] p-3">
      <p className="text-xs text-zinc-500">{label}</p>
      <p className="mt-2 text-xl font-semibold text-white">{value}</p>
    </div>
  );
}

function LatestTradePanel({ trade }) {
  const confidence = trade?.analysis?.confidence_score ?? 0;
  const grade = normalizeGrade(trade?.analysis?.trade_grade, confidence);

  return (
    <Panel title="Latest Trade" icon={trade?.action === "SELL" ? TrendingDown : TrendingUp}>
      {trade ? (
        <div className="grid gap-4 lg:grid-cols-[0.8fr_1.2fr]">
          <div>
            <div className="flex items-center gap-3">
              <span className="text-3xl font-semibold text-white">{trade.ticker}</span>
              <ActionBadge action={trade.action} />
              <GradeBadge grade={grade} />
            </div>
            <p className="mt-2 text-sm text-zinc-500">{formatTime(trade.timestamp)}</p>
            <div className="mt-5">
              <p className="text-xs uppercase tracking-widest text-zinc-500">Confidence</p>
              <ConfidenceBar score={confidence} />
            </div>
          </div>

          <div className="grid grid-cols-3 gap-3">
            <Quote label="Entry Price" value={formatNumber(trade.price)} />
            <Quote label="Stop Loss" value={formatNumber(trade.stop_loss)} />
            <Quote label="Take Profit" value={formatNumber(trade.take_profit)} />
          </div>
        </div>
      ) : (
        <EmptyState text="No trades have been saved yet." />
      )}
    </Panel>
  );
}

function Quote({ label, value }) {
  return (
    <div className="rounded border border-zinc-800 bg-[#0b1017] p-3">
      <p className="text-xs text-zinc-500">{label}</p>
      <p className="mt-2 font-mono text-lg text-white">{value}</p>
    </div>
  );
}

function ActionBadge({ action }) {
  return (
    <span className={`rounded border px-2.5 py-1 text-xs font-semibold ${actionStyles(action)}`}>
      {action}
    </span>
  );
}

function GradeBadge({ grade }) {
  return (
    <span className="rounded border border-cyan-300/40 bg-cyan-300/10 px-2.5 py-1 text-xs font-semibold text-cyan-100">
      {grade}
    </span>
  );
}

function ConfidenceBar({ score }) {
  return (
    <div className="mt-2">
      <div className="h-2 overflow-hidden rounded bg-zinc-800">
        <div className={`h-full ${confidenceClass(score)}`} style={{ width: `${Math.min(100, Math.max(0, score))}%` }} />
      </div>
      <p className="mt-1 font-mono text-sm text-zinc-300">{score}/100</p>
    </div>
  );
}

function AnalysisBlock({ title, text }) {
  return (
    <article className="rounded border border-zinc-800 bg-[#0b1017] p-3">
      <h3 className="text-xs font-semibold uppercase tracking-widest text-zinc-500">{title}</h3>
      <p className="mt-2 leading-7 text-zinc-200">{text || "Cannot be determined from stored data."}</p>
    </article>
  );
}

function TradeHistory({ trades, selectedTradeId, onSelect }) {
  if (!trades.length) {
    return <EmptyState text="Webhook trades will appear here automatically." />;
  }

  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[720px] border-collapse text-left text-sm">
        <thead>
          <tr className="border-b border-zinc-800 text-xs uppercase tracking-widest text-zinc-500">
            <th className="py-3 pr-3 font-medium">Time</th>
            <th className="py-3 pr-3 font-medium">Ticker</th>
            <th className="py-3 pr-3 font-medium">Action</th>
            <th className="py-3 pr-3 font-medium">Entry</th>
            <th className="py-3 pr-3 font-medium">Grade</th>
            <th className="py-3 pr-3 font-medium">Confidence</th>
            <th className="py-3 font-medium">Outcome</th>
          </tr>
        </thead>
        <tbody>
          {trades.map((trade) => {
            const selected = trade.id === selectedTradeId;
            const score = trade.analysis?.confidence_score ?? 0;
            const grade = normalizeGrade(trade.analysis?.trade_grade, score);

            return (
              <tr
                className={`cursor-pointer border-b border-zinc-900 transition hover:bg-zinc-900/80 ${selected ? "bg-cyan-300/5" : ""}`}
                key={trade.id}
                onClick={() => onSelect(trade.id)}
              >
                <td className="py-3 pr-3 text-zinc-300">{formatTime(trade.timestamp)}</td>
                <td className="py-3 pr-3 font-semibold text-white">{trade.ticker}</td>
                <td className="py-3 pr-3"><ActionBadge action={trade.action} /></td>
                <td className="py-3 pr-3 font-mono text-zinc-100">{formatNumber(trade.price)}</td>
                <td className="py-3 pr-3"><GradeBadge grade={grade} /></td>
                <td className="py-3 pr-3">
                  <div className="max-w-32">
                    <ConfidenceBar score={score} />
                  </div>
                </td>
                <td className="py-3 text-zinc-400">{trade.outcome ?? "N/A"}</td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

function EmptyState({ text }) {
  return (
    <div className="flex min-h-32 items-center justify-center rounded border border-dashed border-zinc-800 bg-[#0b1017] text-sm text-zinc-500">
      {text}
    </div>
  );
}

export default App;
