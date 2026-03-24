/**
 * ForeksTrader Frontend Logic — RESET V5
 */

let currentSymbol = "EURUSD";
let currentTimeframe = "15m";
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
        try { initEquityChart(); } catch(e) { console.error("Equity Chart Crash:", e); }
        fetchTradeHistory();
    }, 200);

    // Pair selector listeners
    document.querySelectorAll(".pair-btn").forEach(btn => {
        btn.addEventListener("click", (e) => {
            document.querySelectorAll(".pair-btn").forEach(b => b.classList.remove("active"));
            e.target.classList.add("active");
            currentSymbol = e.target.innerText;
            fetchChartData(currentSymbol, currentTimeframe);
            fetchSentimentData(currentSymbol);
        });
    });

    // Timeframe selector listeners
    document.querySelectorAll("#tf-selector .filter-btn").forEach(btn => {
        btn.addEventListener("click", (e) => {
            document.querySelectorAll("#tf-selector .filter-btn").forEach(b => b.classList.remove("active"));
            e.target.classList.add("active");
            currentTimeframe = e.target.getAttribute("data-tf");
            fetchChartData(currentSymbol, currentTimeframe);
        });
    });

    // Equity timeframe selector listeners
    document.querySelectorAll("#equity-tf-selector .filter-btn").forEach(btn => {
        btn.addEventListener("click", (e) => {
            document.querySelectorAll("#equity-tf-selector .filter-btn").forEach(b => b.classList.remove("active", "bg-gray-800"));
            e.target.classList.add("active", "bg-gray-800");
            window.currentEquityHours = parseInt(e.target.getAttribute("data-hours"));
            fetchEquityHistory(window.currentEquityHours);
        });
    });

    // Auto-refresh trade history
    setInterval(() => {
        if (isConnected) fetchTradeHistory();
    }, 30000);

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

        // If container height is 0, wait and retry
        if (container.clientHeight === 0) {
            console.warn("Chart: Container has no height, retrying...");
            setTimeout(initChart, 200);
            return;
        }

        chart = LightweightCharts.createChart(container, {
            layout: { background: { type: 'solid', color: 'transparent' }, textColor: '#9CA3AF' },
            grid: { vertLines: { color: 'rgba(31, 41, 55, 0.5)' }, horzLines: { color: 'rgba(31, 41, 55, 0.5)' } },
            timeScale: { borderColor: 'rgba(31, 41, 55, 0.5)', timeVisible: true },
        });

        console.log("Chart created successfully:", chart);
        
        // Robust check for candlestick series method
        if (typeof chart.addCandlestickSeries === 'function') {
            candleSeries = chart.addCandlestickSeries({ upColor: '#10B981', downColor: '#EF4444', borderVisible: false, wickVisible: true });
        } else if (typeof chart.addSeries === 'function' && LightweightCharts.CandlestickSeries) {
            candleSeries = chart.addSeries(LightweightCharts.CandlestickSeries, { upColor: '#10B981', downColor: '#EF4444', borderVisible: false, wickVisible: true });
        } else {
            throw new Error("Could not find candlestick series method on chart object. Chart API: " + Object.keys(chart).join(", "));
        }


        const resizeObserver = new ResizeObserver(entries => {
            if (entries[0] && chart) {
                const { width, height } = entries[0].contentRect;
                chart.applyOptions({ width, height });
                chart.timeScale().fitContent();
            }
        });
        resizeObserver.observe(container);
        
        fetchChartData(currentSymbol, currentTimeframe);
        
        // Auto-refresh chart every 30 seconds
        if (window.chartRefreshInterval) clearInterval(window.chartRefreshInterval);
        window.chartRefreshInterval = setInterval(() => {
            if (isConnected) fetchChartData(currentSymbol, currentTimeframe);
        }, 30000);
    } catch(e) { console.error("initChart Error:", e); }
}

