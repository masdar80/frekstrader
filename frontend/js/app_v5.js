/**
 * ForeksTrader Frontend Logic — RESET V5
 */

let currentSymbol = "EURUSD";
let ws;
let isConnected = false;
let currentAuditFilter = 'all';
let cachedDecisions = [];

// DOM Elements
const statusBadge = document.getElementById("status-badge");

// Initialize
document.addEventListener("DOMContentLoaded", async () => {
    console.log("ForeksTrader V5: Booting...");
    
    // 1. WebSocket & Core Data (Highest Priority)
    initWebSocket();
    fetchDashboardSummary();
    fetchSettings();

    // 2. UI Components (Non-blocking)
    setTimeout(() => {
        try { initChart(); } catch(e) { console.error("Chart Crash:", e); }
    }, 200);

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

    // Audit Log Filters
    document.querySelectorAll(".filter-btn").forEach(btn => {
        btn.addEventListener("click", (e) => {
            document.querySelectorAll(".filter-btn").forEach(b => b.classList.remove("active"));
            e.target.classList.add("active");
            currentAuditFilter = e.target.getAttribute("data-filter");
            renderDecisions(cachedDecisions);
        });
    });
});

let chart;
let candleSeries;

function initChart() {
    try {
        const container = document.getElementById('chart-container');
        if (!container || typeof LightweightCharts === 'undefined') return;

        chart = LightweightCharts.createChart(container, {
            layout: { background: { type: 'solid', color: 'transparent' }, textColor: '#9CA3AF' },
            grid: { vertLines: { color: 'rgba(31, 41, 55, 0.5)' }, horzLines: { color: 'rgba(31, 41, 55, 0.5)' } },
            timeScale: { borderColor: 'rgba(31, 41, 55, 0.5)', timeVisible: true },
        });

        // Resilience: check for multiple naming variations of the series creators
        if (typeof chart.addCandlestickSeries === 'function') {
            candleSeries = chart.addCandlestickSeries({ upColor: '#10B981', downColor: '#EF4444' });
        } else if (typeof chart.addAreaSeries === 'function') {
            candleSeries = chart.addAreaSeries({ lineColor: '#3B82F6' });
        }

        new ResizeObserver(entries => {
            if (entries[0] && chart) chart.applyOptions({ width: entries[0].contentRect.width, height: entries[0].contentRect.height });
        }).observe(container);
        
        fetchChartData(currentSymbol);
        fetchSentimentData(currentSymbol);
    } catch(e) { console.error("initChart Error:", e); }
}

async function fetchChartData(symbol) {
    try {
        const res = await fetch(`/api/analysis/chart/${symbol}`);
        if (!res.ok) {
             document.getElementById("chart-overlay").innerHTML = '<div class="text-center text-red-400">Broker Error</div>';
             return;
        }
        
        const data = await res.json();
        // Always hide the "Connecting..." overlay if we got a valid response
        document.getElementById("chart-overlay").classList.add("opacity-0", "pointer-events-none");

        if (data.candles && data.candles.length > 0 && candleSeries) {
            const mapped = data.candles.map(c => ({
                time: new Date(c.time).getTime() / 1000,
                open: c.open, high: c.high, low: c.low, close: c.close
            })).sort((a,b) => a.time - b.time);
            candleSeries.setData(mapped);
            chart.timeScale().fitContent();
        } else {
             console.warn("No candles returned for", symbol);
        }
    } catch (e) { 
        console.error("Chart Data Error:", e);
        document.getElementById("chart-overlay").innerHTML = '<div class="text-center text-red-400">Error Loading Chart</div>';
    }
}

