/* Global Network Canvas Background optimized for Mafqood AI */
document.addEventListener('DOMContentLoaded', () => {
    const canvas = document.getElementById('network-canvas');
    if (!canvas) return;

    const ctx = canvas.getContext('2d');
    let W, H;
    let particles = [];
    const PARTICLE_COUNT = 120; // Optimized node count
    const LINK_DIST = 250;
    const LINK_DIST_SQ = LINK_DIST * LINK_DIST;
    const MOUSE_RADIUS = 250;
    const MOUSE_RADIUS_SQ = MOUSE_RADIUS * MOUSE_RADIUS;
    let mouse = { x: -9999, y: -9999 };
    
    // Gold/Slate Premium Palette
    const PALETTES = [
        [183, 105, 53],    // primary (gold)
        [165, 99, 54],     // secondary (copper)
        [147, 94, 56],     // accent
        [253, 250, 246],   // light text
    ];
    let grid = {};
    let cellSize = LINK_DIST;

    function resizeCanvas() {
        // If placed inside a specific container, match it, otherwise match window
        const container = canvas.parentElement;
        if (container && container.tagName !== 'BODY') {
            W = canvas.width = container.offsetWidth;
            H = canvas.height = container.offsetHeight;
        } else {
            W = canvas.width = window.innerWidth;
            H = canvas.height = window.innerHeight;
        }
    }
    window.addEventListener('resize', resizeCanvas);

    function makeParticle() {
        const c = PALETTES[Math.floor(Math.random() * PALETTES.length)];
        return {
            x: Math.random() * W,
            y: Math.random() * H,
            vx: (Math.random() - 0.5) * 0.4,
            vy: (Math.random() - 0.5) * 0.4,
            baseY: Math.random() * H,
            angle: Math.random() * Math.PI * 2,
            r: Math.random() * 2.0 + 1.0,
            cr: c[0], cg: c[1], cb: c[2],
        };
    }

    function initDots() {
        resizeCanvas();
        particles = [];
        for (let i = 0; i < PARTICLE_COUNT; i++) particles.push(makeParticle());
    }

    function gridKey(cx, cy) { return cx + ',' + cy; }

    function buildGrid() {
        grid = {};
        for (let i = 0; i < particles.length; i++) {
            const p = particles[i];
            const cx = Math.floor(p.x / cellSize);
            const cy = Math.floor(p.y / cellSize);
            const key = gridKey(cx, cy);
            if (!grid[key]) grid[key] = [];
            grid[key].push(i);
        }
    }

    function loop() {
        ctx.clearRect(0, 0, W, H);
        const n = particles.length;

        for (let i = 0; i < n; i++) {
            const p = particles[i];
            
            p.angle += 0.01;
            p.x += p.vx + 0.2;
            p.y += p.vy + Math.sin(p.angle) * 0.3;
            
            if (p.x > W + 50) p.x = -50;
            if (p.x < -50) p.x = W + 50;
            if (p.y > H + 50) p.y = -50;
            if (p.y < -50) p.y = H + 50;

            const dx = mouse.x - p.x;
            const dy = mouse.y - p.y;
            const dSq = dx * dx + dy * dy;
            if (dSq < MOUSE_RADIUS_SQ && dSq > 1) {
                const d = Math.sqrt(dSq);
                const force = (1 - d / MOUSE_RADIUS) * 0.03;
                p.vx += dx / d * force;
                p.vy += dy / d * force;
            }
            p.vx *= 0.999;
            p.vy *= 0.999;
        }

        buildGrid();

        ctx.lineWidth = 0.6;
        const checked = new Set();
        for (let i = 0; i < n; i++) {
            const a = particles[i];
            const cx = Math.floor(a.x / cellSize);
            const cy = Math.floor(a.y / cellSize);
            for (let ox = -1; ox <= 1; ox++) {
                for (let oy = -1; oy <= 1; oy++) {
                    const cell = grid[gridKey(cx + ox, cy + oy)];
                    if (!cell) continue;
                    for (let k = 0; k < cell.length; k++) {
                        const j = cell[k];
                        if (j <= i) continue;
                        const pairKey = i * n + j;
                        if (checked.has(pairKey)) continue;
                        checked.add(pairKey);
                        const b = particles[j];
                        const ddx = a.x - b.x;
                        const ddy = a.y - b.y;
                        const dSq = ddx * ddx + ddy * ddy;
                        if (dSq < LINK_DIST_SQ) {
                            const alpha = (1 - Math.sqrt(dSq) / LINK_DIST) * 0.3;
                            ctx.beginPath();
                            ctx.moveTo(a.x, a.y);
                            ctx.lineTo(b.x, b.y);
                            ctx.strokeStyle = `rgba(${(a.cr + b.cr) >> 1},${(a.cg + b.cg) >> 1},${(a.cb + b.cb) >> 1},${alpha})`;
                            ctx.stroke();
                        }
                    }
                }
            }
        }

        for (let i = 0; i < n; i++) {
            const p = particles[i];
            ctx.beginPath();
            ctx.arc(p.x, p.y, p.r, 0, 6.2832);
            ctx.fillStyle = `rgba(${p.cr},${p.cg},${p.cb},0.85)`;
            ctx.fill();
        }

        if (mouse.x > 0) {
            ctx.beginPath();
            ctx.arc(mouse.x, mouse.y, MOUSE_RADIUS, 0, 6.2832);
            ctx.strokeStyle = 'rgba(var(--primary-rgb), 0.05)';
            ctx.lineWidth = 1;
            ctx.stroke();
        }

        requestAnimationFrame(loop);
    }

    document.addEventListener('mousemove', e => { mouse.x = e.clientX; mouse.y = e.clientY; });
    document.addEventListener('mouseleave', () => { mouse.x = -9999; mouse.y = -9999; });

    initDots();
    loop();
});