async function fetchChartData(symbol, timeframe) {
    try {
        const res = await fetch(`/api/analysis/chart/${symbol}?timeframe=${timeframe || '15m'}`);
        if (!res.ok) {
             document.getElementById("chart-overlay").innerHTML = '<div class="text-center text-red-400">Broker Error</div>';
             return;
        }
        
        const data = await res.json();
        // Always hide the "Connecting..." overlay if we got a valid response
        document.getElementById("chart-overlay").classList.add("opacity-0", "pointer-events-none");

        if (data.candles && data.candles.length > 0) {
            console.log(`API: Received ${data.candles.length} candles for ${symbol} (${timeframe})`);
            if (!candleSeries) {
                console.warn("Chart: candleSeries not ready, waiting...");
                setTimeout(() => fetchChartData(symbol, timeframe), 500);
                return;
            }
            const mapped = data.candles.map(c => ({
                time: new Date(c.time).getTime() / 1000,
                open: c.open, high: c.high, low: c.low, close: c.close
            })).sort((a,b) => a.time - b.time);
            candleSeries.setData(mapped);
            chart.timeScale().fitContent();
        } else {
             console.warn("No candles returned for", symbol, data);
        }
    } catch (e) { 
        console.error("Chart Data Error:", e);
        document.getElementById("chart-overlay").innerHTML = `<div class="text-center text-red-400">Error: ${e.message}</div>`;
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
                updateAuditPulse();
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

function updateAuditPulse() {
    const el = document.getElementById("audit-heartbeat");
    if (!el) return;
    el.classList.remove("opacity-0");
    const time = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });
    el.innerHTML = `<i class="fa-solid fa-bolt text-yellow-400 animate-pulse"></i> Pulse: ${time}`;
    
    // Fade out after 2 seconds
    clearTimeout(window.pulseTimeout);
    window.pulseTimeout = setTimeout(() => {
        el.classList.add("opacity-100");
    }, 2000);
}

function updateConnectionStatus(connected) {
    if (connected) {
        fetchEmergencyStatus();
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
            updateRiskMeters(data.metrics);
            renderDecisions(data.recent_decisions);
        }
        await fetchEmergencyStatus();
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
        
        // Calculate Profit/Loss at TP and SL
        const contractSize = 100000;
        const isJPY = p.symbol.includes("JPY");
        let tpProfit = "0.00";
        let slLoss = "0.00";
        
        const calcVal = (target) => {
            if (!target) return "N/A";
            const diff = isBuy ? (target - p.open_price) : (p.open_price - target);
            let val = diff * p.volume * contractSize;
            if (isJPY) val = val / p.current_price;
            return val.toFixed(2);
        };
        
        tpProfit = calcVal(p.take_profit);
        slLoss = calcVal(p.stop_loss);

        return `
            <div class="bg-panelbg2 rounded-xl p-3 mb-3 border border-gray-800/80 shadow-sm hover:border-gray-700 transition-all group relative overflow-hidden">
                <div class="flex justify-between items-start mb-2">
                    <div>
                        <div class="flex items-center gap-2 mb-1">
                            <span class="font-bold text-white text-base">${p.symbol}</span>
                            <span class="px-1.5 py-0.5 rounded text-[10px] font-bold border ${sideClass}">${sideText} ${p.volume}</span>
                        </div>
                        <p class="text-[10px] text-gray-400 font-mono tracking-tighter">
                            ENTRY @ ${p.open_price.toFixed(5)} <br/>
                            <span class="text-accent font-bold">CURRENT @ ${p.current_price.toFixed(5)}</span>
                        </p>
                    </div>
                    <div class="text-right">
                        <div class="${p.profit >= 0 ? 'text-buytext' : 'text-selltext'} font-bold text-lg leading-tight tracking-tight">
                            ${p.profit >= 0 ? '+' : ''}$${p.profit.toFixed(2)}
                        </div>
                        <div class="flex justify-end gap-2 mt-1 items-center">
                            <span class="text-[9px] text-gray-500 uppercase">${openTime}</span>
                            <button onclick="closePosition('${p.id}')" class="bg-red-900/40 hover:bg-red-800 text-red-300 text-[10px] uppercase font-bold px-2 py-0.5 rounded border border-red-800/50 transition-colors">Close</button>
                        </div>
                    </div>
                </div>
                
                <div class="grid grid-cols-2 gap-2 mt-2 pt-2 border-t border-gray-800/40">
                    <div class="bg-black/20 rounded p-1.5 border border-gray-800/30">
                        <span class="block text-[9px] text-gray-500 uppercase font-bold">Stop Loss</span>
                        <div class="flex justify-between items-end">
                            <span class="text-xs text-red-400/80 font-mono">${p.stop_loss ? p.stop_loss.toFixed(5) : 'Not Set'}</span>
                            <span class="text-[8px] text-red-500/60 font-bold">${slLoss !== "N/A" ? '$' + slLoss : ''}</span>
                        </div>
                    </div>
                    <div class="bg-black/20 rounded p-1.5 border border-gray-800/30">
                        <span class="block text-[9px] text-gray-500 uppercase font-bold">Take Profit</span>
                        <div class="flex justify-between items-end">
                            <span class="text-xs text-emerald-400/80 font-mono">${p.take_profit ? p.take_profit.toFixed(5) : 'Not Set'}</span>
                            <span class="text-[8px] text-emerald-500/60 font-bold">${tpProfit !== "N/A" ? '$' + tpProfit : ''}</span>
                        </div>
                    </div>
                </div>
            </div>
        `;
    }).join("");
}