function initWebSocket() {
    try {
        const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
        const host = window.location.hostname === "localhost" ? "127.0.0.1" : window.location.hostname;
        const port = window.location.port || (protocol === "ws:" ? "80" : "443");
        const wsUrl = `${protocol}//${host}:${port}/ws`;
        
        console.log("WS: Attempting connection to:", wsUrl);
        
        ws = new WebSocket(wsUrl);
        
        ws.onopen = () => {
            console.log("WS: Connection SUCCESS to", wsUrl);
            isConnected = true;
            updateConnectionStatus(true);
            fetchDashboardSummary();
        };
    
    ws.onerror = (e) => {
        console.error("WS: Socket Error", e);
    };
    
    ws.onclose = (e) => {
        console.warn("WS: Closed", e.code, e.reason);
        isConnected = false;
        updateConnectionStatus(false);
        setTimeout(initWebSocket, 3000);
    };
    
    ws.onmessage = (event) => {
        try {
            const msg = JSON.parse(event.data);
            console.log("WS: Message", msg.type);
            if (msg.type === "account_update") {
                updateAccountUI(msg.data.account, msg.data.positions);
            } else if (msg.type === "decision_update") {
                console.log("WS: New Decision!", msg.data);
                prependDecision(msg.data);
                // Also refresh dashboard stats in case an order was placed
                fetchDashboardSummary();
            }
        } catch (e) {
            console.error("WS: Parse error", e);
        }
    };
    } catch(e) {
        console.error("initWebSocket failed:", e);
    }
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
        console.log("API: Fetching summary...");
        const res = await fetch("/api/dashboard/summary");
        if (res.ok) {
            const data = await res.json();
            console.log("API: Summary received", data.status);
            updateAccountUI(data.account, data.positions);
            updateDailyStats(data.metrics);
            renderDecisions(data.recent_decisions);
        }
    } catch (e) {
        console.error("API: Summary failed", e);
    }
}

function updateAccountUI(account, positions) {
    if (account && !account.error) {
        document.getElementById("stat-balance").innerText = `$${(account.balance || 0).toLocaleString()}`;
        document.getElementById("stat-margin").innerText = `$${(account.free_margin || 0).toLocaleString()}`;
        document.getElementById("nav-equity").innerText = `$${(account.equity || 0).toLocaleString()}`;
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
    el.innerText = `${pnl >= 0 ? '+' : ''}$${pnl.toLocaleString()}`;
    el.className = pnl >= 0 ? "font-bold text-buytext" : "font-bold text-selltext";
}

function renderPositions(positions) {
    const container = document.getElementById("positions-list");
    if (!positions || positions.length === 0) {
        container.innerHTML = `<div class="flex h-full items-center justify-center text-gray-500 text-sm italic">No open positions. Brain is being skeptical.</div>`;
        return;
    }
    
    container.innerHTML = positions.map(p => {
        const isBuy = p.type.includes('BUY');
        const sideClass = isBuy ? 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20' : 'bg-red-500/10 text-red-400 border-red-500/20';
        const sideText = isBuy ? 'BUY' : 'SELL';
        
        // Format time properly
        const openTime = p.open_time ? new Date(p.open_time).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) : '--:--';
        
        return `
            <div class="bg-panelbg2 rounded-xl p-3 mb-3 border border-gray-800/80 shadow-sm hover:border-gray-700 transition-all group relative overflow-hidden">
                <div class="flex justify-between items-start mb-2">
                    <div>
                        <div class="flex items-center gap-2 mb-1">
                            <span class="font-bold text-white text-base">${p.symbol}</span>
                            <span class="px-1.5 py-0.5 rounded text-[10px] font-bold border ${sideClass}">${sideText} ${p.volume}</span>
                        </div>
                        <p class="text-[10px] text-gray-500 font-mono tracking-tighter">ENTRY @ ${p.open_price} • ${openTime}</p>
                    </div>
                    <div class="text-right">
                        <div class="${p.profit >= 0 ? 'text-buytext' : 'text-selltext'} font-bold text-lg leading-tight tracking-tight">
                            ${p.profit >= 0 ? '+' : ''}$${p.profit.toFixed(2)}
                        </div>
                    </div>
                </div>
                
                <div class="grid grid-cols-2 gap-2 mt-2 pt-2 border-t border-gray-800/40">
                    <div class="bg-black/20 rounded p-1.5 border border-gray-800/30">
                        <span class="block text-[9px] text-gray-500 uppercase font-bold">Stop Loss</span>
                        <span class="text-xs text-red-400/80 font-mono">${p.stop_loss || 'Not Set'}</span>
                    </div>
                    <div class="bg-black/20 rounded p-1.5 border border-gray-800/30">
                        <span class="block text-[9px] text-gray-500 uppercase font-bold">Take Profit</span>
                        <span class="text-xs text-emerald-400/80 font-mono">${p.take_profit || 'Not Set'}</span>
                    </div>
                </div>
            </div>
        `;
    }).join("");
}

