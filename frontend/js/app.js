/**
 * ForeksTrader Frontend Logic
 */

let chart;
let candleSeries;
let currentSymbol = "EURUSD";
let ws;
let isConnected = false;

// DOM Elements
const statusBadge = document.getElementById("status-badge");
const chartOverlay = document.getElementById("chart-overlay");

// Initialize
document.addEventListener("DOMContentLoaded", async () => {
    console.log("ForeksTrader: Booting...");
    
    // 1. WebSocket & Core Data (Highest Priority)
    try { 
        initWebSocket(); 
    } catch(e) { 
        console.error("WS Boot Crash:", e); 
    }

    // 2. Initial Data Load
    try { 
        await fetchDashboardSummary(); 
    } catch(e) { 
        console.error("Initial Summary Check Failed:", e); 
    }

    try { 
        await fetchSettings(); 
    } catch(e) { 
        console.error("Settings Load Failed:", e); 
    }

    // 3. UI Components (Non-blocking)
    setTimeout(() => {
        try { initChart(); } catch(e) { console.error("Chart Load Failed:", e); }
    }, 100);

    // Pair selector listeners
    document.querySelectorAll(".pair-btn").forEach(btn => {
        btn.addEventListener("click", (e) => {
            document.querySelectorAll(".pair-btn").forEach(b => b.classList.remove("active"));
            e.target.classList.add("active");
            currentSymbol = e.target.innerText;
            fetchChartData(currentSymbol);
            fetchSentimentData(currentSymbol);
        });
    });
});

function initChart() {
    try {
        const chartProperties = {
            layout: {
                background: { type: 'solid', color: 'transparent' },
                textColor: '#9CA3AF',
            },
            grid: {
                vertLines: { color: 'rgba(31, 41, 55, 0.5)' },
                horzLines: { color: 'rgba(31, 41, 55, 0.5)' },
            },
            crosshair: {
                mode: LightweightCharts.CrosshairMode.Normal,
            },
            rightPriceScale: {
                borderColor: 'rgba(31, 41, 55, 0.5)',
            },
            timeScale: {
                borderColor: 'rgba(31, 41, 55, 0.5)',
                timeVisible: true,
            },
        };

        const container = document.getElementById('chart-container');
        if (!container) return;
        
        if (typeof LightweightCharts === 'undefined') {
            console.error("LightweightCharts library not loaded!");
            return;
        }

        chart = LightweightCharts.createChart(container, chartProperties);
        
        // Fallback check for method naming variations in CDN bundles
        if (typeof chart.addCandlestickSeries === 'function') {
            candleSeries = chart.addCandlestickSeries({
                upColor: '#10B981',
                downColor: '#EF4444',
                borderDownColor: '#EF4444',
                borderUpColor: '#10B981',
                wickDownColor: '#EF4444',
                wickUpColor: '#10B981',
            });
        } else if (typeof chart.addAreaSeries === 'function') {
            candleSeries = chart.addAreaSeries({
                lineColor: '#3B82F6',
                topColor: 'rgba(59, 130, 246, 0.4)',
                bottomColor: 'rgba(59, 130, 246, 0.0)',
            });
        }

        // Handle resize
        new ResizeObserver(entries => {
            if (entries.length === 0 || entries[0].target !== container) return;
            const newRect = entries[0].contentRect;
            chart.applyOptions({ width: newRect.width, height: newRect.height });
        }).observe(container);
        
        fetchChartData(currentSymbol);
        fetchSentimentData(currentSymbol);
    } catch(e) {
        console.error("initChart logical error:", e);
    }
}

async function fetchChartData(symbol) {
    try {
        const res = await fetch(`/api/analysis/chart/${symbol}`);
        if (!res.ok) return;
        
        const data = await res.json();
        if (data.candles && data.candles.length > 0) {
            const mappedData = data.candles.map(c => ({
                time: new Date(c.time).getTime() / 1000,
                open: c.open,
                high: c.high,
                low: c.low,
                close: c.close
            }));
            
            mappedData.sort((a,b) => a.time - b.time);
            
            // Critical check for candleSeries before setting data
            if (candleSeries) {
                candleSeries.setData(mappedData);
                chart.timeScale().fitContent();
                chartOverlay.classList.add("opacity-0", "pointer-events-none");
            }
        }
    } catch (e) {
        console.error("Failed to fetch chart data:", e);
    }
}