function renderDecisions(decisions) {
    if (!decisions || decisions.length === 0) return;
    
    // MERGE LOGIC: Keep newer local decisions that might not be in the server's list yet
    const combined = [...cachedDecisions];
    decisions.forEach(d => {
        // Simple check: if this exact timestamp/symbol doesn't exist in combined, add it
        const exists = combined.some(c => c.timestamp === d.timestamp && c.symbol === d.symbol);
        if (!exists) combined.push(d);
    });

    // Sort by timestamp descending
    combined.sort((a,b) => new Date(b.timestamp) - new Date(a.timestamp));
    
    // Keep internal cache limited
    cachedDecisions = combined.slice(0, 100);
    
    const container = document.getElementById("decision-log");
    const filtered = cachedDecisions.filter(d => {
        if (currentAuditFilter === 'all') return true;
        if (currentAuditFilter === 'approved') return d.action !== 'REJECT';
        if (currentAuditFilter === 'rejected') return d.action === 'REJECT';
        return true;
    }).slice(0, 50); // Show top 50

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
    
    // Ensure timestamp is treated as UTC if no offset is present
    let ts = d.timestamp;
    if (ts && !ts.includes('Z') && !ts.includes('+')) ts += 'Z';
    
    // Convert to Local Time
    const dateObj = new Date(ts);
    const timeStr = dateObj.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });
    
    const aiBadge = d.ai_active === false ? 
        `<span class="text-[9px] bg-red-900/20 text-red-500 px-1.5 py-0.5 rounded border border-red-800/30 ml-2 uppercase font-bold tracking-tighter">Indicators Only</span>` :
        `<span class="text-[9px] bg-blue-900/20 text-blue-500 px-1.5 py-0.5 rounded border border-blue-800/30 ml-2 uppercase font-bold tracking-tighter">AI Layer</span>`;

    // Extract indicators
    let indicators = d.indicators || [];
    let sentiment = d.sentiment;
    
    if (d.signals_json) {
        const taSignal = d.signals_json.find(s => s.source === "Technical Analysis");
        if (taSignal && taSignal.data_json && taSignal.data_json.breakdown) {
            indicators = taSignal.data_json.breakdown;
        }
        const sentSignal = d.signals_json.find(s => s.source === "AI Sentiment");
        if (sentSignal && sentSignal.data_json) {
            sentiment = sentSignal.data_json;
        }
    }

    let detailsHTML = `<div class="hidden mt-2 pt-2 border-t border-gray-800/60 bg-black/20 rounded-lg p-2 text-xs">`;
    
    if (indicators && indicators.length > 0) {
        detailsHTML += `<div class="mb-2 uppercase text-[10px] text-gray-500 font-bold">Indicator Breakdown</div>`;
        detailsHTML += `<div class="grid grid-cols-5 gap-1 text-[9px] text-center mb-3">`;
        detailsHTML += `<div class="font-bold text-gray-400 text-left">Ind/TF</div><div class="font-bold text-gray-400">15m</div><div class="font-bold text-gray-400">1h</div><div class="font-bold text-gray-400">4h</div><div class="font-bold text-gray-400">1d</div>`;
        
        // Group by indicator
        const indMap = {};
        indicators.forEach(ind => {
            if (!indMap[ind.indicator]) indMap[ind.indicator] = {};
            indMap[ind.indicator][ind.timeframe] = ind;
        });
        
        ['RSI', 'MACD', 'EMA_Fast', 'EMA_Slow', 'Stoch', 'BBands', 'ADX'].forEach(indName => {
            if (indMap[indName]) {
                detailsHTML += `<div class="text-left font-mono text-gray-400 flex items-center">${indName.replace('EMA_', 'EMA')}</div>`;
                ['15m', '1h', '4h', '1d'].forEach(tf => {
                    const item = indMap[indName][tf];
                    if (item) {
                        const sigColor = item.signal === 'BUY' ? 'text-emerald-400 bg-emerald-900/40 border-emerald-800' : (item.signal === 'SELL' ? 'text-red-400 bg-red-900/40 border-red-800' : 'text-gray-400 bg-gray-800 border-gray-700');
                        detailsHTML += `<div class="rounded border p-1 ${sigColor}">${typeof item.value === 'number' ? item.value.toFixed(2) : String(item.value).substring(0,5)}</div>`;
                    } else {
                        detailsHTML += `<div class="text-gray-700 rounded border border-transparent p-1">-</div>`;
                    }
                });
            }
        });
        detailsHTML += `</div>`;
    }

    if (sentiment && sentiment.signal) {
        detailsHTML += `<div class="mb-1 uppercase text-[10px] text-gray-500 font-bold">AI Sentiment Layer</div>`;
        const sigColor = sentiment.signal === 'BUY' ? 'text-emerald-400' : (sentiment.signal === 'SELL' ? 'text-red-400' : 'text-gray-400');
        detailsHTML += `<div class="text-[10px] text-gray-400 mb-2">Signal: <span class="font-bold ${sigColor}">${sentiment.signal}</span> (Score: ${(sentiment.score * 100).toFixed(0)}%)</div>`;
    }

    if (d.sizing) {
        detailsHTML += `<div class="mt-2 mb-1 uppercase text-[10px] text-gray-500 font-bold">Execution Details</div>`;
        detailsHTML += `<div class="text-[10px] text-gray-400 font-mono bg-panelbg p-1.5 rounded">Volume: ${d.sizing.volume} | SL: ${d.sizing.stop_loss.toFixed(5)} | TP: ${d.sizing.take_profit.toFixed(5)}<br>Risk: $${d.sizing.risk_amount.toFixed(2)}</div>`;
    } else if (d.risk_check && !d.risk_check.allowed) {
        detailsHTML += `<div class="mt-2 mb-1 uppercase text-[10px] text-gray-500 font-bold">Risk Management</div>`;
        detailsHTML += `<div class="text-[10px] text-red-400 font-mono bg-red-900/20 p-1.5 rounded border border-red-800/30">Blocked: ${d.risk_check.reason}</div>`;
    }

    detailsHTML += `</div>`;

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
            <button class="mt-2 text-[10px] text-accent hover:text-accenthover font-bold uppercase tracking-wider flex items-center gap-1 transition-all" onclick="this.nextElementSibling.classList.toggle('hidden');">
                <i class="fa-solid fa-list-ul"></i> Show Breakdown
            </button>
            ${detailsHTML}
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
    container.innerHTML = `<div class="text-center text-gray-500 text-sm py-4"><i class="fa-solid fa-circle-notch fa-spin text-accent mb-2"></i><br>Analyzing news...</div>`;
    try {
        const res = await fetch(`/api/analysis/sentiment/${symbol}`);
        if (res.ok) {
            const data = await res.json();
            
            // Format base/quote breakdown
            const baseObj = data.base || {};
            const quoteObj = data.quote || {};
            
            // Render structured sentiment view
            const signalColor = data.signal === 'BUY' ? 'text-emerald-400' : (data.signal === 'SELL' ? 'text-red-400' : 'text-gray-400');
            const scorePercent = Math.abs(data.score * 100).toFixed(0);
            
            container.innerHTML = `
                <div class="flex items-center justify-between px-2 mb-1">
                    <span class="text-sm font-bold text-gray-300">${symbol} Outlook</span>
                    <span class="text-lg font-bold ${signalColor}">${data.signal}</span>
                </div>
                
                <div class="bg-panelbg2 rounded-xl border border-gray-800 p-3 mb-2">
                    <p class="text-[11px] text-gray-400 leading-relaxed italic mb-2 border-l-2 border-accent pl-2">
                        "${baseObj.reasoning || data.score}"
                    </p>
                    <div class="flex justify-between items-center text-xs">
                        <span class="text-gray-500">Net Strength</span>
                        <span class="font-bold ${signalColor}">${scorePercent}%</span>
                    </div>
                    <div class="w-full bg-gray-800 rounded-full h-1.5 mt-1 overflow-hidden flex">
                        <div class="${data.score > 0 ? 'bg-emerald-500' : 'bg-red-500'} h-1.5" style="width: ${scorePercent}% ${data.score < 0 ? '; margin-left: auto' : ''}"></div>
                    </div>
                </div>
                
                <div class="grid grid-cols-2 gap-2">
                    <div class="bg-panelbg2 rounded-lg p-2 border border-gray-800">
                        <span class="text-[10px] text-gray-500 uppercase block">${symbol.substring(0,3)} News</span>
                        <span class="font-bold text-xs ${baseObj.score > 0 ? 'text-emerald-400' : (baseObj.score < 0 ? 'text-red-400' : 'text-gray-400')}">
                            ${(baseObj.score * 100).toFixed(0)}%
                        </span>
                    </div>
                    <div class="bg-panelbg2 rounded-lg p-2 border border-gray-800">
                        <span class="text-[10px] text-gray-500 uppercase block">${symbol.substring(3,6)} News</span>
                        <span class="font-bold text-xs ${quoteObj.score > 0 ? 'text-emerald-400' : (quoteObj.score < 0 ? 'text-red-400' : 'text-gray-400')}">
                            ${(quoteObj.score * 100).toFixed(0)}%
                        </span>
                    </div>
                </div>
            `;
        } else {
             container.innerHTML = `<div class="text-center text-red-500 text-sm py-4">Sentiment API Error</div>`;
        }
    } catch(e) { 
        console.error(e); 
        container.innerHTML = `<div class="text-center text-gray-500 text-sm py-4">Network error loading sentiment</div>`;
    }
}

