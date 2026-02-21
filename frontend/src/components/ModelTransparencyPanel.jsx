import { useState, useEffect } from 'react';
import { getApiBase } from '../api';

const EUR_TO_INR = 90.0;

export default function ModelTransparencyPanel({ currency = 'EUR' }) {
    const [modelData, setModelData] = useState(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(null);
    const [isExplanationOpen, setIsExplanationOpen] = useState(false);

    useEffect(() => {
        const fetchModelInfo = async () => {
            try {
                const response = await fetch(`${getApiBase()}/predict-price/model-info`);
                if (!response.ok) throw new Error('Failed to fetch model transparency data');
                const data = await response.json();
                if (data.status === "No deployed model") {
                    throw new Error("Model currently unavailable. Please try again later.");
                }
                setModelData(data);
            } catch (err) {
                setError(err.message || "Model transparency data unavailable.");
            } finally {
                setLoading(false);
            }
        };

        fetchModelInfo();
    }, []);

    if (loading) {
        return (
            <div className="w-full bg-white dark:bg-gray-900 rounded-2xl shadow-sm p-6 border border-slate-100 dark:border-gray-800 flex items-center justify-center min-h-[300px] overflow-hidden transition-colors">
                <div className="animate-spin h-6 w-6 border-2 border-slate-300 dark:border-gray-700 border-t-blue-600 dark:border-t-blue-500 rounded-full"></div>
            </div>
        );
    }

    if (error) {
        return (
            <div className="w-full bg-white dark:bg-gray-900 rounded-2xl shadow-sm p-6 border border-red-100 dark:border-red-900/50 overflow-hidden transition-colors">
                <h2 className="text-xl font-semibold text-slate-800 dark:text-gray-100 mb-4">Model Transparency</h2>
                <div className="p-3 bg-red-50 dark:bg-red-900/20 text-red-600 dark:text-red-400 text-sm rounded-lg border border-red-100 dark:border-red-900/50">
                    {error}
                </div>
            </div>
        );
    }

    const badgeColor = modelData?.status === 'deployed'
        ? 'bg-emerald-50 dark:bg-emerald-950/30 text-emerald-700 dark:text-emerald-400 border-emerald-200 dark:border-emerald-800/50'
        : modelData?.status === 'candidate'
            ? 'bg-yellow-50 dark:bg-yellow-950/30 text-yellow-700 dark:text-yellow-400 border-yellow-200 dark:border-yellow-800/50'
            : 'bg-slate-50 dark:bg-gray-800 text-slate-700 dark:text-gray-300 border-slate-200 dark:border-gray-700';

    const r2Percentage = modelData?.test_r2 ? (modelData.test_r2 * 100).toFixed(1) : 'N/A';

    // MAE is stored in EUR; convert display-only
    const maeEur = modelData?.test_mae ?? null;
    const displayMAE = maeEur !== null
        ? (currency === 'EUR' ? maeEur : maeEur * EUR_TO_INR)
        : null;

    const maeFormatter = displayMAE !== null
        ? new Intl.NumberFormat(
            currency === 'EUR' ? 'de-DE' : 'en-IN',
            { style: 'currency', currency: currency, maximumFractionDigits: 2 }
        )
        : null;

    return (
        <div className="w-full h-full bg-white dark:bg-gray-900 rounded-2xl shadow-sm border border-slate-100 dark:border-gray-800 overflow-hidden flex flex-col transition-colors">
            <div className="p-6 border-b border-slate-100 dark:border-gray-800 shrink-0">
                <div className="flex justify-between items-center mb-4">
                    <h2 className="text-xl font-semibold text-slate-800 dark:text-gray-100">Model Transparency</h2>
                    <span className={`px-3 py-1 text-xs font-bold rounded-full border border-opacity-50 uppercase tracking-wider ${badgeColor}`}>
                        {modelData?.status || 'Unknown'}
                    </span>
                </div>
                <div className="text-sm font-mono bg-slate-50 dark:bg-gray-800/50 text-slate-600 dark:text-gray-400 px-3 py-2 rounded-lg border border-slate-200 dark:border-gray-700 truncate">
                    {modelData?.model_version || 'N/A'}
                </div>
            </div>

            <div className="flex-1 overflow-y-auto p-6">
                <div className="grid grid-cols-2 gap-4 mb-6">
                    <div className="bg-slate-50 dark:bg-gray-800 p-4 rounded-xl border border-slate-100 dark:border-gray-700 text-center">
                        <div className="text-sm font-medium text-slate-500 dark:text-gray-400 mb-1">Holdout R²</div>
                        <div className="text-2xl font-bold text-slate-900 dark:text-gray-100">{r2Percentage}%</div>
                    </div>
                    <div className="bg-slate-50 dark:bg-gray-800 p-4 rounded-xl border border-slate-100 dark:border-gray-700 text-center">
                        <div className="text-sm font-medium text-slate-500 dark:text-gray-400 mb-1">Holdout MAE</div>
                        <div className="text-2xl font-bold text-slate-900 dark:text-gray-100">
                            {maeFormatter && displayMAE !== null ? maeFormatter.format(displayMAE) : 'N/A'}
                        </div>
                    </div>
                </div>

                <div className="text-sm text-slate-500 dark:text-gray-400 mb-6 border-b border-slate-100 dark:border-gray-800 pb-6">
                    Trained: <span className="font-semibold text-slate-700 dark:text-gray-300">{modelData?.trained_at ? new Date(modelData.trained_at).toLocaleString() : 'N/A'}</span>
                </div>

                <div>
                    <button
                        onClick={() => setIsExplanationOpen(!isExplanationOpen)}
                        className="w-full flex items-center justify-between text-sm font-semibold text-blue-600 dark:text-blue-400 hover:text-blue-700 dark:hover:text-blue-300 transition-colors"
                    >
                        How This Model Works
                        <svg className={`w-4 h-4 transform transition-transform ${isExplanationOpen ? 'rotate-180' : ''}`} fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M19 9l-7 7-7-7"></path>
                        </svg>
                    </button>

                    {isExplanationOpen && (
                        <div className="mt-4 p-4 bg-blue-50 dark:bg-blue-900/10 rounded-xl border border-blue-100 dark:border-blue-900/30 text-sm text-slate-700 dark:text-gray-300 space-y-2 animate-fade-in shadow-inner">
                            <div className="flex gap-2">
                                <span className="text-blue-500 dark:text-blue-400 font-bold">•</span>
                                <span>Chronological temporal training simulating true real-world forward bounds.</span>
                            </div>
                            <div className="flex gap-2">
                                <span className="text-blue-500 dark:text-blue-400 font-bold">•</span>
                                <span>Yield-management approximations using rolling airline-level moving averages.</span>
                            </div>
                            <div className="flex gap-2">
                                <span className="text-blue-500 dark:text-blue-400 font-bold">•</span>
                                <span>Weekly retraining automated through containerized CI/CD schedules natively.</span>
                            </div>
                            <div className="flex gap-2">
                                <span className="text-blue-500 dark:text-blue-400 font-bold">•</span>
                                <span>Strict Deployment Gates: New models only deploy if validation MAE drops organically.</span>
                            </div>
                            <div className="flex gap-2">
                                <span className="text-blue-500 dark:text-blue-400 font-bold">•</span>
                                <span>Automated guardrails rejecting models failing random permutation leakage audits.</span>
                            </div>
                            <div className="mt-2 pt-2 border-t border-blue-100 dark:border-blue-900/30 text-xs text-slate-500 dark:text-gray-400">
                                Base currency: EUR · Display currency: {currency}
                            </div>
                        </div>
                    )}
                </div>
            </div>
        </div>
    );
}