async function fetchSentimentData(symbol) {
    const container = document.getElementById("sentiment-container");
    container.innerHTML = `<div class="text-center text-gray-500 text-sm py-4"><i class="fa-solid fa-circle-notch fa-spin mr-2"></i>Analyzing sentiment...</div>`;
    
    try {
        // We'll just fetch latest signals for the symbol to see the sentiment
        const res = await fetch(`/api/analysis/signals/${symbol}?limit=5`);
        if (res.ok) {
            const signals = await res.json();
            const sentSignals = signals.filter(s => s.source === 'NEWS_SENTIMENT' || s.source === 'VADER_SENTIMENT');
            
            if (sentSignals.length === 0) {
                container.innerHTML = `<div class="text-center text-gray-500 text-sm py-4">No recent news sentiment for ${symbol}.</div>`;
                return;
            }
            
            const sig = sentSignals[0]; // the latest
            let color = "text-gray-400";
            let icon = "fa-minus";
            if (sig.direction === "BUY") { color = "text-buytext"; icon = "fa-arrow-up"; }
            if (sig.direction === "SELL") { color = "text-selltext"; icon = "fa-arrow-down"; }
            
            container.innerHTML = `
                <div class="flex items-center gap-3">
                    <div class="w-10 h-10 rounded-full bg-panelbg2 flex items-center justify-center border border-gray-800">
                        <i class="fa-solid ${icon} ${color} text-lg"></i>
                    </div>
                    <div>
                        <p class="text-sm font-bold text-gray-200">Confidence: ${(sig.confidence * 100).toFixed(0)}%</p>
                        <p class="text-xs text-gray-500">${sig.direction} Signal</p>
                    </div>
                </div>
                <p class="text-xs text-gray-400 italic bg-panelbg2 p-3 rounded-xl border border-gray-800/50 leading-relaxed mt-2">
                    "${sig.reasoning}"
                </p>
            `;
        }
    } catch(e) {
        container.innerHTML = `<div class="text-center text-red-500 text-sm py-4">Failed to load sentiment.</div>`;
    }
}

function initWebSocket() {
    const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
    const wsUrl = `${protocol}//${window.location.host}/ws`;
    
    ws = new WebSocket(wsUrl);
    
    ws.onopen = () => {
        console.log("WS: Connection established.");
        isConnected = true;
        updateConnectionStatus(true);
        // Always fetch the latest summary when connection is established
        fetchDashboardSummary();
        // Also ensure chart and sentiment are loaded if they weren't
        fetchChartData(currentSymbol);
        fetchSentimentData(currentSymbol);
    };
    
    ws.onerror = (err) => {
        console.error("WS: Connection error caught:", err);
    };
    
    ws.onclose = (event) => {
        console.warn("WS: Connection closed. Code:", event.code, "Reason:", event.reason);
        isConnected = false;
        updateConnectionStatus(false);
        setTimeout(initWebSocket, 3000); // Reconnect
    };
    
    ws.onmessage = (event) => {
        try {
            const msg = JSON.parse(event.data);
            if (msg.type === "account_update") {
                updateAccountUI(msg.data.account, msg.data.positions);
            }
        } catch (e) {
            console.error("WS parse error", e);
        }
    };
}

function updateConnectionStatus(connected) {
    if (connected) {
        statusBadge.className = "ml-4 px-2.5 py-1 rounded-full text-xs font-medium bg-emerald-900/40 text-emerald-400 border border-emerald-800/50 flex items-center gap-1.5";
        statusBadge.innerHTML = `<div class="w-1.5 h-1.5 rounded-full bg-emerald-500 shadow-[0_0_8px_#10B981]"></div> Active`;
    } else {
        statusBadge.className = "ml-4 px-2.5 py-1 rounded-full text-xs font-medium bg-red-900/40 text-red-400 border border-red-800/50 flex items-center gap-1.5";
        statusBadge.innerHTML = `<div class="w-1.5 h-1.5 rounded-full bg-red-500 animate-pulse"></div> Offline`;
    }
}

