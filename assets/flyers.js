// While the mouse is over "Job Radar", little sci-fi critters and ships launch from the radar mark and fly
// across the page. The art is drawn here as inline SVG (original drawings, no game art). Nothing runs on touch
// screens or when the viewer has asked the system for reduced motion.
(() => {
  "use strict";

  const brand = document.getElementById("brand");
  const reduce = window.matchMedia ? matchMedia("(prefers-reduced-motion: reduce)") : { matches: false };
  if (!brand || !Element.prototype.animate) return;

  // Each drawing faces right in a 64 x 64 box. Classes (wing, flame, glow, bob, sway, blink) animate in style.css.
  const SPRITES = [
    // A round purple bug with buzzing wings
    `<svg viewBox="0 0 64 64">
      <g transform="rotate(-18 27 27)"><ellipse class="wing" cx="27" cy="15" rx="7" ry="12" fill="#ddd6fe" stroke="#a78bfa" stroke-width="1.2" opacity=".85"/></g>
      <path d="M13 36Q5 35 2 28Q8 31 14 31Z" fill="#7c3aed"/>
      <ellipse cx="27" cy="37" rx="15" ry="11" fill="#8b5cf6"/>
      <path d="M19 29Q16.5 37 19.5 45M26 26.5Q23 37 26.5 47.5" stroke="#6d28d9" stroke-width="2.2" fill="none" stroke-linecap="round"/>
      <circle cx="33" cy="31" r="1.8" fill="#c4b5fd"/><circle cx="22" cy="40" r="1.4" fill="#c4b5fd"/>
      <path d="M20 47l-2 4.5M26 48.5l-.5 4.5M32 47.5l1.5 4.5" stroke="#6d28d9" stroke-width="2" stroke-linecap="round"/>
      <g transform="rotate(14 32 27)"><ellipse class="wing" cx="32" cy="14" rx="8" ry="13" fill="#ede9fe" stroke="#a78bfa" stroke-width="1.2" opacity=".9"/></g>
      <path d="M41 23Q38 15 33.5 12.5M47 22.5Q49 14 54 11" stroke="#7c3aed" stroke-width="2" fill="none" stroke-linecap="round"/>
      <circle cx="33.5" cy="12.5" r="2.6" fill="#f0abfc"/><circle cx="54" cy="11" r="2.6" fill="#f0abfc"/>
      <circle cx="44" cy="33" r="12" fill="#a78bfa"/>
      <g class="blink">
        <ellipse cx="39.5" cy="31" rx="3.6" ry="4.2" fill="#fff"/><ellipse cx="47.5" cy="30.5" rx="4.8" ry="5.4" fill="#fff"/>
        <circle cx="40.4" cy="31.6" r="2.2" fill="#1e1b4b"/><circle cx="48.8" cy="31.2" r="3" fill="#1e1b4b"/>
        <circle cx="41.2" cy="30.5" r=".8" fill="#fff"/><circle cx="49.9" cy="29.8" r="1.1" fill="#fff"/>
      </g>
      <ellipse cx="37.5" cy="38" rx="2" ry="1.2" fill="#f9a8d4"/><ellipse cx="51.5" cy="37.8" rx="2.8" ry="1.6" fill="#f9a8d4"/>
      <path d="M43 39.2Q45.2 41.4 47.4 39.2" stroke="#4c1d95" stroke-width="1.4" fill="none" stroke-linecap="round"/>
      <path d="M44.2 40.2l.7 1.7.7-1.5Z" fill="#fff"/>
    </svg>`,

    // A golden crystal drone with a glowing face and two orbiting shards
    `<svg viewBox="0 0 64 64">
      <ellipse class="glow" cx="31" cy="58" rx="13" ry="3.2" fill="#67e8f9" opacity=".45"/>
      <path d="M27 14L22 3 36 12Z" fill="#f59e0b"/><path d="M27 50L22 61 36 52Z" fill="#f59e0b"/>
      <path d="M8 32C8 19 21 11 34 12C47 13 57 22 57 32C57 42 47 51 34 52C21 53 8 45 8 32Z" fill="#fbbf24" stroke="#b45309" stroke-width="1.6"/>
      <path d="M15 24C19 17.5 27 14.5 35 15" stroke="#fef3c7" stroke-width="3" fill="none" stroke-linecap="round"/>
      <path d="M12 38l6-2M13 30h6" stroke="#d97706" stroke-width="1.6" stroke-linecap="round"/>
      <ellipse class="glow" cx="39" cy="32" rx="15" ry="13" fill="#67e8f9" opacity=".4"/>
      <ellipse cx="39" cy="32" rx="12" ry="10" fill="#155e75"/>
      <g class="blink">
        <ellipse cx="34.5" cy="31" rx="2.7" ry="3.5" fill="#a5f3fc"/><ellipse cx="43.5" cy="31" rx="2.7" ry="3.5" fill="#a5f3fc"/>
        <circle cx="35.4" cy="29.8" r=".9" fill="#fff"/><circle cx="44.4" cy="29.8" r=".9" fill="#fff"/>
      </g>
      <path d="M36.5 36Q39 38.3 41.5 36" stroke="#a5f3fc" stroke-width="1.5" fill="none" stroke-linecap="round"/>
      <path class="bob" d="M3 17l4-6 4 6-4 6Z" fill="#a5f3fc" stroke="#0891b2" stroke-width="1.2"/>
      <path class="bob late" d="M55 46l3-4.5 3 4.5-3 4.5Z" fill="#a5f3fc" stroke="#0891b2" stroke-width="1.2"/>
    </svg>`,

    // A chubby little dropship with a cockpit face and flickering thrusters
    `<svg viewBox="0 0 64 64">
      <path class="flame" d="M12 9C6 9 2 11.5 0 11.5 2 11.5 6 14 12 14Z" fill="#fb923c"/>
      <path class="flame" d="M12 50C6 50 2 52.5 0 52.5 2 52.5 6 55 12 55Z" fill="#fb923c"/>
      <path class="flame" d="M9 30C4 30 1 34-2 34 1 34 4 38 9 38Z" fill="#fdba74"/>
      <path d="M22 23L19 14H31L33 23Z" fill="#64748b"/><path d="M22 45L19 52H31L33 45Z" fill="#64748b"/>
      <rect x="11" y="8" width="20" height="7" rx="3.5" fill="#475569"/><rect x="11" y="49" width="20" height="7" rx="3.5" fill="#475569"/>
      <rect x="25" y="9.5" width="4" height="4" rx="1" fill="#facc15"/><rect x="25" y="50.5" width="4" height="4" rx="1" fill="#facc15"/>
      <rect x="8" y="29" width="7" height="10" rx="2" fill="#475569"/>
      <rect x="12" y="21" width="44" height="26" rx="13" fill="#94a3b8" stroke="#475569" stroke-width="1.6"/>
      <rect x="15" y="40" width="23" height="3.5" rx="1.75" fill="#64748b"/>
      <circle cx="18" cy="27" r="1.1" fill="#cbd5e1"/><circle cx="22" cy="27" r="1.1" fill="#cbd5e1"/>
      <path d="M20 31l3 3-3 3" stroke="#facc15" stroke-width="2.2" fill="none" stroke-linecap="round" stroke-linejoin="round"/>
      <ellipse cx="43" cy="31" rx="9.5" ry="7.5" fill="#7dd3fc" stroke="#0369a1" stroke-width="1.3"/>
      <path d="M36.5 28Q39.5 24.8 45 24.9" stroke="#fff" stroke-width="1.6" fill="none" stroke-linecap="round" opacity=".85"/>
      <g class="blink">
        <ellipse cx="40.5" cy="31.8" rx="2" ry="2.5" fill="#0f172a"/><ellipse cx="47" cy="31.8" rx="2" ry="2.5" fill="#0f172a"/>
        <circle cx="41.2" cy="30.8" r=".75" fill="#fff"/><circle cx="47.7" cy="30.8" r=".75" fill="#fff"/>
      </g>
      <ellipse cx="52.3" cy="38.6" rx="2.4" ry="1.4" fill="#fda4af"/>
      <path d="M43 41Q45.5 43 48 41" stroke="#334155" stroke-width="1.4" fill="none" stroke-linecap="round"/>
    </svg>`,

    // A pink space jelly that paddles along with its tentacles
    `<svg viewBox="0 0 64 64">
      <path class="sway" d="M20 37q-3 6 0 11t0 10" stroke="#f9a8d4" stroke-width="3" fill="none" stroke-linecap="round"/>
      <path class="sway late" d="M28 38q3 6 0 11t0 9" stroke="#f472b6" stroke-width="3" fill="none" stroke-linecap="round"/>
      <path class="sway" d="M36 38q-3 6 0 11t0 9" stroke="#f9a8d4" stroke-width="3" fill="none" stroke-linecap="round"/>
      <path class="sway late" d="M44 37q3 6 0 11t0 10" stroke="#f472b6" stroke-width="3" fill="none" stroke-linecap="round"/>
      <path d="M12 37C12 21 21 11 32 11C43 11 52 21 52 37C47 40 43 36.5 38 39.5C34 36.5 30 36.5 26 39.5C21 36.5 17 40 12 37Z" fill="#f472b6"/>
      <path d="M18 27C19 20 24 15 30 14" stroke="#fdf2f8" stroke-width="2.6" fill="none" stroke-linecap="round" opacity=".85"/>
      <circle cx="41" cy="18" r="2.4" fill="#fbcfe8"/><circle cx="46" cy="24" r="1.5" fill="#fbcfe8"/>
      <g class="blink">
        <ellipse cx="27" cy="28" rx="3" ry="3.6" fill="#1f2937"/><ellipse cx="38" cy="28" rx="3" ry="3.6" fill="#1f2937"/>
        <circle cx="28" cy="26.7" r="1.1" fill="#fff"/><circle cx="39" cy="26.7" r="1.1" fill="#fff"/>
      </g>
      <ellipse cx="22.5" cy="32.5" rx="2.6" ry="1.5" fill="#fda4af"/><ellipse cx="42.5" cy="32.5" rx="2.6" ry="1.5" fill="#fda4af"/>
      <path d="M29.5 32.5Q32.5 35.3 35.5 32.5" stroke="#831843" stroke-width="1.5" fill="none" stroke-linecap="round"/>
      <path class="glow" d="M55 9l1.2 3.3 3.3 1.2-3.3 1.2-1.2 3.3-1.2-3.3-3.3-1.2 3.3-1.2Z" fill="#fde68a"/>
    </svg>`,
  ];

  const MAX_ALIVE = 14;
  const STEPS = 30;
  let alive = 0;
  let next = Math.floor(Math.random() * SPRITES.length);
  let timer = 0;
  const pending = new Set();

  const between = (lo, hi) => lo + Math.random() * (hi - lo);
  const cubic = (a, b, c, d, t) => {
    const u = 1 - t;
    return u * u * u * a + 3 * u * u * t * b + 3 * u * t * t * c + t * t * t * d;
  };
  const slope = (a, b, c, d, t) => {
    const u = 1 - t;
    return 3 * u * u * (b - a) + 6 * u * t * (c - b) + 3 * t * t * (d - c);
  };

  // A swoop from the radar mark through a random spot on screen and off an edge, with a little wobble.
  function flight(start, size) {
    const w = window.innerWidth;
    const h = window.innerHeight;
    const pad = size + 30;
    const side = Math.random();
    const end =
      side < 0.6 ? { x: w + pad, y: between(0.05, 0.9) * h }
      : side < 0.85 ? { x: between(0.25, 0.95) * w, y: h + pad }
      : { x: between(0.45, 0.95) * w, y: -pad };
    const c1 = { x: start.x + between(80, 340), y: start.y + between(20, 240) };
    const c2 = { x: between(0.15, 0.9) * w, y: between(0.1, 0.8) * h };
    const wobble = between(4, 12);
    const waves = between(1.5, 3.5);
    const phase = between(0, Math.PI * 2);
    const frames = [];
    let facing = 1;
    let length = 0;
    let prev = null;
    for (let i = 0; i <= STEPS; i++) {
      const t = i / STEPS;
      const dx = slope(start.x, c1.x, c2.x, end.x, t);
      const dy = slope(start.y, c1.y, c2.y, end.y, t);
      const speed = Math.hypot(dx, dy) || 1;
      const sway = Math.sin(t * Math.PI * 2 * waves + phase) * wobble * Math.min(1, t * 5);
      const x = cubic(start.x, c1.x, c2.x, end.x, t) - (dy / speed) * sway;
      const y = cubic(start.y, c1.y, c2.y, end.y, t) + (dx / speed) * sway;
      if (prev) length += Math.hypot(x - prev.x, y - prev.y);
      prev = { x, y };
      // Turn around only when clearly heading the other way, so a ship does not flicker on a vertical stretch.
      if (Math.abs(dx) > speed * 0.3) facing = dx < 0 ? -1 : 1;
      let tilt = (Math.atan2(dy, dx) * 180) / Math.PI;
      if (facing < 0) tilt = tilt > 0 ? tilt - 180 : tilt + 180;
      tilt = Math.max(-32, Math.min(32, tilt));
      const grow = Math.min(1, 0.3 + t * 7);
      frames.push({
        offset: t,
        transform: `translate(${(x - size / 2).toFixed(1)}px, ${(y - size / 2).toFixed(1)}px) rotate(${tilt.toFixed(1)}deg) scale(${(facing * grow).toFixed(3)}, ${grow.toFixed(3)})`,
        opacity: t < 0.04 ? t / 0.04 : t > 0.9 ? Math.max(0, (1 - t) / 0.1) : 1,
      });
    }
    return { frames, duration: Math.max(2600, Math.min(6500, (length / between(260, 420)) * 1000)) };
  }

  function launch() {
    if (alive >= MAX_ALIVE || document.hidden || reduce.matches) return;
    const mark = brand.querySelector(".brand-mark") || brand;
    const box = mark.getBoundingClientRect();
    const size = Math.round(between(40, 56));
    const { frames, duration } = flight({ x: box.left + box.width / 2, y: box.top + box.height / 2 }, size);
    const el = document.createElement("div");
    el.className = "flyer";
    el.setAttribute("aria-hidden", "true");
    el.style.width = el.style.height = size + "px";
    el.innerHTML = SPRITES[next++ % SPRITES.length];
    document.body.appendChild(el);
    alive++;
    const anim = el.animate(frames, { duration, easing: "linear", fill: "forwards" });
    let gone = false;
    const done = () => {
      if (gone) return;
      gone = true;
      alive--;
      el.remove();
    };
    anim.onfinish = done;
    anim.oncancel = done;
  }

  function stop() {
    clearInterval(timer);
    timer = 0;
    for (const id of pending) clearTimeout(id);
    pending.clear();
  }

  brand.addEventListener("pointerenter", (e) => {
    if (e.pointerType !== "mouse" || reduce.matches) return;
    stop();
    launch();
    for (const wait of [140, 280]) {
      const id = setTimeout(() => {
        pending.delete(id);
        launch();
      }, wait);
      pending.add(id);
    }
    timer = setInterval(launch, 450);
  });
  brand.addEventListener("pointerleave", stop);

  // If reduced motion is switched on while ships are flying, clear them away at once.
  const onReduce = () => {
    if (!reduce.matches) return;
    stop();
    for (const el of document.querySelectorAll(".flyer")) el.getAnimations().forEach((a) => a.cancel());
  };
  if (reduce.addEventListener) reduce.addEventListener("change", onReduce);
})();