async function closePosition(id) {
    if (!confirm("Are you sure you want to manually close this position?")) return;
    
    // Attempt to retrieve API key before sending
    // For local dev, we might not have it in the UI unless provided
    // If endpoints are protected, UI needs a way to store X-API-Key.
    // For now, we will send the request. If it 403s, we alert the user.
    try {
        // First try to fetch the key from local storage if the user saved it
        let headers = { "Content-Type": "application/json" };
        const savedKey = localStorage.getItem("foreks_api_key");
        if (savedKey) headers["X-API-Key"] = savedKey;

        const res = await fetch(`/api/trading/close/${id}`, {
            method: "POST",
            headers: headers
        });
        
        if (res.ok) {
            console.log("Position closed");
            fetchDashboardSummary(); // refresh UI
        } else if (res.status === 401 || res.status === 403) {
            const key = prompt("API Key required for manual trading. Please enter your APP_API_KEY from .env:");
            if (key) {
                localStorage.setItem("foreks_api_key", key);
                closePosition(id); // Retry
            }
        } else {
            const data = await res.json();
            alert(`Error closing position: ${data.detail || "Unknown error"}`);
        }
    } catch(e) {
        console.error("Close Error:", e);
        alert("Failed to close position: network error");
    }
}

async function getApiKeyForAction(actionName) {
    let savedKey = localStorage.getItem("foreks_api_key");
    if (!savedKey) {
        savedKey = prompt(`API Key required for ${actionName}. Please enter your APP_API_KEY from .env:`);
        if (savedKey) localStorage.setItem("foreks_api_key", savedKey);
    }
    return savedKey;
}