async function fetchDashboardSummary() {
    try {
        const res = await fetch("/api/dashboard/summary");
        if (res.ok) {
            const data = await res.json();
            if (data.status === "online" && data.account) {
                updateAccountUI(data.account, data.positions); // Positions might be omitted in summary, but it will handle gracefully
            }
            updateDailyStats(data.metrics);
            renderDecisions(data.recent_decisions);
        }
    } catch (e) {
        console.error(e);
    }
}

function updateAccountUI(account, positions) {
    if (account && !account.error) {
        const eq = account.equity || 0;
        document.getElementById("stat-balance").innerText = `$${(account.balance || 0).toFixed(2)}`;
        document.getElementById("stat-margin").innerText = `$${(account.free_margin || 0).toFixed(2)}`;
        document.getElementById("nav-equity").innerText = `$${eq.toFixed(2)}`;
    }
    
    if (positions) {
        document.getElementById("pos-count").innerText = positions.length;
        renderPositions(positions);
    }
}

function updateDailyStats(metrics) {
    if (!metrics) return;
    const pnl = metrics.daily_pnl || 0;
    const el = document.getElementById("nav-pnl");
    el.innerText = `${pnl >= 0 ? '+' : ''}$${pnl.toFixed(2)}`;
    if (pnl > 0) el.className = "font-bold text-buytext";
    else if (pnl < 0) el.className = "font-bold text-selltext";
}

function renderPositions(positions) {
    const container = document.getElementById("positions-list");
    if (!positions || positions.length === 0) {
        container.innerHTML = `<div class="flex h-full items-center justify-center text-gray-500 text-sm italic">No open positions. Brain is being skeptical.</div>`;
        return;
    }
    
    container.innerHTML = positions.map(p => {
        const isBuy = p.type === "POSITION_TYPE_BUY";
        const color = isBuy ? "text-buytext" : "text-selltext";
        const pnlColor = p.profit >= 0 ? "text-buytext" : "text-selltext";
        
        return `
        <div class="bg-panelbg2 rounded-lg p-3 mb-2 border border-gray-800 flex justify-between items-center group">
            <div>
                <div class="flex items-center gap-2 mb-1">
                    <span class="font-bold text-white text-sm">${p.symbol}</span>
                    <span class="text-xs font-semibold px-1.5 py-0.5 rounded bg-gray-800 ${color}">${isBuy ? 'BUY' : 'SELL'} ${p.volume}</span>
                </div>
                <div class="text-xs text-gray-500 flex gap-3">
                    <span>Open: ${p.open_price}</span>
                    <span>Cur: <span class="text-gray-300 group-hover:text-white transition-colors">${p.current_price}</span></span>
                </div>
            </div>
            <div class="text-right">
                <div class="${pnlColor} font-bold text-sm">$${p.profit.toFixed(2)}</div>
                <button onclick="closePosition('${p.id}')" class="text-xs text-gray-500 hover:text-red-400 mt-1 transition-colors"><i class="fa-solid fa-xmark mr-1"></i>Close</button>
            </div>
        </div>
        `;
    }).join("");
}

function renderDecisions(decisions) {
    const container = document.getElementById("decision-log");
    if (!decisions || decisions.length === 0) return;
    
    container.innerHTML = decisions.map(d => {
        let typeClass = "reject";
        let icon = "fa-shield-halved text-gray-400";
        if (d.action === "BUY") { typeClass = "buy"; icon = "fa-arrow-up text-buytext"; }
        if (d.action === "SELL") { typeClass = "sell"; icon = "fa-arrow-down text-selltext"; }
        
        const date = new Date(d.timestamp).toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'});
        
        return `
        <div class="log-card ${typeClass} bg-panelbg2 rounded-lg p-3 mb-2 border-y border-r border-gray-800 text-sm">
            <div class="flex justify-between items-start mb-1.5">
                <div class="flex items-center gap-2">
                    <i class="fa-solid ${icon}"></i>
                    <span class="font-bold text-gray-200">${d.symbol}</span>
                    <span class="text-xs text-gray-500">${d.action} (Conf: ${d.confidence.toFixed(2)})</span>
                </div>
                <span class="text-xs text-gray-600">${date}</span>
            </div>
            <p class="text-gray-400 text-xs leading-relaxed">${d.reasoning}</p>
        </div>
        `;
    }).join("");
}

