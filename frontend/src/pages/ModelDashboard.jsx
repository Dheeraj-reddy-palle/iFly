import React, { useState, useEffect } from 'react';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from 'recharts';
import { getApiBase } from '../api';

const ModelDashboard = () => {
    const [modelHistory, setModelHistory] = useState([]);
    const [deployedModel, setDeployedModel] = useState(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(null);
    const [rollingBack, setRollingBack] = useState(false);

    const fetchDashboardData = async () => {
        setLoading(true);
        setError(null);
        try {
            const [historyResponse, infoResponse] = await Promise.all([
                fetch(`${getApiBase()}/predict-price/model-history`),
                fetch(`${getApiBase()}/predict-price/model-info`),
            ]);

            if (!historyResponse.ok || !infoResponse.ok) {
                throw new Error('Failed to fetch model registry data.');
            }

            const historyData = await historyResponse.json();
            const infoData = await infoResponse.json();

            // Ensure chronological sort ascending naturally (as mandated)
            const sortedHistory = historyData.sort((a, b) => new Date(a.trained_at) - new Date(b.trained_at));

            setModelHistory(sortedHistory);
            setDeployedModel(infoData.status !== "No deployed model" ? infoData : null);
        } catch (err) {
            setError(err.message);
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        fetchDashboardData();
    }, []);

    const handleRollback = async (version) => {
        if (!window.confirm(`Are you sure you want to forcibly deploy version ${version}?`)) return;

        setRollingBack(true);
        try {
            const response = await fetch(`${getApiBase()}/predict-price/model-rollback/${version}`, {
                method: 'POST',
            });
            if (!response.ok) throw new Error('Failed to execute rollback safely.');
            await fetchDashboardData();
        } catch (err) {
            alert(err.message);
        } finally {
            setRollingBack(false);
        }
    };

    if (loading && modelHistory.length === 0) {
        return (
            <div className="flex justify-center items-center h-screen bg-gray-50">
                <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-indigo-600"></div>
            </div>
        );
    }

    // Formatting helper
    const formatDate = (isoString) => new Date(isoString).toLocaleString('en-US', {
        month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit'
    });

    // Calculate Last 5
    const last5Models = [...modelHistory].sort((a, b) => new Date(b.trained_at) - new Date(a.trained_at)).slice(0, 5);

    return (
        <div className="min-h-screen bg-gray-50 py-12 px-4 sm:px-6 lg:px-8 font-sans">
            <div className="max-w-7xl mx-auto space-y-8">

                {/* Header Section */}
                <div className="flex justify-between items-center pb-4 border-b border-gray-200">
                    <div>
                        <h1 className="text-3xl font-extrabold text-gray-900 tracking-tight">ML Operations Engine</h1>
                        <p className="mt-2 text-sm text-gray-500">Self-improving autonomous deployment gates and chronological registry metrics.</p>
                    </div>
                    <button
                        onClick={fetchDashboardData}
                        disabled={loading}
                        className="inline-flex items-center px-4 py-2 border border-transparent text-sm font-medium rounded-md shadow-sm text-white bg-indigo-600 hover:bg-indigo-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-indigo-500 disabled:opacity-50 transition-colors"
                    >
                        {loading ? 'Syncing Pipeline...' : 'Force Refresh Registry'}
                    </button>
                </div>

                {error && (
                    <div className="rounded-md bg-red-50 p-4 border border-red-200 shadow-sm">
                        <div className="flex">
                            <div className="ml-3 text-sm text-red-700 font-medium">Critical Failure: {error}</div>
                        </div>
                    </div>
                )}

                {/* Current Deployment HUD */}
                <div className="bg-white overflow-hidden shadow-xl rounded-2xl border border-gray-100 p-8 relative isolate">
                    <div className="absolute inset-0 -z-10 bg-[radial-gradient(45rem_50rem_at_top,theme(colors.indigo.100),white)] opacity-20"></div>
                    <h2 className="text-sm uppercase tracking-wider font-bold text-gray-500 mb-6 drop-shadow-sm">Currently Active Production Artifact</h2>

                    {deployedModel ? (
                        <div className="grid grid-cols-1 md:grid-cols-4 gap-6">
                            <div className="bg-indigo-50/50 rounded-xl p-5 border border-indigo-100 shadow-sm">
                                <p className="text-xs font-semibold text-indigo-600 uppercase tracking-wide">Version ID</p>
                                <p className="mt-2 text-2xl font-bold text-gray-900 font-mono tracking-tight">{deployedModel.model_version}</p>
                                <div className="mt-2 inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-green-100 text-green-800 border border-green-200 shadow-sm">
                                    <span className="w-1.5 h-1.5 rounded-full bg-green-500 mr-1.5 animate-pulse"></span>
                                    Active Routing
                                </div>
                            </div>

                            <div className="bg-gray-50/50 rounded-xl p-5 border border-gray-100 shadow-sm">
                                <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide">Validation R² (Accuracy)</p>
                                <p className="mt-2 text-3xl font-black text-gray-900 tracking-tighter">
                                    {(deployedModel.test_r2 * 100).toFixed(1)}<span className="text-xl text-gray-400 font-medium">%</span>
                                </p>
                            </div>

                            <div className="bg-gray-50/50 rounded-xl p-5 border border-gray-100 shadow-sm">
                                <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide">Validation MAE (Error)</p>
                                <p className="mt-2 text-3xl font-black text-gray-900 tracking-tighter">
                                    <span className="text-xl text-gray-400 font-medium mr-1">$</span>{deployedModel.test_mae.toFixed(2)}
                                </p>
                            </div>

                            <div className="bg-gray-50/50 rounded-xl p-5 border border-gray-100 shadow-sm flex flex-col justify-center">
                                <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide">Trained Timestamp</p>
                                <p className="mt-2 text-md font-medium text-gray-900">{formatDate(deployedModel.trained_at)}</p>
                            </div>
                        </div>
                    ) : (
                        <div className="text-center py-6 bg-red-50/50 border border-red-100 rounded-xl">
                            <p className="text-xl font-bold text-red-600 drop-shadow-sm">No Models Actively Bounded in Memory</p>
                            <p className="text-sm text-red-500 mt-1">Inference engines critically failing. Fast track retraining immediately.</p>
                        </div>
                    )}
                </div>

                {/* Charts & Trends */}
                <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">

                    <div className="bg-white shadow-lg rounded-2xl border border-gray-100 p-6 transition-all hover:shadow-xl">
                        <h2 className="text-sm font-bold text-gray-500 uppercase tracking-wider mb-6">Validation R² Evolution</h2>
                        <div className="h-72">
                            <ResponsiveContainer width="100%" height="100%">
                                <LineChart data={modelHistory}>
                                    <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#f0f0f0" />
                                    <XAxis
                                        dataKey="trained_at"
                                        tickFormatter={(tick) => new Date(tick).toLocaleDateString(undefined, { month: 'short', day: 'numeric' })}
                                        tick={{ fontSize: 12, fill: '#6b7280' }}
                                        axisLine={false}
                                        tickLine={false}
                                    />
                                    <YAxis
                                        domain={['auto', 'auto']}
                                        tick={{ fontSize: 12, fill: '#6b7280' }}
                                        axisLine={false}
                                        tickLine={false}
                                        tickFormatter={(val) => val.toFixed(2)}
                                    />
                                    <Tooltip
                                        labelFormatter={(label) => formatDate(label)}
                                        contentStyle={{ borderRadius: '12px', border: 'none', boxShadow: '0 10px 15px -3px rgba(0, 0, 0, 0.1), 0 4px 6px -2px rgba(0, 0, 0, 0.05)' }}
                                    />
                                    <Line
                                        type="monotone"
                                        dataKey="test_r2"
                                        name="Test R²"
                                        stroke="#4f46e5"
                                        strokeWidth={3}
                                        dot={{ r: 4, fill: '#4f46e5', strokeWidth: 2, stroke: 'white' }}
                                        activeDot={{ r: 6, strokeWidth: 0 }}
                                        animationDuration={1500}
                                    />
                                </LineChart>
                            </ResponsiveContainer>
                        </div>
                    </div>

                    <div className="bg-white shadow-lg rounded-2xl border border-gray-100 p-6 transition-all hover:shadow-xl">
                        <h2 className="text-sm font-bold text-gray-500 uppercase tracking-wider mb-6">Absolute Error (MAE) Drift</h2>
                        <div className="h-72">
                            <ResponsiveContainer width="100%" height="100%">
                                <LineChart data={modelHistory}>
                                    <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#f0f0f0" />
                                    <XAxis
                                        dataKey="trained_at"
                                        tickFormatter={(tick) => new Date(tick).toLocaleDateString(undefined, { month: 'short', day: 'numeric' })}
                                        tick={{ fontSize: 12, fill: '#6b7280' }}
                                        axisLine={false}
                                        tickLine={false}
                                    />
                                    <YAxis
                                        domain={['auto', 'auto']}
                                        tick={{ fontSize: 12, fill: '#6b7280' }}
                                        axisLine={false}
                                        tickLine={false}
                                        tickFormatter={(val) => `$${val.toFixed(0)}`}
                                    />
                                    <Tooltip
                                        labelFormatter={(label) => formatDate(label)}
                                        formatter={(value) => [`$${value.toFixed(2)}`, 'MAE']}
                                        contentStyle={{ borderRadius: '12px', border: 'none', boxShadow: '0 10px 15px -3px rgba(0, 0, 0, 0.1), 0 4px 6px -2px rgba(0, 0, 0, 0.05)' }}
                                    />
                                    <Line
                                        type="monotone"
                                        dataKey="mae"
                                        name="MAE"
                                        stroke="#ea580c"
                                        strokeWidth={3}
                                        dot={{ r: 4, fill: '#ea580c', strokeWidth: 2, stroke: 'white' }}
                                        activeDot={{ r: 6, strokeWidth: 0 }}
                                        animationDuration={1500}
                                    />
                                </LineChart>
                            </ResponsiveContainer>
                        </div>
                    </div>

                </div>

                {/* Global Registry Ledger */}
                <div className="bg-white shadow-lg rounded-2xl border border-gray-100 overflow-hidden">
                    <div className="px-6 py-5 border-b border-gray-200 bg-gray-50/50">
                        <h3 className="text-lg leading-6 font-bold text-gray-900">Training Registry Ledger (Last 5 Iterations)</h3>
                    </div>
                    <div className="overflow-x-auto">
                        <table className="min-w-full divide-y divide-gray-200">
                            <thead className="bg-gray-50">
                                <tr>
                                    <th scope="col" className="px-6 py-3 text-left text-xs font-bold text-gray-500 uppercase tracking-wider">Version Identity</th>
                                    <th scope="col" className="px-6 py-3 text-left text-xs font-bold text-gray-500 uppercase tracking-wider">Train R²</th>
                                    <th scope="col" className="px-6 py-3 text-left text-xs font-bold text-gray-500 uppercase tracking-wider">Test R²</th>
                                    <th scope="col" className="px-6 py-3 text-left text-xs font-bold text-gray-500 uppercase tracking-wider">Abs. Error (MAE)</th>
                                    <th scope="col" className="px-6 py-3 text-left text-xs font-bold text-gray-500 uppercase tracking-wider">Root Sq. Error (RMSE)</th>
                                    <th scope="col" className="px-6 py-3 text-left text-xs font-bold text-gray-500 uppercase tracking-wider">Pipeline Status</th>
                                    <th scope="col" className="px-6 py-3 text-right text-xs font-bold text-gray-500 uppercase tracking-wider">Actions</th>
                                </tr>
                            </thead>
                            <tbody className="bg-white divide-y divide-gray-100">
                                {last5Models.map((m) => (
                                    <tr key={m.version} className="hover:bg-gray-50/50 transition-colors">
                                        <td className="px-6 py-4 whitespace-nowrap">
                                            <div className="flex flex-col">
                                                <span className="text-sm font-bold text-gray-900 font-mono">{m.version}</span>
                                                <span className="text-xs text-gray-500">{formatDate(m.trained_at)}</span>
                                            </div>
                                        </td>
                                        <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-700 font-medium">
                                            {m.train_r2 ? m.train_r2.toFixed(4) : 'N/A'}
                                        </td>
                                        <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900 font-bold">
                                            {m.test_r2 ? m.test_r2.toFixed(4) : 'N/A'}
                                        </td>
                                        <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-700">
                                            {m.mae ? `$${m.mae.toFixed(2)}` : 'N/A'}
                                        </td>
                                        <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                                            {m.rmse ? `$${m.rmse.toFixed(2)}` : 'N/A'}
                                        </td>
                                        <td className="px-6 py-4 whitespace-nowrap">
                                            {m.deployed ? (
                                                <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-semibold bg-green-100 text-green-800 border border-green-200 shadow-sm">
                                                    Deployed Active
                                                </span>
                                            ) : m.is_candidate ? (
                                                <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-semibold bg-yellow-100 text-yellow-800 border border-yellow-200 shadow-sm">
                                                    Candidate (Held)
                                                </span>
                                            ) : (
                                                <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-semibold bg-red-100 text-red-800 border border-red-200 shadow-sm">
                                                    Rejected / Rolled Back
                                                </span>
                                            )}
                                        </td>
                                        <td className="px-6 py-4 whitespace-nowrap text-right text-sm font-medium">
                                            {!m.deployed && !m.is_candidate && m.test_r2 && (
                                                <button
                                                    onClick={() => handleRollback(m.version)}
                                                    disabled={rollingBack}
                                                    className="text-indigo-600 hover:text-indigo-900 hover:underline font-bold disabled:opacity-50 transition-all font-sans"
                                                >
                                                    {rollingBack ? 'Reverting...' : 'Force Rollback'}
                                                </button>
                                            )}
                                        </td>
                                    </tr>
                                ))}

                                {last5Models.length === 0 && (
                                    <tr>
                                        <td colSpan="7" className="px-6 py-12 text-center text-gray-500 text-sm italic bg-gray-50/30">
                                            Model registry database contains zero temporal iterations cleanly.
                                        </td>
                                    </tr>
                                )}
                            </tbody>
                        </table>
                    </div>
                </div>

            </div>
        </div>
    );
};

export default ModelDashboard;