async function emergencyStop() {
    if (!confirm("🚨 EMERGENCY STOP: Are you sure you want to CLOSE ALL POSITIONS and PAUSE the bot?")) return;
    
    const key = await getApiKeyForAction("emergency close-all");
    if (!key) return;

    try {
        const res = await fetch("/api/emergency/close-all", {
            method: "POST",
            headers: { "Content-Type": "application/json", "X-API-Key": key }
        });
        
        if (res.ok) {
            alert("Emergency stop triggered successfully!");
            updateEmergencyUI(true);
            fetchDashboardSummary();
        } else if (res.status === 401 || res.status === 403) {
            localStorage.removeItem("foreks_api_key");
            alert("Invalid API Key");
        } else {
            const data = await res.json();
            alert(`Error: ${data.detail || "Unknown error"}`);
        }
    } catch(e) {
        console.error("Emergency Stop Error:", e);
        alert("Network error starting emergency stop");
    }
}

async function resumeTrading() {
    if (!confirm("▶️ Resume trading? The bot will start placing new trades based on the strategy.")) return;
    
    const key = await getApiKeyForAction("resuming trading");
    if (!key) return;

    try {
        const res = await fetch("/api/emergency/resume", {
            method: "POST",
            headers: { "Content-Type": "application/json", "X-API-Key": key }
        });
        
        if (res.ok) {
            updateEmergencyUI(false);
            fetchDashboardSummary();
        } else if (res.status === 401 || res.status === 403) {
            localStorage.removeItem("foreks_api_key");
            alert("Invalid API Key");
        }
    } catch(e) {
        console.error("Resume Error:", e);
    }
}

