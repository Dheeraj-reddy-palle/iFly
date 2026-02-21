import { useState, useRef } from 'react';
import { predictPrice } from '../api';

const ROUTES = [
    { origin: "DEL", destination: "BOM", airline: "AI" },
    { origin: "BLR", destination: "DEL", airline: "6E" },
    { origin: "BOM", destination: "BLR", airline: "SG" },
    { origin: "JFK", destination: "LHR", airline: "BA" },
    { origin: "LHR", destination: "DXB", airline: "EK" },
    { origin: "SIN", destination: "FRA", airline: "LH" },
];

const getTodayDateString = () => {
    const today = new Date();
    today.setMinutes(today.getMinutes() - today.getTimezoneOffset());
    return today.toISOString().split('T')[0];
};

const EXPLANATIONS = [
    "Live API endpoint availability",
    "Model inference execution consistency",
    "Response latency under sequential load",
    "Frontend state isolation integrity",
    "Error rate tracking under repetition",
    "Deployment stability of active model version",
];

export default function StressTestPanel() {
    // dual state: string for display, number for logic
    const [runInput, setRunInput] = useState("16");
    const [runCount, setRunCount] = useState(16);

    const [currentRun, setCurrentRun] = useState(0);
    const [successCount, setSuccessCount] = useState(0);
    const [failCount, setFailCount] = useState(0);
    const [isRunning, setIsRunning] = useState(false);
    const [isDone, setIsDone] = useState(false);
    const [liveLatency, setLiveLatency] = useState(null);
    const [avgLatency, setAvgLatency] = useState(0);
    const [history, setHistory] = useState([]);
    const [routeLog, setRouteLog] = useState([]);
    const [explanationOpen, setExplanationOpen] = useState(false);

    const stopRef = useRef(false);

    const runStressTest = async () => {
        setCurrentRun(0);
        setSuccessCount(0);
        setFailCount(0);
        setAvgLatency(0);
        setLiveLatency(null);
        setIsDone(false);
        setRouteLog([]);

        stopRef.current = false;
        setIsRunning(true);

        let localSuccess = 0;
        let localFail = 0;
        let rollingAvg = 0;

        for (let i = 0; i < runCount; i++) {
            if (stopRef.current) break;

            const scenario = ROUTES[i % ROUTES.length];
            const payload = {
                origin: scenario.origin,
                destination: scenario.destination,
                departure_date: getTodayDateString(),
                airline: scenario.airline,
                stops: 0,
            };

            const start = performance.now();
            let status = "OK";
            try {
                await predictPrice(payload);
                localSuccess++;
                setSuccessCount(localSuccess);
            } catch {
                localFail++;
                setFailCount(localFail);
                status = "FAIL";
            }
            const latency = Math.round(performance.now() - start);
            setLiveLatency(latency);

            // rolling average
            rollingAvg = ((rollingAvg * i) + latency) / (i + 1);
            setAvgLatency(rollingAvg);

            // route fetch log
            setRouteLog((prev) => [
                {
                    route: `${scenario.origin}→${scenario.destination}`,
                    airline: scenario.airline,
                    latency,
                    status,
                },
                ...prev,
            ].slice(0, 4));

            setCurrentRun(i + 1);
            await new Promise((r) => setTimeout(r, 150));
        }

        const completedRuns = localSuccess + localFail;
        const finalHealth = completedRuns > 0
            ? Math.round((localSuccess / completedRuns) * 100)
            : 0;

        setHistory((prev) => [
            {
                timestamp: new Date().toLocaleString(),
                runs: completedRuns,
                success: localSuccess,
                failed: localFail,
                health: finalHealth,
                avgLatency: Math.round(rollingAvg),
            },
            ...prev.slice(0, 4),
        ]);

        setIsRunning(false);
        setIsDone(true);
        setRunInput("16");
        setRunCount(16);
    };

    const stopTest = () => {
        stopRef.current = true;
        setIsRunning(false);
    };

    const completedRuns = successCount + failCount;
    const progress = runCount > 0
        ? Math.min(100, (currentRun / runCount) * 100)
        : 0;

    const healthScore = completedRuns > 0
        ? Math.round((successCount / completedRuns) * 100)
        : null;

    const healthConfig = healthScore !== null
        ? healthScore >= 95
            ? { label: 'SYSTEM STABLE', bg: 'bg-emerald-50 dark:bg-emerald-950/30', text: 'text-emerald-700 dark:text-emerald-400', border: 'border-emerald-200 dark:border-emerald-800', dot: 'bg-emerald-500' }
            : healthScore >= 80
                ? { label: 'MINOR INSTABILITY', bg: 'bg-yellow-50 dark:bg-yellow-950/30', text: 'text-yellow-700 dark:text-yellow-400', border: 'border-yellow-200 dark:border-yellow-800', dot: 'bg-yellow-500' }
                : { label: 'UNSTABLE', bg: 'bg-red-50 dark:bg-red-950/30', text: 'text-red-700 dark:text-red-400', border: 'border-red-200 dark:border-red-800', dot: 'bg-red-500' }
        : null;

    return (
        <div className="w-full bg-white dark:bg-gray-900 rounded-2xl shadow-sm border border-slate-100 dark:border-gray-800 overflow-hidden transition-colors h-[520px] flex flex-col">

            {/* Header */}
            <div className="p-6 border-b border-slate-100 dark:border-gray-800 bg-slate-50/50 dark:bg-gray-800/50 shrink-0">
                <h2 className="text-xl font-semibold text-slate-800 dark:text-gray-100">System Stress Test Engine</h2>
                <p className="mt-1 text-slate-500 dark:text-gray-400 text-sm">Sequential inference load‑test with live health scoring and route monitoring.</p>
            </div>

            <div className="flex-1 overflow-hidden p-6">
                <div className="grid grid-cols-1 lg:grid-cols-2 gap-8 h-full">

                    {/* LEFT — Controls + Results */}
                    <div className="flex flex-col gap-5 overflow-y-auto pr-2">

                        {/* Expandable explanation */}
                        <div>
                            <button
                                onClick={() => setExplanationOpen(v => !v)}
                                className="w-full flex items-center justify-between text-xs font-semibold text-blue-600 dark:text-blue-400 hover:text-blue-700 dark:hover:text-blue-300 transition-colors"
                            >
                                What This Stress Test Evaluates
                                <svg className={`w-4 h-4 transform transition-transform ${explanationOpen ? 'rotate-180' : ''}`} fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M19 9l-7 7-7-7" />
                                </svg>
                            </button>
                            {explanationOpen && (
                                <div className="mt-3 p-4 bg-blue-50 dark:bg-blue-900/10 rounded-xl border border-blue-100 dark:border-blue-900/30 text-left text-xs text-slate-700 dark:text-gray-300 space-y-1.5">
                                    {EXPLANATIONS.map((item) => (
                                        <div key={item} className="flex gap-2">
                                            <span className="text-blue-500 font-bold shrink-0">•</span>
                                            <span>{item}</span>
                                        </div>
                                    ))}
                                </div>
                            )}
                        </div>

                        {/* Input */}
                        <div className="flex flex-col items-center gap-1.5">
                            <label className="text-xs font-semibold text-slate-500 dark:text-gray-400 uppercase tracking-wide">
                                Number of Runs <span className="text-slate-400 dark:text-gray-600 normal-case font-normal">(16–200)</span>
                            </label>
                            <input
                                type="text"
                                inputMode="numeric"
                                value={runInput}
                                onChange={(e) => {
                                    const raw = e.target.value;
                                    if (raw === "") { setRunInput(""); return; }
                                    if (!/^\d+$/.test(raw)) return;
                                    setRunInput(raw);
                                }}
                                onBlur={() => {
                                    let parsed = parseInt(runInput || "16", 10);
                                    parsed = Math.min(200, Math.max(16, parsed));
                                    setRunCount(parsed);
                                    setRunInput(String(parsed));
                                }}
                                disabled={isRunning}
                                className={`w-full max-w-[180px] text-center px-4 py-2.5 rounded-xl border border-slate-200 dark:border-gray-700 bg-white dark:bg-gray-800 text-slate-900 dark:text-gray-100 focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 transition-all font-semibold shadow-sm ${isRunning ? 'opacity-50 cursor-not-allowed' : ''}`}
                            />
                        </div>

                        {/* Buttons */}
                        <div className="flex items-center gap-3">
                            <button
                                onClick={runStressTest}
                                disabled={isRunning}
                                className={`flex-1 py-2.5 rounded-xl font-bold text-sm transition-all ${isRunning
                                    ? 'bg-indigo-300 dark:bg-indigo-900/50 cursor-not-allowed text-white dark:text-gray-400'
                                    : 'bg-indigo-600 hover:bg-indigo-700 text-white shadow-md shadow-indigo-200 dark:shadow-none'
                                    }`}
                            >
                                {isRunning ? (
                                    <span className="flex items-center justify-center gap-2">
                                        <svg className="animate-spin h-3.5 w-3.5" fill="none" viewBox="0 0 24 24">
                                            <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                                            <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                                        </svg>
                                        Running…
                                    </span>
                                ) : 'Start Test'}
                            </button>
                            <button
                                onClick={stopTest}
                                disabled={!isRunning}
                                className={`flex-1 py-2.5 rounded-xl font-bold text-sm border transition-all ${isRunning
                                    ? 'border-red-400 dark:border-red-600 text-red-600 dark:text-red-400 hover:bg-red-50 dark:hover:bg-red-900/20'
                                    : 'border-slate-200 dark:border-gray-700 text-slate-400 dark:text-gray-600 cursor-not-allowed'
                                    }`}
                            >
                                Stop
                            </button>
                        </div>

                        {/* Live latency */}
                        {isRunning && liveLatency !== null && (
                            <div className="text-xs font-semibold text-indigo-500 dark:text-indigo-400 text-center">
                                Live Latency: {liveLatency} ms
                            </div>
                        )}

                        {/* Progress bar */}
                        {(isRunning || isDone) && (
                            <div className="flex flex-col gap-1">
                                <div className="flex justify-between text-xs text-slate-500 dark:text-gray-400 font-medium">
                                    <span>{currentRun} / {currentRun > runCount ? currentRun : runCount} runs</span>
                                    <span>{Math.round(progress)}%</span>
                                </div>
                                <div className="w-full bg-gray-200 dark:bg-gray-800 rounded-full h-2">
                                    <div
                                        className="bg-indigo-500 h-2 rounded-full transition-all duration-300"
                                        style={{ width: `${progress}%` }}
                                    />
                                </div>
                            </div>
                        )}

                        {/* Health Badge */}
                        {healthConfig && completedRuns > 0 && (
                            <div className="flex justify-center">
                                <div className={`inline-flex items-center gap-2 px-4 py-2 rounded-xl border ${healthConfig.bg} ${healthConfig.border}`}>
                                    <span className={`w-2 h-2 rounded-full shrink-0 ${healthConfig.dot}`}></span>
                                    <span className={`text-xs font-bold uppercase tracking-widest ${healthConfig.text}`}>
                                        {healthConfig.label}
                                    </span>
                                </div>
                            </div>
                        )}

                        {/* Stats Grid */}
                        {completedRuns > 0 && (
                            <div className="grid grid-cols-2 gap-2">
                                {[
                                    { label: 'Successful', value: successCount, color: 'text-emerald-600 dark:text-emerald-400' },
                                    { label: 'Failed', value: failCount, color: 'text-red-500 dark:text-red-400' },
                                    { label: 'Health Score', value: healthScore !== null ? `${healthScore}%` : '—', color: 'text-indigo-600 dark:text-indigo-400' },
                                    { label: 'Avg Latency', value: avgLatency > 0 ? `${Math.round(avgLatency)} ms` : '—', color: 'text-slate-700 dark:text-gray-200' },
                                ].map(({ label, value, color }) => (
                                    <div key={label} className="bg-slate-50 dark:bg-gray-800 rounded-xl p-3 text-center border border-slate-100 dark:border-gray-700">
                                        <div className="text-[10px] font-medium text-slate-500 dark:text-gray-400 uppercase tracking-wide">{label}</div>
                                        <div className={`text-lg font-bold break-words ${color}`}>{value}</div>
                                    </div>
                                ))}
                            </div>
                        )}

                        {isDone && !isRunning && (
                            <p className="text-[11px] text-slate-400 dark:text-gray-600 text-center">
                                Test complete · {completedRuns} runs executed
                            </p>
                        )}

                        {/* Previous Results */}
                        {history.length > 0 && (
                            <div className="border-t border-slate-100 dark:border-gray-800 pt-4">
                                <p className="text-xs font-semibold text-slate-500 dark:text-gray-400 uppercase tracking-wide mb-3">
                                    Previous Test Results
                                </p>
                                <div className="flex flex-col gap-2">
                                    {history.map((h, idx) => (
                                        <div key={idx} className="flex items-center justify-between gap-2 bg-slate-50 dark:bg-gray-800 rounded-xl px-3 py-2.5 border border-slate-100 dark:border-gray-700 text-xs overflow-hidden">
                                            <div className="flex flex-col items-start min-w-0">
                                                <span className="text-slate-500 dark:text-gray-400 truncate">{h.timestamp}</span>
                                                <span className="text-slate-700 dark:text-gray-300 font-semibold">{h.runs} runs</span>
                                            </div>
                                            <div className="flex items-center gap-3 shrink-0">
                                                <span className={`font-bold ${h.health >= 95 ? 'text-emerald-600 dark:text-emerald-400' : h.health >= 80 ? 'text-yellow-600 dark:text-yellow-400' : 'text-red-500 dark:text-red-400'}`}>
                                                    {h.health}%
                                                </span>
                                                <span className="text-slate-400 dark:text-gray-500">{h.avgLatency}ms</span>
                                            </div>
                                        </div>
                                    ))}
                                </div>
                            </div>
                        )}
                    </div>

                    {/* RIGHT — Live Route Fetch Monitor + Architectural Note */}
                    <div className="flex flex-col gap-4 h-full overflow-hidden">
                        <div className="bg-slate-50 dark:bg-gray-800 rounded-xl p-5 border border-slate-100 dark:border-gray-700 h-[220px] flex flex-col shrink-0">
                            <div className="flex items-center justify-between mb-3 shrink-0">
                                <h3 className="text-sm font-semibold text-slate-800 dark:text-gray-100 uppercase tracking-wide">Live Route Fetch Monitor</h3>
                                {isRunning && (
                                    <span className="flex items-center gap-1.5 text-[10px] font-semibold text-emerald-600 dark:text-emerald-400">
                                        <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse"></span>
                                        Streaming
                                    </span>
                                )}
                            </div>

                            {routeLog.length === 0 ? (
                                <div className="flex-1 flex flex-col items-center justify-center text-slate-400 dark:text-gray-600">
                                    <svg className="w-8 h-8 mb-2 opacity-40" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="1.5" d="M9 17v-2m3 2v-4m3 4v-6m2 10H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                                    </svg>
                                    <p className="text-xs font-medium">No route data yet</p>
                                    <p className="text-[10px] mt-1">Start a stress test to see live fetches</p>
                                </div>
                            ) : (
                                <div className="space-y-2">
                                    {routeLog.map((r, idx) => (
                                        <div
                                            key={idx}
                                            className={`flex items-center justify-between text-xs px-3 py-2 rounded-lg border transition-all ${idx === 0 && isRunning
                                                ? 'bg-indigo-50 dark:bg-indigo-900/20 border-indigo-200 dark:border-indigo-800'
                                                : 'bg-white dark:bg-gray-900 border-slate-100 dark:border-gray-700'
                                                }`}
                                        >
                                            <div className="flex items-center gap-2.5 min-w-0">
                                                <span className={`w-1.5 h-1.5 rounded-full shrink-0 ${r.status === "OK" ? "bg-emerald-500" : "bg-red-500"}`}></span>
                                                <span className="font-semibold text-slate-700 dark:text-gray-200 truncate">{r.route}</span>
                                                <span className="text-slate-400 dark:text-gray-500 font-mono text-[10px]">{r.airline}</span>
                                            </div>
                                            <div className="flex items-center gap-2 shrink-0">
                                                <span className={`font-bold ${r.status === "OK" ? "text-emerald-600 dark:text-emerald-400" : "text-red-500 dark:text-red-400"}`}>
                                                    {r.latency}ms
                                                </span>
                                                <span className={`text-[10px] font-bold uppercase tracking-wider px-1.5 py-0.5 rounded ${r.status === "OK"
                                                    ? "bg-emerald-50 dark:bg-emerald-950/30 text-emerald-600 dark:text-emerald-400"
                                                    : "bg-red-50 dark:bg-red-950/30 text-red-600 dark:text-red-400"
                                                    }`}>
                                                    {r.status}
                                                </span>
                                            </div>
                                        </div>
                                    ))}
                                </div>
                            )}
                        </div>

                        {/* Architectural Note — fixed position, never moves */}
                        <div className="bg-white dark:bg-gray-900 p-4 rounded-xl border border-slate-100 dark:border-gray-800 border-l-4 border-l-indigo-500 shrink-0">
                            <p className="text-xs text-slate-500 dark:text-gray-400 leading-relaxed">
                                <strong className="text-slate-700 dark:text-gray-300 block mb-1 text-[10px] uppercase tracking-wide">Architectural Note</strong>
                                Inferences are routed through the actively deployed model without static fallback, guaranteeing continuous temporal alignment with market yield structures.
                            </p>
                        </div>
                    </div>

                </div>
            </div>
        </div>
    );
}