function renderDecisions(decisions) {
    cachedDecisions = decisions; // Store for filtering
    const container = document.getElementById("decision-log");
    if (!decisions || decisions.length === 0) return;
    
    const filtered = decisions.filter(d => {
        if (currentAuditFilter === 'all') return true;
        if (currentAuditFilter === 'approved') return d.action !== 'REJECT';
        if (currentAuditFilter === 'rejected') return d.action === 'REJECT';
        return true;
    });

    if (filtered.length === 0) {
        container.innerHTML = `<div class="text-center text-gray-600 text-xs py-10 italic">No ${currentAuditFilter} decisions yet.</div>`;
        return;
    }
    
    container.innerHTML = filtered.map(d => getDecisionHTML(d)).join("");
}

function prependDecision(d) {
    cachedDecisions.unshift(d);
    if (cachedDecisions.length > 50) cachedDecisions.pop();
    
    // Only update DOM if the new decision matches the current filter
    if (currentAuditFilter === 'all' || 
        (currentAuditFilter === 'approved' && d.action !== 'REJECT') ||
        (currentAuditFilter === 'rejected' && d.action === 'REJECT')) {
        
        const container = document.getElementById("decision-log");
        if (container.innerHTML.includes("italic")) container.innerHTML = "";
        
        const div = document.createElement("div");
        div.innerHTML = getDecisionHTML(d);
        container.insertBefore(div.firstElementChild, container.firstChild);
        
        if (container.children.length > 50) container.removeChild(container.lastChild);
    }
}

function getDecisionHTML(d) {
    const isReject = d.action === 'REJECT';
    const borderClass = isReject ? 'border-gray-700' : 'border-emerald-500';
    
    // Convert to Local Time
    const dateObj = new Date(d.timestamp);
    const timeStr = dateObj.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });
    
    const aiBadge = d.ai_active === false ? 
        `<span class="text-[9px] bg-red-900/20 text-red-500 px-1.5 py-0.5 rounded border border-red-800/30 ml-2 uppercase font-bold tracking-tighter">Indicators Only</span>` :
        `<span class="text-[9px] bg-blue-900/20 text-blue-500 px-1.5 py-0.5 rounded border border-blue-800/30 ml-2 uppercase font-bold tracking-tighter">AI Layer</span>`;

    return `
        <div class="bg-panelbg2 rounded-lg p-3 mb-2 border-l-4 ${borderClass} text-xs transition-all duration-500 animate-in slide-in-from-left-2 shadow-sm border border-gray-800/50">
            <div class="flex justify-between mb-1 items-center">
                <div class="flex items-center">
                    <span class="font-bold text-gray-200 tracking-wide">${d.symbol} ${d.action}</span>
                    ${aiBadge}
                </div>
                <span class="text-gray-600 font-mono text-[10px]">${timeStr}</span>
            </div>
            <p class="text-gray-500 leading-relaxed">${d.reasoning}</p>
        </div>
    `;
}

// Settings Modal Logic
const modeMetadata = [
    { value: 'ultra_conservative', title: 'Ultra Conservative', desc: 'Extreme skepticism. Requires 5+ indicators. 0.5% risk.', thresh: '> 0.85', risk: '0.5%' },
    { value: 'conservative', title: 'Conservative', desc: 'Very skeptical. Requires 4+ indicators. 1.0% risk.', thresh: '> 0.75', risk: '1.0%' },
    { value: 'balanced', title: 'Balanced', desc: 'Standard logic. Requires 3+ indicators. 1.5% risk.', thresh: '> 0.65', risk: '1.5%' },
    { value: 'aggressive', title: 'Aggressive', desc: 'Opportunistic. Requires 2+ indicators. 2.5% risk.', thresh: '> 0.55', risk: '2.5%' },
    { value: 'ultra_aggressive', title: 'Ultra Aggressive', desc: 'High risk. Requires 1 indicator. 4.0% risk.', thresh: '> 0.45', risk: '4.0%' }
];

