/**
 * Octopoda Agent Runtime — Agent Map (D3.js Force Graph)
 * Live force-directed graph of all registered agents.
 */

(function() {
    'use strict';

    const STATE_COLORS = {
        running: '#10b981',
        idle: '#f59e0b',
        crashed: '#ef4444',
        recovering: '#3b82f6',
        deregistered: '#475569'
    };

    const TYPE_LETTERS = {
        researcher: 'R',
        analyst: 'A',
        writer: 'W',
        coder: 'C',
        planner: 'P',
        monitor: 'M',
        generic: 'G',
        custom: 'X'
    };

    let svg, simulation, nodesGroup, linksGroup, width, height;
    let currentNodes = [];
    let currentLinks = [];

    function initAgentMap() {
        const container = document.getElementById('agent-map-container');
        if (!container) return;

        const rect = container.getBoundingClientRect();
        width = rect.width || 600;
        height = rect.height || 400;

        svg = d3.select('#agent-map-svg');
        if (svg.empty()) {
            svg = d3.select('#agent-map-container')
                .append('svg')
                .attr('id', 'agent-map-svg')
                .attr('width', '100%')
                .attr('height', '100%');
        }
        svg.attr('viewBox', `0 0 ${width} ${height}`);

        // Clear any previous content
        svg.selectAll('*').remove();

        // Defs for glow filter
        const defs = svg.append('defs');

        const glowFilter = defs.append('filter').attr('id', 'glow');
        glowFilter.append('feGaussianBlur').attr('stdDeviation', '3').attr('result', 'coloredBlur');
        const feMerge = glowFilter.append('feMerge');
        feMerge.append('feMergeNode').attr('in', 'coloredBlur');
        feMerge.append('feMergeNode').attr('in', 'SourceGraphic');

        const pulseFilter = defs.append('filter').attr('id', 'pulse-glow');
        pulseFilter.append('feGaussianBlur').attr('stdDeviation', '6').attr('result', 'coloredBlur');
        const feMerge2 = pulseFilter.append('feMerge');
        feMerge2.append('feMergeNode').attr('in', 'coloredBlur');
        feMerge2.append('feMergeNode').attr('in', 'SourceGraphic');

        linksGroup = svg.append('g').attr('class', 'links');
        nodesGroup = svg.append('g').attr('class', 'nodes');

        simulation = d3.forceSimulation()
            .force('charge', d3.forceManyBody().strength(-120))
            .force('center', d3.forceCenter(width / 2, height / 2))
            .force('collision', d3.forceCollide().radius(45))
            .force('link', d3.forceLink().id(d => d.id).distance(100))
            .on('tick', ticked);

        // Empty start
        simulation.nodes([]);
    }

    function updateAgentMap(agents, sharedSpaces) {
        if (!svg) return;

        // Build nodes from agents
        const nodes = agents.map(a => {
            const existing = currentNodes.find(n => n.id === a.agent_id);
            return {
                id: a.agent_id,
                type: a.type || a.agent_type || 'generic',
                state: a.state || 'running',
                score: a.performance_score || 100,
                memoryCount: a.memory_node_count || 0,
                x: existing ? existing.x : width / 2 + (Math.random() - 0.5) * 100,
                y: existing ? existing.y : height / 2 + (Math.random() - 0.5) * 100,
            };
        });

        // Build links from shared memory spaces
        const links = [];
        if (sharedSpaces && sharedSpaces.length > 0) {
            for (const space of sharedSpaces) {
                const spaceAgents = space.active_agents || [];
                for (let i = 0; i < spaceAgents.length; i++) {
                    for (let j = i + 1; j < spaceAgents.length; j++) {
                        const src = nodes.find(n => n.id === spaceAgents[i]);
                        const tgt = nodes.find(n => n.id === spaceAgents[j]);
                        if (src && tgt) {
                            links.push({ source: src.id, target: tgt.id, space: space.name });
                        }
                    }
                }
            }
        }

        currentNodes = nodes;
        currentLinks = links;

        // Update links
        const link = linksGroup.selectAll('line').data(links, d => `${d.source}-${d.target}`);
        link.exit().transition().duration(300).attr('opacity', 0).remove();
        const linkEnter = link.enter().append('line')
            .attr('stroke', '#E8E5DE')
            .attr('stroke-width', 1.5)
            .attr('stroke-dasharray', '4,4')
            .attr('opacity', 0);
        linkEnter.transition().duration(300).attr('opacity', 0.6);

        // Update nodes
        const node = nodesGroup.selectAll('g.agent-node').data(nodes, d => d.id);
        node.exit().transition().duration(300).attr('opacity', 0).remove();

        const nodeEnter = node.enter().append('g')
            .attr('class', 'agent-node')
            .style('cursor', 'pointer')
            .on('click', (event, d) => {
                if (window.selectAgent) window.selectAgent(d.id);
            })
            .call(d3.drag()
                .on('start', dragStarted)
                .on('drag', dragged)
                .on('end', dragEnded));

        // Background circle (glow)
        nodeEnter.append('circle')
            .attr('class', 'node-glow')
            .attr('r', 28)
            .attr('fill', 'none')
            .attr('stroke', d => STATE_COLORS[d.state] || '#6366f1')
            .attr('stroke-width', 2)
            .attr('opacity', 0.3)
            .attr('filter', 'url(#glow)');

        // Main circle
        nodeEnter.append('circle')
            .attr('class', 'node-main')
            .attr('r', d => Math.max(18, Math.min(30, 18 + (d.memoryCount || 0) / 10)))
            .attr('fill', '#FFFFFF')
            .attr('stroke', d => STATE_COLORS[d.state] || '#6366f1')
            .attr('stroke-width', 2.5);

        // Score arc
        nodeEnter.append('path')
            .attr('class', 'node-score-arc')
            .attr('fill', 'none')
            .attr('stroke', d => STATE_COLORS[d.state] || '#6366f1')
            .attr('stroke-width', 3)
            .attr('opacity', 0.5);

        // Type letter
        nodeEnter.append('text')
            .attr('class', 'node-letter')
            .attr('text-anchor', 'middle')
            .attr('dy', '0.35em')
            .attr('fill', '#1A1A1A')
            .attr('font-family', 'JetBrains Mono, monospace')
            .attr('font-size', '14px')
            .attr('font-weight', 'bold')
            .text(d => TYPE_LETTERS[d.type] || 'G');

        // Label
        nodeEnter.append('text')
            .attr('class', 'node-label')
            .attr('text-anchor', 'middle')
            .attr('dy', '42px')
            .attr('fill', '#5C5C5C')
            .attr('font-family', 'Inter, sans-serif')
            .attr('font-size', '10px')
            .text(d => d.id.length > 14 ? d.id.substring(0, 12) + '..' : d.id);

        // Update existing nodes
        const allNodes = nodeEnter.merge(node);

        allNodes.select('.node-main')
            .transition().duration(300)
            .attr('stroke', d => STATE_COLORS[d.state] || '#6366f1')
            .attr('r', d => Math.max(18, Math.min(30, 18 + (d.memoryCount || 0) / 10)));

        allNodes.select('.node-glow')
            .transition().duration(300)
            .attr('stroke', d => STATE_COLORS[d.state] || '#6366f1');

        allNodes.select('.node-score-arc')
            .transition().duration(300)
            .attr('d', d => describeArc(0, 0, 32, 0, (d.score / 100) * 360))
            .attr('stroke', d => STATE_COLORS[d.state] || '#6366f1');

        // Update simulation
        simulation.nodes(nodes);
        simulation.force('link').links(links);
        simulation.alpha(0.3).restart();
    }

    function ticked() {
        linksGroup.selectAll('line')
            .attr('x1', d => d.source.x)
            .attr('y1', d => d.source.y)
            .attr('x2', d => d.target.x)
            .attr('y2', d => d.target.y);

        nodesGroup.selectAll('g.agent-node')
            .attr('transform', d => `translate(${d.x},${d.y})`);
    }

    function dragStarted(event, d) {
        if (!event.active) simulation.alphaTarget(0.3).restart();
        d.fx = d.x;
        d.fy = d.y;
    }

    function dragged(event, d) {
        d.fx = event.x;
        d.fy = event.y;
    }

    function dragEnded(event, d) {
        if (!event.active) simulation.alphaTarget(0);
        d.fx = null;
        d.fy = null;
    }

    function describeArc(x, y, radius, startAngle, endAngle) {
        const start = polarToCartesian(x, y, radius, endAngle);
        const end = polarToCartesian(x, y, radius, startAngle);
        const largeArcFlag = endAngle - startAngle <= 180 ? '0' : '1';
        return `M ${start.x} ${start.y} A ${radius} ${radius} 0 ${largeArcFlag} 0 ${end.x} ${end.y}`;
    }

    function polarToCartesian(cx, cy, radius, angleDeg) {
        const angleRad = (angleDeg - 90) * Math.PI / 180;
        return {
            x: cx + radius * Math.cos(angleRad),
            y: cy + radius * Math.sin(angleRad)
        };
    }

    // Pulse animation on memory write
    function pulseAgent(agentId) {
        const node = nodesGroup.selectAll('g.agent-node')
            .filter(d => d.id === agentId);
        if (node.empty()) return;

        node.append('circle')
            .attr('r', 20)
            .attr('fill', 'none')
            .attr('stroke', '#6366f1')
            .attr('stroke-width', 2)
            .attr('opacity', 0.8)
            .transition().duration(600)
            .attr('r', 50)
            .attr('opacity', 0)
            .remove();
    }

    // Crash animation
    function crashAgent(agentId) {
        const node = nodesGroup.selectAll('g.agent-node')
            .filter(d => d.id === agentId);
        if (node.empty()) return;

        // Shake
        node.transition().duration(50).attr('transform', d => `translate(${d.x-5},${d.y})`)
            .transition().duration(50).attr('transform', d => `translate(${d.x+5},${d.y})`)
            .transition().duration(50).attr('transform', d => `translate(${d.x-3},${d.y})`)
            .transition().duration(50).attr('transform', d => `translate(${d.x+3},${d.y})`)
            .transition().duration(50).attr('transform', d => `translate(${d.x},${d.y})`);

        node.select('.node-main')
            .transition().duration(200)
            .attr('stroke', '#ef4444')
            .attr('fill', '#FEE2E2');
    }

    // Recovery animation
    function recoverAgent(agentId) {
        const node = nodesGroup.selectAll('g.agent-node')
            .filter(d => d.id === agentId);
        if (node.empty()) return;

        node.select('.node-main')
            .transition().duration(300)
            .attr('stroke', '#3b82f6')
            .attr('fill', '#EBF5FF')
            .transition().duration(500)
            .attr('stroke', '#10b981')
            .attr('fill', '#FFFFFF');

        // Flash
        node.append('circle')
            .attr('r', 30)
            .attr('fill', '#10b981')
            .attr('opacity', 0.4)
            .transition().duration(400)
            .attr('r', 50)
            .attr('opacity', 0)
            .remove();
    }

    // Expose globally
    window.agentMap = {
        init: initAgentMap,
        update: updateAgentMap,
        pulse: pulseAgent,
        crash: crashAgent,
        recover: recoverAgent
    };
})();
