/**
 * Octopoda Agent Runtime — Charts
 * Chart.js powered performance visualizations.
 */

(function() {
    'use strict';

    let latencyChart = null;
    let opsChart = null;
    let comparisonChart = null;

    // Light theme colors
    const ACCENT = '#D4612C';
    const ACCENT_LIGHT = 'rgba(212, 97, 44, 0.15)';
    const ACCENT_BAR = 'rgba(212, 97, 44, 0.6)';
    const GRID_COLOR = '#E8E5DE';
    const TEXT_PRIMARY = '#1A1A1A';
    const TEXT_SECONDARY = '#5C5C5C';
    const TEXT_MUTED = '#9CA3AF';

    function initCharts() {
        // Charts are created on demand when their panels are shown
    }

    function createLatencyChart(canvasId, data) {
        const canvas = document.getElementById(canvasId);
        if (!canvas) return;

        if (latencyChart) latencyChart.destroy();

        const labels = data.map(d => {
            const date = new Date(d.timestamp * 1000);
            return date.toLocaleTimeString();
        });
        const values = data.map(d => d.latency_us);

        latencyChart = new Chart(canvas, {
            type: 'line',
            data: {
                labels: labels,
                datasets: [{
                    label: 'Latency (us)',
                    data: values,
                    borderColor: ACCENT,
                    backgroundColor: ACCENT_LIGHT,
                    fill: true,
                    tension: 0.3,
                    pointRadius: 2,
                    pointHoverRadius: 5,
                    borderWidth: 2,
                }]
            },
            options: chartOptions('Latency Over Time', 'us')
        });
    }

    function createOpsChart(canvasId, data) {
        const canvas = document.getElementById(canvasId);
        if (!canvas) return;

        if (opsChart) opsChart.destroy();

        // Group by minute
        const minuteBuckets = {};
        for (const d of data) {
            const minute = Math.floor(d.timestamp / 60) * 60;
            minuteBuckets[minute] = (minuteBuckets[minute] || 0) + 1;
        }

        const sorted = Object.entries(minuteBuckets).sort((a, b) => a[0] - b[0]);
        const labels = sorted.map(([ts]) => {
            const date = new Date(Number(ts) * 1000);
            return date.toLocaleTimeString();
        });
        const values = sorted.map(([, count]) => count);

        opsChart = new Chart(canvas, {
            type: 'bar',
            data: {
                labels: labels,
                datasets: [{
                    label: 'Ops / Minute',
                    data: values,
                    backgroundColor: ACCENT_BAR,
                    borderColor: ACCENT,
                    borderWidth: 1,
                    borderRadius: 4,
                }]
            },
            options: chartOptions('Operations Per Minute', 'ops')
        });
    }

    function createComparisonChart(canvasId, agents) {
        const canvas = document.getElementById(canvasId);
        if (!canvas) return;

        if (comparisonChart) comparisonChart.destroy();

        const labels = agents.map(a => a.agent_id);
        const scores = agents.map(a => a.performance_score || 0);
        const colors = scores.map(s => {
            if (s >= 90) return '#16A34A';
            if (s >= 70) return '#D4612C';
            if (s >= 50) return '#CA8A04';
            return '#DC2626';
        });

        comparisonChart = new Chart(canvas, {
            type: 'bar',
            data: {
                labels: labels,
                datasets: [{
                    label: 'Performance Score',
                    data: scores,
                    backgroundColor: colors.map(c => c + '66'),
                    borderColor: colors,
                    borderWidth: 2,
                    borderRadius: 6,
                }]
            },
            options: {
                ...chartOptions('Agent Performance Comparison', 'score'),
                indexAxis: 'y',
                plugins: {
                    ...chartOptions().plugins,
                    legend: { display: false }
                },
                scales: {
                    x: {
                        max: 100,
                        grid: { color: GRID_COLOR },
                        ticks: { color: TEXT_SECONDARY, font: { family: 'Inter', size: 11 } }
                    },
                    y: {
                        grid: { display: false },
                        ticks: { color: TEXT_PRIMARY, font: { family: 'Inter', size: 11 } }
                    }
                }
            }
        });
    }

    function chartOptions(title, unit) {
        return {
            responsive: true,
            maintainAspectRatio: false,
            animation: { duration: 300 },
            plugins: {
                title: {
                    display: !!title,
                    text: title || '',
                    color: TEXT_PRIMARY,
                    font: { family: 'Inter', size: 13, weight: '600' }
                },
                legend: {
                    labels: {
                        color: TEXT_SECONDARY,
                        font: { family: 'Inter' }
                    }
                },
                tooltip: {
                    backgroundColor: '#FFFFFF',
                    titleColor: TEXT_PRIMARY,
                    bodyColor: TEXT_SECONDARY,
                    borderColor: GRID_COLOR,
                    borderWidth: 1,
                    titleFont: { family: 'Inter' },
                    bodyFont: { family: 'Inter' },
                    callbacks: {
                        label: function(context) {
                            return `${context.parsed.y || context.parsed.x} ${unit || ''}`;
                        }
                    }
                }
            },
            scales: {
                x: {
                    grid: { color: GRID_COLOR },
                    ticks: { color: TEXT_SECONDARY, font: { family: 'Inter', size: 10 }, maxRotation: 45 }
                },
                y: {
                    grid: { color: GRID_COLOR },
                    ticks: { color: TEXT_SECONDARY, font: { family: 'Inter', size: 11 } }
                }
            }
        };
    }

    function loadAgentLatencyChart(agentId) {
        fetch(`/api/agents/${agentId}/metrics?type=write&minutes=60`)
            .then(r => r.json())
            .then(data => {
                if (Array.isArray(data) && data.length > 0) {
                    createLatencyChart('chart-latency', data);
                }
            })
            .catch(err => console.error('Latency chart error:', err));
    }

    function loadAgentOpsChart(agentId) {
        fetch(`/api/agents/${agentId}/metrics?type=write&minutes=60`)
            .then(r => r.json())
            .then(data => {
                if (Array.isArray(data) && data.length > 0) {
                    createOpsChart('chart-ops-min', data);
                }
            })
            .catch(err => console.error('Ops chart error:', err));
    }

    function loadComparisonChart() {
        fetch('/api/agents')
            .then(r => r.json())
            .then(agents => {
                if (Array.isArray(agents) && agents.length > 0) {
                    createComparisonChart('chart-agent-comparison', agents);
                }
            })
            .catch(err => console.error('Comparison chart error:', err));
    }

    window.charts = {
        init: initCharts,
        latency: createLatencyChart,
        ops: createOpsChart,
        comparison: createComparisonChart,
        loadAgentLatency: loadAgentLatencyChart,
        loadAgentOps: loadAgentOpsChart,
        loadComparison: loadComparisonChart
    };
})();