function toggleSettingsModal() {
    const modal = document.getElementById("settings-modal");
    if (!modal) return;
    
    if (modal.classList.contains("hidden")) {
        modal.classList.remove("hidden");
        // Trigger reflow for animation
        modal.offsetWidth;
        modal.classList.remove("opacity-0");
        modal.querySelector('.bg-panelbg').classList.remove("scale-95");
    } else {
        modal.classList.add("opacity-0");
        modal.querySelector('.bg-panelbg').classList.add("scale-95");
        setTimeout(() => modal.classList.add("hidden"), 300);
    }
}

// Slider update listener
document.addEventListener("DOMContentLoaded", () => {
    const slider = document.getElementById("mode-slider");
    if (slider) {
        slider.addEventListener("input", (e) => {
            const index = e.target.value;
            const meta = modeMetadata[index];
            document.getElementById("mode-title").innerText = meta.title;
            document.getElementById("mode-desc").innerText = meta.desc;
            document.getElementById("mode-thresh").innerText = meta.thresh;
            document.getElementById("mode-risk").innerText = meta.risk;
        });
    }
});

async function saveSettings() {
    const slider = document.getElementById("mode-slider");
    const index = slider.value;
    const mode = modeMetadata[index].value;
    const useAI = document.getElementById("ai-toggle").checked;
    
    try {
        const res = await fetch("/api/settings/mode", {
            method: "PUT",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ mode: mode, use_ai_sentiment: useAI })
        });
        
        if (res.ok) {
            const data = await res.json();
            console.log("Settings saved:", data);
            document.getElementById("mode-badge").innerText = data.mode.toUpperCase();
            updateAISettingsUI(useAI);
            toggleSettingsModal();
            // Refresh summary to reflect potential changes
            fetchDashboardSummary();
        } else {
            console.error("Failed to save settings");
            alert("Error saving settings. Check console.");
        }
    } catch (e) {
        console.error("Save error:", e);
    }
}

async function fetchSettings() {
    try {
        const res = await fetch("/api/settings/");
        if (res.ok) {
            const data = await res.json();
            document.getElementById("mode-badge").innerText = data.trading_mode.toUpperCase();
            
            // Sync AI toggle
            const aiToggle = document.getElementById("ai-toggle");
            if (aiToggle) {
                aiToggle.checked = data.use_ai_sentiment;
                updateAISettingsUI(data.use_ai_sentiment);
            }

            // Sync slider
            const index = modeMetadata.findIndex(m => m.value === data.trading_mode);
            if (index !== -1) {
                const slider = document.getElementById("mode-slider");
                if (slider) {
                    slider.value = index;
                    // Trigger input event to update descriptions
                    slider.dispatchEvent(new Event('input'));
                }
            }
        }
    } catch(e) { console.error(e); }
}

function updateAISettingsUI(useAI) {
    const badge = document.getElementById("ai-status-badge");
    if (!badge) return;
    
    if (useAI) {
        badge.innerText = "ACTIVE";
        badge.className = "px-3 py-1 rounded-lg text-xs font-bold transition-all border border-emerald-800/50 bg-emerald-900/40 text-emerald-400";
    } else {
        badge.innerText = "DISABLED";
        badge.className = "px-3 py-1 rounded-lg text-xs font-bold transition-all border border-red-800/50 bg-red-900/40 text-red-400 uppercase";
    }
}

async function fetchSentimentData(symbol) {
    const container = document.getElementById("sentiment-container");
    try {
        const res = await fetch(`/api/analysis/signals/${symbol}?limit=1`);
        if (res.ok) {
            const data = await res.json();
            if (data.length > 0) {
                const s = data[0];
                container.innerHTML = `
                    <div class="p-3 bg-panelbg2 rounded-xl border border-gray-800">
                        <p class="text-sm font-bold">Confidence: ${(s.confidence*100).toFixed(0)}%</p>
                        <p class="text-xs text-gray-400 mt-1">${s.reasoning}</p>
                    </div>
                `;
            }
        }
    } catch(e) { console.error(e); }
}