function updateEmergencyUI(isPaused) {
    const btnEmergency = document.getElementById("btn-emergency");
    const btnResume = document.getElementById("btn-resume");
    
    if (!btnEmergency || !btnResume) return;

    if (isPaused) {
        btnEmergency.classList.add("hidden");
        btnResume.classList.remove("hidden");
        
        statusBadge.className = "ml-4 px-2.5 py-1 rounded-full text-xs font-medium bg-orange-900/40 text-orange-400 border border-orange-800/50 flex items-center gap-1.5";
        statusBadge.innerHTML = `<i class="fa-solid fa-pause"></i> PAUSED`;
    } else {
        btnEmergency.classList.remove("hidden");
        btnResume.classList.add("hidden");
        
        if (isConnected) {
            statusBadge.className = "ml-4 px-2.5 py-1 rounded-full text-xs font-medium bg-emerald-900/40 text-emerald-400 border border-emerald-800/50 flex items-center gap-1.5";
            statusBadge.innerHTML = `<div class="w-1.5 h-1.5 rounded-full bg-emerald-500 shadow-[0_0_8px_#10B981]"></div> Active`;
        }
    }
}

async function fetchEmergencyStatus() {
    try {
        const res = await fetch("/api/emergency/status");
        if (res.ok) {
            const data = await res.json();
            if (isConnected) updateEmergencyUI(data.is_paused);
        }
    } catch (e) {
         console.error("fetchEmergencyStatus error:", e);
    }
}

let equityChart;
let equitySeries;
window.currentEquityHours = 24;

function initEquityChart() {
    try {
        const container = document.getElementById('equity-chart');
        if (!container || typeof LightweightCharts === 'undefined') return;

        if (container.clientHeight === 0) {
            setTimeout(initEquityChart, 200);
            return;
        }

        equityChart = LightweightCharts.createChart(container, {
            layout: { background: { type: 'solid', color: 'transparent' }, textColor: '#9CA3AF' },
            grid: { vertLines: { color: 'rgba(31, 41, 55, 0.2)' }, horzLines: { color: 'rgba(31, 41, 55, 0.2)' } },
            timeScale: { borderColor: 'rgba(31, 41, 55, 0.5)', timeVisible: true },
            rightPriceScale: { borderVisible: false }
        });
        
        if (typeof equityChart.addLineSeries === 'function') {
            equitySeries = equityChart.addLineSeries({
                color: '#3B82F6',
                lineWidth: 2,
                crosshairMarkerVisible: false,
                lastValueVisible: false,
                priceLineVisible: false,
            });
        }
        
        const resizeObserver = new ResizeObserver(entries => {
            if (entries[0] && equityChart) {
                const { width, height } = entries[0].contentRect;
                equityChart.applyOptions({ width, height });
            }
        });
        resizeObserver.observe(container);
        
        fetchEquityHistory(24);
        
        setInterval(() => { if (isConnected) fetchEquityHistory(window.currentEquityHours); }, 60000);
    } catch(e) { console.error("initEquityChart Error:", e); }
}

