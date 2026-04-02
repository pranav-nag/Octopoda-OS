/**
 * Octopoda Agent Runtime — Memory Explorer
 * File-system-style browser for all agent memory in Octopoda.
 */

(function() {
    'use strict';

    const NAMESPACES = ['agents', 'shared', 'tasks', 'metrics', 'audit', 'runtime', 'alerts'];
    let currentPrefix = '';
    let liveMode = false;
    let liveInterval = null;

    function initMemoryExplorer() {
        buildNamespaceTree();
        setupSearch();
        setupLiveToggle();
    }

    function buildNamespaceTree() {
        const tree = document.getElementById('memory-tree');
        if (!tree) return;

        tree.innerHTML = '';
        for (const ns of NAMESPACES) {
            const item = document.createElement('div');
            item.className = 'tree-item';
            item.innerHTML = `
                <span class="tree-icon">&#9662;</span>
                <span class="tree-label">${ns}/</span>
            `;
            item.addEventListener('click', () => browseNamespace(ns + ':'));
            tree.appendChild(item);
        }
    }

    function browseNamespace(prefix) {
        currentPrefix = prefix;
        const breadcrumb = document.getElementById('memory-breadcrumb');
        if (breadcrumb) {
            breadcrumb.textContent = prefix || '/';
        }

        fetch(`/api/memory/browse?prefix=${encodeURIComponent(prefix)}&limit=100`)
            .then(r => r.json())
            .then(data => {
                renderKeyTable(data.items || []);
                const latencyEl = document.getElementById('memory-query-latency');
                if (latencyEl) {
                    latencyEl.textContent = `${(data.latency_us || 0).toFixed(1)}μs`;
                }
            })
            .catch(err => console.error('Memory browse error:', err));
    }

    function renderKeyTable(items) {
        const table = document.getElementById('memory-key-table-body');
        if (!table) return;

        table.innerHTML = '';
        for (const item of items) {
            const row = document.createElement('tr');
            const valueStr = typeof item.value === 'object' ? JSON.stringify(item.value) : String(item.value);
            const preview = valueStr.length > 80 ? valueStr.substring(0, 80) + '...' : valueStr;
            const size = item.size_bytes || 0;

            row.innerHTML = `
                <td class="key-cell" title="${escapeHtml(item.key)}">${escapeHtml(item.key)}</td>
                <td class="value-preview">${escapeHtml(preview)}</td>
                <td class="mono">${item.node_id || '-'}</td>
                <td class="mono">${formatBytes(size)}</td>
            `;
            row.addEventListener('click', () => showKeyDetail(item));
            table.appendChild(row);
        }

        const countEl = document.getElementById('memory-key-count');
        if (countEl) countEl.textContent = items.length;
    }

    function showKeyDetail(item) {
        const viewer = document.getElementById('memory-json-viewer');
        if (!viewer) return;

        const formatted = JSON.stringify(item.value, null, 2);
        viewer.innerHTML = `
            <div class="json-header">
                <span class="json-key-name">${escapeHtml(item.key)}</span>
                <span class="json-node-id">Node: ${item.node_id || 'N/A'}</span>
            </div>
            <pre class="json-content">${escapeHtml(formatted)}</pre>
        `;
        viewer.style.display = 'block';
    }

    function setupSearch() {
        const searchInput = document.getElementById('memory-search');
        if (!searchInput) return;

        let debounceTimer;
        searchInput.addEventListener('input', () => {
            clearTimeout(debounceTimer);
            debounceTimer = setTimeout(() => {
                const query = searchInput.value.trim();
                if (query.length > 0) {
                    browseNamespace(query);
                } else if (currentPrefix) {
                    browseNamespace(currentPrefix);
                }
            }, 300);
        });
    }

    function setupLiveToggle() {
        const toggle = document.getElementById('live-mode-toggle');
        if (!toggle) return;

        toggle.addEventListener('change', () => {
            liveMode = toggle.checked;
            if (liveMode) {
                liveInterval = setInterval(() => {
                    if (currentPrefix) browseNamespace(currentPrefix);
                }, 2000);
            } else {
                clearInterval(liveInterval);
            }
        });
    }

    function formatBytes(bytes) {
        if (bytes === 0) return '0 B';
        if (bytes < 1024) return bytes + ' B';
        if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB';
        return (bytes / (1024 * 1024)).toFixed(1) + ' MB';
    }

    function escapeHtml(str) {
        const div = document.createElement('div');
        div.textContent = str;
        return div.innerHTML;
    }

    window.memoryExplorer = {
        init: initMemoryExplorer,
        browse: browseNamespace,
        refresh: () => { if (currentPrefix) browseNamespace(currentPrefix); }
    };
})();
