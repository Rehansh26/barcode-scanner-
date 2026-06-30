(function () {
  var svgNS = 'http://www.w3.org/2000/svg';
  var container = document.getElementById('kg-graph');
  if (!container) return;

  var width = container.clientWidth || 900;
  var height = 560;

  var typeColors = {
    category: '#F2A33C',
    location: '#4C9A6A',
    item: '#9AA0A6',
  };
  var statusColors = {
    IN_STOCK: '#4C9A6A',
    LOW_STOCK: '#F2A33C',
    OUT_OF_STOCK: '#D9534F',
    DISCONTINUED: '#D9534F',
  };

  fetch(container.dataset.url)
    .then(function (response) { return response.json(); })
    .then(function (data) { renderGraph(data); })
    .catch(function () {
      container.innerHTML = '<div class="empty-state">Could not load graph data.</div>';
    });

  function renderGraph(data) {
    if (!data.nodes.length) {
      container.innerHTML = '<div class="empty-state">No items, categories, or locations to graph yet.</div>';
      return;
    }

    var nodes = data.nodes.map(function (n, i) {
      var angle = (i / data.nodes.length) * Math.PI * 2;
      return {
        id: n.id,
        label: n.label,
        type: n.type,
        status: n.status,
        x: width / 2 + Math.cos(angle) * 180 + (Math.random() * 30 - 15),
        y: height / 2 + Math.sin(angle) * 180 + (Math.random() * 30 - 15),
        vx: 0,
        vy: 0,
      };
    });

    var nodeById = {};
    nodes.forEach(function (n) { nodeById[n.id] = n; });

    var edges = data.edges
      .map(function (e) { return { source: nodeById[e.source], target: nodeById[e.target] }; })
      .filter(function (e) { return e.source && e.target; });

    // --- run a simple force simulation for a fixed number of steps ---
    var repulsion = 1800;
    var springLength = 90;
    var springStrength = 0.02;
    var centerStrength = 0.012;
    var ticks = 220;

    for (var t = 0; t < ticks; t++) {
      for (var i = 0; i < nodes.length; i++) {
        for (var j = i + 1; j < nodes.length; j++) {
          var a = nodes[i], b = nodes[j];
          var dx = a.x - b.x, dy = a.y - b.y;
          var distSq = dx * dx + dy * dy;
          if (distSq < 1) distSq = 1;
          var dist = Math.sqrt(distSq);
          var force = repulsion / distSq;
          dx /= dist; dy /= dist;
          a.vx += dx * force; a.vy += dy * force;
          b.vx -= dx * force; b.vy -= dy * force;
        }
      }
      edges.forEach(function (e) {
        var dx = e.target.x - e.source.x, dy = e.target.y - e.source.y;
        var dist = Math.sqrt(dx * dx + dy * dy) || 0.01;
        var diff = (dist - springLength) * springStrength;
        dx /= dist; dy /= dist;
        e.source.vx += dx * diff; e.source.vy += dy * diff;
        e.target.vx -= dx * diff; e.target.vy -= dy * diff;
      });
      nodes.forEach(function (n) {
        n.vx += (width / 2 - n.x) * centerStrength;
        n.vy += (height / 2 - n.y) * centerStrength;
        n.vx *= 0.85; n.vy *= 0.85;
        n.x += n.vx; n.y += n.vy;
        n.x = Math.max(24, Math.min(width - 24, n.x));
        n.y = Math.max(24, Math.min(height - 24, n.y));
      });
    }

    // --- render SVG ---
    container.innerHTML = '';
    var svg = document.createElementNS(svgNS, 'svg');
    svg.setAttribute('viewBox', '0 0 ' + width + ' ' + height);
    svg.setAttribute('class', 'kg-svg');
    container.appendChild(svg);

    var edgeGroup = document.createElementNS(svgNS, 'g');
    var nodeGroup = document.createElementNS(svgNS, 'g');
    svg.appendChild(edgeGroup);
    svg.appendChild(nodeGroup);

    var edgeLines = edges.map(function (e) {
      var line = document.createElementNS(svgNS, 'line');
      line.setAttribute('class', 'kg-edge');
      edgeGroup.appendChild(line);
      return { el: line, edge: e };
    });

    var nodeEls = nodes.map(function (n) {
      var g = document.createElementNS(svgNS, 'g');
      g.setAttribute('class', 'kg-node kg-node-' + n.type);
      g.style.cursor = 'pointer';

      var radius = n.type === 'item' ? 7 : 12;
      var circle = document.createElementNS(svgNS, 'circle');
      circle.setAttribute('r', radius);
      var fill = n.type === 'item' ? (statusColors[n.status] || typeColors.item) : typeColors[n.type];
      circle.setAttribute('fill', fill);
      g.appendChild(circle);

      var label = document.createElementNS(svgNS, 'text');
      label.textContent = n.label;
      label.setAttribute('class', 'kg-label');
      label.setAttribute('x', radius + 5);
      label.setAttribute('y', 4);
      g.appendChild(label);

      g.addEventListener('click', function () {
        if (dragMoved) { dragMoved = false; return; }
        if (n.type === 'item') {
          window.location.href = '/items/' + n.id.replace('item-', '') + '/';
        } else if (n.type === 'category') {
          window.location.href = '/?category=' + n.id.replace('cat-', '');
        } else if (n.type === 'location') {
          window.location.href = '/?location=' + n.id.replace('loc-', '');
        }
      });

      nodeGroup.appendChild(g);
      return { el: g, node: n };
    });

    function updatePositions() {
      nodeEls.forEach(function (entry) {
        entry.el.setAttribute('transform', 'translate(' + entry.node.x + ',' + entry.node.y + ')');
      });
      edgeLines.forEach(function (entry) {
        entry.el.setAttribute('x1', entry.edge.source.x);
        entry.el.setAttribute('y1', entry.edge.source.y);
        entry.el.setAttribute('x2', entry.edge.target.x);
        entry.el.setAttribute('y2', entry.edge.target.y);
      });
    }
    updatePositions();

    // --- dragging ---
    var draggingNode = null;
    var dragMoved = false;

    nodeEls.forEach(function (entry) {
      entry.el.addEventListener('mousedown', function (event) {
        draggingNode = entry.node;
        dragMoved = false;
        event.stopPropagation();
      });
    });

    window.addEventListener('mousemove', function (event) {
      if (!draggingNode) return;
      dragMoved = true;
      var rect = svg.getBoundingClientRect();
      var scaleX = width / rect.width;
      var scaleY = height / rect.height;
      draggingNode.x = (event.clientX - rect.left) * scaleX;
      draggingNode.y = (event.clientY - rect.top) * scaleY;
      updatePositions();
    });

    window.addEventListener('mouseup', function () {
      draggingNode = null;
    });
  }
})();
