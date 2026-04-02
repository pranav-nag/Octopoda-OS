/**
 * Octopoda Agent Runtime Dashboard — main.js
 * Handles SSE streaming, tab navigation, data fetching, real-time UI updates,
 * toast notifications, and demo controls.
 */

document.addEventListener("DOMContentLoaded", function () {
    "use strict";

    // ---------------------------------------------------------------------------
    // Global state
    // ---------------------------------------------------------------------------
    window.synrixState = {
        agents: [],
        systemMetrics: {},
        anomalies: [],
        recoveryHistory: [],
        sharedSpaces: [],
        activeTab: "overview",
        sseConnected: false,
        memoryOps: [],
        eventLog: [],
        agentSortField: "agent_id",
        agentSortAsc: true,
        expandedAgents: new Set(),
    };

    // ---------------------------------------------------------------------------
    // Constants
    // ---------------------------------------------------------------------------
    var MAX_STREAM_ENTRIES = 50;
    var TAB_IDS = [
        "overview",
        "agents",
        "memory-explorer",
        "audit",
        "performance",
        "recovery",
        "shared-memory",
        "agent-map",
    ];

    var TAB_TITLES = {
        "overview": "Dashboard",
        "agents": "Agents",
        "memory-explorer": "Memory Explorer",
        "audit": "Audit Trail",
        "performance": "Performance",
        "recovery": "Recovery Console",
        "shared-memory": "Shared Spaces",
        "agent-map": "Agent Map",
    };
    var RECONNECT_DELAY_MS = 3000;

    // ---------------------------------------------------------------------------
    // Utility functions
    // ---------------------------------------------------------------------------

    /**
     * Format a microsecond latency value into a human-readable string.
     * @param {number} us - Microseconds.
     * @returns {string}
     */
    function formatLatency(us) {
        if (us == null || isNaN(us)) return "--";
        if (us < 1000) return us.toFixed(0) + " us";
        if (us < 1000000) return (us / 1000).toFixed(1) + " ms";
        return (us / 1000000).toFixed(2) + " s";
    }

    /**
     * Format seconds into "Xh Xm Xs".
     * @param {number} seconds
     * @returns {string}
     */
    function formatUptime(seconds) {
        if (seconds == null || isNaN(seconds)) return "--";
        seconds = Math.floor(seconds);
        var h = Math.floor(seconds / 3600);
        var m = Math.floor((seconds % 3600) / 60);
        var s = seconds % 60;
        if (h > 0) return h + "h " + m + "m " + s + "s";
        if (m > 0) return m + "m " + s + "s";
        return s + "s";
    }

    /**
     * Return a relative time string from a UNIX timestamp.
     * @param {number} timestamp - Seconds since epoch.
     * @returns {string}
     */
    function timeAgo(timestamp) {
        if (!timestamp) return "never";
        var diff = Math.floor(Date.now() / 1000 - timestamp);
        if (diff < 0) return "just now";
        if (diff < 5) return "just now";
        if (diff < 60) return diff + "s ago";
        if (diff < 3600) return Math.floor(diff / 60) + "m ago";
        if (diff < 86400) return Math.floor(diff / 3600) + "h ago";
        return Math.floor(diff / 86400) + "d ago";
    }

    /**
     * Smoothly animate an element's text from its current numeric value to a target.
     * @param {HTMLElement} element
     * @param {number} target
     * @param {number} [duration=400] - Animation duration in ms.
     */
    function animateNumber(element, target, duration) {
        if (!element) return;
        duration = duration || 400;
        var start = parseInt(element.textContent, 10) || 0;
        if (start === target) return;
        var range = target - start;
        var startTime = performance.now();

        function step(now) {
            var elapsed = now - startTime;
            var progress = Math.min(elapsed / duration, 1);
            var eased = 1 - Math.pow(1 - progress, 3);
            element.textContent = Math.round(start + range * eased);
            if (progress < 1) {
                requestAnimationFrame(step);
            }
        }
        requestAnimationFrame(step);
    }

    /**
     * Safely query an element and set its textContent.
     */
    function setText(selector, value) {
        var el = document.querySelector(selector);
        if (el) el.textContent = value;
    }

    /**
     * Create a DOM element with optional class names and text content.
     */
    function elem(tag, className, text) {
        var el = document.createElement(tag);
        if (className) el.className = className;
        if (text !== undefined) el.textContent = text;
        return el;
    }

    // ---------------------------------------------------------------------------
    // Tab navigation
    // ---------------------------------------------------------------------------

    function switchTab(tabId) {
        if (TAB_IDS.indexOf(tabId) === -1) return;
        window.synrixState.activeTab = tabId;

        // Update sidebar nav items
        var links = document.querySelectorAll("[data-tab]");
        for (var i = 0; i < links.length; i++) {
            var link = links[i];
            if (link.getAttribute("data-tab") === tabId) {
                link.classList.add("nav-item--active");
            } else {
                link.classList.remove("nav-item--active");
            }
        }

        // Update page title in header
        var titleEl = document.getElementById("page-title");
        if (titleEl && TAB_TITLES[tabId]) {
            titleEl.textContent = TAB_TITLES[tabId];
        }

        // Show / hide tab content sections (id="tab-{tabId}")
        for (var j = 0; j < TAB_IDS.length; j++) {
            var panel = document.getElementById("tab-" + TAB_IDS[j]);
            if (panel) {
                panel.style.display = TAB_IDS[j] === tabId ? "" : "none";
            }
        }

        // Load tab-specific data on switch
        if (tabId === "performance") {
            loadPerformanceData();
        } else if (tabId === "audit") {
            if (window.audit && window.audit.init) window.audit.init();
        } else if (tabId === "shared-memory") {
            fetchSharedSpaces();
        } else if (tabId === "recovery") {
            fetchRecoveryHistory();
        } else if (tabId === "agent-map") {
            loadAgentMap();
        } else if (tabId === "memory-explorer") {
            if (window.memoryExplorer && window.memoryExplorer.init) window.memoryExplorer.init();
        }
    }

    function loadAgentMap() {
        if (window.agentMap) {
            window.agentMap.init();
            var agents = window.synrixState.agents;
            if (agents && agents.length > 0) {
                // Build shared spaces info for links
                fetchJSON("/api/shared", function (err, spaces) {
                    window.agentMap.update(agents, spaces || []);
                });
            }
        }
    }

    function loadPerformanceData() {
        if (window.charts) {
            var agents = window.synrixState.agents;
            if (agents && agents.length > 0) {
                window.charts.loadAgentLatency(agents[0].agent_id);
                window.charts.loadAgentOps(agents[0].agent_id);
            }
            window.charts.loadComparison();
        }
        renderAnomalyLog(window.synrixState.anomalies);
        fetchAnomalies();
    }

    function bindTabNavigation() {
        var links = document.querySelectorAll("[data-tab]");
        for (var i = 0; i < links.length; i++) {
            links[i].addEventListener("click", function (e) {
                e.preventDefault();
                switchTab(this.getAttribute("data-tab"));
            });
        }
    }

    // ---------------------------------------------------------------------------
    // Toast notifications
    // ---------------------------------------------------------------------------

    var _toastReady = false;
    var MAX_VISIBLE_TOASTS = 4;
    setTimeout(function () { _toastReady = true; }, 5000); // suppress initial data dump

    function showToast(message, type) {
        if (!_toastReady) return; // skip toasts during initial SSE data flood
        type = type || "info";
        var container = document.getElementById("toast-container");
        if (!container) {
            container = document.createElement("div");
            container.id = "toast-container";
            container.style.cssText =
                "position:fixed;top:1rem;right:1rem;z-index:9999;display:flex;flex-direction:column;gap:0.5rem;";
            document.body.appendChild(container);
        }

        // Cap visible toasts
        while (container.children.length >= MAX_VISIBLE_TOASTS) {
            container.removeChild(container.firstChild);
        }

        var toast = elem("div", "toast toast-" + type);
        toast.textContent = message;
        toast.style.cssText =
            "padding:0.75rem 1.25rem;border-radius:6px;color:#fff;font-size:0.85rem;" +
            "opacity:0;transition:opacity 0.3s;max-width:360px;word-break:break-word;" +
            "box-shadow:0 4px 12px rgba(0,0,0,0.25);";

        var bgMap = {
            info: "#3b82f6",
            success: "#10b981",
            warning: "#f59e0b",
            error: "#ef4444",
        };
        toast.style.backgroundColor = bgMap[type] || bgMap.info;

        container.appendChild(toast);
        requestAnimationFrame(function () {
            toast.style.opacity = "1";
        });

        setTimeout(function () {
            toast.style.opacity = "0";
            setTimeout(function () {
                if (toast.parentNode) toast.parentNode.removeChild(toast);
            }, 350);
        }, 4000);
    }

    // ---------------------------------------------------------------------------
    // Overview panel — metric cards & agent grid
    // ---------------------------------------------------------------------------

    function updateMetricCards(data) {
        var cards = [
            { sel: "#metric-active-agents", val: data.active_agents },
            { sel: "#metric-total-ops", val: data.total_operations },
            { sel: "#metric-crashes", val: data.total_crashes },
            { sel: "#metric-recovery-time", val: formatLatency(data.mean_recovery_time_us) },
        ];

        for (var i = 0; i < cards.length; i++) {
            var el = document.querySelector(cards[i].sel);
            if (!el) continue;
            if (typeof cards[i].val === "number" && cards[i].sel !== "#metric-uptime") {
                animateNumber(el, cards[i].val);
            } else {
                el.textContent = cards[i].val != null ? cards[i].val : "--";
            }
        }
    }

    function updateAgentGrid(agents) {
        var grid = document.getElementById("agent-grid");
        if (!grid) return;
        grid.innerHTML = "";

        if (!agents || agents.length === 0) {
            grid.innerHTML = '<div class="empty-state">No agents registered</div>';
            return;
        }

        for (var i = 0; i < agents.length; i++) {
            var a = agents[i];
            var card = elem("div", "agent-card");
            card.setAttribute("data-status", a.status || "unknown");

            var header = elem("div", "agent-card-header");
            var dot = elem("span", "status-dot status-" + (a.status || "unknown"));
            var name = elem("span", "agent-name", a.agent_id || "unknown");
            header.appendChild(dot);
            header.appendChild(name);
            card.appendChild(header);

            var body = elem("div", "agent-card-body");
            body.innerHTML =
                '<div class="agent-stat"><span class="label">Ops</span><span class="value">' +
                (a.total_operations || 0) +
                "</span></div>" +
                '<div class="agent-stat"><span class="label">Score</span><span class="value">' +
                (a.performance_score != null ? a.performance_score.toFixed(1) : "--") +
                "</span></div>" +
                '<div class="agent-stat"><span class="label">Uptime</span><span class="value">' +
                formatUptime(a.uptime_seconds) +
                "</span></div>";
            card.appendChild(body);

            var actions = elem("div", "agent-card-actions");
            var crashBtn = elem("button", "btn btn-sm btn-danger", "Crash");
            crashBtn.setAttribute("data-agent", a.agent_id);
            crashBtn.addEventListener("click", function () {
                crashAgent(this.getAttribute("data-agent"));
            });
            var rebootBtn = elem("button", "btn btn-sm btn-success", "Reboot");
            rebootBtn.setAttribute("data-agent", a.agent_id);
            rebootBtn.addEventListener("click", function () {
                rebootAgent(this.getAttribute("data-agent"));
            });
            actions.appendChild(crashBtn);
            actions.appendChild(rebootBtn);
            card.appendChild(actions);

            grid.appendChild(card);
        }
    }

    // ---------------------------------------------------------------------------
    // Agent Status List (overview sidebar)
    // ---------------------------------------------------------------------------

    function updateAgentStatusList(agents) {
        var list = document.getElementById("agent-status-list");
        if (!list) return;
        list.innerHTML = "";

        if (!agents || agents.length === 0) {
            list.innerHTML = '<div class="empty-state">No agents registered</div>';
            return;
        }

        for (var i = 0; i < agents.length; i++) {
            var a = agents[i];
            var item = elem("div", "agent-status-item");

            var statusColor = "var(--text-muted)";
            if (a.status === "active" || a.status === "running") statusColor = "var(--color-success)";
            else if (a.status === "idle") statusColor = "var(--color-warning)";
            else if (a.status === "error" || a.status === "crashed") statusColor = "var(--color-danger)";
            else if (a.status === "recovering") statusColor = "var(--color-recovery)";

            var score = a.performance_score != null ? a.performance_score.toFixed(0) : "--";
            var scoreClass = "agent-status-item__score--warn";
            if (a.performance_score >= 90) scoreClass = "agent-status-item__score--good";
            else if (a.performance_score < 70) scoreClass = "agent-status-item__score--bad";

            item.innerHTML =
                '<span class="agent-status-item__dot" style="background:' + statusColor + ';"></span>' +
                '<span class="agent-status-item__name">' + escapeHtml(a.agent_id || "unknown") + '</span>' +
                '<span class="agent-status-item__score ' + scoreClass + '">' + score + '</span>' +
                '<span class="agent-status-item__time">' + formatUptime(a.uptime_seconds) + '</span>';

            list.appendChild(item);
        }
    }

    // ---------------------------------------------------------------------------
    // Agents panel — sortable table with expand/collapse
    // ---------------------------------------------------------------------------

    function updateAgentsTable(agents) {
        var tbody = document.querySelector("#agents-table tbody");
        if (!tbody) return;
        tbody.innerHTML = "";

        if (!agents || agents.length === 0) {
            var tr = elem("tr");
            var td = elem("td", "empty-state", "No agents registered");
            td.setAttribute("colspan", "8");
            tr.appendChild(td);
            tbody.appendChild(tr);
            return;
        }

        var sorted = agents.slice().sort(function (a, b) {
            var field = window.synrixState.agentSortField;
            var valA = a[field] != null ? a[field] : "";
            var valB = b[field] != null ? b[field] : "";
            if (typeof valA === "string") valA = valA.toLowerCase();
            if (typeof valB === "string") valB = valB.toLowerCase();
            var cmp = valA < valB ? -1 : valA > valB ? 1 : 0;
            return window.synrixState.agentSortAsc ? cmp : -cmp;
        });

        for (var i = 0; i < sorted.length; i++) {
            var a = sorted[i];
            var row = document.createElement("tr");
            row.className = "agent-row";
            row.setAttribute("data-agent", a.agent_id);
            row.innerHTML =
                "<td>" + escapeHtml(a.agent_id) + "</td>" +
                '<td><span class="status-badge status-' + (a.status || "unknown") + '">' + (a.status || "unknown") + "</span></td>" +
                "<td>" + (a.total_operations || 0) + "</td>" +
                "<td>" + formatLatency(a.avg_write_latency_us) + "</td>" +
                "<td>" + formatLatency(a.avg_read_latency_us) + "</td>" +
                "<td>" + (a.performance_score != null ? a.performance_score.toFixed(1) : "--") + "</td>" +
                "<td>" + (a.crash_count || 0) + "</td>" +
                "<td>" + formatUptime(a.uptime_seconds) + "</td>";

            row.addEventListener("click", (function (agentId) {
                return function () {
                    toggleAgentDetail(agentId);
                };
            })(a.agent_id));

            tbody.appendChild(row);

            // Expanded detail row
            if (window.synrixState.expandedAgents.has(a.agent_id)) {
                var detailRow = document.createElement("tr");
                detailRow.className = "agent-detail-row";
                var detailTd = document.createElement("td");
                detailTd.setAttribute("colspan", "8");
                detailTd.innerHTML =
                    '<div class="agent-detail">' +
                    '<div class="detail-grid">' +
                    '<div><strong>Memory Nodes:</strong> ' + (a.memory_node_count || 0) + "</div>" +
                    '<div><strong>Error Rate:</strong> ' + ((a.error_rate || 0) * 100).toFixed(1) + "%</div>" +
                    '<div><strong>Crash Count:</strong> ' + (a.crash_count || 0) + "</div>" +
                    '<div class="detail-actions">' +
                    '<button class="btn btn-sm btn-danger" onclick="crashAgent(\'' + escapeHtml(a.agent_id) + "')\">" + "Simulate Crash</button>" +
                    '<button class="btn btn-sm btn-success" onclick="rebootAgent(\'' + escapeHtml(a.agent_id) + "')\">" + "Trigger Recovery</button>" +
                    "</div></div></div>";
                detailRow.appendChild(detailTd);
                tbody.appendChild(detailRow);
            }
        }
    }

    function toggleAgentDetail(agentId) {
        var expanded = window.synrixState.expandedAgents;
        if (expanded.has(agentId)) {
            expanded.delete(agentId);
        } else {
            expanded.add(agentId);
        }
        updateAgentsTable(window.synrixState.agents);
    }

    function bindTableSorting() {
        var headers = document.querySelectorAll("#agents-table th[data-sort]");
        for (var i = 0; i < headers.length; i++) {
            headers[i].addEventListener("click", function () {
                var field = this.getAttribute("data-sort");
                if (window.synrixState.agentSortField === field) {
                    window.synrixState.agentSortAsc = !window.synrixState.agentSortAsc;
                } else {
                    window.synrixState.agentSortField = field;
                    window.synrixState.agentSortAsc = true;
                }
                updateAgentsTable(window.synrixState.agents);
            });
        }
    }

    function escapeHtml(str) {
        if (!str) return "";
        return String(str)
            .replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;")
            .replace(/"/g, "&quot;");
    }

    // ---------------------------------------------------------------------------
    // Memory stream (bottom-left panel)
    // ---------------------------------------------------------------------------

    function appendMemoryOp(op) {
        var container = document.getElementById("memory-stream");
        if (!container) return;

        window.synrixState.memoryOps.push(op);
        if (window.synrixState.memoryOps.length > MAX_STREAM_ENTRIES) {
            window.synrixState.memoryOps.shift();
        }

        var entry = elem("div", "stream-entry memory-op");
        entry.innerHTML =
            '<span class="op-key" title="' + escapeHtml(op.key) + '">' + escapeHtml(truncate(op.key, 40)) + "</span>" +
            '<span class="op-latency">' + formatLatency(op.latency_us) + "</span>" +
            '<span class="op-time">' + timeAgo(op.timestamp) + "</span>";
        container.appendChild(entry);

        // Trim DOM to max entries
        while (container.children.length > MAX_STREAM_ENTRIES) {
            container.removeChild(container.firstChild);
        }
        container.scrollTop = container.scrollHeight;
    }

    function truncate(str, len) {
        if (!str) return "";
        return str.length > len ? str.substring(0, len) + "..." : str;
    }

    // ---------------------------------------------------------------------------
    // Events log (bottom-right panel)
    // ---------------------------------------------------------------------------

    function appendEvent(event) {
        var container = document.getElementById("events-log");
        if (!container) return;

        window.synrixState.eventLog.push(event);
        if (window.synrixState.eventLog.length > MAX_STREAM_ENTRIES) {
            window.synrixState.eventLog.shift();
        }

        var typeClass = "event-" + (event.type || "info");
        var entry = elem("div", "stream-entry " + typeClass);
        entry.innerHTML =
            '<span class="event-type">' + escapeHtml(event.type || "event") + "</span>" +
            '<span class="event-message">' + escapeHtml(truncate(event.message || JSON.stringify(event.data || {}), 80)) + "</span>" +
            '<span class="event-time">' + timeAgo(event.timestamp) + "</span>";
        container.appendChild(entry);

        while (container.children.length > MAX_STREAM_ENTRIES) {
            container.removeChild(container.firstChild);
        }
        container.scrollTop = container.scrollHeight;
    }

    // ---------------------------------------------------------------------------
    // Quick metrics — top bar
    // ---------------------------------------------------------------------------

    function updateTopBarMetrics(data) {
        setText("#topbar-agents", (data.active_agents || 0) + " / " + (data.total_agents || 0));
        setText("#topbar-ops", String(data.total_operations || 0));
        setText("#topbar-crashes", String(data.total_crashes || 0));
        setText("#topbar-recoveries", String(data.total_recoveries || 0));
    }

    function flashLiveIndicator() {
        var indicator = document.getElementById("live-indicator");
        if (!indicator) return;
        indicator.classList.add("pulse");
        setTimeout(function () {
            indicator.classList.remove("pulse");
        }, 800);
    }

    // ---------------------------------------------------------------------------
    // SSE connection
    // ---------------------------------------------------------------------------

    function initSSE() {
        if (window.synrixState.sseSource) {
            window.synrixState.sseSource.close();
        }

        var source = new EventSource("/stream/events");
        window.synrixState.sseSource = source;

        source.addEventListener("agent_update", function (e) {
            try {
                var data = JSON.parse(e.data);
                var agents = data.agents || [];
                window.synrixState.agents = agents;
                updateAgentGrid(agents);
                updateAgentsTable(agents);
                updateAgentStatusList(agents);
            } catch (err) {
                console.error("[SSE] agent_update parse error:", err);
            }
        });

        source.addEventListener("metrics_update", function (e) {
            try {
                var data = JSON.parse(e.data);
                window.synrixState.systemMetrics = data;
                updateTopBarMetrics(data);
                updateMetricCards(data);
            } catch (err) {
                console.error("[SSE] metrics_update parse error:", err);
            }
        });

        source.addEventListener("memory_update", function (e) {
            try {
                var data = JSON.parse(e.data);
                var ops = data.operations || [];
                for (var i = 0; i < ops.length; i++) {
                    appendMemoryOp(ops[i]);
                }
            } catch (err) {
                console.error("[SSE] memory_update parse error:", err);
            }
        });

        var _seenAnomalyKeys = {};
        source.addEventListener("anomaly_alert", function (e) {
            try {
                var data = JSON.parse(e.data);
                var anomalies = data.anomalies || [];
                window.synrixState.anomalies = anomalies;
                renderAnomalyLog(anomalies);
                for (var i = 0; i < anomalies.length; i++) {
                    var a = anomalies[i];
                    var aKey = (a.agent_id || "") + ":" + (a.type || "") + ":" + Math.floor((a.timestamp || 0) / 10);
                    if (!_seenAnomalyKeys[aKey]) {
                        _seenAnomalyKeys[aKey] = true;
                        showToast("Anomaly: " + (a.description || a.type || "Unknown"), "warning");
                        appendEvent({
                            type: "anomaly",
                            message: a.description || a.type || "Anomaly detected",
                            timestamp: data.timestamp,
                            data: a,
                        });
                    }
                }
            } catch (err) {
                console.error("[SSE] anomaly_alert parse error:", err);
            }
        });

        var _seenRecoveryKeys = {};
        source.addEventListener("recovery_event", function (e) {
            try {
                var data = JSON.parse(e.data);
                var recoveries = data.recoveries || [];
                var newRecoveries = [];
                for (var i = 0; i < recoveries.length; i++) {
                    var r = recoveries[i];
                    var rKey = (r.agent_id || "") + ":" + Math.floor((r.timestamp || 0));
                    if (!_seenRecoveryKeys[rKey]) {
                        _seenRecoveryKeys[rKey] = true;
                        showToast("Recovery: " + (r.agent_id || "agent") + " recovered", "success");
                        appendEvent({
                            type: "recovery",
                            message: (r.agent_id || "Agent") + " recovered successfully",
                            timestamp: data.timestamp,
                            data: r,
                        });
                        newRecoveries.push(r);
                    }
                }
                if (newRecoveries.length > 0) updateRecoveryConsole(newRecoveries);
            } catch (err) {
                console.error("[SSE] recovery_event parse error:", err);
            }
        });

        source.addEventListener("system_heartbeat", function () {
            window.synrixState.sseConnected = true;
            flashLiveIndicator();
        });

        source.addEventListener("error", function (e) {
            console.warn("[SSE] connection error:", e);
        });

        source.onerror = function () {
            window.synrixState.sseConnected = false;
            var dot = document.getElementById("live-indicator-dot");
            var text = document.getElementById("live-indicator-text");
            if (dot) dot.classList.add("sidebar__status-dot--disconnected");
            if (text) text.textContent = "Disconnected";
            setTimeout(function () {
                console.log("[SSE] Attempting reconnect...");
                initSSE();
            }, RECONNECT_DELAY_MS);
        };

        source.onopen = function () {
            window.synrixState.sseConnected = true;
            var dot = document.getElementById("live-indicator-dot");
            var text = document.getElementById("live-indicator-text");
            if (dot) dot.classList.remove("sidebar__status-dot--disconnected");
            if (text) text.textContent = "System Online";
            console.log("[SSE] Connected to /stream/events");
        };
    }

    // ---------------------------------------------------------------------------
    // Recovery console helper
    // ---------------------------------------------------------------------------

    function updateRecoveryConsole(recoveries) {
        var container = document.getElementById("recovery-log");
        if (!container) return;

        for (var i = 0; i < recoveries.length; i++) {
            var r = recoveries[i];
            var entry = elem("div", "stream-entry recovery-entry");
            entry.innerHTML =
                '<span class="recovery-agent">' + escapeHtml(r.agent_id || "unknown") + "</span>" +
                '<span class="recovery-strategy">' + escapeHtml(r.strategy || "auto") + "</span>" +
                '<span class="recovery-time">' + timeAgo(r.timestamp) + "</span>";
            container.appendChild(entry);

            while (container.children.length > MAX_STREAM_ENTRIES) {
                container.removeChild(container.firstChild);
            }
        }
    }

    // ---------------------------------------------------------------------------
    // Data fetching — initial load
    // ---------------------------------------------------------------------------

    function fetchJSON(url, callback) {
        fetch(url)
            .then(function (res) {
                if (!res.ok) throw new Error("HTTP " + res.status);
                return res.json();
            })
            .then(function (data) {
                callback(null, data);
            })
            .catch(function (err) {
                console.error("[FETCH] " + url + " failed:", err);
                callback(err, null);
            });
    }

    function fetchSystemStatus() {
        fetchJSON("/api/system/status", function (err, data) {
            if (err || !data) return;
            window.synrixState.systemStatus = data;
            setText("#system-status-label", data.status || "unknown");
        });
    }

    function fetchAgents() {
        fetchJSON("/api/agents", function (err, data) {
            if (err || !data) return;
            window.synrixState.agents = data;
            updateAgentGrid(data);
            updateAgentsTable(data);
            updateAgentStatusList(data);
        });
    }

    function fetchSystemMetrics() {
        fetchJSON("/api/metrics/system", function (err, data) {
            if (err || !data) return;
            window.synrixState.systemMetrics = data;
            updateTopBarMetrics(data);
            updateMetricCards(data);
        });
    }

    function renderAnomalyLog(anomalies) {
        var log = document.getElementById("anomaly-log");
        if (!log) return;
        if (!anomalies || anomalies.length === 0) {
            log.innerHTML = '<li style="color:var(--text-secondary);font-size:0.9em;">No anomalies detected</li>';
            return;
        }
        var html = "";
        var severityColors = { critical: "#ef4444", warning: "#f59e0b", info: "#3b82f6" };
        for (var i = 0; i < Math.min(anomalies.length, 20); i++) {
            var a = anomalies[i];
            if (typeof a !== "object" || !a) continue;
            var severity = a.severity || "info";
            var color = severityColors[severity] || "#3b82f6";
            var ts = a.timestamp ? new Date(a.timestamp * 1000).toLocaleTimeString() : "";
            var agent = a.agent_id || "unknown";
            var detail = a.detail || a.description || a.type || "Anomaly";
            html += '<li style="padding:8px 0;border-bottom:1px solid var(--border);font-size:0.9em;">'
                + '<span style="display:inline-block;width:8px;height:8px;border-radius:50%;background:'
                + color + ';margin-right:8px;"></span>'
                + '<strong style="color:' + color + ';">[' + severity.toUpperCase() + ']</strong> '
                + '<span style="color:var(--text-secondary);">' + ts + '</span> '
                + '<span style="color:var(--accent);">' + agent + '</span> — '
                + detail
                + '</li>';
        }
        log.innerHTML = html;
    }

    function fetchAnomalies() {
        fetchJSON("/api/anomalies", function (err, data) {
            if (err || !Array.isArray(data)) return;
            window.synrixState.anomalies = data;
            renderAnomalyLog(data);
            for (var i = 0; i < data.length; i++) {
                appendEvent({
                    type: "anomaly",
                    message: data[i].description || data[i].type || "Anomaly",
                    timestamp: data[i].timestamp,
                    data: data[i],
                });
            }
        });
    }

    function fetchRecoveryHistory() {
        fetchJSON("/api/recovery/history", function (err, data) {
            if (err || !data) return;
            window.synrixState.recoveryHistory = data.history || [];
            var history = data.history || [];
            var stats = data.stats || {};
            for (var i = 0; i < history.length; i++) {
                appendEvent({
                    type: "recovery",
                    message: (history[i].agent_id || "Agent") + " — " + (history[i].strategy || "recovered"),
                    timestamp: history[i].timestamp,
                    data: history[i],
                });
            }
            updateRecoveryConsole(history);

            // Update recovery page stat cards
            setText("#recovery-total", history.length || stats.total_recoveries || 0);
            var avgTime = stats.mean_recovery_time_us || 0;
            if (avgTime > 0) {
                setText("#recovery-avg-time", formatLatency(avgTime));
            }
        });
    }

    function fetchSharedSpaces() {
        fetchJSON("/api/shared", function (err, data) {
            if (err || !Array.isArray(data)) return;
            window.synrixState.sharedSpaces = data;
            renderSharedSpaces(data);
        });
    }

    function renderSharedSpaces(spaces) {
        var container = document.getElementById("shared-spaces-list");
        if (!container) return;
        container.innerHTML = "";

        if (!spaces || spaces.length === 0) {
            container.innerHTML = '<div class="empty-state">No shared memory spaces</div>';
            return;
        }

        for (var i = 0; i < spaces.length; i++) {
            var space = spaces[i];
            var item = elem("div", "shared-space-item");
            item.innerHTML =
                '<span class="space-name">' + escapeHtml(space.name || space.space_id || space) + "</span>" +
                '<span class="space-meta">' + (space.key_count || 0) + " keys</span>";
            container.appendChild(item);
        }
    }

    function loadInitialData() {
        fetchSystemStatus();
        fetchAgents();
        fetchSystemMetrics();
        fetchAnomalies();
        fetchRecoveryHistory();
        fetchSharedSpaces();
    }

    // ---------------------------------------------------------------------------
    // Demo controls
    // ---------------------------------------------------------------------------

    function startDemo() {
        fetch("/api/demo/start", { method: "POST" })
            .then(function (res) { return res.json(); })
            .then(function (data) {
                if (data.started) {
                    showToast("Demo started: " + (data.message || ""), "success");
                } else {
                    showToast("Demo start failed", "error");
                }
            })
            .catch(function (err) {
                showToast("Demo start error: " + err.message, "error");
            });
    }

    function crashAgent(agentId) {
        if (!agentId) return;
        fetch("/api/demo/crash/" + encodeURIComponent(agentId), { method: "POST" })
            .then(function (res) { return res.json(); })
            .then(function (data) {
                showToast("Crashed agent: " + agentId, "warning");
                appendEvent({
                    type: "crash",
                    message: "Agent " + agentId + " crashed (simulated)",
                    timestamp: Date.now() / 1000,
                    data: data,
                });
            })
            .catch(function (err) {
                showToast("Crash failed: " + err.message, "error");
            });
    }

    function rebootAgent(agentId) {
        if (!agentId) return;
        fetch("/api/demo/reboot/" + encodeURIComponent(agentId), { method: "POST" })
            .then(function (res) { return res.json(); })
            .then(function (data) {
                showToast("Rebooting agent: " + agentId, "success");
                appendEvent({
                    type: "recovery",
                    message: "Agent " + agentId + " recovery triggered",
                    timestamp: Date.now() / 1000,
                    data: data,
                });
            })
            .catch(function (err) {
                showToast("Reboot failed: " + err.message, "error");
            });
    }

    function bindDemoControls() {
        var startBtn = document.getElementById("btn-start-demo");
        if (startBtn) {
            startBtn.addEventListener("click", function () {
                startDemo();
            });
        }
    }

    // ---------------------------------------------------------------------------
    // Modal close handlers
    // ---------------------------------------------------------------------------

    function bindModalClose() {
        var overlay = document.getElementById("modal-overlay");
        var closeBtn = document.getElementById("modal-close");
        var closeFooter = document.getElementById("modal-close-footer");

        function hideModal() {
            if (overlay) overlay.classList.add("hidden");
        }

        if (closeBtn) closeBtn.addEventListener("click", hideModal);
        if (closeFooter) closeFooter.addEventListener("click", hideModal);
        if (overlay) {
            overlay.addEventListener("click", function (e) {
                if (e.target === overlay) hideModal();
            });
        }
    }

    // ---------------------------------------------------------------------------
    // Expose functions globally for inline onclick handlers & external use
    // ---------------------------------------------------------------------------
    window.switchTab = switchTab;
    window.startDemo = startDemo;
    window.crashAgent = crashAgent;
    window.rebootAgent = rebootAgent;
    window.showToast = showToast;
    window.formatLatency = formatLatency;
    window.formatUptime = formatUptime;
    window.timeAgo = timeAgo;
    window.animateNumber = animateNumber;

    // ---------------------------------------------------------------------------
    // Initialization
    // ---------------------------------------------------------------------------

    bindTabNavigation();
    bindTableSorting();
    bindDemoControls();
    bindModalClose();
    switchTab("overview");
    loadInitialData();
    initSSE();

    console.log("[Octopoda] Dashboard initialized");
});
