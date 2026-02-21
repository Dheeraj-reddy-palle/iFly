import { useState } from 'react';
import { predictPrice } from '../api';

const EUR_TO_INR = 90.0;

export default function PredictionCard({ currency = 'EUR' }) {
    const [formData, setFormData] = useState({
        origin: '',
        destination: '',
        departure_date: '',
        airline: '',
        stops: 0,
    });

    // Explicit tri-state handling
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState(null);
    const [prediction, setPrediction] = useState(null);       // stored in EUR
    const [confidenceInterval, setConfidenceInterval] = useState(null); // stored in EUR
    const [shieldTriggered, setShieldTriggered] = useState(false);

    const MAX_REASONABLE_PRICE_EUR = 1000000;

    const getTodayDateString = () => {
        const today = new Date();
        today.setMinutes(today.getMinutes() - today.getTimezoneOffset());
        return today.toISOString().split('T')[0];
    };

    const validateInputs = () => {
        if (formData.origin === formData.destination && formData.origin !== '') {
            return "Origin and Destination cannot be identical.";
        }
        if (formData.departure_date < getTodayDateString() && formData.departure_date !== '') {
            return "Departure date cannot be in the past.";
        }
        return null;
    };

    const fetchPrediction = async (scenarioPayload = null) => {
        const validationError = !scenarioPayload && validateInputs();
        if (validationError) {
            setError(validationError);
            return;
        }

        setLoading(true);
        setError(null);
        setPrediction(null);
        setShieldTriggered(false);
        setConfidenceInterval(null);

        try {
            const defaultPayload = {
                ...formData,
                origin: formData.origin.toUpperCase(),
                destination: formData.destination.toUpperCase(),
                airline: formData.airline.toUpperCase()
            };

            const payload = scenarioPayload || defaultPayload;
            const res = await predictPrice(payload);

            // Map new EUR-keyed response fields
            const pPriceEur = res.predicted_price_eur;

            if (pPriceEur && Math.abs(pPriceEur) > MAX_REASONABLE_PRICE_EUR) {
                setShieldTriggered(true);
            }

            setPrediction(pPriceEur);
            if (res.confidence_interval_eur) {
                setConfidenceInterval(res.confidence_interval_eur);
            }

        } catch (err) {
            console.error("Prediction Error:", err);
            setError("Prediction engine currently unavailable. Please try again later.");
        } finally {
            setLoading(false);
        }
    };

    const handleSubmit = async (e) => {
        e.preventDefault();
        await fetchPrediction();
    };

    const runStressTest = async () => {
        const scenarios = [
            { origin: "DEL", destination: "BOM" },
            { origin: "BLR", destination: "DEL" },
            { origin: "BOM", destination: "BLR" },
            { origin: "JFK", destination: "LHR" }
        ];

        for (let s of scenarios) {
            const autoPayload = {
                origin: s.origin,
                destination: s.destination,
                departure_date: getTodayDateString(),
                airline: "AI",
                stops: 0
            };
            setFormData(autoPayload);
            await fetchPrediction(autoPayload);
            await new Promise(r => setTimeout(r, 600));
        }
    };

    const handleChange = (e) => {
        const { name, value } = e.target;
        setFormData(prev => ({
            ...prev,
            [name]: name === 'stops' ? parseInt(value) : (name === 'origin' || name === 'destination' || name === 'airline' ? value.toUpperCase() : value)
        }));
        if (error) setError(null);
    };

    // Display-layer currency conversion
    const displayPrice = currency === 'EUR' ? prediction : (prediction !== null ? prediction * EUR_TO_INR : null);
    const displayLower = currency === 'EUR' ? confidenceInterval?.lower : (confidenceInterval?.lower != null ? confidenceInterval.lower * EUR_TO_INR : null);
    const displayUpper = currency === 'EUR' ? confidenceInterval?.upper : (confidenceInterval?.upper != null ? confidenceInterval.upper * EUR_TO_INR : null);

    const formatter = displayPrice !== null ? new Intl.NumberFormat(
        currency === 'EUR' ? 'de-DE' : 'en-IN',
        { style: 'currency', currency: currency, maximumFractionDigits: 2 }
    ) : null;

    return (
        <div className="w-full h-full bg-white dark:bg-gray-900 rounded-2xl shadow-sm text-slate-800 dark:text-gray-100 border border-slate-100 dark:border-gray-800 flex flex-col overflow-hidden transition-colors">
            <div className="p-6 border-b border-slate-100 dark:border-gray-800 bg-slate-50/50 dark:bg-gray-800/50 shrink-0">
                <h2 className="text-xl font-semibold text-slate-800 dark:text-gray-100">Flight Price Inference</h2>
                <p className="mt-1 text-slate-500 dark:text-gray-400 text-sm">Query the active model registry for deterministic market yield arrays.</p>
            </div>

            <div className="flex-1 overflow-y-auto p-6">
                <form onSubmit={handleSubmit} className="space-y-5">
                    <div className="grid grid-cols-2 gap-4">
                        <div>
                            <label className="block text-xs font-semibold text-slate-500 dark:text-gray-400 mb-1.5 uppercase tracking-wide">Origin (IATA)</label>
                            <input required type="text" maxLength={3} name="origin" value={formData.origin} onChange={handleChange} className="w-full px-4 py-2.5 rounded-xl border border-slate-200 dark:border-gray-700 bg-white dark:bg-gray-800 text-slate-900 dark:text-gray-100 focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 transition-all font-semibold uppercase placeholder:normal-case shadow-sm" placeholder="DEL" />
                        </div>
                        <div>
                            <label className="block text-xs font-semibold text-slate-500 dark:text-gray-400 mb-1.5 uppercase tracking-wide">Dest (IATA)</label>
                            <input required type="text" maxLength={3} name="destination" value={formData.destination} onChange={handleChange} className="w-full px-4 py-2.5 rounded-xl border border-slate-200 dark:border-gray-700 bg-white dark:bg-gray-800 text-slate-900 dark:text-gray-100 focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 transition-all font-semibold uppercase placeholder:normal-case shadow-sm" placeholder="BOM" />
                        </div>
                    </div>

                    <div className="grid grid-cols-2 gap-4">
                        <div>
                            <label className="block text-xs font-semibold text-slate-500 dark:text-gray-400 mb-1.5 uppercase tracking-wide">Departure Date</label>
                            <input required type="date" min={getTodayDateString()} name="departure_date" value={formData.departure_date} onChange={handleChange} className="w-full px-4 py-2.5 rounded-xl border border-slate-200 dark:border-gray-700 bg-white dark:bg-gray-800 text-slate-900 dark:text-gray-100 focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 transition-all font-semibold shadow-sm text-sm" />
                        </div>
                        <div>
                            <label className="block text-xs font-semibold text-slate-500 dark:text-gray-400 mb-1.5 uppercase tracking-wide">Airline Code</label>
                            <input required type="text" maxLength={2} name="airline" value={formData.airline} onChange={handleChange} className="w-full px-4 py-2.5 rounded-xl border border-slate-200 dark:border-gray-700 bg-white dark:bg-gray-800 text-slate-900 dark:text-gray-100 focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 transition-all font-semibold uppercase placeholder:normal-case shadow-sm" placeholder="AI" />
                        </div>
                    </div>

                    <div>
                        <label className="block text-xs font-semibold text-slate-500 dark:text-gray-400 mb-1.5 uppercase tracking-wide">Stops</label>
                        <select name="stops" value={formData.stops} onChange={handleChange} className="w-full px-4 py-2.5 rounded-xl border border-slate-200 dark:border-gray-700 bg-white dark:bg-gray-800 text-slate-900 dark:text-gray-100 focus:ring-2 focus:ring-indigo-500 transition-all font-semibold shadow-sm appearance-none text-sm">
                            <option value={0}>0 Stops (Direct)</option>
                            <option value={1}>1 Stop</option>
                            <option value={2}>2+ Stops</option>
                        </select>
                    </div>

                    <div className="pt-2">
                        <button disabled={loading || !!validateInputs()} type="submit" className={`w-full py-3.5 rounded-xl font-bold text-base shadow-lg transition-all flex items-center justify-center gap-3 ${loading || validateInputs() ? 'bg-indigo-300 dark:bg-indigo-900/50 shadow-none cursor-not-allowed text-white dark:text-gray-400' : 'bg-indigo-600 hover:bg-indigo-700 dark:bg-indigo-600 dark:hover:bg-indigo-500 active:transform active:scale-[0.98] text-white shadow-indigo-200 dark:shadow-none'}`}>
                            {loading ? (
                                <>
                                    <svg className="animate-spin h-5 w-5 text-white" fill="none" viewBox="0 0 24 24">
                                        <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                                        <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                                    </svg>
                                    Crunching Topology...
                                </>
                            ) : "Predict Price Trajectory"}
                        </button>
                    </div>
                </form>

                {/* --- DISPLAY RENDER LOGIC (EXPLICIT TRI-STATE) --- */}
                <div className="mt-6">
                    {!loading && error && (
                        <div className="p-4 bg-red-50 dark:bg-red-900/20 text-red-600 dark:text-red-400 rounded-xl border border-red-100 dark:border-red-900/50 text-center font-medium text-sm animate-fade-in shadow-sm flex flex-col items-center">
                            <div>{error}</div>
                            <button type="button" onClick={() => setError(null)} className="mt-2 text-xs font-bold uppercase tracking-wider text-red-700 dark:text-red-500 hover:opacity-80 underline underline-offset-2">Dismiss</button>
                        </div>
                    )}

                    {!loading && !error && shieldTriggered && (
                        <div className="animate-fade-in transition-colors bg-slate-50 dark:bg-gray-800/50 p-6 rounded-2xl border border-slate-100 dark:border-gray-800 shadow-sm text-center">
                            <p className="text-red-500 font-bold mb-1 uppercase tracking-widest text-[11px]">System Shield Triggered</p>
                            <div className="text-sm font-semibold text-slate-700 dark:text-gray-300 tracking-tight mt-2 break-words">
                                Prediction exceeds expected market range safely.
                            </div>
                        </div>
                    )}

                    {!loading && !error && !shieldTriggered && prediction !== null && formatter && (
                        <div className="animate-fade-in transition-colors bg-slate-50 dark:bg-gray-800/50 p-6 rounded-2xl border border-slate-100 dark:border-gray-800 shadow-sm flex flex-col justify-center min-w-0">
                            <div className="text-center w-full min-w-0">
                                <p className="text-slate-500 dark:text-gray-400 font-bold mb-1 uppercase tracking-widest text-[11px] flex items-center justify-center gap-1.5 break-words">
                                    <span className="w-1.5 h-1.5 bg-emerald-500 rounded-full shrink-0"></span>
                                    Target Inference · {currency}
                                </p>
                                <div className="flex items-center justify-center mt-2 overflow-hidden w-full">
                                    <div className="text-3xl font-semibold tracking-tight break-words max-h-24 overflow-y-auto w-full text-slate-900 dark:text-white">
                                        {formatter.format(displayPrice)}
                                    </div>
                                </div>
                            </div>

                            {displayLower !== null && displayUpper !== null && (
                                <div className="mt-6 min-w-0 w-full">
                                    <div className="flex items-center justify-center gap-2 text-xs font-semibold text-slate-500 dark:text-gray-400 mb-3 uppercase tracking-wider">
                                        <span>Variance Interval</span>
                                        <div className="group relative flex items-center justify-center">
                                            <svg className="w-4 h-4 text-slate-400 dark:text-gray-500 cursor-help" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"></path></svg>
                                            <div className="absolute bottom-full left-1/2 transform -translate-x-1/2 mb-2 w-48 p-2 bg-slate-800 dark:bg-gray-700 text-white text-[10px] rounded shadow-xl opacity-0 group-hover:opacity-100 transition-opacity pointer-events-none z-10 text-center font-normal leading-relaxed">
                                                68% statistical confidence interval computed symmetrically from longitudinal model residuals.
                                            </div>
                                        </div>
                                    </div>

                                    <div className="flex flex-col sm:flex-row items-center justify-between gap-2 text-sm font-bold text-slate-700 dark:text-gray-200 bg-white dark:bg-gray-900 px-4 py-3 rounded-xl border border-slate-200 dark:border-gray-700 shadow-sm overflow-hidden w-full">
                                        <span className="text-indigo-600 dark:text-indigo-400 break-all">{formatter.format(displayLower)}</span>
                                        <span className="hidden sm:block h-px w-6 bg-slate-300 dark:bg-gray-600 shrink-0"></span>
                                        <span className="text-indigo-600 dark:text-indigo-400 break-all">{formatter.format(displayUpper)}</span>
                                    </div>
                                </div>
                            )}
                        </div>
                    )}
                </div>
            </div>
        </div>
    );
}