async function closePosition(id) {
    if (!confirm("Close this position manually?")) return;
    try {
        await fetch(`/api/trading/close/${id}`, { method: 'POST' });
        // Alert handled or wait for WS update
    } catch(e) { console.error(e); }
}

// --- Settings Modal Logic ---

const MODES = [
    { id: "ultra_conservative", name: "🛡️ Ultra Conservative", thresh: "> 0.85", risk: "0.5%", desc: "Only takes absolutely perfect setups across all timeframes. High rejection rate." },
    { id: "conservative", name: "🔒 Conservative", thresh: "> 0.75", risk: "1.0%", desc: "Focuses on capital protection. Requires strong confluence." },
    { id: "balanced", name: "⚖️ Balanced", thresh: "> 0.65", risk: "1.5%", desc: "Smart risk/reward ratio. Standard settings for normal markets." },
    { id: "aggressive", name: "🎯 Aggressive", thresh: "> 0.55", risk: "2.5%", desc: "Takes more trades, willing to accept higher exposure and drawdowns." },
    { id: "ultra_aggressive", name: "🔥 Ultra Aggressive", thresh: "> 0.45", risk: "4.0%", desc: "Maximum opportunity seeking. Will trade on weaker signals." },
];

async function fetchSettings() {
    try {
        const res = await fetch("/api/settings/");
        const data = await res.json();
        
        const idx = MODES.findIndex(m => m.id === data.trading_mode);
        if (idx !== -1) {
            document.getElementById("mode-slider").value = idx;
            updateModeUI(idx);
            document.getElementById("mode-badge").innerText = MODES[idx].name;
            
            // Adjust badge color
            const badge = document.getElementById("mode-badge");
            if (idx <= 1) badge.className = "px-3 py-1 rounded-lg text-xs font-bold bg-emerald-900/40 text-emerald-400 border border-emerald-800/50";
            else if (idx === 2) badge.className = "px-3 py-1 rounded-lg text-xs font-bold bg-blue-900/40 text-blue-400 border border-blue-800/50";
            else badge.className = "px-3 py-1 rounded-lg text-xs font-bold bg-orange-900/40 text-orange-400 border border-orange-800/50";
        }
    } catch(e) { console.error(e); }
}

document.getElementById("mode-slider").addEventListener("input", (e) => {
    updateModeUI(e.target.value);
});

function updateModeUI(val) {
    const mode = MODES[val];
    document.getElementById("mode-title").innerText = mode.name;
    document.getElementById("mode-desc").innerText = mode.desc;
    document.getElementById("mode-thresh").innerText = mode.thresh;
    document.getElementById("mode-risk").innerText = mode.risk;
    
    // Change slider color dynamically
    const slider = document.getElementById("mode-slider");
    if (val <= 1) slider.style.accentColor = "#10B981";
    else if (val == 2) slider.style.accentColor = "#3B82F6";
    else slider.style.accentColor = "#EF4444";
}

function toggleSettingsModal() {
    const modal = document.getElementById("settings-modal");
    const inner = modal.querySelector("div");
    
    if (modal.classList.contains("hidden")) {
        modal.classList.remove("hidden");
        setTimeout(() => {
            modal.classList.remove("opacity-0");
            inner.classList.remove("scale-95");
            inner.classList.add("scale-100");
        }, 10);
    } else {
        modal.classList.add("opacity-0");
        inner.classList.remove("scale-100");
        inner.classList.add("scale-95");
        setTimeout(() => modal.classList.add("hidden"), 300);
    }
}

async function saveSettings() {
    const val = document.getElementById("mode-slider").value;
    const mode = MODES[val].id;
    
    try {
        const res = await fetch("/api/settings/mode", {
            method: "PUT",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ mode: mode })
        });
        
        if (res.ok) {
            toggleSettingsModal();
            fetchSettings(); // Refresh UI
        }
    } catch(e) { console.error(e); }
}
