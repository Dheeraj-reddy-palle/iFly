const API_BASE = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';

export async function predictPrice(payload) {
    const response = await fetch(`${API_BASE}/predict-price`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
    });

    if (!response.ok) throw new Error("Prediction failed");
    return await response.json();
}

export function getApiBase() {
    return API_BASE;
}