async function fetchEquityHistory(hours) {
    try {
        const res = await fetch(`/api/dashboard/equity-history?hours=${hours}`);
        if (res.ok) {
            const data = await res.json();
            if (data.length > 0 && equitySeries) {
                const mapped = data.map(d => ({
                    time: new Date(d.timestamp).getTime() / 1000,
                    value: d.equity
                })).sort((a,b) => a.time - b.time);
                
                // deduplicate identical times
                const deduped = [];
                for (let i = 0; i < mapped.length; i++) {
                    if (i === 0 || mapped[i].time !== mapped[i-1].time) {
                        deduped.push(mapped[i]);
                    }
                }
                
                if (deduped.length > 0) {
                    equitySeries.setData(deduped);
                    equityChart.timeScale().fitContent();
                }
            }
        }
    } catch (e) { console.error("Equity History fetch error:", e); }
}

async function fetchTradeHistory() {
    try {
        const res = await fetch(`/api/dashboard/trade-history?limit=50`);
        if (res.ok) {
            const data = await res.json();
            renderTradeHistory(data);
        }
    } catch (e) { console.error("Trade History fetch error:", e); }
}

function renderTradeHistory(trades) {
    const list = document.getElementById("trade-history-list");
    if (!trades || trades.length === 0) {
        list.innerHTML = `<div class="flex h-full items-center justify-center text-gray-500 text-sm italic py-8">No closed trades yet.</div>`;
        return;
    }
    
    let html = `<table class="w-full text-left text-xs bg-transparent">
        <thead class="text-gray-500 bg-black/20 sticky top-0 uppercase font-bold text-[9px] mb-2 tracking-widest">
            <tr>
                <th class="p-2">Time</th>
                <th class="p-2">Pair</th>
                <th class="p-2">Side</th>
                <th class="p-2 text-right">P&L</th>
            </tr>
        </thead>
        <tbody class="divide-y divide-gray-800/50">`;
        
    trades.forEach(t => {
        const d = new Date(t.closed_at);
        const timeStr = d.toLocaleDateString([], { month: 'short', day: 'numeric'}) + " " + d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit'});
        
        const isBuy = t.direction.includes("BUY");
        const dirColor = isBuy ? "text-emerald-400" : "text-red-400";
        
        const pnlStr = (t.profit >= 0 ? "+" : "") + "$" + t.profit.toFixed(2);
        const pnlColor = t.profit >= 0 ? "text-emerald-400" : "text-red-400";
        
        html += `
            <tr class="hover:bg-gray-800/30 transition-colors group">
                <td class="p-2 text-gray-500 text-[10px] whitespace-nowrap">${timeStr}</td>
                <td class="p-2 font-bold text-gray-300">${t.symbol}</td>
                <td class="p-2 font-bold ${dirColor}">${t.direction}</td>
                <td class="p-2 font-mono font-bold text-right ${pnlColor}">${pnlStr}</td>
            </tr>
        `;
    });
    
    html += `</tbody></table>`;
    list.innerHTML = html;
}

function updateRiskMeters(metrics) {
    if (!metrics) return;
    
    const dailyLossLimitPct = metrics.max_daily_loss || 3.0; // as positive number
    // metrics.daily_pnl is in dollars. To get a percent, we need peak equity or balance.
    // We already fetch account_info which gives equity, but for the true percent we need 
    // to calculate it based on the day's starting balance. Let's approximate based on drawdowns for now.
    // Or, we use drawdown_pct directly.
    const drawdownLimitPct = 10.0;
    
    // Instead of precise calculation since we lack daily start balance here, 
    // let's grab drawdown from the most recent snippet or estimate
    const navEquity = document.getElementById("nav-equity").innerText.replace('$', '').replace(/,/g, '');
    const equity = parseFloat(navEquity);
    
    if (equity > 0) {
        const dailyLossPctCalc = Math.max(0, -metrics.daily_pnl / equity * 100);
        const dBar = document.getElementById("risk-daily-bar");
        const dText = document.getElementById("risk-daily-text");
        if (dBar) {
            const w = Math.min(100, Math.max(0, (dailyLossPctCalc / dailyLossLimitPct) * 100));
            dBar.style.width = `${w}%`;
            dText.innerText = `${dailyLossPctCalc.toFixed(1)}% / ${dailyLossLimitPct}%`;
            dBar.className = w > 80 ? "bg-red-500 h-1.5 transition-all" : (w > 50 ? "bg-orange-500 h-1.5 transition-all" : "bg-emerald-500 h-1.5 transition-all");
        }
    }
}


