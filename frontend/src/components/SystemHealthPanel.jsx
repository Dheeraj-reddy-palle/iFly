import { useState, useEffect } from 'react';
import { getApiBase } from '../api';

export default function SystemHealthPanel() {
    const [healthData, setHealthData] = useState(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(null);
    const [isDrawerOpen, setIsDrawerOpen] = useState(false);

    useEffect(() => {
        const fetchHealth = async () => {
            try {
                const response = await fetch(`${getApiBase()}/system-health`);
                if (!response.ok) throw new Error('Failed to fetch system health');
                const data = await response.json();
                setHealthData(data);
            } catch (err) {
                setError("System health data unavailable.");
            } finally {
                setLoading(false);
            }
        };

        fetchHealth();
    }, []);

    if (loading) {
        return (
            <div className="w-full bg-white dark:bg-gray-900 rounded-2xl shadow-sm p-6 border border-slate-100 dark:border-gray-800 flex items-center justify-center min-h-[300px] overflow-hidden transition-colors">
                <div className="animate-spin h-6 w-6 border-2 border-slate-300 dark:border-gray-700 border-t-indigo-600 dark:border-t-indigo-500 rounded-full"></div>
            </div>
        );
    }

    if (error) {
        return (
            <div className="w-full bg-white dark:bg-gray-900 rounded-2xl shadow-sm p-6 border border-red-100 dark:border-red-900/50 overflow-hidden transition-colors">
                <h2 className="text-xl font-semibold text-slate-800 dark:text-gray-100 mb-4">System Health</h2>
                <div className="p-3 bg-red-50 dark:bg-red-900/20 text-red-600 dark:text-red-400 text-sm rounded-lg border border-red-100 dark:border-red-900/50">
                    {error}
                </div>
            </div>
        );
    }

    return (
        <div className="w-full h-full bg-white dark:bg-gray-900 rounded-2xl shadow-sm border border-slate-100 dark:border-gray-800 overflow-hidden flex flex-col transition-colors">
            <div className="p-6 border-b border-slate-100 dark:border-gray-800 shrink-0">
                <div className="flex justify-between items-center">
                    <h2 className="text-xl font-semibold text-slate-800 dark:text-gray-100">System Health</h2>
                    <span className="flex items-center gap-1.5 text-xs font-semibold text-emerald-600 dark:text-emerald-400 bg-emerald-50 dark:bg-emerald-950/30 px-2 py-1 rounded-full border border-emerald-100 dark:border-emerald-800">
                        <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse"></span>
                        API Active
                    </span>
                </div>
            </div>

            <div className="flex-1 overflow-y-auto p-6">
                <div className="grid grid-cols-2 gap-4 mb-6">
                    <div className="bg-slate-50 dark:bg-gray-800 p-4 rounded-xl border border-slate-100 dark:border-gray-700">
                        <div className="text-sm font-medium text-slate-500 dark:text-gray-400 mb-1">Routes Tracked</div>
                        <div className="text-2xl font-bold text-slate-900 dark:text-gray-100">{healthData?.total_routes?.toLocaleString() || 0}</div>
                    </div>
                    <div className="bg-slate-50 dark:bg-gray-800 p-4 rounded-xl border border-slate-100 dark:border-gray-700">
                        <div className="text-sm font-medium text-slate-500 dark:text-gray-400 mb-1">Airlines Tracked</div>
                        <div className="text-2xl font-bold text-slate-900 dark:text-gray-100">{healthData?.total_airlines?.toLocaleString() || 0}</div>
                    </div>
                </div>

                <div className="bg-slate-50 dark:bg-gray-800 p-4 rounded-xl border border-slate-100 dark:border-gray-700 mb-6">
                    <div className="text-sm font-medium text-slate-500 dark:text-gray-400 mb-1">Data Points Optimized</div>
                    <div className="text-2xl font-bold text-slate-900 dark:text-gray-100">{healthData?.total_records?.toLocaleString() || 0}</div>
                </div>

                <div className="text-sm text-slate-500 dark:text-gray-400 mb-6">
                    Last Retrain: <span className="font-semibold text-slate-700 dark:text-gray-300">{healthData?.last_retrain_timestamp ? new Date(healthData.last_retrain_timestamp).toLocaleString() : 'N/A'}</span>
                </div>

                <div className="border-t border-slate-100 dark:border-gray-800 pt-4">
                    <button
                        onClick={() => setIsDrawerOpen(!isDrawerOpen)}
                        className="w-full flex items-center justify-between text-sm font-semibold text-indigo-600 dark:text-indigo-400 hover:text-indigo-700 dark:hover:text-indigo-300 transition-colors"
                    >
                        Engineering Details
                        <svg className={`w-4 h-4 transform transition-transform ${isDrawerOpen ? 'rotate-180' : ''}`} fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M19 9l-7 7-7-7"></path>
                        </svg>
                    </button>

                    {isDrawerOpen && (
                        <div className="mt-4 text-sm text-slate-600 dark:text-gray-400 space-y-2 animate-fade-in pl-2 border-l-2 border-indigo-100 dark:border-indigo-900/50">
                            <div className="flex gap-2">
                                <span className="text-indigo-400 dark:text-indigo-500">•</span>
                                <span>SQL window-based rolling features</span>
                            </div>
                            <div className="flex gap-2">
                                <span className="text-indigo-400 dark:text-indigo-500">•</span>
                                <span>Quota-aware route rotation</span>
                            </div>
                            <div className="flex gap-2">
                                <span className="text-indigo-400 dark:text-indigo-500">•</span>
                                <span>Permutation leakage protection</span>
                            </div>
                            <div className="flex gap-2">
                                <span className="text-indigo-400 dark:text-indigo-500">•</span>
                                <span>Dynamic model hot reload</span>
                            </div>
                            <div className="flex gap-2">
                                <span className="text-indigo-400 dark:text-indigo-500">•</span>
                                <span>Automated deployment gate</span>
                            </div>
                        </div>
                    )}
                </div>
            </div>
        </div>
    );
}
