/**
 * Octopoda Agent Runtime — Audit & Replay
 * Timeline view, replay controls, and decision explanation.
 */

(function() {
    'use strict';

    let replayEvents = [];
    let replayIndex = 0;
    let replayTimer = null;
    let replaySpeed = 1;

    function initAudit() {
        loadTimeline();
        setupReplayControls();
    }

    function loadTimeline() {
        fetch('/api/audit/timeline?limit=50')
            .then(r => r.json())
            .then(events => renderTimeline(events))
            .catch(err => console.error('Audit timeline error:', err));
    }

    function renderTimeline(events) {
        const container = document.getElementById('audit-timeline');
        if (!container) return;

        container.innerHTML = '';
        for (const event of events) {
            const item = document.createElement('div');
            item.className = 'timeline-item';

            const type = event.event_type || 'unknown';
            const badges = {
                decision: { class: 'badge-indigo', label: 'DECISION' },
                handoff: { class: 'badge-blue', label: 'HANDOFF' },
                crash: { class: 'badge-red', label: 'CRASH' },
                recovery: { class: 'badge-green', label: 'RECOVERY' },
                anomaly: { class: 'badge-amber', label: 'ANOMALY' },
                snapshot: { class: 'badge-slate', label: 'SNAPSHOT' },
            };
            const badge = badges[type] || { class: 'badge-slate', label: type.toUpperCase() };

            const agentId = event.agent_id || event.from_agent || 'system';
            const timestamp = event.timestamp ? new Date(event.timestamp * 1000).toLocaleTimeString() : '';
            const summary = getSummary(event);

            item.innerHTML = `
                <div class="timeline-header">
                    <span class="timeline-time mono">${timestamp}</span>
                    <span class="timeline-agent">${escapeHtml(agentId)}</span>
                    <span class="badge ${badge.class}">${badge.label}</span>
                </div>
                <div class="timeline-summary">${escapeHtml(summary)}</div>
                <button class="btn-expand" data-expanded="false">Expand</button>
                <div class="timeline-detail" style="display:none;"></div>
                ${type === 'decision' ? `<button class="btn-explain" data-agent="${agentId}" data-ts="${event.timestamp}">Explain Decision</button>` : ''}
            `;

            const expandBtn = item.querySelector('.btn-expand');
            const detailDiv = item.querySelector('.timeline-detail');
            expandBtn.addEventListener('click', () => {
                const expanded = expandBtn.dataset.expanded === 'true';
                if (expanded) {
                    detailDiv.style.display = 'none';
                    expandBtn.textContent = 'Expand';
                    expandBtn.dataset.expanded = 'false';
                } else {
                    detailDiv.innerHTML = `<pre class="json-content">${escapeHtml(JSON.stringify(event, null, 2))}</pre>`;
                    detailDiv.style.display = 'block';
                    expandBtn.textContent = 'Collapse';
                    expandBtn.dataset.expanded = 'true';
                }
            });

            const explainBtn = item.querySelector('.btn-explain');
            if (explainBtn) {
                explainBtn.addEventListener('click', () => {
                    const agent = explainBtn.dataset.agent;
                    const ts = explainBtn.dataset.ts;
                    explainDecision(agent, ts);
                });
            }

            container.appendChild(item);
        }
    }

    function getSummary(event) {
        switch (event.event_type) {
            case 'decision':
                return event.decision || 'Agent made a decision';
            case 'handoff':
                return `${event.from_agent} -> ${event.to_agent}: task ${event.task_id}`;
            case 'crash':
                return `Agent ${event.agent_id} crashed: ${event.reason || 'unknown'}`;
            case 'recovery':
                const rt = event.recovery_result;
                if (rt) return `Recovered in ${(rt.recovery_time_us || 0).toFixed(1)}μs`;
                return 'Agent recovered';
            case 'anomaly':
                return `${event.anomaly_type}: ${event.details?.detail || ''}`;
            default:
                return JSON.stringify(event).substring(0, 100);
        }
    }

    function explainDecision(agentId, timestamp) {
        fetch(`/api/audit/explain/${agentId}/${timestamp}`)
            .then(r => r.json())
            .then(data => showExplanationModal(data))
            .catch(err => console.error('Explain error:', err));
    }

    function showExplanationModal(data) {
        const overlay = document.getElementById('modal-overlay');
        if (!overlay) return;

        const content = overlay.querySelector('.modal-body');
        if (!content) return;

        const decision = data.what_it_decided || {};
        const knew = data.what_agent_knew || {};
        const queried = data.what_it_queried || [];
        const wrote = data.what_it_wrote || [];

        content.innerHTML = `
            <div class="explain-section">
                <h4>What the Agent Knew</h4>
                <pre class="json-content">${escapeHtml(JSON.stringify(knew, null, 2)).substring(0, 2000)}</pre>
            </div>
            <div class="explain-section">
                <h4>What It Queried (30s before)</h4>
                <p class="mono">${queried.length} read operations</p>
                ${queried.length > 0 ? `<pre class="json-content">${escapeHtml(JSON.stringify(queried.slice(0, 5), null, 2))}</pre>` : ''}
            </div>
            <div class="explain-section">
                <h4>What It Decided</h4>
                <div class="decision-box">
                    <strong>${escapeHtml(decision.decision || '')}</strong>
                    <p>${escapeHtml(decision.reasoning || '')}</p>
                </div>
            </div>
            <div class="explain-section">
                <h4>What It Wrote After (30s after)</h4>
                <p class="mono">${wrote.length} write operations</p>
                ${wrote.length > 0 ? `<pre class="json-content">${escapeHtml(JSON.stringify(wrote.slice(0, 5), null, 2))}</pre>` : ''}
            </div>
        `;

        overlay.classList.remove('hidden');
    }

    function setupReplayControls() {
        const playBtn = document.getElementById('replay-play');
        const speedBtns = document.querySelectorAll('.replay-speed-btn');
        const agentSelect = document.getElementById('replay-agent-select');

        if (playBtn) {
            playBtn.addEventListener('click', () => {
                if (replayTimer) {
                    stopReplay();
                    playBtn.textContent = 'Play';
                } else {
                    const agentId = agentSelect ? agentSelect.value : '';
                    if (agentId) startReplay(agentId);
                    playBtn.textContent = 'Stop';
                }
            });
        }

        speedBtns.forEach(btn => {
            btn.addEventListener('click', () => {
                speedBtns.forEach(b => b.classList.remove('active'));
                btn.classList.add('active');
                replaySpeed = parseInt(btn.dataset.speed) || 1;
            });
        });
    }

    function startReplay(agentId) {
        fetch(`/api/agents/${agentId}/replay`)
            .then(r => r.json())
            .then(events => {
                replayEvents = events;
                replayIndex = 0;
                playNextEvent();
            })
            .catch(err => console.error('Replay error:', err));
    }

    function playNextEvent() {
        if (replayIndex >= replayEvents.length) {
            stopReplay();
            return;
        }

        const event = replayEvents[replayIndex];
        highlightReplayEvent(event);
        replayIndex++;

        replayTimer = setTimeout(playNextEvent, 1000 / replaySpeed);
    }

    function highlightReplayEvent(event) {
        const items = document.querySelectorAll('.timeline-item');
        items.forEach(item => item.classList.remove('replaying'));

        if (replayIndex < items.length) {
            items[replayIndex].classList.add('replaying');
            items[replayIndex].scrollIntoView({ behavior: 'smooth', block: 'nearest' });
        }
    }

    function stopReplay() {
        if (replayTimer) {
            clearTimeout(replayTimer);
            replayTimer = null;
        }
    }

    function loadAgentAudit(agentId) {
        fetch(`/api/agents/${agentId}/audit`)
            .then(r => r.json())
            .then(events => renderTimeline(events))
            .catch(err => console.error('Agent audit error:', err));
    }

    function escapeHtml(str) {
        const div = document.createElement('div');
        div.textContent = str;
        return div.innerHTML;
    }

    window.audit = {
        init: initAudit,
        loadTimeline: loadTimeline,
        loadAgent: loadAgentAudit,
        explain: explainDecision,
        startReplay: startReplay,
        stopReplay: stopReplay
    };
})();
