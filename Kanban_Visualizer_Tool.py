"""
title: Inline Visualizer v2
author: Classic298
version: 2.0.0
description: Renders interactive HTML/SVG visualizations inline in chat. Requires "iframe Sandbox Allow Same Origin" to be enabled in Open WebUI Settings -> Interface. For design instructions, the model should call view_skill("visualize").
"""

import re
from typing import Literal

# Build marker embedded into the rendered iframe so the running
# version can be verified at runtime (search DevTools for
# `data-iv-build` on <html>).  Bump on every protocol-level change
# so stale cached iframes can be spotted immediately.
_IV_BUILD = "2.0.0"

from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Injected CSS — Theme variables (light default, dark via data-theme)
# ---------------------------------------------------------------------------

THEME_CSS = """
:root {
  --color-text-primary: #1F2937;
  --color-text-secondary: #6B7280;
  --color-text-tertiary: #9CA3AF;
  --color-text-info: #2563EB;
  --color-text-success: #059669;
  --color-text-warning: #D97706;
  --color-text-danger: #DC2626;
  --color-bg-primary: #FFFFFF;
  --color-bg-secondary: #F9FAFB;
  --color-bg-tertiary: #F3F4F6;
  --color-border-tertiary: rgba(0,0,0,0.15);
  --color-border-secondary: rgba(0,0,0,0.3);
  --color-border-primary: rgba(0,0,0,0.4);
  --font-sans: system-ui, -apple-system, 'Segoe UI', Roboto, sans-serif;
  --font-mono: 'SF Mono', Menlo, Consolas, monospace;
  --radius-md: 8px;
  --radius-lg: 12px;
  --radius-xl: 16px;
  /* --- Color ramp variables (light) --- */
  --ramp-purple-fill:#EEEDFE; --ramp-purple-stroke:#534AB7; --ramp-purple-th:#3C3489; --ramp-purple-ts:#534AB7;
  --ramp-teal-fill:#E1F5EE;   --ramp-teal-stroke:#0F6E56;   --ramp-teal-th:#085041;   --ramp-teal-ts:#0F6E56;
  --ramp-coral-fill:#FAECE7;  --ramp-coral-stroke:#993C1D;  --ramp-coral-th:#712B13;  --ramp-coral-ts:#993C1D;
  --ramp-pink-fill:#FBEAF0;   --ramp-pink-stroke:#993556;   --ramp-pink-th:#72243E;   --ramp-pink-ts:#993556;
  --ramp-gray-fill:#F1EFE8;   --ramp-gray-stroke:#5F5E5A;   --ramp-gray-th:#444441;   --ramp-gray-ts:#5F5E5A;
  --ramp-blue-fill:#E6F1FB;   --ramp-blue-stroke:#185FA5;   --ramp-blue-th:#0C447C;   --ramp-blue-ts:#185FA5;
  --ramp-green-fill:#EAF3DE;  --ramp-green-stroke:#3B6D11;  --ramp-green-th:#27500A;  --ramp-green-ts:#3B6D11;
  --ramp-amber-fill:#FAEEDA;  --ramp-amber-stroke:#854F0B;  --ramp-amber-th:#633806;  --ramp-amber-ts:#854F0B;
  --ramp-red-fill:#FCEBEB;    --ramp-red-stroke:#A32D2D;    --ramp-red-th:#791F1F;    --ramp-red-ts:#A32D2D;
  /* --- Common aliases (catch hallucinated variable names) --- */
  /* Text */
  --fg: var(--color-text-primary);
  --text: var(--color-text-primary);
  --foreground: var(--color-text-primary);
  --text-primary: var(--color-text-primary);
  --text-color: var(--color-text-primary);
  --color-text: var(--color-text-primary);
  --color-foreground: var(--color-text-primary);
  --body-color: var(--color-text-primary);
  --muted: var(--color-text-secondary);
  --muted-foreground: var(--color-text-secondary);
  --text-muted: var(--color-text-secondary);
  --text-secondary: var(--color-text-secondary);
  --secondary: var(--color-text-secondary);
  --subtle: var(--color-text-tertiary);
  --text-tertiary: var(--color-text-tertiary);
  /* Backgrounds */
  --bg: var(--color-bg-primary);
  --background: var(--color-bg-primary);
  --bg-primary: var(--color-bg-primary);
  --body-bg: var(--color-bg-primary);
  --color-bg: var(--color-bg-primary);
  --surface: var(--color-bg-secondary);
  --surface-1: var(--color-bg-secondary);
  --surface-2: var(--color-bg-tertiary);
  --card: var(--color-bg-secondary);
  --card-bg: var(--color-bg-secondary);
  --card-foreground: var(--color-text-primary);
  --card-background: var(--color-bg-secondary);
  --popover: var(--color-bg-secondary);
  --popover-foreground: var(--color-text-primary);
  --hover: rgba(0,0,0,0.04);
  /* Borders */
  --border: var(--color-border-tertiary);
  --border-color: var(--color-border-tertiary);
  --divider: var(--color-border-tertiary);
  --separator: var(--color-border-tertiary);
  --input: var(--color-border-tertiary);
  --ring: var(--color-border-secondary);
  /* Accent / Primary (AI uses --accent as brand color, not surface) */
  --primary: #6c2eb9;
  --primary-foreground: #ffffff;
  --accent: #6c2eb9;
  --accent-foreground: #ffffff;
}
:root[data-theme="dark"] {
  --color-text-primary: #E5E7EB;
  --color-text-secondary: #9CA3AF;
  --color-text-tertiary: #6B7280;
  --color-text-info: #60A5FA;
  --color-text-success: #34D399;
  --color-text-warning: #FBBF24;
  --color-text-danger: #F87171;
  --color-bg-primary: #1A1A1A;
  --color-bg-secondary: #262626;
  --color-bg-tertiary: #111111;
  --color-border-tertiary: rgba(255,255,255,0.15);
  --color-border-secondary: rgba(255,255,255,0.3);
  --color-border-primary: rgba(255,255,255,0.4);
  --ramp-purple-fill:#3C3489; --ramp-purple-stroke:#AFA9EC; --ramp-purple-th:#CECBF6; --ramp-purple-ts:#AFA9EC;
  --ramp-teal-fill:#085041;   --ramp-teal-stroke:#5DCAA5;   --ramp-teal-th:#9FE1CB;   --ramp-teal-ts:#5DCAA5;
  --ramp-coral-fill:#712B13;  --ramp-coral-stroke:#F0997B;  --ramp-coral-th:#F5C4B3;  --ramp-coral-ts:#F0997B;
  --ramp-pink-fill:#72243E;   --ramp-pink-stroke:#ED93B1;   --ramp-pink-th:#F4C0D1;   --ramp-pink-ts:#ED93B1;
  --ramp-gray-fill:#444441;   --ramp-gray-stroke:#B4B2A9;   --ramp-gray-th:#D3D1C7;   --ramp-gray-ts:#B4B2A9;
  --ramp-blue-fill:#0C447C;   --ramp-blue-stroke:#85B7EB;   --ramp-blue-th:#B5D4F4;   --ramp-blue-ts:#85B7EB;
  --ramp-green-fill:#27500A;  --ramp-green-stroke:#97C459;  --ramp-green-th:#C0DD97;  --ramp-green-ts:#97C459;
  --ramp-amber-fill:#633806;  --ramp-amber-stroke:#EF9F27;  --ramp-amber-th:#FAC775;  --ramp-amber-ts:#EF9F27;
  --ramp-red-fill:#791F1F;    --ramp-red-stroke:#F09595;    --ramp-red-th:#F7C1C1;    --ramp-red-ts:#F09595;
  /* --- Common aliases (dark overrides) --- */
  --text: var(--color-text-primary);
  --foreground: var(--color-text-primary);
  --text-primary: var(--color-text-primary);
  --text-color: var(--color-text-primary);
  --color-text: var(--color-text-primary);
  --body-color: var(--color-text-primary);
  --muted: var(--color-text-secondary);
  --muted-foreground: var(--color-text-secondary);
  --text-muted: var(--color-text-secondary);
  --text-secondary: var(--color-text-secondary);
  --secondary: var(--color-text-secondary);
  --subtle: var(--color-text-tertiary);
  --text-tertiary: var(--color-text-tertiary);
  --bg: var(--color-bg-primary);
  --background: var(--color-bg-primary);
  --bg-primary: var(--color-bg-primary);
  --body-bg: var(--color-bg-primary);
  --color-bg: var(--color-bg-primary);
  --surface: var(--color-bg-secondary);
  --surface-1: var(--color-bg-secondary);
  --surface-2: var(--color-bg-tertiary);
  --card: var(--color-bg-secondary);
  --card-bg: var(--color-bg-secondary);
  --card-foreground: var(--color-text-primary);
  --card-background: var(--color-bg-secondary);
  --popover: var(--color-bg-secondary);
  --popover-foreground: var(--color-text-primary);
  --hover: rgba(255,255,255,0.06);
  --border: var(--color-border-tertiary);
  --border-color: var(--color-border-tertiary);
  --divider: var(--color-border-tertiary);
  --separator: var(--color-border-tertiary);
  --input: var(--color-border-tertiary);
  --ring: var(--color-border-secondary);
  --primary: #a78bfa;
  --primary-foreground: #1A1A1A;
  --accent: #a78bfa;
  --accent-foreground: #ffffff;
}
"""

# ---------------------------------------------------------------------------
# Injected CSS — SVG utility classes + color ramp selectors
# ---------------------------------------------------------------------------

SVG_CLASSES = """
/* --- Text --- */
.t  { font: 400 14px/1.4 var(--font-sans); fill: var(--color-text-primary); }
.ts { font: 400 12px/1.4 var(--font-sans); fill: var(--color-text-secondary); }
.th { font: 500 14px/1.4 var(--font-sans); fill: var(--color-text-primary); }

/* --- Shapes --- */
.box    { fill: var(--color-bg-secondary); stroke: var(--color-border-tertiary); stroke-width: 0.5; }
.node   { cursor: pointer; }
.node:hover { opacity: 0.85; }
.arr    { stroke: var(--color-border-secondary); stroke-width: 1.5; fill: none; }
.leader { stroke: var(--color-text-tertiary); stroke-width: 0.5; stroke-dasharray: 3 2; fill: none; }

/* --- Color ramp selectors (fill/stroke adapt via CSS vars) --- */
.c-purple>rect,.c-purple>circle,.c-purple>ellipse{fill:var(--ramp-purple-fill);stroke:var(--ramp-purple-stroke);stroke-width:.5}
.c-purple>.th{fill:var(--ramp-purple-th)!important} .c-purple>.ts{fill:var(--ramp-purple-ts)!important}
.c-teal>rect,.c-teal>circle,.c-teal>ellipse{fill:var(--ramp-teal-fill);stroke:var(--ramp-teal-stroke);stroke-width:.5}
.c-teal>.th{fill:var(--ramp-teal-th)!important} .c-teal>.ts{fill:var(--ramp-teal-ts)!important}
.c-coral>rect,.c-coral>circle,.c-coral>ellipse{fill:var(--ramp-coral-fill);stroke:var(--ramp-coral-stroke);stroke-width:.5}
.c-coral>.th{fill:var(--ramp-coral-th)!important} .c-coral>.ts{fill:var(--ramp-coral-ts)!important}
.c-pink>rect,.c-pink>circle,.c-pink>ellipse{fill:var(--ramp-pink-fill);stroke:var(--ramp-pink-stroke);stroke-width:.5}
.c-pink>.th{fill:var(--ramp-pink-th)!important} .c-pink>.ts{fill:var(--ramp-pink-ts)!important}
.c-gray>rect,.c-gray>circle,.c-gray>ellipse{fill:var(--ramp-gray-fill);stroke:var(--ramp-gray-stroke);stroke-width:.5}
.c-gray>.th{fill:var(--ramp-gray-th)!important} .c-gray>.ts{fill:var(--ramp-gray-ts)!important}
.c-blue>rect,.c-blue>circle,.c-blue>ellipse{fill:var(--ramp-blue-fill);stroke:var(--ramp-blue-stroke);stroke-width:.5}
.c-blue>.th{fill:var(--ramp-blue-th)!important} .c-blue>.ts{fill:var(--ramp-blue-ts)!important}
.c-green>rect,.c-green>circle,.c-green>ellipse{fill:var(--ramp-green-fill);stroke:var(--ramp-green-stroke);stroke-width:.5}
.c-green>.th{fill:var(--ramp-green-th)!important} .c-green>.ts{fill:var(--ramp-green-ts)!important}
.c-amber>rect,.c-amber>circle,.c-amber>ellipse{fill:var(--ramp-amber-fill);stroke:var(--ramp-amber-stroke);stroke-width:.5}
.c-amber>.th{fill:var(--ramp-amber-th)!important} .c-amber>.ts{fill:var(--ramp-amber-ts)!important}
.c-red>rect,.c-red>circle,.c-red>ellipse{fill:var(--ramp-red-fill);stroke:var(--ramp-red-stroke);stroke-width:.5}
.c-red>.th{fill:var(--ramp-red-th)!important} .c-red>.ts{fill:var(--ramp-red-ts)!important}
"""

# ---------------------------------------------------------------------------
# Injected CSS — Base resets & interactive element styles
# ---------------------------------------------------------------------------

BASE_STYLES = """
* { box-sizing: border-box; margin: 0; font-family: var(--font-sans); }
html, body { overflow: hidden; }
body { background: transparent; color: var(--color-text-primary); line-height: 1.5; padding: 8px; }
svg { overflow: visible; }
svg text { fill: var(--color-text-primary); }
h1 { font-size: 22px; font-weight: 500; color: var(--color-text-primary); margin-bottom: 12px; }
h2 { font-size: 18px; font-weight: 500; color: var(--color-text-primary); margin-bottom: 8px; }
h3 { font-size: 16px; font-weight: 500; color: var(--color-text-primary); margin-bottom: 6px; }
p  { font-size: 14px; color: var(--color-text-secondary); margin-bottom: 8px; }
button {
  background: transparent; border: 0.5px solid var(--color-border-secondary);
  border-radius: var(--radius-md); padding: 6px 14px; font-size: 13px;
  color: var(--color-text-primary); cursor: pointer; font-family: var(--font-sans);
}
button:hover { background: var(--color-bg-secondary); }
button.active { background: var(--color-bg-secondary); border-color: var(--color-border-primary); }
input[type="range"] {
  -webkit-appearance: none; width: 100%; height: 4px;
  background: var(--color-border-tertiary); border-radius: 2px; outline: none;
}
input[type="range"]::-webkit-slider-thumb {
  -webkit-appearance: none; width: 18px; height: 18px; border-radius: 50%;
  background: var(--color-bg-primary); border: 0.5px solid var(--color-border-secondary); cursor: pointer;
}
select {
  background: var(--color-bg-secondary); border: 0.5px solid var(--color-border-tertiary);
  border-radius: var(--radius-md); padding: 6px 10px; font-size: 13px;
  color: var(--color-text-primary); font-family: var(--font-sans);
}
code {
  font-family: var(--font-mono); font-size: 13px; background: var(--color-bg-tertiary);
  padding: 2px 6px; border-radius: 4px;
}
#iv-dl-wrap{position:fixed;top:4px;right:4px;z-index:9999}
#iv-dl-btn{width:26px;height:26px;padding:0;display:flex;align-items:center;justify-content:center;
  opacity:0.3;border-color:var(--color-border-tertiary);background:var(--color-bg-primary)}
#iv-dl-btn:hover{opacity:0.9;background:var(--color-bg-secondary)}
#iv-dl-btn svg{width:14px;height:14px;stroke:var(--color-text-secondary);fill:none;
  stroke-width:1.5;stroke-linecap:round;stroke-linejoin:round}
/* --- Print ---
 * overflow:hidden on html/body clips content in print (needed on screen
 * for iframe sizing). Chart.js canvas scaling is handled by JS beforeprint
 * handler in BODY_SCRIPTS — it directly mutates inline styles that CSS
 * cannot reliably override in Chrome's print engine.
 */
@media print {
  @page { margin: 12mm; }
  html, body { overflow: visible !important; height: auto !important;
    background: #fff !important; }
  body { padding: 4px !important; }
  #iv-dl-wrap { display: none !important; }
  * { -webkit-print-color-adjust: exact; print-color-adjust: exact; }
}
"""

# ---------------------------------------------------------------------------
# Injected JavaScript — theme detection (head), height reporting & bridges (body)
# ---------------------------------------------------------------------------
# Theme script runs in <head> before user content so CSS vars are resolved
# when model scripts read them at parse time.
THEME_DETECTION_SCRIPT = """
<script>
(function() {
  function detectTheme(root) {
    return root.classList.contains('dark')
      || root.getAttribute('data-theme') === 'dark'
      || getComputedStyle(root).colorScheme === 'dark';
  }

  function applyTheme(isDark) {
    var theme = isDark ? 'dark' : 'light';
    if (document.documentElement.getAttribute('data-theme') === theme) return;
    document.documentElement.setAttribute('data-theme', theme);
    if (window.Chart && Chart.instances) {
      var s = getComputedStyle(document.documentElement);
      var tc = s.getPropertyValue('--color-text-secondary').trim();
      var gc = s.getPropertyValue('--color-border-tertiary').trim();
      Chart.defaults.color = tc;
      Chart.defaults.borderColor = gc;
      Object.values(Chart.instances).forEach(function(chart) {
        Object.values(chart.options.scales || {}).forEach(function(scale) {
          if (scale.ticks) scale.ticks.color = tc;
          if (scale.grid) scale.grid.color = gc;
        });
        var leg = (chart.options.plugins || {}).legend;
        if (leg && leg.labels) leg.labels.color = tc;
        chart.update();
      });
    }
  }

  try {
    var p = parent.document.documentElement;
    applyTheme(detectTheme(p));
    new MutationObserver(function() {
      applyTheme(detectTheme(p));
    }).observe(p, { attributes: true, attributeFilter: ['class', 'data-theme', 'style'] });
  } catch(e) {
    // No same-origin access — fall back to OS preference.
    var mq = window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)');
    if (mq) {
      applyTheme(mq.matches);
      mq.addEventListener('change', function(e) { applyTheme(e.matches); });
    }
  }
})();
</script>
"""

BODY_SCRIPTS = """
<script>
// --- Height reporting ---
var _rh_last = 0;          // last reported height
var _rh_consecutive = 0;   // consecutive small-growth reports
var _rh_raf = 0;           // rAF id for debouncing ResizeObserver

function reportHeight() {
  var b = document.body;
  // Measure SVG overflow before the body collapse below — getBBox
  // needs normal layout.
  var svgOverflow = 0;
  document.querySelectorAll('svg[viewBox]').forEach(function(svg) {
    try {
      var bbox = svg.getBBox();
      var vb = svg.viewBox.baseVal;
      if (vb && vb.width > 0 && vb.height > 0) {
        var overflow = bbox.y + bbox.height - (vb.y + vb.height);
        if (overflow > 0) {
          var scale = svg.getBoundingClientRect().width / vb.width;
          svgOverflow += Math.ceil(overflow * scale);
        }
      }
    } catch(e) {}
  });

  // Force height:auto on body + direct children — vh in an auto-sized
  // iframe tracks iframe height, creating a feedback loop.
  var savedBody = b.style.cssText;
  b.style.setProperty('height', 'auto', 'important');
  b.style.setProperty('overflow', 'visible', 'important');
  b.style.setProperty('display', 'block', 'important');
  var saved = [];
  Array.from(b.children).forEach(function(el) {
    if (el.nodeType !== 1) return;
    saved.push({ el: el, css: el.style.cssText });
    el.style.setProperty('height', 'auto', 'important');
    el.style.setProperty('max-height', 'none', 'important');
    el.style.setProperty('min-height', '0', 'important');
    el.style.setProperty('overflow', 'visible', 'important');
  });
  var h = Math.min(b.scrollHeight + svgOverflow, 8000);
  b.style.cssText = savedBody;
  saved.forEach(function(s) { s.el.style.cssText = s.css; });

  // Loop guard: 3+ consecutive small monotonic increases → stop.
  var delta = h - _rh_last;
  if (_rh_last > 0 && delta > 0 && delta < 50) {
    _rh_consecutive++;
    if (_rh_consecutive >= 3) return;
  } else {
    _rh_consecutive = 0;
  }

  _rh_last = h;
  parent.postMessage({ type: 'iframe:height', height: h }, '*');
}
window.addEventListener('load', reportHeight);
window.addEventListener('resize', reportHeight);
// rAF-debounced ResizeObserver avoids tight synchronous loops.
new ResizeObserver(function() {
  cancelAnimationFrame(_rh_raf);
  _rh_raf = requestAnimationFrame(reportHeight);
}).observe(document.body);
// <details> toggle — ResizeObserver misses this in some browsers.
document.addEventListener('toggle', function() {
  _rh_consecutive = 0;
  setTimeout(reportHeight, 50);
}, true);
// Dynamic content swaps (innerHTML assignments, SPA-style updates).
var _rh_mutRaf = 0;
new MutationObserver(function() {
  _rh_consecutive = 0;
  cancelAnimationFrame(_rh_mutRaf);
  _rh_mutRaf = requestAnimationFrame(reportHeight);
}).observe(document.body, { childList: true, subtree: true });
// Click covers custom expand/collapse via style.display / class swaps.
document.addEventListener('click', function() {
  _rh_consecutive = 0;
  cancelAnimationFrame(_rh_mutRaf);
  _rh_mutRaf = requestAnimationFrame(reportHeight);
}, true);

// --- Post-render fixes (theme defaults, overlap prevention) ---
window.addEventListener('load', function() {
  // Chart.js theme defaults + legend overflow prevention
  if (window.Chart) {
    var s = getComputedStyle(document.documentElement);
    var textColor = s.getPropertyValue('--color-text-secondary').trim();
    var gridColor = s.getPropertyValue('--color-border-tertiary').trim();
    Chart.defaults.color = textColor;
    Chart.defaults.borderColor = gridColor;
    Chart.defaults.plugins.legend.labels.color = textColor;
    Chart.defaults.plugins.legend.maxHeight = 120;
    Chart.defaults.plugins.legend.labels.boxWidth = 12;
    Chart.defaults.plugins.legend.labels.font = { size: 11 };
    Object.values(Chart.instances || {}).forEach(function(chart) {
      var leg = chart.options.plugins && chart.options.plugins.legend;
      if (leg) {
        leg.maxHeight = leg.maxHeight || 120;
        if (leg.labels) {
          leg.labels.boxWidth = leg.labels.boxWidth || 12;
        }
      }
      chart.update();
    });
  }

  // De-overlap SVG axis labels only — add data-no-stagger on a <svg>
  // to opt out.
  document.querySelectorAll('svg').forEach(function(svg) {
    if (svg.hasAttribute('data-no-stagger')) return;
    var texts = Array.from(svg.querySelectorAll('text'));
    if (texts.length < 4) return;
    var items = [];
    texts.forEach(function(t) {
      var r = t.getBoundingClientRect();
      if (r.width < 1) return;
      items.push({ el: t, rect: r, cx: r.left + r.width / 2, cy: r.top + r.height / 2 });
    });
    if (items.length < 4) return;
    // Only touch texts in a narrow y-band (axis labels). Diagrams with
    // texts spread across the canvas are left alone.
    var minY = Infinity, maxY = -Infinity;
    items.forEach(function(it) {
      if (it.cy < minY) minY = it.cy;
      if (it.cy > maxY) maxY = it.cy;
    });
    var ySpan = maxY - minY;
    if (ySpan < 1) return;
    // Pick the densest y-band (likely the axis row).
    var bandSize = 30;
    var bestBand = [], bestCount = 0;
    items.forEach(function(anchor) {
      var band = items.filter(function(it) { return Math.abs(it.cy - anchor.cy) < bandSize; });
      if (band.length > bestCount) { bestCount = band.length; bestBand = band; }
    });
    if (bestBand.length < 3 || bestBand.length === items.length && ySpan > 60) return;
    var groups = [];
    bestBand.forEach(function(it) {
      for (var i = 0; i < groups.length; i++) {
        if (Math.abs(groups[i].cx - it.cx) < 15) {
          groups[i].items.push(it);
          return;
        }
      }
      groups.push({ cx: it.cx, items: [it] });
    });
    if (groups.length < 3) return;
    groups.sort(function(a, b) { return a.cx - b.cx; });
    var needsStagger = false;
    for (var i = 0; i < groups.length - 1; i++) {
      var maxR = 0, minL = Infinity;
      groups[i].items.forEach(function(it) { if (it.rect.right > maxR) maxR = it.rect.right; });
      groups[i+1].items.forEach(function(it) { if (it.rect.left < minL) minL = it.rect.left; });
      if (maxR > minL - 2) { needsStagger = true; break; }
    }
    if (needsStagger) {
      for (var i = 1; i < groups.length; i += 2) {
        groups[i].items.forEach(function(it) {
          var cy = parseFloat(it.el.getAttribute('y') || 0);
          it.el.setAttribute('y', String(cy + 18));
        });
      }
    }
  });

  setTimeout(reportHeight, 100);
});

// --- sendPrompt bridge (requires iframe Sandbox Allow Same Origin) ---
function sendPrompt(text) {
  try {
    // Open WebUI's native prompt-submit postMessage — queues if the
    // model is mid-generation.
    parent.postMessage({ type: 'input:prompt:submit', text: text }, '*');
  } catch(e) { /* iframe sandbox restriction */ }
}

// --- Open link in parent window ---
function openLink(url) {
  try { parent.window.open(url, '_blank'); }
  catch(e) { window.open(url, '_blank'); }
}

// --- navigator.vibrate silencer ---
// Chrome spams `[Intervention] Blocked call to navigator.vibrate…` on
// every call without a prior user gesture. Replace with a no-op so the
// block path never runs.
try {
  if (typeof navigator !== 'undefined' && navigator.vibrate) {
    navigator.vibrate = function() { return false; };
  }
} catch(e) {}

// --- Toast bridge ---
// Floating auto-dismissing top-right banner. kind = success/info/warn/error.
function toast(msg, kind) {
  kind = kind || 'success';
  var color = kind === 'error' ? 'var(--color-text-danger)'
           : kind === 'info'  ? 'var(--color-text-info)'
           : kind === 'warn'  ? 'var(--color-text-warning)'
           : 'var(--color-text-success)';
  var wrap = document.getElementById('iv-toast-wrap');
  if (!wrap) {
    wrap = document.createElement('div');
    wrap.id = 'iv-toast-wrap';
    wrap.style.cssText =
      'position:fixed;top:4px;right:38px;z-index:9998;' +
      'display:flex;flex-direction:column;gap:4px;pointer-events:none;' +
      'max-width:280px;';
    document.body.appendChild(wrap);
  }
  var el = document.createElement('div');
  el.style.cssText =
    'padding:6px 12px;border-radius:var(--radius-md);' +
    'background:var(--color-bg-secondary);' +
    'border:0.5px solid var(--color-border-tertiary);' +
    'color:' + color + ';font-size:12px;line-height:1.4;' +
    'font-family:var(--font-sans);font-weight:500;' +
    'opacity:0;transform:translateY(-4px);transition:all 0.2s ease;' +
    'pointer-events:auto;white-space:nowrap;' +
    'overflow:hidden;text-overflow:ellipsis;';
  el.textContent = String(msg == null ? '' : msg);
  wrap.appendChild(el);
  requestAnimationFrame(function() {
    el.style.opacity = '1';
    el.style.transform = 'none';
  });
  setTimeout(function() {
    el.style.opacity = '0';
    el.style.transform = 'translateY(-4px)';
    setTimeout(function() { if (el.parentNode) el.parentNode.removeChild(el); }, 220);
  }, 2200);
}

// --- copyText bridge ---
// Async Clipboard API with execCommand fallback (Open WebUI's iframe
// sandbox lacks allow-clipboard-write). Toast fires unconditionally —
// execCommand can silently fail and swallowing feedback leaves the user
// confused. silent=true suppresses the toast.
function copyText(text, silent) {
  var s = String(text == null ? '' : text);
  var label = (typeof _ivCopiedStr !== 'undefined' &&
               (_ivCopiedStr[_ivLang] || _ivCopiedStr.en)) || 'Copied';
  function fire() { if (!silent) try { toast(label, 'success'); } catch(e) {} }

  function legacy() {
    try {
      var ta = document.createElement('textarea');
      ta.value = s;
      ta.setAttribute('readonly', '');
      ta.style.cssText =
        'position:fixed;left:-9999px;top:-9999px;opacity:0;';
      document.body.appendChild(ta);
      ta.focus();
      ta.select();
      try { ta.setSelectionRange(0, s.length); } catch(e) {}
      try { document.execCommand('copy'); } catch(e) {}
      ta.remove();
    } catch(e) {}
    fire();
  }

  try {
    if (navigator.clipboard && navigator.clipboard.writeText) {
      navigator.clipboard.writeText(s).then(fire, legacy);
      return;
    }
  } catch(e) {}
  legacy();
}

// --- saveState / loadState bridges ---
// parent.localStorage proxy scoped to the assistant message id — state
// persists across reloads but never leaks between chats / messages.
// Silent no-op if localStorage / parent is unreachable.
function _ivStatePrefix() {
  try {
    var f = window.frameElement;
    var msg = f && f.closest && f.closest('[id^="message-"]');
    return 'iv-state:' + ((msg && msg.id) || 'global') + ':';
  } catch(e) { return 'iv-state:global:'; }
}
function saveState(key, value) {
  try {
    parent.localStorage.setItem(
      _ivStatePrefix() + String(key),
      JSON.stringify(value === undefined ? null : value)
    );
  } catch(e) {}
}
function loadState(key, fallback) {
  try {
    var v = parent.localStorage.getItem(_ivStatePrefix() + String(key));
    if (v == null) return fallback === undefined ? null : fallback;
    return JSON.parse(v);
  } catch(e) { return fallback === undefined ? null : fallback; }
}

/*__CHIME_BLOCK__*/

// --- Print fix for Chart.js canvases ---
// Chart.js writes explicit pixel widths as inline styles that CSS
// max-width can't override in Chrome's print engine. Mutate inline
// styles before print, restore after.
(function() {
  window.addEventListener('beforeprint', function() {
    document.querySelectorAll('canvas').forEach(function(c) {
      c.setAttribute('data-print-style', c.style.cssText);
      c.style.setProperty('width', '100%', 'important');
      c.style.setProperty('max-width', '100%', 'important');
      c.style.setProperty('height', 'auto', 'important');
      var p = c.parentElement;
      if (p) {
        p.setAttribute('data-print-style', p.style.cssText);
        p.style.setProperty('width', '100%', 'important');
        p.style.setProperty('max-width', '100%', 'important');
      }
    });
  });
  window.addEventListener('afterprint', function() {
    document.querySelectorAll('[data-print-style]').forEach(function(el) {
      el.style.cssText = el.getAttribute('data-print-style');
      el.removeAttribute('data-print-style');
    });
  });
})();

// --- Download visualization as self-contained HTML ---
var _ivLang = 'en';
var _ivStr = {
  // Required languages
  en: 'Download as HTML',
  de: 'Als HTML herunterladen',
  cs: 'Stáhnout jako HTML',
  hu: 'Letöltés HTML-ként',
  hr: 'Preuzmi kao HTML',
  pl: 'Pobierz jako HTML',
  fr: 'Télécharger en HTML',
  nl: 'Downloaden als HTML',
  // Western & Southern European
  es: 'Descargar como HTML',
  pt: 'Baixar como HTML',
  it: 'Scarica come HTML',
  ca: 'Baixa com a HTML',
  gl: 'Descargar como HTML',
  eu: 'Deskargatu HTML gisa',
  // Northern European
  da: 'Download som HTML',
  sv: 'Ladda ner som HTML',
  no: 'Last ned som HTML',
  fi: 'Lataa HTML-tiedostona',
  is: 'Hlaða niður sem HTML',
  // Eastern European & Slavic
  sk: 'Stiahnuť ako HTML',
  sl: 'Prenesi kot HTML',
  sr: 'Преузми као HTML',
  bs: 'Preuzmi kao HTML',
  bg: 'Изтегли като HTML',
  mk: 'Преземи како HTML',
  uk: 'Завантажити як HTML',
  ru: 'Скачать как HTML',
  be: 'Спампаваць як HTML',
  // Baltic
  lt: 'Atsisiųsti kaip HTML',
  lv: 'Lejupielādēt kā HTML',
  et: 'Laadi alla HTML-ina',
  // Other European
  ro: 'Descarcă ca HTML',
  el: 'Λήψη ως HTML',
  sq: 'Shkarko si HTML',
  // Middle Eastern
  tr: 'HTML olarak indir',
  ar: 'تحميل كـ HTML',

  he: 'הורד כ-HTML',
  // East & South Asian
  zh: '下载为HTML',
  ja: 'HTMLでダウンロード',
  ko: 'HTML로 다운로드',
  vi: 'Tải xuống dạng HTML',
  th: 'ดาวน์โหลดเป็น HTML',
  id: 'Unduh sebagai HTML',
  ms: 'Muat turun sebagai HTML',
  hi: 'HTML के रूप में डाउनलोड करें',
  bn: 'HTML হিসেবে ডাউনলোড করুন',
  // African
  sw: 'Pakua kama HTML'
};

// Loader label (shown while waiting for the first content chunk).
var _ivLoadStr = {
  en: 'Rendering visualization\u2026',
  de: 'Visualisierung wird erstellt\u2026',
  cs: 'Vykresluje se vizualizace\u2026',
  hu: 'Vizualizáció renderelése\u2026',
  hr: 'Iscrtavanje vizualizacije\u2026',
  pl: 'Renderowanie wizualizacji\u2026',
  fr: 'Rendu de la visualisation\u2026',
  nl: 'Visualisatie renderen\u2026',
  es: 'Renderizando visualización\u2026',
  pt: 'Renderizando visualização\u2026',
  it: 'Rendering della visualizzazione\u2026',
  ca: 'Renderitzant visualització\u2026',
  gl: 'Renderizando visualización\u2026',
  eu: 'Bistaratzea errendatzen\u2026',
  da: 'Gengiver visualisering\u2026',
  sv: 'Renderar visualisering\u2026',
  no: 'Gjengir visualisering\u2026',
  fi: 'Renderöidään visualisointia\u2026',
  is: 'Teiknar sjónræna framsetningu\u2026',
  sk: 'Vykresľuje sa vizualizácia\u2026',
  sl: 'Upodabljanje vizualizacije\u2026',
  sr: 'Исцртавање визуализације\u2026',
  bs: 'Iscrtavanje vizualizacije\u2026',
  bg: 'Изчертаване на визуализацията\u2026',
  mk: 'Исцртување на визуализацијата\u2026',
  uk: 'Відображення візуалізації\u2026',
  ru: 'Отрисовка визуализации\u2026',
  be: 'Адмалёўка візуалізацыі\u2026',
  lt: 'Atvaizduojama vizualizacija\u2026',
  lv: 'Vizualizācijas renderēšana\u2026',
  et: 'Visualiseeringu renderdamine\u2026',
  ro: 'Randare vizualizare\u2026',
  el: 'Απόδοση οπτικοποίησης\u2026',
  sq: 'Duke renderuar vizualizimin\u2026',
  tr: 'Görselleştirme oluşturuluyor\u2026',
  ar: 'جارٍ عرض التصور\u2026',
  he: 'מציג הדמיה\u2026',
  zh: '正在渲染可视化\u2026',
  ja: 'ビジュアライゼーションを描画中\u2026',
  ko: '시각화 렌더링 중\u2026',
  vi: 'Đang kết xuất hình ảnh\u2026',
  th: 'กำลังแสดงผลการแสดงภาพ\u2026',
  id: 'Merender visualisasi\u2026',
  ms: 'Memaparkan visualisasi\u2026',
  hi: 'विज़ुअलाइज़ेशन रेंडर हो रहा है\u2026',
  bn: 'ভিজ্যুয়ালাইজেশন রেন্ডার হচ্ছে\u2026',
  sw: 'Inarendi taswira\u2026'
};

// "Streaming visualization unavailable" title + body, shown only when
// the iframe cannot reach parent.document (Allow Same Origin disabled).
var _ivErrTitleStr = {
  en: 'Streaming visualization unavailable',
  de: 'Streaming-Visualisierung nicht verfügbar',
  cs: 'Streamovaná vizualizace není dostupná',
  hu: 'A streamelt vizualizáció nem érhető el',
  hr: 'Streaming vizualizacija nije dostupna',
  pl: 'Strumieniowa wizualizacja niedostępna',
  fr: 'Visualisation en streaming indisponible',
  nl: 'Streaming visualisatie niet beschikbaar',
  es: 'Visualización en streaming no disponible',
  pt: 'Visualização em streaming indisponível',
  it: 'Visualizzazione in streaming non disponibile',
  ca: 'Visualització en streaming no disponible',
  gl: 'Visualización en streaming non dispoñíbel',
  eu: 'Streaming bistaratzea ez dago erabilgarri',
  da: 'Streaming-visualisering utilgængelig',
  sv: 'Strömmande visualisering otillgänglig',
  no: 'Streaming-visualisering utilgjengelig',
  fi: 'Suoratoistettu visualisointi ei käytettävissä',
  is: 'Streymandi sjónræn framsetning ekki tiltæk',
  sk: 'Streamovaná vizualizácia nie je dostupná',
  sl: 'Pretočna vizualizacija ni na voljo',
  sr: 'Стриминг визуализација није доступна',
  bs: 'Streaming vizualizacija nije dostupna',
  bg: 'Поточната визуализация е недостъпна',
  mk: 'Стриминг визуализација недостапна',
  uk: 'Потокова візуалізація недоступна',
  ru: 'Потоковая визуализация недоступна',
  be: 'Струменевая візуалізацыя недаступная',
  lt: 'Srautinė vizualizacija nepasiekiama',
  lv: 'Straumētā vizualizācija nav pieejama',
  et: 'Voogedastuse visualiseering pole saadaval',
  ro: 'Vizualizarea în streaming indisponibilă',
  el: 'Η ροή οπτικοποίησης δεν είναι διαθέσιμη',
  sq: 'Vizualizimi i transmetimit i padisponueshëm',
  tr: 'Akış görselleştirmesi kullanılamıyor',
  ar: 'التصور المتدفق غير متاح',
  he: 'הדמיה בסטרימינג אינה זמינה',
  zh: '流式可视化不可用',
  ja: 'ストリーミングビジュアライゼーションは利用できません',
  ko: '스트리밍 시각화를 사용할 수 없습니다',
  vi: 'Hình ảnh trực quan phát trực tuyến không khả dụng',
  th: 'การแสดงผลแบบสตรีมไม่พร้อมใช้งาน',
  id: 'Visualisasi streaming tidak tersedia',
  ms: 'Visualisasi strim tidak tersedia',
  hi: 'स्ट्रीमिंग विज़ुअलाइज़ेशन अनुपलब्ध',
  bn: 'স্ট্রিমিং ভিজ্যুয়ালাইজেশন অনুপলব্ধ',
  sw: 'Taswira ya utiririshaji haipatikani'
};

// Confirmation toast shown after copyText() succeeds.
var _ivCopiedStr = {
  en: 'Copied', de: 'Kopiert', cs: 'Zkopírováno', hu: 'Másolva',
  hr: 'Kopirano', pl: 'Skopiowano', fr: 'Copié', nl: 'Gekopieerd',
  es: 'Copiado', pt: 'Copiado', it: 'Copiato', ca: 'Copiat',
  gl: 'Copiado', eu: 'Kopiatuta',
  da: 'Kopieret', sv: 'Kopierat', no: 'Kopiert', fi: 'Kopioitu',
  is: 'Afritað',
  sk: 'Skopírované', sl: 'Kopirano', sr: 'Копирано', bs: 'Kopirano',
  bg: 'Копирано', mk: 'Копирано', uk: 'Скопійовано', ru: 'Скопировано',
  be: 'Скапіявана',
  lt: 'Nukopijuota', lv: 'Nokopēts', et: 'Kopeeritud',
  ro: 'Copiat', el: 'Αντιγράφηκε', sq: 'U kopjua',
  tr: 'Kopyalandı', ar: 'تم النسخ', he: 'הועתק',
  zh: '已复制', ja: 'コピーしました', ko: '복사됨',
  vi: 'Đã sao chép', th: 'คัดลอกแล้ว', id: 'Disalin', ms: 'Disalin',
  hi: 'कॉपी किया गया', bn: 'অনুলিপি করা হয়েছে',
  sw: 'Imenakiliwa'
};

// Shown as a top-right toast when streaming completes and the
// visualization has finished rendering. Only appears if we actually
// witnessed live streaming — refreshes of completed messages stay silent.
var _ivDoneStr = {
  en: 'Visualization ready',
  de: 'Visualisierung bereit',
  cs: 'Vizualizace připravena',
  hu: 'Vizualizáció kész',
  hr: 'Vizualizacija spremna',
  pl: 'Wizualizacja gotowa',
  fr: 'Visualisation prête',
  nl: 'Visualisatie klaar',
  es: 'Visualización lista',
  pt: 'Visualização pronta',
  it: 'Visualizzazione pronta',
  ca: 'Visualització llesta',
  gl: 'Visualización lista',
  eu: 'Bistaratzea prest',
  da: 'Visualisering klar',
  sv: 'Visualisering klar',
  no: 'Visualisering klar',
  fi: 'Visualisointi valmis',
  is: 'Sjónræn framsetning tilbúin',
  sk: 'Vizualizácia pripravená',
  sl: 'Vizualizacija pripravljena',
  sr: 'Визуализација спремна',
  bs: 'Vizualizacija spremna',
  bg: 'Визуализацията е готова',
  mk: 'Визуализацијата е подготвена',
  uk: 'Візуалізація готова',
  ru: 'Визуализация готова',
  be: 'Візуалізацыя гатовая',
  lt: 'Vizualizacija paruošta',
  lv: 'Vizualizācija gatava',
  et: 'Visualiseering valmis',
  ro: 'Vizualizare gata',
  el: 'Η οπτικοποίηση είναι έτοιμη',
  sq: 'Vizualizimi gati',
  tr: 'Görselleştirme hazır',
  ar: 'التصور جاهز',
  he: 'ההדמיה מוכנה',
  zh: '可视化已完成',
  ja: 'ビジュアライゼーション完成',
  ko: '시각화 완료',
  vi: 'Hình ảnh đã sẵn sàng',
  th: 'การแสดงภาพพร้อมแล้ว',
  id: 'Visualisasi siap',
  ms: 'Visualisasi sedia',
  hi: 'विज़ुअलाइज़ेशन तैयार',
  bn: 'ভিজ্যুয়ালাইজেশন প্রস্তুত',
  sw: 'Taswira tayari'
};

var _ivErrBodyStr = {
  en: 'Open User Settings \u2192 Interface, scroll down, and enable "Allow iframe same origin" to use streaming mode.',
  de: 'Öffne Benutzereinstellungen \u2192 Oberfläche, scrolle nach unten und aktiviere „Allow iframe same origin" für den Streaming-Modus.',
  cs: 'Otevřete Uživatelská nastavení \u2192 Rozhraní, sjeďte dolů a zapněte „Allow iframe same origin" pro režim streamování.',
  hu: 'Nyissa meg a Felhasználói beállítások \u2192 Felület menüt, görgessen le, és kapcsolja be az „Allow iframe same origin" opciót a streamelési módhoz.',
  hr: 'Otvorite Korisničke postavke \u2192 Sučelje, pomaknite se prema dolje i uključite „Allow iframe same origin" za streaming način.',
  pl: 'Otwórz Ustawienia użytkownika \u2192 Interfejs, przewiń w dół i włącz „Allow iframe same origin" dla trybu strumieniowego.',
  fr: 'Ouvrez Paramètres utilisateur \u2192 Interface, faites défiler vers le bas et activez « Allow iframe same origin » pour le mode streaming.',
  nl: 'Open Gebruikersinstellingen \u2192 Interface, scrol omlaag en schakel "Allow iframe same origin" in voor streamingmodus.',
  es: 'Abre Configuración de usuario \u2192 Interfaz, desplázate hacia abajo y activa "Allow iframe same origin" para el modo streaming.',
  pt: 'Abra Configurações do usuário \u2192 Interface, role para baixo e ative "Allow iframe same origin" para o modo streaming.',
  it: 'Apri Impostazioni utente \u2192 Interfaccia, scorri in basso e attiva "Allow iframe same origin" per la modalità streaming.',
  ca: 'Obre Configuració d\u2019usuari \u2192 Interfície, desplaça\u2019t avall i activa "Allow iframe same origin" per al mode streaming.',
  gl: 'Abre Configuración de usuario \u2192 Interface, desprázate cara abaixo e activa "Allow iframe same origin" para o modo streaming.',
  eu: 'Ireki Erabiltzaile-ezarpenak \u2192 Interfazea, egin behera eta gaitu "Allow iframe same origin" streaming modua erabiltzeko.',
  da: 'Åbn Brugerindstillinger \u2192 Grænseflade, rul ned, og aktivér "Allow iframe same origin" for streamingtilstand.',
  sv: 'Öppna Användarinställningar \u2192 Gränssnitt, rulla ner och aktivera "Allow iframe same origin" för strömningsläge.',
  no: 'Åpne Brukerinnstillinger \u2192 Grensesnitt, rull ned og aktiver "Allow iframe same origin" for streamingmodus.',
  fi: 'Avaa Käyttäjäasetukset \u2192 Käyttöliittymä, vieritä alas ja ota "Allow iframe same origin" käyttöön suoratoistotilaa varten.',
  is: 'Opnaðu Notandastillingar \u2192 Viðmót, skrunaðu niður og kveiktu á "Allow iframe same origin" fyrir streymisstillingu.',
  sk: 'Otvorte Používateľské nastavenia \u2192 Rozhranie, posuňte sa nadol a zapnite „Allow iframe same origin" pre režim streamovania.',
  sl: 'Odprite Uporabniške nastavitve \u2192 Vmesnik, pomaknite se navzdol in omogočite "Allow iframe same origin" za pretočni način.',
  sr: 'Отворите Корисничка подешавања \u2192 Интерфејс, померите надоле и омогућите „Allow iframe same origin" за стриминг режим.',
  bs: 'Otvorite Korisničke postavke \u2192 Sučelje, skrolajte prema dolje i uključite "Allow iframe same origin" za streaming mod.',
  bg: 'Отворете Потребителски настройки \u2192 Интерфейс, превъртете надолу и активирайте „Allow iframe same origin" за поточен режим.',
  mk: 'Отворете Кориснички поставки \u2192 Интерфејс, листајте надолу и овозможете „Allow iframe same origin" за стриминг режим.',
  uk: 'Відкрийте Налаштування користувача \u2192 Інтерфейс, прокрутіть униз і ввімкніть «Allow iframe same origin» для потокового режиму.',
  ru: 'Откройте Настройки пользователя \u2192 Интерфейс, прокрутите вниз и включите «Allow iframe same origin» для режима потоковой передачи.',
  be: 'Адкрыйце Налады карыстальніка \u2192 Інтэрфейс, прагартайце ўніз і ўключыце «Allow iframe same origin» для струменевага рэжыму.',
  lt: 'Atidarykite Naudotojo nustatymai \u2192 Sąsaja, slinkite žemyn ir įjunkite „Allow iframe same origin" srautiniam režimui.',
  lv: 'Atveriet Lietotāja iestatījumi \u2192 Saskarne, ritiniet lejup un iespējojiet "Allow iframe same origin" straumēšanas režīmam.',
  et: 'Ava Kasutaja seaded \u2192 Liides, keri alla ja luba „Allow iframe same origin" voogedastusrežiimi jaoks.',
  ro: 'Deschide Setări utilizator \u2192 Interfață, derulează în jos și activează "Allow iframe same origin" pentru modul streaming.',
  el: 'Ανοίξτε Ρυθμίσεις χρήστη \u2192 Διεπαφή, κυλήστε προς τα κάτω και ενεργοποιήστε το «Allow iframe same origin» για λειτουργία ροής.',
  sq: 'Hapni Cilësimet e përdoruesit \u2192 Ndërfaqja, rrëshqitni poshtë dhe aktivizoni "Allow iframe same origin" për modalitetin e transmetimit.',
  tr: 'Kullanıcı Ayarları \u2192 Arayüz\u2019ü açın, aşağı kaydırın ve akış modu için "Allow iframe same origin" seçeneğini etkinleştirin.',
  ar: 'افتح إعدادات المستخدم \u2190 الواجهة، مرر لأسفل وفعّل "Allow iframe same origin" لاستخدام وضع التدفق.',
  he: 'פתח הגדרות משתמש \u2190 ממשק, גלול מטה והפעל את "Allow iframe same origin" למצב סטרימינג.',
  zh: '打开 用户设置 \u2192 界面，向下滚动并启用"Allow iframe same origin"以使用流式模式。',
  ja: 'ユーザー設定 \u2192 インターフェースを開き、下にスクロールして「Allow iframe same origin」を有効にするとストリーミングモードを使用できます。',
  ko: '사용자 설정 \u2192 인터페이스를 열고 아래로 스크롤하여 "Allow iframe same origin"을 활성화하면 스트리밍 모드를 사용할 수 있습니다.',
  vi: 'Mở Cài đặt người dùng \u2192 Giao diện, cuộn xuống và bật "Allow iframe same origin" để sử dụng chế độ phát trực tiếp.',
  th: 'เปิดการตั้งค่าผู้ใช้ \u2192 อินเทอร์เฟซ เลื่อนลงและเปิดใช้งาน "Allow iframe same origin" เพื่อใช้โหมดสตรีม',
  id: 'Buka Pengaturan Pengguna \u2192 Antarmuka, gulir ke bawah dan aktifkan "Allow iframe same origin" untuk mode streaming.',
  ms: 'Buka Tetapan Pengguna \u2192 Antara Muka, tatal ke bawah dan dayakan "Allow iframe same origin" untuk mod strim.',
  hi: 'उपयोगकर्ता सेटिंग्स \u2192 इंटरफ़ेस खोलें, नीचे स्क्रॉल करें और स्ट्रीमिंग मोड के लिए "Allow iframe same origin" सक्षम करें।',
  bn: 'ব্যবহারকারী সেটিংস \u2192 ইন্টারফেস খুলুন, নিচে স্ক্রোল করুন এবং স্ট্রিমিং মোডের জন্য "Allow iframe same origin" সক্ষম করুন।',
  sw: 'Fungua Mipangilio ya Mtumiaji \u2192 Kiolesura, sogeza chini na washa "Allow iframe same origin" kwa hali ya utiririshaji.'
};

(function() {
  function detectLang() {
    // 1. Pre-detected via __event_call__ (baked into HTML by the tool)
    var pre = document.documentElement.getAttribute('data-iv-lang');
    if (pre && _ivStr[pre]) return pre;
    // 2. Fallback: parent localStorage (needs same-origin)
    try {
      var s = parent.localStorage.getItem('locale')
           || parent.localStorage.getItem('language')
           || parent.localStorage.getItem('i18nextLng');
      if (s) { var l = s.split('-')[0].toLowerCase(); if (_ivStr[l]) return l; }
    } catch(e) {}
    // 3. Fallback: browser language (standalone HTML / no same-origin)
    try {
      var bl = (navigator.language || navigator.userLanguage || 'en').split('-')[0].toLowerCase();
      if (_ivStr[bl]) return bl;
    } catch(e) {}
    return 'en';
  }
  _ivLang = detectLang();
  var btn = document.getElementById('iv-dl-btn');
  if (btn) btn.title = _ivStr[_ivLang] || _ivStr.en;
  // Swap the server-baked English loader label for the detected locale.
  var loadLabel = document.querySelector('.iv-loading-label');
  if (loadLabel) loadLabel.textContent = _ivLoadStr[_ivLang] || _ivLoadStr.en;
})();

// ---------------------------------------------------------------------------
// Download as self-contained HTML
// ---------------------------------------------------------------------------
// Desktop / Android: blob + <a download> + target="_blank" safety net
// (gracefully opens in a new tab if the iframe sandbox blocks downloads).
// iOS: NO target="_blank" (would strand PWA users on a blob page with no
// back button), setTimeout(0) deferral avoids a synchronous WebKit
// "Load failed" throw, and error listeners suppress the residual toast
// for 60s. iOS detection also catches iPadOS via MacIntel+touchpoints.
// ---------------------------------------------------------------------------

var _ivIsIOS = /iPad|iPhone|iPod/.test(navigator.userAgent)
  || (navigator.platform === 'MacIntel' && navigator.maxTouchPoints > 1);

function _ivDownload() {
  // Strip download button + overflow:hidden for standalone use.
  var w = document.getElementById('iv-dl-wrap');
  if (w) w.remove();
  var html = '<!DOCTYPE html>\\n' + document.documentElement.outerHTML;
  if (w) document.body.appendChild(w);
  html = html.replace('html, body { overflow: hidden; }', '');

  var fname = (document.title || 'visualization').replace(/[<>:"\\/|?*]+/g, '-').replace(/\s+/g, ' ').trim();
  if (!fname) fname = 'visualization';
  // Cap at 200 chars to stay under the Windows 255-char filename limit.
  if (fname.length > 200) fname = fname.substring(0, 200).trim();
  fname += '.html';

  var blob = new Blob([html], {type: 'text/html;charset=utf-8'});
  var url = URL.createObjectURL(blob);

  if (_ivIsIOS) {
    // iOS — deferred click + "Load failed" error suppression.
    setTimeout(function() {
      var _origOnerror = window.onerror;
      window.onerror = function(msg) {
        if (typeof msg === 'string' && msg.indexOf('Load failed') !== -1) return true;
        if (_origOnerror) return _origOnerror.apply(this, arguments);
      };
      var _sup = function(ev) {
        var m = ev && (ev.message || (ev.reason && ev.reason.message) || '');
        if (m.indexOf('Load failed') !== -1) { ev.preventDefault(); ev.stopImmediatePropagation(); return true; }
      };
      window.addEventListener('error', _sup, true);
      window.addEventListener('unhandledrejection', _sup, true);

      var a = document.createElement('a');
      a.style.display = 'none';
      a.href = url;
      a.download = fname;
      // No target="_blank" on iOS — strands PWA users on a blob page.
      document.body.appendChild(a);
      a.click();

      // Restore original handlers after 60s.
      setTimeout(function() {
        window.onerror = _origOnerror;
        window.removeEventListener('error', _sup, true);
        window.removeEventListener('unhandledrejection', _sup, true);
        URL.revokeObjectURL(url);
        a.remove();
      }, 60000);
    }, 0);
  } else {
    // Desktop / Android — straightforward blob download.
    var a = document.createElement('a');
    a.href = url;
    a.download = fname;
    // Safety net: new tab if the iframe sandbox blocks downloads.
    a.target = '_blank';
    a.style.display = 'none';
    document.body.appendChild(a);
    a.click();
    setTimeout(function() { a.remove(); URL.revokeObjectURL(url); }, 60000);
  }
}

// ---------------------------------------------------------------------------
// OOXML fallback helpers — pure JS, zero CDN, works on air-gapped networks
// ---------------------------------------------------------------------------

// XML special-char escaping for attribute values and text content
function _ivXe(s){return String(s==null?'':s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;').replace(/'/g,'&apos;');}

// CRC32 table + function (required by ZIP local/central headers)
var _ivCT=null;
function _ivCrc(d){
  if(!_ivCT){_ivCT=new Uint32Array(256);for(var n=0;n<256;n++){var c=n;for(var k=0;k<8;k++)c=(c&1)?(0xEDB88320^(c>>>1)):(c>>>1);_ivCT[n]=c;}}
  var crc=0xFFFFFFFF;
  for(var i=0;i<d.length;i++)crc=(crc>>>8)^_ivCT[(crc^d[i])&0xFF];
  return(crc^0xFFFFFFFF)>>>0;
}

// Minimal stored-mode ZIP builder (no deflate — OOXML does not require compression)
// files: [{name:string, data:string|Uint8Array}]
function _ivZip(files){
  var enc=new TextEncoder(),entries=[],off=0;
  files.forEach(function(f){
    var d=typeof f.data==='string'?enc.encode(f.data):f.data;
    var nm=enc.encode(f.name);
    var lh=new Uint8Array(30+nm.length),dv=new DataView(lh.buffer);
    dv.setUint32(0,0x04034b50,true);dv.setUint16(4,20,true);
    var crc=_ivCrc(d);
    dv.setUint32(14,crc,true);dv.setUint32(18,d.length,true);dv.setUint32(22,d.length,true);
    dv.setUint16(26,nm.length,true);lh.set(nm,30);
    entries.push({nm:nm,lh:lh,d:d,crc:crc,off:off});
    off+=lh.length+d.length;
  });
  var cdOff=off,cdSz=0,cdParts=[];
  entries.forEach(function(e){
    var cd=new Uint8Array(46+e.nm.length),dv=new DataView(cd.buffer);
    dv.setUint32(0,0x02014b50,true);dv.setUint16(4,20,true);dv.setUint16(6,20,true);
    dv.setUint32(16,e.crc,true);dv.setUint32(20,e.d.length,true);dv.setUint32(24,e.d.length,true);
    dv.setUint16(28,e.nm.length,true);dv.setUint32(42,e.off,true);
    cd.set(e.nm,46);cdParts.push(cd);cdSz+=cd.length;
  });
  var eocd=new Uint8Array(22),dv2=new DataView(eocd.buffer);
  dv2.setUint32(0,0x06054b50,true);dv2.setUint16(8,entries.length,true);dv2.setUint16(10,entries.length,true);
  dv2.setUint32(12,cdSz,true);dv2.setUint32(16,cdOff,true);
  var tot=off+cdSz+22,res=new Uint8Array(tot),pos=0;
  entries.forEach(function(e){res.set(e.lh,pos);pos+=e.lh.length;res.set(e.d,pos);pos+=e.d.length;});
  cdParts.forEach(function(cd){res.set(cd,pos);pos+=cd.length;});
  res.set(eocd,pos);
  return new Blob([res],{type:'application/octet-stream'});
}

// Trigger a file download from a Blob
function _ivDl(blob,fname){
  var url=URL.createObjectURL(blob),a=document.createElement('a');
  a.href=url;a.download=fname;a.style.display='none';
  document.body.appendChild(a);a.click();
  setTimeout(function(){a.remove();URL.revokeObjectURL(url);},60000);
}

// Excel column letter for 0-based index (0=A, 25=Z, 26=AA ...)
function _ivCol(n){var s='';n++;while(n>0){n--;s=String.fromCharCode(65+(n%26))+s;n=Math.floor(n/26);}return s;}

// ---------------------------------------------------------------------------
// Pure OOXML .xlsx builder — sheets:[{name, headers, rows}]
// ---------------------------------------------------------------------------
function _ivXlsxOoxml(sheets,base){
  var strs=[],sm={};
  function si(v){var s=String(v==null?'':v);if(sm[s]===undefined){sm[s]=strs.length;strs.push(s);}return sm[s];}
  var sh=sheets||[],f=[];
  f.push({name:'[Content_Types].xml',data:'<?xml version="1.0" encoding="UTF-8"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/><Override PartName="/xl/sharedStrings.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sharedStrings+xml"/>'+sh.map(function(s,i){return '<Override PartName="/xl/worksheets/sheet'+(i+1)+'.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>';}).join('')+'</Types>'});
  f.push({name:'_rels/.rels',data:'<?xml version="1.0" encoding="UTF-8"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/></Relationships>'});
  f.push({name:'xl/workbook.xml',data:'<?xml version="1.0" encoding="UTF-8"?><workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets>'+sh.map(function(s,i){return '<sheet name="'+_ivXe((s.name||'Sheet'+(i+1)).substring(0,31))+'" sheetId="'+(i+1)+'" r:id="rId'+(i+1)+'"/>';}).join('')+'</sheets></workbook>'});
  f.push({name:'xl/_rels/workbook.xml.rels',data:'<?xml version="1.0" encoding="UTF-8"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'+sh.map(function(s,i){return '<Relationship Id="rId'+(i+1)+'" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet'+(i+1)+'.xml"/>';}).join('')+'<Relationship Id="rId'+(sh.length+1)+'" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/sharedStrings" Target="sharedStrings.xml"/></Relationships>'});
  sh.forEach(function(s,i){
    var rows=[s.headers||[]].concat(s.rows||[]);
    var rx=rows.map(function(row,ri){return '<row r="'+(ri+1)+'">'+(row||[]).map(function(cell,ci){var ref=_ivCol(ci)+(ri+1),num=Number(cell);if(cell!==''&&cell!==null&&cell!==undefined&&!isNaN(num))return '<c r="'+ref+'"><v>'+num+'</v></c>';return '<c r="'+ref+'" t="s"><v>'+si(cell)+'</v></c>';}).join('')+'</row>';}).join('');
    f.push({name:'xl/worksheets/sheet'+(i+1)+'.xml',data:'<?xml version="1.0" encoding="UTF-8"?><worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData>'+rx+'</sheetData></worksheet>'});
  });
  f.push({name:'xl/sharedStrings.xml',data:'<?xml version="1.0" encoding="UTF-8"?><sst xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" count="'+strs.length+'" uniqueCount="'+strs.length+'">'+strs.map(function(s){return '<si><t xml:space="preserve">'+_ivXe(s)+'</t></si>';}).join('')+'</sst>'});
  _ivDl(_ivZip(f),base+'.xlsx');
  try{toast('Excel ready (built-in)','success');}catch(e){}
}

// ---------------------------------------------------------------------------
// Pure OOXML .pptx builder — slides:[{title, subtitle, bg, headerBg, headerH,
//   titleColor, bodyColor, subtitleColor, accentColor, items, stats, table, footer,
//   tableHeaderBg, tableHeaderColor}]
// ---------------------------------------------------------------------------
function _ivPptxOoxml(slides,base){
  var W=12192000,H=6858000,sld=slides||[],f=[];
  var NS_A='http://schemas.openxmlformats.org/drawingml/2006/main';
  var NS_R='http://schemas.openxmlformats.org/officeDocument/2006/relationships';
  var NS_P='http://schemas.openxmlformats.org/presentationml/2006/main';
  f.push({name:'[Content_Types].xml',data:'<?xml version="1.0" encoding="UTF-8"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Override PartName="/ppt/presentation.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.presentation.main+xml"/><Override PartName="/ppt/slideMasters/slideMaster1.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.slideMaster+xml"/><Override PartName="/ppt/slideLayouts/slideLayout1.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.slideLayout+xml"/>'+sld.map(function(s,i){return '<Override PartName="/ppt/slides/slide'+(i+1)+'.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.slide+xml"/>';}).join('')+'</Types>'});
  f.push({name:'_rels/.rels',data:'<?xml version="1.0" encoding="UTF-8"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="ppt/presentation.xml"/></Relationships>'});
  f.push({name:'ppt/presentation.xml',data:'<?xml version="1.0" encoding="UTF-8"?><p:presentation xmlns:a="'+NS_A+'" xmlns:r="'+NS_R+'" xmlns:p="'+NS_P+'" saveSubsetFonts="1"><p:sldMasterIdLst><p:sldMasterId id="2148739216" r:id="rIdM1"/></p:sldMasterIdLst><p:sldIdLst>'+sld.map(function(s,i){return '<p:sldId id="'+(256+i)+'" r:id="rId'+(i+1)+'"/>';}).join('')+'</p:sldIdLst><p:sldSz cx="'+W+'" cy="'+H+'" type="custom"/><p:notesSz cx="6858000" cy="9144000"/></p:presentation>'});
  f.push({name:'ppt/_rels/presentation.xml.rels',data:'<?xml version="1.0" encoding="UTF-8"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'+sld.map(function(s,i){return '<Relationship Id="rId'+(i+1)+'" Type="'+NS_R+'/slide" Target="slides/slide'+(i+1)+'.xml"/>';}).join('')+'<Relationship Id="rIdM1" Type="'+NS_R+'/slideMaster" Target="slideMasters/slideMaster1.xml"/></Relationships>'});
  f.push({name:'ppt/slideMasters/slideMaster1.xml',data:'<?xml version="1.0" encoding="UTF-8"?><p:sldMaster xmlns:a="'+NS_A+'" xmlns:r="'+NS_R+'" xmlns:p="'+NS_P+'"><p:cSld><p:bg><p:bgRef idx="1001"><a:srgbClr val="FFFFFF"/></p:bgRef></p:bg><p:spTree><p:nvGrpSpPr><p:cNvPr id="1" name=""/><p:cNvGrpSpPr/><p:nvPr/></p:nvGrpSpPr><p:grpSpPr><a:xfrm><a:off x="0" y="0"/><a:ext cx="0" cy="0"/><a:chOff x="0" y="0"/><a:chExt cx="0" cy="0"/></a:xfrm></p:grpSpPr></p:spTree></p:cSld><p:clrMap bg1="lt1" tx1="dk1" bg2="lt2" tx2="dk2" accent1="accent1" accent2="accent2" accent3="accent3" accent4="accent4" accent5="accent5" accent6="accent6" hlink="hlink" folHlink="folHlink"/><p:sldLayoutIdLst><p:sldLayoutId id="2049" r:id="rIdL1"/></p:sldLayoutIdLst></p:sldMaster>'});
  f.push({name:'ppt/slideMasters/_rels/slideMaster1.xml.rels',data:'<?xml version="1.0" encoding="UTF-8"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rIdL1" Type="'+NS_R+'/slideLayout" Target="../slideLayouts/slideLayout1.xml"/></Relationships>'});
  f.push({name:'ppt/slideLayouts/slideLayout1.xml',data:'<?xml version="1.0" encoding="UTF-8"?><p:sldLayout xmlns:a="'+NS_A+'" xmlns:r="'+NS_R+'" xmlns:p="'+NS_P+'" type="blank" preserve="1"><p:cSld><p:spTree><p:nvGrpSpPr><p:cNvPr id="1" name=""/><p:cNvGrpSpPr/><p:nvPr/></p:nvGrpSpPr><p:grpSpPr><a:xfrm><a:off x="0" y="0"/><a:ext cx="0" cy="0"/><a:chOff x="0" y="0"/><a:chExt cx="0" cy="0"/></a:xfrm></p:grpSpPr></p:spTree></p:cSld></p:sldLayout>'});
  f.push({name:'ppt/slideLayouts/_rels/slideLayout1.xml.rels',data:'<?xml version="1.0" encoding="UTF-8"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="'+NS_R+'/slideMaster" Target="../slideMasters/slideMaster1.xml"/></Relationships>'});
  sld.forEach(function(sd,idx){
    var bg=sd.bg||'FFFFFF';
    var headerBg=sd.headerBg||'';
    var headerH_emu=Math.round((sd.headerH||1.3)*914400);
    var titleColor=sd.titleColor||(headerBg?'FFFFFF':'1F2937');
    var bodyColor=sd.bodyColor||(bg!=='FFFFFF'?'F3F4F6':'374151');
    var subtitleColor=sd.subtitleColor||(bg!=='FFFFFF'?'A3A3A3':'6B7280');
    var accentColor=sd.accentColor||'0062FF';
    var shapes=[],shId=2;
    if(headerBg){
      shapes.push('<p:sp><p:nvSpPr><p:cNvPr id="'+shId+'" name="hdr"/><p:cNvSpPr/><p:nvPr/></p:nvSpPr>'+
        '<p:spPr><a:xfrm><a:off x="0" y="0"/><a:ext cx="'+W+'" cy="'+headerH_emu+'"/></a:xfrm>'+
        '<a:prstGeom prst="rect"><a:avLst/></a:prstGeom>'+
        '<a:solidFill><a:srgbClr val="'+headerBg+'"/></a:solidFill>'+
        '<a:ln><a:noFill/></a:ln></p:spPr>'+
        '<p:txBody><a:bodyPr/><a:lstStyle/><a:p/></p:txBody></p:sp>');
      shId++;
    }
    var py=headerBg?Math.round(0.2*914400):Math.round(0.3*914400);
    if(sd.title){
      shapes.push('<p:sp><p:nvSpPr><p:cNvPr id="'+shId+'" name="ttl"/><p:cNvSpPr><a:spLocks noGrp="1"/></p:cNvSpPr><p:nvPr/></p:nvSpPr>'+
        '<p:spPr><a:xfrm><a:off x="457200" y="'+py+'"/><a:ext cx="11277600" cy="594360"/></a:xfrm>'+
        '<a:prstGeom prst="rect"><a:avLst/></a:prstGeom><a:noFill/></p:spPr>'+
        '<p:txBody><a:bodyPr/><a:lstStyle/><a:p><a:r>'+
        '<a:rPr lang="en-US" sz="2800" b="1" dirty="0"><a:solidFill><a:srgbClr val="'+titleColor+'"/></a:solidFill></a:rPr>'+
        '<a:t>'+_ivXe(sd.title)+'</a:t></a:r></a:p></p:txBody></p:sp>');
      shId++;
      py=headerBg?(headerH_emu+Math.round(0.15*914400)):(py+Math.round(0.85*914400));
    }
    if(sd.subtitle){
      shapes.push('<p:sp><p:nvSpPr><p:cNvPr id="'+shId+'" name="sub"/><p:cNvSpPr/><p:nvPr/></p:nvSpPr>'+
        '<p:spPr><a:xfrm><a:off x="457200" y="'+py+'"/><a:ext cx="11277600" cy="457200"/></a:xfrm>'+
        '<a:prstGeom prst="rect"><a:avLst/></a:prstGeom><a:noFill/></p:spPr>'+
        '<p:txBody><a:bodyPr/><a:lstStyle/><a:p><a:r>'+
        '<a:rPr lang="en-US" sz="1600" i="1" dirty="0"><a:solidFill><a:srgbClr val="'+subtitleColor+'"/></a:solidFill></a:rPr>'+
        '<a:t>'+_ivXe(sd.subtitle)+'</a:t></a:r></a:p></p:txBody></p:sp>');
      shId++;
      py+=Math.round(0.55*914400);
    }
    if(sd.items&&sd.items.length){
      var paras=sd.items.map(function(it){
        return '<a:p><a:pPr marL="342900" indent="-342900">'+
          '<a:buClr><a:srgbClr val="'+accentColor+'"/></a:buClr>'+
          '<a:buChar char="&#x2022;"/></a:pPr><a:r>'+
          '<a:rPr lang="en-US" sz="1400" dirty="0"><a:solidFill><a:srgbClr val="'+bodyColor+'"/></a:solidFill></a:rPr>'+
          '<a:t>'+_ivXe(String(it))+'</a:t></a:r></a:p>';
      }).join('');
      var ith=Math.max(457200,sd.items.length*480000);
      shapes.push('<p:sp><p:nvSpPr><p:cNvPr id="'+shId+'" name="itm"/><p:cNvSpPr/><p:nvPr/></p:nvSpPr>'+
        '<p:spPr><a:xfrm><a:off x="457200" y="'+py+'"/><a:ext cx="11277600" cy="'+ith+'"/></a:xfrm>'+
        '<a:prstGeom prst="rect"><a:avLst/></a:prstGeom><a:noFill/></p:spPr>'+
        '<p:txBody><a:bodyPr/><a:lstStyle/>'+paras+'</p:txBody></p:sp>');
      shId++;
      py+=ith+Math.round(0.2*914400);
    }
    if(sd.stats&&sd.stats.length){
      var n=sd.stats.length;
      var sw=Math.min(Math.round(3.5*914400),Math.floor(11277600/n)-50000);
      var statBg=bg!=='FFFFFF'?'2D3748':'F3F4F6';
      sd.stats.forEach(function(st,i){
        var sx=457200+i*(sw+50000);
        shapes.push('<p:sp><p:nvSpPr><p:cNvPr id="'+shId+'" name="sb'+i+'"/><p:cNvSpPr/><p:nvPr/></p:nvSpPr>'+
          '<p:spPr><a:xfrm><a:off x="'+sx+'" y="'+py+'"/><a:ext cx="'+sw+'" cy="822960"/></a:xfrm>'+
          '<a:prstGeom prst="rect"><a:avLst/></a:prstGeom>'+
          '<a:solidFill><a:srgbClr val="'+statBg+'"/></a:solidFill>'+
          '<a:ln><a:noFill/></a:ln></p:spPr>'+
          '<p:txBody><a:bodyPr/><a:lstStyle/><a:p/></p:txBody></p:sp>');shId++;
        shapes.push('<p:sp><p:nvSpPr><p:cNvPr id="'+shId+'" name="sv'+i+'"/><p:cNvSpPr/><p:nvPr/></p:nvSpPr>'+
          '<p:spPr><a:xfrm><a:off x="'+(sx+50000)+'" y="'+(py+60000)+'"/><a:ext cx="'+(sw-100000)+'" cy="400000"/></a:xfrm>'+
          '<a:prstGeom prst="rect"><a:avLst/></a:prstGeom><a:noFill/></p:spPr>'+
          '<p:txBody><a:bodyPr/><a:lstStyle/><a:p><a:pPr algn="ctr"/><a:r>'+
          '<a:rPr lang="en-US" sz="2400" b="1" dirty="0"><a:solidFill><a:srgbClr val="'+accentColor+'"/></a:solidFill></a:rPr>'+
          '<a:t>'+_ivXe(String(st.value||''))+'</a:t></a:r></a:p></p:txBody></p:sp>');shId++;
        shapes.push('<p:sp><p:nvSpPr><p:cNvPr id="'+shId+'" name="sl'+i+'"/><p:cNvSpPr/><p:nvPr/></p:nvSpPr>'+
          '<p:spPr><a:xfrm><a:off x="'+(sx+50000)+'" y="'+(py+480000)+'"/><a:ext cx="'+(sw-100000)+'" cy="280000"/></a:xfrm>'+
          '<a:prstGeom prst="rect"><a:avLst/></a:prstGeom><a:noFill/></p:spPr>'+
          '<p:txBody><a:bodyPr/><a:lstStyle/><a:p><a:pPr algn="ctr"/><a:r>'+
          '<a:rPr lang="en-US" sz="900" dirty="0"><a:solidFill><a:srgbClr val="'+bodyColor+'"/></a:solidFill></a:rPr>'+
          '<a:t>'+_ivXe(String(st.label||''))+'</a:t></a:r></a:p></p:txBody></p:sp>');shId++;
      });
      py+=Math.round(1.05*914400);
    }
    if(sd.table&&sd.table.length){
      var cc=Math.max(1,Math.max.apply(null,sd.table.map(function(r){return(r||[]).length;})));
      var cw=Math.floor(11277600/cc);
      var gridXml='';for(var gi=0;gi<cc;gi++)gridXml+='<a:gridCol w="'+cw+'"/>';
      var hdrBg=sd.tableHeaderBg||(bg!=='FFFFFF'?'374151':'E5E7EB');
      var hdrColor=sd.tableHeaderColor||(bg!=='FFFFFF'?'FFFFFF':'1F2937');
      var brdColor=bg!=='FFFFFF'?'4B5563':'D1D5DB';
      var trows=sd.table.map(function(row,ri){
        var cells='';
        for(var ci=0;ci<cc;ci++){
          var cv=(row||[])[ci];cv=cv==null?'':String(cv);
          var isHdr=ri===0;
          var cellColor=isHdr?hdrColor:bodyColor;
          var brd='<a:lnL w="9525"><a:solidFill><a:srgbClr val="'+brdColor+'"/></a:solidFill></a:lnL>'+
            '<a:lnR w="9525"><a:solidFill><a:srgbClr val="'+brdColor+'"/></a:solidFill></a:lnR>'+
            '<a:lnT w="9525"><a:solidFill><a:srgbClr val="'+brdColor+'"/></a:solidFill></a:lnT>'+
            '<a:lnB w="9525"><a:solidFill><a:srgbClr val="'+brdColor+'"/></a:solidFill></a:lnB>';
          cells+='<a:tc><a:txBody><a:bodyPr/><a:lstStyle/><a:p><a:r>'+
            '<a:rPr lang="en-US" sz="1100"'+(isHdr?' b="1"':'')+'>'+
            '<a:solidFill><a:srgbClr val="'+cellColor+'"/></a:solidFill></a:rPr>'+
            '<a:t>'+_ivXe(cv)+'</a:t></a:r></a:p></a:txBody>'+
            '<a:tcPr>'+(isHdr?'<a:solidFill><a:srgbClr val="'+hdrBg+'"/></a:solidFill>':'')+brd+'</a:tcPr></a:tc>';
        }
        return '<a:tr h="370840">'+cells+'</a:tr>';
      }).join('');
      var th=sd.table.length*370840;
      shapes.push('<p:graphicFrame><p:nvGraphicFramePr><p:cNvPr id="'+shId+'" name="tbl"/><p:cNvGraphicFramePr><a:graphicFrameLocks noGrp="1"/></p:cNvGraphicFramePr><p:nvPr/></p:nvGraphicFramePr><p:xfrm><a:off x="457200" y="'+py+'"/><a:ext cx="11277600" cy="'+th+'"/></p:xfrm><a:graphic><a:graphicData uri="http://schemas.openxmlformats.org/drawingml/2006/table"><a:tbl><a:tblPr firstRow="1" bandRow="1"/><a:tblGrid>'+gridXml+'</a:tblGrid>'+trows+'</a:tbl></a:graphicData></a:graphic></p:graphicFrame>');
      shId++;
    }
    if(sd.footer){
      shapes.push('<p:sp><p:nvSpPr><p:cNvPr id="'+shId+'" name="ft"/><p:cNvSpPr/><p:nvPr/></p:nvSpPr>'+
        '<p:spPr><a:xfrm><a:off x="457200" y="'+Math.round(6.15*914400)+'"/><a:ext cx="11277600" cy="274320"/></a:xfrm>'+
        '<a:prstGeom prst="rect"><a:avLst/></a:prstGeom><a:noFill/></p:spPr>'+
        '<p:txBody><a:bodyPr/><a:lstStyle/><a:p><a:r>'+
        '<a:rPr lang="en-US" sz="800" i="1" dirty="0"><a:solidFill><a:srgbClr val="'+(bg!=='FFFFFF'?'6B7280':'9CA3AF')+'"/></a:solidFill></a:rPr>'+
        '<a:t>'+_ivXe(sd.footer)+'</a:t></a:r></a:p></p:txBody></p:sp>');
      shId++;
    }
    var bgXml=bg!=='FFFFFF'?'<p:bg><p:bgPr><a:solidFill><a:srgbClr val="'+bg+'"/></a:solidFill><a:effectLst/></p:bgPr></p:bg>':'';
    f.push({name:'ppt/slides/slide'+(idx+1)+'.xml',
      data:'<?xml version="1.0" encoding="UTF-8"?><p:sld xmlns:a="'+NS_A+'" xmlns:r="'+NS_R+'" xmlns:p="'+NS_P+'">'+
        '<p:cSld>'+bgXml+'<p:spTree>'+
        '<p:nvGrpSpPr><p:cNvPr id="1" name=""/><p:cNvGrpSpPr/><p:nvPr/></p:nvGrpSpPr>'+
        '<p:grpSpPr><a:xfrm><a:off x="0" y="0"/><a:ext cx="0" cy="0"/><a:chOff x="0" y="0"/><a:chExt cx="0" cy="0"/></a:xfrm></p:grpSpPr>'+
        shapes.join('')+'</p:spTree></p:cSld></p:sld>'});
    f.push({name:'ppt/slides/_rels/slide'+(idx+1)+'.xml.rels',data:'<?xml version="1.0" encoding="UTF-8"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="'+NS_R+'/slideLayout" Target="../slideLayouts/slideLayout1.xml"/></Relationships>'});
  });
  _ivDl(_ivZip(f),base+'.pptx');
  try{toast('PowerPoint ready (built-in)','success');}catch(e){}
}

// ---------------------------------------------------------------------------
// Pure OOXML .docx builder — parses HTML and converts to WordprocessingML
// ---------------------------------------------------------------------------
function _ivDocxOoxml(htmlContent,base){
  var WNS='http://schemas.openxmlformats.org/wordprocessingml/2006/main';
  var pd=(new DOMParser()).parseFromString('<body>'+(htmlContent||'')+'</body>','text/html');
  var wbody='';
  function wp(text,bold,sz){return '<w:p><w:r><w:rPr>'+(bold?'<w:b/>':'')+'<w:sz>'+(sz||2200)+'</w:sz></w:rPr><w:t xml:space="preserve">'+_ivXe(text)+'</w:t></w:r></w:p>';}
  function wtable(tbl){
    var rows=tbl.querySelectorAll('tr');
    if(!rows.length)return '';
    var x='<w:tbl><w:tblPr><w:tblStyle w:val="TableGrid"/><w:tblW w:w="0" w:type="auto"/></w:tblPr><w:tblGrid/>';
    rows.forEach(function(tr,ri){
      x+='<w:tr>';
      tr.querySelectorAll('th,td').forEach(function(td){
        var h=ri===0||td.tagName==='TH';
        x+='<w:tc><w:tcPr>'+(h?'<w:shd w:val="clear" w:color="auto" w:fill="E5E7EB"/>':'')+'</w:tcPr>'+
          '<w:p><w:r><w:rPr>'+(h?'<w:b/>':'')+'<w:sz>2000</w:sz></w:rPr>'+
          '<w:t xml:space="preserve">'+_ivXe(td.textContent.trim())+'</w:t></w:r></w:p></w:tc>';
      });
      x+='</w:tr>';
    });
    return x+'</w:tbl><w:p/>';
  }
  function traverse(nodes){
    Array.prototype.forEach.call(nodes,function(n){
      if(n.nodeType===3){var t=n.textContent.trim();if(t)wbody+=wp(t);}
      else if(n.nodeType===1){
        var tag=n.tagName;
        // Skip non-content elements and SVG (tagName is lowercase in SVG namespace)
        if(tag==='STYLE'||tag==='SCRIPT'||tag==='svg'||tag==='SVG'||(n.namespaceURI&&n.namespaceURI.indexOf('svg')>-1))return;
        if(tag==='H1')wbody+=wp(n.textContent.trim(),true,3200);
        else if(tag==='H2')wbody+=wp(n.textContent.trim(),true,2800);
        else if(tag==='H3')wbody+=wp(n.textContent.trim(),true,2400);
        else if(tag==='TABLE')wbody+=wtable(n);
        else if(tag==='P'){var t2=n.textContent.trim();if(t2)wbody+=wp(t2);}
        else if(tag==='UL'||tag==='OL'){Array.prototype.forEach.call(n.querySelectorAll('li'),function(li){wbody+=wp('\u2022 '+li.textContent.trim());});}
        else if(n.childNodes&&n.childNodes.length){traverse(n.childNodes);}
        else{var t3=n.textContent.trim();if(t3)wbody+=wp(t3);}
      }
    });
  }
  traverse(pd.body.childNodes);
  if(!wbody)wbody='<w:p><w:r><w:t>'+_ivXe(pd.body.textContent.trim())+'</w:t></w:r></w:p>';
  var docXml='<?xml version="1.0" encoding="UTF-8"?><w:document xmlns:w="'+WNS+'"><w:body>'+wbody+
    '<w:sectPr><w:pgSz w:w="12240" w:h="15840"/></w:sectPr></w:body></w:document>';
  var styles='<?xml version="1.0" encoding="UTF-8"?><w:styles xmlns:w="'+WNS+'">'+
    '<w:style w:type="table" w:styleId="TableGrid"><w:name w:val="Table Grid"/><w:tblPr>'+
    '<w:tblBorders><w:top w:val="single" w:sz="4" w:space="0" w:color="auto"/>'+
    '<w:left w:val="single" w:sz="4" w:space="0" w:color="auto"/>'+
    '<w:bottom w:val="single" w:sz="4" w:space="0" w:color="auto"/>'+
    '<w:right w:val="single" w:sz="4" w:space="0" w:color="auto"/>'+
    '<w:insideH w:val="single" w:sz="4" w:space="0" w:color="auto"/>'+
    '<w:insideV w:val="single" w:sz="4" w:space="0" w:color="auto"/>'+
    '</w:tblBorders></w:tblPr></w:style></w:styles>';
  var f=[
    {name:'[Content_Types].xml',data:'<?xml version="1.0" encoding="UTF-8"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/><Override PartName="/word/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.styles+xml"/></Types>'},
    {name:'_rels/.rels',data:'<?xml version="1.0" encoding="UTF-8"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/></Relationships>'},
    {name:'word/document.xml',data:docXml},
    {name:'word/styles.xml',data:styles},
    {name:'word/_rels/document.xml.rels',data:'<?xml version="1.0" encoding="UTF-8"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/></Relationships>'}
  ];
  _ivDl(_ivZip(f),base+'.docx');
  try{toast('Word document ready (built-in)','success');}catch(e){}
}

// ---------------------------------------------------------------------------
// Download functions — CDN library first, pure OOXML fallback if CDN blocked
// ---------------------------------------------------------------------------

// Usage: downloadAsExcel([{name:'Sheet1', headers:['Col A','Col B'], rows:[['a1','b1']]}], 'myfile')
function downloadAsExcel(sheets, filename) {
  var base=(filename||'export').replace(/\.xlsx$/i,'');
  function _go(){
    var wb=XLSX.utils.book_new();
    (sheets||[]).forEach(function(s){
      var ws=XLSX.utils.aoa_to_sheet([s.headers||[]].concat(s.rows||[]));
      XLSX.utils.book_append_sheet(wb,ws,(s.name||'Sheet1').substring(0,31));
    });
    try{XLSX.writeFile(wb,base+'.xlsx');toast('Excel downloading...','success');}
    catch(e){try{toast('SheetJS error — using built-in','warn');}catch(_){}  _ivXlsxOoxml(sheets,base);}
  }
  if(window.XLSX){_go();return;}
  var s=document.createElement('script');
  s.src='https://cdn.jsdelivr.net/npm/xlsx@0.18.5/dist/xlsx.full.min.js';
  s.onload=_go;
  s.onerror=function(){try{toast('CDN unavailable — generating Excel locally','info');}catch(e){}  _ivXlsxOoxml(sheets,base);};
  document.head.appendChild(s);
}

// Slide schema: {title, subtitle, bg, headerBg, headerH, titleColor, bodyColor,
//   subtitleColor, accentColor, items:['...'], stats:[{value,label},...],
//   table:[[cell,...],...], footer, tableHeaderBg, tableHeaderColor}
// Usage: downloadAsPPTX([{title:'S1', bg:'1F2937', headerBg:'0062FF', items:['Pt']}], 'file')
function downloadAsPPTX(slides, filename) {
  var base=(filename||'export').replace(/\.pptx$/i,'');
  function _go(){
    var pptx=new PptxGenJS();pptx.layout='LAYOUT_WIDE';
    (slides||[]).forEach(function(sd){
      var slide=pptx.addSlide();
      var bg=sd.bg||'FFFFFF';
      var headerBg=sd.headerBg||'';
      var headerH=sd.headerH||1.3;
      var titleColor=sd.titleColor||(headerBg?'FFFFFF':'1F2937');
      var bodyColor=sd.bodyColor||(bg!=='FFFFFF'?'F3F4F6':'374151');
      var subtitleColor=sd.subtitleColor||(bg!=='FFFFFF'?'A3A3A3':'6B7280');
      var accentColor=sd.accentColor||'0062FF';
      slide.background={color:bg};
      if(headerBg){slide.addShape(pptx.ShapeType.rect,{x:0,y:0,w:'100%',h:headerH,fill:{color:headerBg},line:{type:'none'}});}
      var y=headerBg?0.2:0.3;
      if(sd.title){slide.addText(sd.title,{x:0.4,y:y,w:'90%',h:0.65,fontSize:22,bold:true,color:titleColor});y=headerBg?(headerH+0.15):(y+0.85);}
      if(sd.subtitle){slide.addText(sd.subtitle,{x:0.4,y:y,w:'90%',h:0.4,fontSize:14,italic:true,color:subtitleColor});y+=0.5;}
      if(sd.items&&sd.items.length){sd.items.forEach(function(it){slide.addText(String(it),{x:0.6,y:y,w:'88%',h:0.38,fontSize:12,color:bodyColor,bullet:{type:'bullet',color:accentColor}});y+=0.4;});y+=0.1;}
      if(sd.stats&&sd.stats.length){
        var n=sd.stats.length,sw=Math.min(3.5,12.3/n)-0.1,statBg=bg!=='FFFFFF'?'2D3748':'F3F4F6';
        sd.stats.forEach(function(st,i){var sx=0.4+i*(sw+0.1);
          slide.addShape(pptx.ShapeType.rect,{x:sx,y:y,w:sw,h:0.9,fill:{color:statBg},line:{type:'none'}});
          slide.addText(String(st.value||''),{x:sx+0.05,y:y+0.06,w:sw-0.1,h:0.44,fontSize:22,bold:true,color:accentColor,align:'center'});
          slide.addText(String(st.label||''),{x:sx+0.05,y:y+0.52,w:sw-0.1,h:0.3,fontSize:9,color:bodyColor,align:'center'});
        });y+=1.05;
      }
      if(sd.table&&sd.table.length){
        var hdrBg=sd.tableHeaderBg||(bg!=='FFFFFF'?'374151':'E5E7EB');
        var hdrColor=sd.tableHeaderColor||(bg!=='FFFFFF'?'FFFFFF':'1F2937');
        var rows=sd.table.map(function(row,ri){return row.map(function(cell){return{text:String(cell==null?'':cell),options:ri===0?{bold:true,fill:{color:hdrBg},color:hdrColor}:{color:bodyColor}};});});
        slide.addTable(rows,{x:0.4,y:y,w:12.3,fontSize:11,border:{type:'solid',color:bg!=='FFFFFF'?'4B5563':'D1D5DB',pt:0.5}});
      }
      if(sd.footer){slide.addText(sd.footer,{x:0.4,y:6.2,w:'90%',h:0.3,fontSize:8,color:bg!=='FFFFFF'?'6B7280':'9CA3AF',italic:true});}
    });
    pptx.writeFile({fileName:base+'.pptx'}).then(function(){try{toast('PowerPoint downloading...','success');}catch(e){}});
  }
  if(window.PptxGenJS){_go();return;}
  var s=document.createElement('script');
  s.src='https://cdn.jsdelivr.net/npm/pptxgenjs@3.12.0/dist/pptxgen.bundle.js';
  s.onload=_go;
  s.onerror=function(){try{toast('CDN unavailable — generating PPTX locally','info');}catch(e){}  _ivPptxOoxml(slides,base);};
  document.head.appendChild(s);
}

// Usage: downloadAsDOCX(htmlString, 'myfile')
// htmlString is the HTML body content to export; pass null to auto-export the rendered visualization.
function downloadAsDOCX(htmlContent, filename) {
  var base=(filename||'export').replace(/\.docx$/i,'');
  var body=htmlContent||(document.getElementById('iv-render')?document.getElementById('iv-render').innerHTML:document.body.innerHTML);
  function _go(){
    var full='<!DOCTYPE html><html><head><meta charset="UTF-8"><style>'+
      'body{font-family:Calibri,Arial,sans-serif;font-size:11pt;color:#1F2937}'+
      'table{border-collapse:collapse;width:100%;margin:12pt 0}'+
      'th,td{border:1px solid #D1D5DB;padding:6px 10px;text-align:left;font-size:10pt}'+
      'th{background:#F3F4F6;font-weight:bold}'+
      'h1{font-size:18pt;font-weight:600}h2{font-size:14pt}h3{font-size:12pt}p{margin:0 0 8pt}'+
      '</style></head><body>'+body+'</body></html>';
    var blob=htmlDocx.asBlob(full),url=URL.createObjectURL(blob),a=document.createElement('a');
    a.href=url;a.download=base+'.docx';a.style.display='none';
    document.body.appendChild(a);a.click();
    setTimeout(function(){a.remove();URL.revokeObjectURL(url);},60000);
    try{toast('Word document downloading...','success');}catch(e){}
  }
  if(window.htmlDocx){_go();return;}
  var s=document.createElement('script');
  s.src='https://cdn.jsdelivr.net/npm/html-docx-js@0.3.1/dist/html-docx.js';
  s.onload=_go;
  s.onerror=function(){try{toast('CDN unavailable — generating DOCX locally','info');}catch(e){}  _ivDocxOoxml(body,base);};
  document.head.appendChild(s);
}
</script>
"""


# ---------------------------------------------------------------------------
# Happy chime on live-stream completion
# ---------------------------------------------------------------------------
# Injected into BODY_SCRIPTS via a /*__CHIME_BLOCK__*/ placeholder so the
# ``chime`` valve can strip it out entirely when disabled — no bytes
# shipped, not just a silent no-op. finalize() calls playDoneSound() inside
# a ``typeof playDoneSound === 'function'`` guard, so omission is safe.
# ---------------------------------------------------------------------------

CHIME_SCRIPT = """
// --- Happy chime ---
// C-major arpeggio (C5 → E5 → G5) on sine oscillators with exponential
// decay. ~300 ms, gentle volume. Silent no-op if AudioContext is still
// suspended (no prior user gesture).
var _ivAudioCtx = null;
function playDoneSound() {
  try {
    var AC = window.AudioContext || window.webkitAudioContext;
    if (!AC) return;
    if (!_ivAudioCtx) _ivAudioCtx = new AC();
    var ctx = _ivAudioCtx;
    if (ctx.state === 'suspended') { try { ctx.resume(); } catch(e) {} }
    var now = ctx.currentTime;
    var notes = [523.25, 659.25, 783.99]; // C5, E5, G5
    notes.forEach(function(freq, i) {
      var osc = ctx.createOscillator();
      var gain = ctx.createGain();
      osc.type = 'sine';
      osc.frequency.value = freq;
      var start = now + i * 0.09;
      var dur = 0.35;
      gain.gain.setValueAtTime(0.0001, start);
      gain.gain.exponentialRampToValueAtTime(0.16, start + 0.015);
      gain.gain.exponentialRampToValueAtTime(0.0001, start + dur);
      osc.connect(gain).connect(ctx.destination);
      osc.start(start);
      osc.stop(start + dur + 0.02);
    });
  } catch(e) {}
}
"""

# ---------------------------------------------------------------------------
# STRICT-mode script — strip query params from openLink / window.open /
# <a href>. Supplementary hygiene only; the real exfil blocker is the
# CSP connect-src directive. Paths, fragments, and location.assign are
# not intercepted.
# ---------------------------------------------------------------------------

STRICT_SECURITY_SCRIPT = """
<script>
(function() {
  function stripParams(rawUrl) {
    try { var u = new URL(rawUrl, location.href); u.search = ''; return u.toString(); }
    catch(e) { return rawUrl; }
  }

  // Override openLink to strip query/hash parameters
  var _origOpenLink = window.openLink;
  window.openLink = function(url) {
    _origOpenLink(stripParams(url));
  };

  // Override window.open to strip query parameters
  var _origOpen = window.open;
  window.open = function(url) {
    arguments[0] = stripParams(url);
    return _origOpen.apply(this, arguments);
  };

  // Strip params from all existing and future <a> tags
  function sanitizeLinks(root) {
    (root.querySelectorAll ? root : document).querySelectorAll('a[href]').forEach(function(a) {
      a.href = stripParams(a.href);
    });
  }
  sanitizeLinks(document);
  new MutationObserver(function(muts) {
    muts.forEach(function(m) {
      m.addedNodes.forEach(function(n) { if (n.nodeType === 1) sanitizeLinks(n); });
    });
  }).observe(document.body, { childList: true, subtree: true });
})();
</script>
"""

# ---------------------------------------------------------------------------
# STREAMING mode — text-marker observer (CodeBlock-free)
# ---------------------------------------------------------------------------
# Model emits plain-text @@@VIZ-START … @@@VIZ-END markers (NOT a code
# fence — that path routed through CodeMirror's virtualizer and lost
# content on scroll / refresh). Markdown renders them as ordinary
# paragraph/html tokens, so nothing we scan goes through CodeBlock.
#
# Observer loop:
#   1. Find enclosing message via frame.closest('[id^="message-"]').
#   2. Read msg.textContent (skipping <details type="tool_calls"> etc).
#   3. Regex-extract the idx-th @@@VIZ-START … @@@VIZ-END block.
#   4. Safe-cut partial HTML, reconcile into #iv-render.
#   5. Walk the message DOM to hide the raw markers + between-marker
#      content inline (display:none !important).
#
# idx comes from the embed container id "{messageId}-embeds-{N}", so
# multiple visualizations in the same message claim in order.
#
# Requires iframe Sandbox Allow Same Origin.
# ---------------------------------------------------------------------------

STREAMING_OBSERVER_SCRIPT = """
<script>
(function() {
  'use strict';
  // Delimiters — must match SKILL.md exactly. Chosen because:
  //   * no collision with ``` / ~~~ / ::: / $$ / --- / *** / ===
  //   * markdown tokenizes them as ordinary paragraph / html content,
  //     never as a code block, so Open WebUI's CodeBlock.svelte +
  //     CodeMirror never touch them → no virtualization edge cases.
  var START_MARK = '@@@VIZ-START';
  var END_MARK = '@@@VIZ-END';
  // Regex finds one block. Non-greedy, handles unclosed (streaming) by
  // falling through to end-of-input. Match [1] is the inner SVG source.
  // `+?` (not `*?`) forces at least 1 char of body — otherwise, the
  // instant the model emits just `@@@VIZ-START` (no content yet), the
  // `$` alternation matches an empty capture, readSource returns "",
  // the 800 ms idle timer fires, finalize("") runs, and the reconciler
  // wipes the render area → thin-strip regression.
  var BLOCK_RE = /@@@VIZ-START\\n?([\\s\\S]+?)(?:\\n?@@@VIZ-END|$)/g;

  var renderArea = document.getElementById('iv-render');
  if (!renderArea) return;

  // Require same-origin access to parent — otherwise show a helpful notice.
  var hasParentAccess = false;
  try { void parent.document.body; hasParentAccess = true; } catch(e) {}
  if (!hasParentAccess) {
    // _ivLang / _ivErrTitleStr / _ivErrBodyStr come from BODY_SCRIPTS
    // which runs before this observer script.
    var _lang = (typeof _ivLang !== 'undefined' && _ivLang) || 'en';
    var _t = (typeof _ivErrTitleStr !== 'undefined' &&
              (_ivErrTitleStr[_lang] || _ivErrTitleStr.en)) ||
             'Streaming visualization unavailable';
    var _b = (typeof _ivErrBodyStr !== 'undefined' &&
              (_ivErrBodyStr[_lang] || _ivErrBodyStr.en)) ||
             'Open User Settings \u2192 Interface, scroll down, and enable ' +
             '"Allow iframe same origin" to use streaming mode.';
    function _esc(s) {
      return String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;')
                      .replace(/>/g, '&gt;').replace(/"/g, '&quot;');
    }
    renderArea.innerHTML =
      '<div style="padding:16px 18px;border:0.5px solid var(--color-border-tertiary);' +
      'border-radius:var(--radius-md);background:var(--color-bg-secondary);' +
      'color:var(--color-text-primary);font-size:13px;line-height:1.5;">' +
      '<div style="font-weight:500;margin-bottom:6px;">' + _esc(_t) + '</div>' +
      '<div style="color:var(--color-text-secondary);">' + _esc(_b) + '</div></div>';
    return;
  }

  // Claim: each tool call renders an embed at "{messageId}-embeds-{N}".
  // The N-th embed owns the N-th @@@VIZ-START/END pair in the message.

  var myMessage = null;
  var myIndex = null;        // this wrapper's position among embed siblings
  var lastRawText = '';
  var lastSafeRendered = '';
  var finalizeTimer = null;
  var finalized = false;

  function findMyMessage() {
    if (myMessage && parent.document.contains(myMessage)) return myMessage;
    try {
      var f = window.frameElement;
      if (!f) return null;
      myMessage = f.closest && f.closest('[id^="message-"]');
      return myMessage;
    } catch(e) { return null; }
  }

  function determineIndex() {
    if (myIndex !== null) return myIndex;
    try {
      var f = window.frameElement;
      if (!f) return null;
      var embedContainer = f.closest && f.closest('[id*="-embeds-"]');
      if (embedContainer) {
        var m = embedContainer.id.match(/-embeds-(\\d+)$/);
        if (m) { myIndex = parseInt(m[1], 10); return myIndex; }
      }
      // Fallback: count preceding sibling iframes within the same message.
      var msg = findMyMessage();
      if (msg) {
        var iframes = msg.querySelectorAll('iframe');
        for (var i = 0, n = 0; i < iframes.length; i++) {
          if (iframes[i] === f) { myIndex = n; return myIndex; }
          n++;
        }
      }
    } catch(e) {}
    return null;
  }

  // Concatenate the searchable text of `msg`, SKIPPING any text that
  // lives inside a <details> subtree (Open WebUI renders tool-call
  // results in collapsed <details>, and OUR own result_context
  // includes a literal @@@VIZ-START / @@@VIZ-END example that would
  // otherwise be matched first by the regex and rendered instead of
  // the model's real content).
  function getSearchableText(msg) {
    var out = '';
    try {
      var walker = parent.document.createTreeWalker(
        msg, NodeFilter.SHOW_TEXT, {
          acceptNode: function(n) {
            var p = n.parentNode;
            while (p && p !== msg) {
              if (p.nodeType === 1 && p.tagName === 'DETAILS') {
                // Only skip tool-result / reasoning / code_execution
                // details — those carry our own result_context example
                // markers. Other <details> (including the bare
                // __DETAIL_N__ placeholder shims Open WebUI emits
                // during streaming before it substitutes real tool
                // markup) DO carry the model's actual response and
                // must remain visible to the scanner.
                var t = p.getAttribute && p.getAttribute('type');
                if (t === 'tool_calls' || t === 'reasoning' ||
                    t === 'code_execution' || t === 'code_interpreter') {
                  return NodeFilter.FILTER_REJECT;
                }
              }
              p = p.parentNode;
            }
            return NodeFilter.FILTER_ACCEPT;
          }
        }
      );
      var t;
      while ((t = walker.nextNode())) out += t.nodeValue || '';
    } catch(e) { return msg.textContent || ''; }
    return out;
  }

  // Read the full assistant message text and return the myIndex-th VIZ
  // block's inner content (or null if not yet present).
  function readSource() {
    var msg = findMyMessage();
    if (!msg) return null;
    var idx = determineIndex();
    if (idx === null) idx = 0;
    var text = getSearchableText(msg);
    BLOCK_RE.lastIndex = 0;
    var m, n = 0;
    while ((m = BLOCK_RE.exec(text)) !== null) {
      if (n === idx) return m[1];
      n++;
      // Guard against zero-length match infinite loop
      if (m.index === BLOCK_RE.lastIndex) BLOCK_RE.lastIndex++;
    }
    return null;
  }

  // Hide markers + between-marker content with inline
  // `display:none !important` (beats every stylesheet, survives Svelte
  // updates). Bare text nodes that marked emits for inline-html get
  // wrapped in a hidden <span data-iv-chat-wrap>. Single-pass walker
  // with a small state machine (OUTSIDE → START → INSIDE → END →
  // OUTSIDE). Runs every tick, idempotent.

  function hideEl(el) {
    if (!el || el.nodeType !== 1) return;
    if (el.getAttribute('data-iv-chat-hidden') !== '1') {
      el.setAttribute('data-iv-chat-hidden', '1');
    }
    // setProperty(_, _, 'important') emits `display: none !important`
    // as an inline style — beats any stylesheet without specificity
    // fights, and survives DOM re-renders that keep the element alive.
    try { el.style.setProperty('display', 'none', 'important'); } catch(e) {}
  }

  function wrapAndHideText(textNode) {
    var parent = textNode.parentNode;
    if (!parent) return;
    if (parent.nodeType === 1 &&
        parent.getAttribute &&
        parent.getAttribute('data-iv-chat-wrap') === '1') return;
    try {
      var doc = parent.ownerDocument || document;
      var wrap = doc.createElement('span');
      wrap.setAttribute('data-iv-chat-wrap', '1');
      wrap.setAttribute('data-iv-chat-hidden', '1');
      wrap.style.setProperty('display', 'none', 'important');
      parent.insertBefore(wrap, textNode);
      wrap.appendChild(textNode);
    } catch(e) {}
  }

  // Nearest ancestor that's a block-ish container — we prefer hiding
  // block elements over inline ones so we don't leave empty block
  // boxes visible. Stops at `stopAt` (the message root) — never hides
  // the message itself.
  function nearestBlockAncestor(el, stopAt) {
    var BLOCK = { P:1, DIV:1, SECTION:1, ARTICLE:1, BLOCKQUOTE:1,
                  PRE:1, H1:1, H2:1, H3:1, H4:1, H5:1, H6:1,
                  UL:1, OL:1, LI:1, TABLE:1 };
    var cur = el;
    while (cur && cur !== stopAt) {
      if (cur.nodeType === 1 && BLOCK[cur.tagName]) return cur;
      cur = cur.parentNode;
    }
    return null;
  }

  function hideMarkerRange() {
    var msg = findMyMessage();
    if (!msg) return;
    var myFrame = window.frameElement;

    // Find my own embed container so we NEVER hide it — our iframe
    // lives inside it. Everything else in the message body is fair game.
    var myEmbedContainer = null;
    try { myEmbedContainer = myFrame && myFrame.closest('[id*="-embeds-"]'); }
    catch(e) {}
    var embedsRoot = null;
    try { embedsRoot = myFrame && myFrame.closest('[id$="-embeds-container"]'); }
    catch(e) {}

    // Walk every text node in document order — but skip anything inside
    // a <details> subtree (Open WebUI renders tool-call results there,
    // and OUR result_context carries an example @@@VIZ-START/END pair
    // that would flip the state machine and hide unrelated chat prose).
    var walker;
    try {
      walker = parent.document.createTreeWalker(
        msg, NodeFilter.SHOW_TEXT, {
          acceptNode: function(n) {
            var p = n.parentNode;
            while (p && p !== msg) {
              if (p.nodeType === 1 && p.tagName === 'DETAILS') {
                // Only skip tool-result / reasoning / code_execution
                // details — those carry our own result_context example
                // markers. Other <details> (including the bare
                // __DETAIL_N__ placeholder shims Open WebUI emits
                // during streaming before it substitutes real tool
                // markup) DO carry the model's actual response and
                // must remain visible to the scanner.
                var t = p.getAttribute && p.getAttribute('type');
                if (t === 'tool_calls' || t === 'reasoning' ||
                    t === 'code_execution' || t === 'code_interpreter') {
                  return NodeFilter.FILTER_REJECT;
                }
              }
              p = p.parentNode;
            }
            return NodeFilter.FILTER_ACCEPT;
          }
        }
      );
    } catch(e) { return; }

    var inside = false;
    var tn;
    var toHideEls = [];
    var toWrapText = [];

    while ((tn = walker.nextNode())) {
      // Skip text nodes that live inside our embed container / iframe —
      // those are our own rendered UI, never chat content to hide.
      if (embedsRoot && embedsRoot.contains(tn)) continue;
      if (myEmbedContainer && myEmbedContainer.contains(tn)) continue;

      var tv = tn.nodeValue || '';
      var startIdx = tv.indexOf(START_MARK);
      var endIdx = tv.indexOf(END_MARK);
      var hadStartLocal = startIdx !== -1;
      var hadEndLocal = endIdx !== -1;

      var hideThis = inside || hadStartLocal || hadEndLocal;

      if (hideThis) {
        var block = nearestBlockAncestor(tn.parentNode, msg);
        if (block && block !== msg) {
          // Make sure we're not about to hide the message itself, or
          // any ancestor of our iframe.
          if (!block.contains(myFrame)) {
            toHideEls.push(block);
          } else {
            toWrapText.push(tn);
          }
        } else {
          toWrapText.push(tn);
        }
      }

      // State flip AFTER this node is processed (so the node carrying
      // END_MARK is itself hidden).
      if (hadStartLocal && hadEndLocal) {
        // Both markers in same text — treat as self-contained block,
        // remain OUTSIDE afterwards.
        inside = false;
      } else if (hadStartLocal) {
        inside = true;
      } else if (hadEndLocal) {
        inside = false;
      }
    }

    // Apply hides (deduped via the attribute check inside hideEl).
    for (var i = 0; i < toHideEls.length; i++) hideEl(toHideEls[i]);
    for (var j = 0; j < toWrapText.length; j++) wrapAndHideText(toWrapText[j]);
  }

  // Safe-cut partial-HTML parser
  //
  // Returns the last index in `text` where the parser is in a safe
  // state (TEXT, not mid-tag / mid-attribute / mid-script / mid-CDATA)
  // so we can flush the prefix to innerHTML without breakage. Depth
  // doesn't matter — the browser auto-closes open tags on innerHTML
  // assignment, which is what lets a <svg> progressively render as
  // children stream in.
  var VOID_TAGS = {area:1,base:1,br:1,col:1,embed:1,hr:1,img:1,input:1,
                   link:1,meta:1,param:1,source:1,track:1,wbr:1};
  var RAW_TAGS = {script:1, style:1};

  function findSafeCut(text) {
    var i = 0, len = text.length;
    var state = 'TEXT';
    var quote = 0;
    var safeCut = 0;
    var tagNameBuf = '';
    var tagNameEnd = false;
    var inClosingTag = false;
    var selfClosing = false;
    var rawTag = '';  // active raw-text tag close-tag name

    while (i < len) {
      var ch = text.charCodeAt(i);

      if (state === 'RAW') {
        // Inside a raw-text element. Contents are NOT a safe cut — we
        // have to wait for the full close tag before flushing, otherwise
        // innerHTML would include partial JS/CSS.
        var marker = '</' + rawTag;
        if (text.substr(i, marker.length).toLowerCase() === marker) {
          var end = text.indexOf('>', i + marker.length);
          if (end === -1) break;
          rawTag = '';
          state = 'TEXT';
          i = end + 1;
          safeCut = i;
          continue;
        }
        i++; continue;
      }

      if (state === 'TEXT') {
        if (ch === 60 /* < */) {
          // Built by concatenation so the HTML tokenizer never sees
          // the raw comment / CDATA delimiters inside this very
          // script — those tokens would put the outer parser into
          // data-escape / double-escape mode and corrupt our
          // enclosing element's boundary.
          var CMT_OPEN = '<' + '!--';
          var CMT_CLOSE = '--' + '>';
          var CDATA_OPEN = '<' + '![CDATA[';
          if (text.substr(i, 4) === CMT_OPEN) {
            var ce = text.indexOf(CMT_CLOSE, i + 4);
            if (ce === -1) break;
            i = ce + 3;
            safeCut = i;
            continue;
          }
          if (text.substr(i, 9) === CDATA_OPEN) {
            var ke = text.indexOf(']]>', i + 9);
            if (ke === -1) break;
            i = ke + 3;
            safeCut = i;
            continue;
          }
          state = 'TAG';
          tagNameBuf = ''; tagNameEnd = false;
          inClosingTag = false; selfClosing = false;
          i++; continue;
        }
        i++;
        safeCut = i;
        continue;
      }

      if (state === 'TAG') {
        if (ch === 47 /* / */) {
          if (tagNameBuf === '' && !tagNameEnd) { inClosingTag = true; i++; continue; }
          selfClosing = true; i++; continue;
        }
        if (ch === 62 /* > */) {
          var tn = tagNameBuf.toLowerCase();
          if (!inClosingTag && !selfClosing && RAW_TAGS[tn]) {
            state = 'RAW'; rawTag = tn; i++; continue;
          }
          state = 'TEXT'; i++;
          safeCut = i;
          continue;
        }
        if (ch === 32 || ch === 9 || ch === 10 || ch === 13) {
          tagNameEnd = true; i++; state = 'ATTR_NAME'; continue;
        }
        if (!tagNameEnd) tagNameBuf += text.charAt(i);
        i++; continue;
      }

      if (state === 'ATTR_NAME') {
        if (ch === 62) {
          var tn2 = tagNameBuf.toLowerCase();
          if (!inClosingTag && !selfClosing && RAW_TAGS[tn2]) {
            state = 'RAW'; rawTag = tn2; i++; continue;
          }
          state = 'TEXT'; i++;
          safeCut = i;
          continue;
        }
        if (ch === 47) { selfClosing = true; i++; continue; }
        if (ch === 61 /* = */) { state = 'ATTR_VAL_START'; i++; continue; }
        i++; continue;
      }

      if (state === 'ATTR_VAL_START') {
        if (ch === 32 || ch === 9 || ch === 10 || ch === 13) { i++; continue; }
        if (ch === 34) { quote = 34; state = 'ATTR_VAL_Q'; i++; continue; }
        if (ch === 39) { quote = 39; state = 'ATTR_VAL_Q'; i++; continue; }
        if (ch === 62) { state = 'ATTR_NAME'; continue; }
        state = 'ATTR_VAL_U'; i++; continue;
      }

      if (state === 'ATTR_VAL_Q') {
        if (ch === quote) { state = 'ATTR_NAME'; i++; continue; }
        i++; continue;
      }

      if (state === 'ATTR_VAL_U') {
        if (ch === 32 || ch === 9 || ch === 10 || ch === 13) { state = 'ATTR_NAME'; i++; continue; }
        if (ch === 62) { state = 'ATTR_NAME'; continue; }
        i++; continue;
      }
    }
    return safeCut;
  }

  // Incremental DOM reconciler — avoids flicker.
  //
  // Safe-cut output is append-only (each flush is a prefix superset of
  // the last), so we parse the new safe into a detached tree and walk
  // both trees in parallel, APPENDING new nodes and UPDATING grown
  // text. Existing element nodes stay put — no reflow, no animation
  // re-trigger. Attributes are immutable between cuts (the parser
  // can't cut mid-tag), so we never sync them on existing elements.

  // Promise chain that serializes script execution across an entire
  // visualization. Each enqueue returns a fresh link in the chain that
  // resolves only after the previous script has fully executed (or, for
  // external scripts, fully loaded). Inline scripts created via
  // createElement run synchronously on insertion, so the only way to
  // make them wait for a preceding external src-script is to defer
  // the insertion itself via this chain.
  var _ivScriptChain = Promise.resolve();
  var _ivEnqueuedScripts = Object.create(null);

  // FNV-1a over the script body — cheap content-hash used as a dedupe
  // key so the SAME script body is never executed twice, no matter how
  // many reconciler branches re-encountered the same incoming node.
  function _ivHashScript(s) {
    var h = 2166136261;
    for (var i = 0; i < s.length; i++) {
      h = (h ^ s.charCodeAt(i)) >>> 0;
      h = Math.imul(h, 16777619) >>> 0;
    }
    return h.toString(36);
  }

  function enqueueScript(incoming) {
    var src = incoming.getAttribute && incoming.getAttribute('src');
    var code = incoming.textContent || '';

    // Dedupe by (src|body hash). The reconciler can legitimately hit
    // the same script twice across its branches (`!exist` + position
    // mismatch + descend paths) when the streaming-era tree shape
    // differs from the finalize-era one. Running the body twice
    // redeclares `const` / rebinds classes / double-wires event
    // listeners — always a bug, so collapse here.
    var key = src ? ('src:' + src) : ('code:' + code.length + ':' + _ivHashScript(code));
    if (_ivEnqueuedScripts[key]) return;
    _ivEnqueuedScripts[key] = true;

    var attrs = [];
    for (var a = 0; a < incoming.attributes.length; a++) {
      attrs.push([incoming.attributes[a].name, incoming.attributes[a].value]);
    }
    if (src) {
      _ivScriptChain = _ivScriptChain.then(function() {
        return new Promise(function(resolve) {
          var el = document.createElement('script');
          attrs.forEach(function(pair) { el.setAttribute(pair[0], pair[1]); });
          el.onload = el.onerror = function() { resolve(); };
          document.head.appendChild(el);
        });
      });
    } else {
      _ivScriptChain = _ivScriptChain.then(function() {
        try {
          var el = document.createElement('script');
          attrs.forEach(function(pair) { el.setAttribute(pair[0], pair[1]); });
          el.textContent = code;
          document.head.appendChild(el);
        } catch(e) { try { console.error(e); } catch(_){} }
      });
    }
  }

  // importNode preserves SVG namespaces. Script elements are handled
  // specially via enqueueScript so external + inline scripts execute
  // in source order with proper load-waiting.
  function importAndAppend(parent, incoming) {
    var nt = incoming.nodeType;
    if (nt === 3) {
      parent.appendChild(document.createTextNode(incoming.textContent));
      return;
    }
    if (nt === 8) {
      parent.appendChild(document.createComment(incoming.textContent));
      return;
    }
    if (nt !== 1) return;
    var tag = incoming.nodeName;
    var el;
    if (tag === 'SCRIPT' || tag === 'script') {
      // Serialize script execution: external src-scripts load async,
      // inline scripts run synchronously on insertion, so an inline
      // consumer would fire before the preceding external bundle
      // finished loading. The promise chain makes every script wait
      // for all previously-queued ones first.
      enqueueScript(incoming);
      return;
    }
    // Shallow import preserves HTML-vs-SVG namespace.
    el = document.importNode(incoming, false);
    parent.appendChild(el);
    for (var i = 0; i < incoming.childNodes.length; i++) {
      importAndAppend(el, incoming.childNodes[i]);
    }
  }

  function reconcile(existing, incoming) {
    var existCh = existing.childNodes;
    var incCh = incoming.childNodes;
    var i;
    for (i = 0; i < incCh.length; i++) {
      var inc = incCh[i];
      var exist = existCh[i];
      if (!exist) {
        importAndAppend(existing, inc);
        continue;
      }
      // Position mismatch — rare with append-only streams, guard anyway.
      if (exist.nodeType !== inc.nodeType ||
          (exist.nodeType === 1 && exist.nodeName !== inc.nodeName)) {
        existing.removeChild(exist);
        var next = existCh[i] || null;
        var holder = document.createDocumentFragment();
        importAndAppend(holder, inc);
        if (next) existing.insertBefore(holder, next);
        else existing.appendChild(holder);
        continue;
      }
      if (exist.nodeType === 3) {
        // Text node — cheap update if content grew/changed.
        if (exist.nodeValue !== inc.nodeValue) exist.nodeValue = inc.nodeValue;
        continue;
      }
      if (exist.nodeType === 1) reconcile(exist, inc);
    }
    // Shouldn't happen with append-only, but trim if it does.
    while (existing.childNodes.length > incCh.length) {
      existing.removeChild(existing.lastChild);
    }
  }

  // withScripts=true materializes inline script tags (finalize path).
  // withScripts=false strips them during streaming to avoid repeat exec.
  // Regexes built at runtime via string concatenation — writing them
  // as literals would bake the raw open/close tokens into our own
  // embedded script, which the outer HTML parser sees and flips into
  // double-escape mode (corrupts our enclosing element boundary).
  var _ivOpen = '<' + 'script';
  var _ivClose = '<' + '\\/script>';
  var _ivStripPaired = new RegExp(_ivOpen + '[\\\\s\\\\S]*?' + _ivClose, 'gi');
  var _ivStripOpen = new RegExp(_ivOpen + '[\\\\s\\\\S]*$', 'i');
  // Strip document-level tags that models sometimes wrap VIZ content in.
  // These are invalid inside a div's innerHTML and mangle the DOM tree.
  var _ivStripDocTags = new RegExp('<' + '!DOCTYPE[^>]*>|<' + '/?(?:html|head|body)[^>]*>', 'gi');
  function renderSafeInto(text, withScripts) {
    var html = withScripts
      ? text
      : text.replace(_ivStripPaired, '').replace(_ivStripOpen, '');
    html = html.replace(_ivStripDocTags, '');
    var temp = document.createElement('div');
    try {
      temp.innerHTML = html;
    } catch(e) {
      // Fallback to full replace on any parse oddity.
      renderArea.innerHTML = html;
      return;
    }
    reconcile(renderArea, temp);
  }

  // ---- Fade-in animation for newly-complete elements ------------------
  function markAndAnimate(root) {
    var toAnimate = [];
    function visit(node, top) {
      if (!node || node.nodeType !== 1) return;
      var isSvgChild = node.ownerSVGElement != null;
      if ((top || isSvgChild || node.tagName === 'svg') && !node.hasAttribute('data-iv-faded')) {
        node.setAttribute('data-iv-faded', '1');
        toAnimate.push(node);
      }
      if (node.tagName === 'svg') {
        for (var c = node.firstElementChild; c; c = c.nextElementSibling) visit(c, false);
      }
    }
    for (var c = root.firstElementChild; c; c = c.nextElementSibling) visit(c, true);
    if (toAnimate.length === 0) return;
    requestAnimationFrame(function() {
      toAnimate.forEach(function(el) { el.classList.add('iv-fade-in'); });
    });
  }

  // ---- Height handling during streaming -------------------------------
  var heightRaf = 0;
  function scheduleHeight() {
    cancelAnimationFrame(heightRaf);
    heightRaf = requestAnimationFrame(function() {
      try { if (typeof reportHeight === 'function') reportHeight(); } catch(e) {}
    });
  }

  // ---- Finalize: run scripts, final height nudge ----------------------
  function finalize(fullText) {
    if (finalized) return;
    finalized = true;
    // Reconcile with scripts included — the reconciler materializes
    // fresh script elements which execute on insertion.
    renderSafeInto(fullText, true);
    hideLoader();
    markAndAnimate(renderArea);
    // Nudge the height reporter across layout settle.
    // Extra retries at 800ms + 1500ms cover the race where OWUI's
    // parent postMessage listener registers after finalize fires.
    scheduleHeight();
    setTimeout(scheduleHeight, 120);
    setTimeout(scheduleHeight, 400);
    setTimeout(scheduleHeight, 800);
    setTimeout(scheduleHeight, 1500);
    // Done announcement — only on live streams, not on rehydration.
    if (wasStreaming) {
      try {
        var label = (typeof _ivDoneStr !== 'undefined' &&
                     (_ivDoneStr[_ivLang] || _ivDoneStr.en)) || 'Visualization ready';
        if (typeof toast === 'function') toast(label, 'success');
      } catch(e) {}
      try { if (typeof playDoneSound === 'function') playDoneSound(); } catch(e) {}
    }
  }

  function isBlockClosed() {
    var msg = findMyMessage();
    if (!msg) return false;
    var idx = determineIndex();
    if (idx === null) idx = 0;
    var text = getSearchableText(msg);
    // True iff the idx-th block's full match contains END_MARK.
    BLOCK_RE.lastIndex = 0;
    var m, n = 0;
    while ((m = BLOCK_RE.exec(text)) !== null) {
      if (n === idx) return m[0].indexOf(END_MARK) !== -1;
      n++;
      if (m.index === BLOCK_RE.lastIndex) BLOCK_RE.lastIndex++;
    }
    return false;
  }

  // Tick skips its whole pipeline when the searchable text is
  // unchanged. A childList mutation sets forceHide=true so Svelte
  // rebuilds that preserve the text string still get re-hidden.
  var lastMsgText = null;
  var wasStreaming = false;
  var firstSeenLen = null;

  function tick(forceHide) {
    if (finalized) return;
    var msg = findMyMessage();
    if (!msg) return;

    var currentText = getSearchableText(msg);
    var textChanged = currentText !== lastMsgText;
    lastMsgText = currentText;

    // Live-stream detection by GROWTH — the first-seen searchable
    // length never grows on refreshes of completed messages, so
    // wasStreaming stays false and we don't fire the done toast/chime.
    if (firstSeenLen === null) firstSeenLen = currentText.length;
    else if (!wasStreaming && currentText.length > firstSeenLen) {
      wasStreaming = true;
    }

    if (textChanged || forceHide) hideMarkerRange();

    // Source-dependent work only runs on actual changes.
    if (!textChanged) return;

    var raw = readSource();
    if (raw === null) return;
    if (raw === lastRawText) {
      scheduleFinalize(raw);
      return;
    }
    lastRawText = raw;

    var cut = findSafeCut(raw);
    var safe = raw.substring(0, cut);

    if (safe !== lastSafeRendered && safe.length > 0) {
      lastSafeRendered = safe;
      renderSafeInto(safe, false);
      markAndAnimate(renderArea);
      scheduleHeight();
    }

    scheduleFinalize(raw);
  }

  // Forces hideMarkerRange to re-run even when textContent is unchanged
  // — Svelte can rebuild a text node without altering its string value.
  function _ivHasChildListMutation(records) {
    if (!records) return false;
    for (var i = 0; i < records.length; i++) {
      if (records[i] && records[i].type === 'childList') return true;
    }
    return false;
  }

  function scheduleFinalize(raw) {
    // Primary signal: @@@VIZ-END present → finalize instantly.
    // Fallback: 30s of completely stable source (user stopped
    // generation / model forgot END / network died). 30s is longer
    // than any realistic inter-chunk stall (Gemini 3.1 Pro 200-token
    // chunks, proxy buffering, etc) so we can't trip it mid-stream.
    clearTimeout(finalizeTimer);
    if (isBlockClosed()) { finalize(raw); return; }
    finalizeTimer = setTimeout(function() {
      if (finalized) return;
      var latest = readSource();
      if (latest === null) return;
      if (isBlockClosed() || latest === raw) {
        finalize(latest);
      }
    }, 30000);
  }

  // ---- Inject fade-in + loader CSS into our OWN document -------------
  (function injectFadeCss() {
    var s = document.createElement('style');
    s.textContent =
      '@keyframes iv-fade-in-kf {' +
      '  from { opacity: 0; transform: translateY(2px); }' +
      '  to   { opacity: 1; transform: none; }' +
      '}' +
      '@keyframes iv-fade-in-svg-kf {' +
      '  from { opacity: 0; } to { opacity: 1; }' +
      '}' +
      '#iv-render .iv-fade-in { animation: iv-fade-in-kf 500ms ease-out both; }' +
      '#iv-render svg .iv-fade-in { animation: iv-fade-in-svg-kf 500ms ease-out both; }' +
      // Three pulsing dots + label shown while waiting for content.
      '@keyframes iv-pulse-kf {' +
      '  0%, 80%, 100% { opacity: 0.25; transform: scale(0.85); }' +
      '  40%           { opacity: 1;    transform: scale(1); }' +
      '}' +
      '.iv-loading {' +
      '  display: flex; flex-direction: column; align-items: center;' +
      '  justify-content: center; gap: 12px;' +
      '  padding: 48px 20px; min-height: 120px;' +
      '  color: var(--color-text-tertiary);' +
      '  font-size: 12px; letter-spacing: 0.02em;' +
      '}' +
      '.iv-loading-dots { display: inline-flex; gap: 8px; }' +
      '.iv-loading-dots span {' +
      '  width: 8px; height: 8px; border-radius: 50%;' +
      '  background: var(--color-text-tertiary);' +
      '  animation: iv-pulse-kf 1.4s infinite ease-in-out both;' +
      '}' +
      '.iv-loading-dots span:nth-child(1) { animation-delay: -0.32s; }' +
      '.iv-loading-dots span:nth-child(2) { animation-delay: -0.16s; }' +
      '.iv-loading-label { opacity: 0.6; }';
    document.head.appendChild(s);
  })();

  // #iv-loader is rendered server-side as a sibling below #iv-render;
  // we only need to remove it on finalize.
  function hideLoader() {
    try {
      var l = document.getElementById('iv-loader');
      if (l && l.parentNode) l.parentNode.removeChild(l);
    } catch(e) {}
  }

  // Defense in depth: outer observer on parent.document.body sees new
  // messages as chat scrolls / navigates; inner observer on our own
  // message catches every streaming text mutation; 400ms poll is a
  // safety net in case the observers miss anything.
  var innerMo = null;
  function attachInnerObserver() {
    if (innerMo) return;
    var msg = findMyMessage();
    if (!msg) return;
    try {
      innerMo = new MutationObserver(function(records) {
        tick(_ivHasChildListMutation(records));
      });
      innerMo.observe(msg, {
        childList: true, subtree: true, characterData: true
      });
    } catch(e) {}
  }

  function pollTick() {
    tick(false);
    attachInnerObserver();
  }

  tick(false);
  attachInnerObserver();
  try {
    new MutationObserver(function(records) {
      tick(_ivHasChildListMutation(records));
      attachInnerObserver();
    }).observe(parent.document.body, {
      childList: true, subtree: true, characterData: true
    });
  } catch(e) {}
  setInterval(pollTick, 400);
})();
</script>
"""


# Kept for backwards compatibility in case anything references the old name
INJECTED_SCRIPTS = BODY_SCRIPTS

DOWNLOAD_BUTTON = (
    '<div id="iv-dl-wrap">'
    '<button id="iv-dl-btn" onclick="_ivDownload()" title="Download">'
    '<svg viewBox="0 0 16 16"><path d="M8 2v8M5 7l3 3 3-3"/><path d="M3 12h10"/></svg>'
    '</button></div>'
)


# ---------------------------------------------------------------------------
# CSP generation per security level
# ---------------------------------------------------------------------------

_KNOWN_CDNS = (
    "https://cdnjs.cloudflare.com"
    " https://cdn.jsdelivr.net"
    " https://unpkg.com"
)


def _build_csp_tag(level: str) -> str:
    """Return a <meta> CSP tag for the given security level, or empty string.

    'unsafe-eval' is included because runtime expression compilers like
    Vega / Vega-Lite use new Function() internally and fail under
    strict CSP. 'unsafe-inline' is already present (inline scripts can
    execute arbitrary code), so adding 'unsafe-eval' does not
    meaningfully widen the attack surface — the real exfil blockers
    (connect-src, form-action, img-src, object-src) remain intact.
    """
    if level == "none":
        return ""

    if level == "strict":
        return (
            '<meta http-equiv="Content-Security-Policy" content="'
            f"default-src 'self'; "
            f"script-src 'unsafe-inline' 'unsafe-eval' {_KNOWN_CDNS}; "
            "style-src 'self' 'unsafe-inline'; "
            "connect-src 'none'; "
            "form-action 'none'; "
            "img-src 'self' data: blob:; "
            "font-src 'self' data:; "
            "media-src 'self'; "
            "object-src 'none'; "
            "base-uri 'self'; "
            '">'
        )

    # balanced: block outbound connections & forms, allow external images
    return (
        '<meta http-equiv="Content-Security-Policy" content="'
        f"default-src 'self'; "
        f"script-src 'unsafe-inline' 'unsafe-eval' {_KNOWN_CDNS}; "
        "style-src 'self' 'unsafe-inline'; "
        "connect-src 'none'; "
        "form-action 'none'; "
        "img-src * data: blob:; "
        "font-src 'self' data:; "
        "media-src 'self'; "
        "object-src 'none'; "
        "base-uri 'self'; "
        '">'
    )


def _build_html(security_level: str = "strict",
                title: str = "Visualization", lang: str = "en",
                chime: bool = True) -> str:
    """Wrap the streaming visualization shell: empty render area + observer.

    The observer tails the parent chat DOM for an ``@@@VIZ-START`` …
    ``@@@VIZ-END`` plain-text block in the assistant message and renders
    its contents live into #iv-render.
    """
    csp_tag = _build_csp_tag(security_level)
    strict_script = STRICT_SECURITY_SCRIPT if security_level == "strict" else ""
    safe_title = (title.replace('&', '&amp;').replace('<', '&lt;')
                       .replace('>', '&gt;').replace('"', '&quot;'))
    # Sanitize lang to a simple lowercase BCP-47 primary subtag.
    # Split on '-' first so "zh-CN" → "zh", not "zhcn".
    safe_lang = re.sub(r'[^a-z]', '', lang.split('-')[0].lower()[:5]) or "en"

    # Strip the chime script entirely when the valve is off — no bytes
    # shipped, no defined playDoneSound in the iframe. finalize()'s
    # typeof-function guard turns the missing definition into a no-op.
    body_scripts = BODY_SCRIPTS.replace(
        '/*__CHIME_BLOCK__*/', CHIME_SCRIPT if chime else ''
    )

    # Loader sits *below* the render area so content appears to flow
    # downward toward the pulsing dots — like a cursor following a pen.
    # The observer removes #iv-loader entirely on finalize().
    body_inner = (
        '<div id="iv-render"></div>\n'
        '<div id="iv-loader" class="iv-loading" aria-live="polite">'
        '<div class="iv-loading-dots"><span></span><span></span><span></span></div>'
        '<div class="iv-loading-label">Rendering visualization\u2026</div>'
        '</div>\n'
        f'{DOWNLOAD_BUTTON}\n'
        f'{body_scripts}'
        f'{STREAMING_OBSERVER_SCRIPT}'
        f'{strict_script}'
    )

    return (
        f'<!DOCTYPE html><html data-iv-lang="{safe_lang}" data-iv-build="{_IV_BUILD}"><head>'
        f"<title>{safe_title}</title>"
        f"{csp_tag}"
        f"<style>{THEME_CSS}\n{SVG_CLASSES}\n{BASE_STYLES}</style>"
        f'<script>try{{console.info("iv[build]","{_IV_BUILD}");}}catch(e){{}}</script>'
        f"{THEME_DETECTION_SCRIPT}"
        f"</head><body>\n{body_inner}\n</body></html>"
    )


# ---------------------------------------------------------------------------
# Valves (user-configurable settings)
# ---------------------------------------------------------------------------

# Developer reference for security levels:
#
#   STRICT   — Containment-oriented default. Blocks outbound fetch/XHR
#              (connect-src 'none'), form submissions, external images,
#              embedded objects, and base-URI hijacking. Injects a script
#              that strips URL query parameters from link navigation as
#              additional hygiene (query-only; does not cover path or
#              fragment, and does not intercept location.assign/replace).
#              Script execution within the visualization is intentionally
#              allowed ('unsafe-inline' + CDN allowlist) — this is
#              required for Chart.js, D3, and interactive visualizations.
#
#   BALANCED — Same as STRICT but allows external image loading (img-src *).
#              No URL parameter stripping. Note: img-src * permits
#              tracking pixels — this is an accepted privacy tradeoff
#              for visualizations that need external images.
#
#   NONE     — No CSP applied. Visualization can make arbitrary network
#              requests. Use only for visualizations that fetch live API
#              data (CORS restrictions still apply).
#
# Limitations that apply to ALL levels:
# - Script execution is always permitted (required for core features).
# - When iframe Same-Origin is enabled at the platform level, JS inside
#   the visualization can access the parent Open WebUI page. No CSP
#   level can prevent this — it is controlled by the platform setting.


class Tools:
    """Inline Visualizer — renders interactive HTML/SVG in chat.

    Security is controlled via the ``security_level`` valve, which applies
    a Content Security Policy to the rendered iframe.  Defaults to STRICT,
    which blocks outbound network requests (fetch/XHR) and form submissions.
    Script execution is always permitted — it is required for interactive
    visualizations, Chart.js, and D3.  See the developer reference above
    for the full security model and its limitations.
    """

    class Valves(BaseModel):
        security_level: Literal["strict", "balanced", "none"] = Field(
            default="strict",
            description="Strict (default): blocks outbound fetch/XHR, images, and forms; scripts always allowed. Balanced: also allows external images. None: no restrictions.",
        )
        chime: bool = Field(
            default=True,
            description="Play a soft three-note chime when a live-streamed visualization finishes. When off, the chime script is omitted from the iframe entirely (not shipped as a no-op).",
        )

    def __init__(self):
        self.valves = self.Valves()

    async def render_visualization(
        self,
        title: str = "Visualization",
        __event_call__=None,
        __event_emitter__=None,
    ):
        """
        Render an interactive HTML or SVG visualization inline in the chat.

        IMPORTANT: You MUST call view_skill("visualize") FIRST to load the design system
        before calling this tool. Never generate a visualization without reading the skill
        instructions first — they contain critical rules for colors, layout, SVG setup,
        chart patterns, and common failure points.

        **IMPORTANT:** When to use the tool:
        Use this tool only when the user has explicitly said to visualize something.
        Do not use it when it would fit the response to visualize something but only when
        there is CLEAR INTENT by the user to want something visualized in the chat.

        The tool mounts an empty visualization wrapper in the chat.
        Then, in your text response that follows, wrap the HTML/SVG in the TEXT DELIMITERS
        @@@VIZ-START / @@@VIZ-END:

            @@@VIZ-START
            <svg viewBox="0 0 680 240">...</svg>
            @@@VIZ-END

        The wrapper tails your streaming text and renders the content between the
        markers LIVE, token-by-token, into the iframe. Users see the visualization
        paint progressively as you generate it. The raw markers + SVG source are
        auto-hidden from the chat, so users see only the rendered iframe.

        The system automatically injects:
        - Theme CSS variables (auto-detected light/dark mode)
        - SVG utility classes: .t .ts .th .box .node .arr .leader
        - Color ramp classes: .c-purple .c-teal .c-coral .c-pink .c-gray .c-blue .c-green .c-amber .c-red
        - Base element styles (button, range, select, code, headings)
        - Height auto-sizing script
        - sendPrompt(text) function — sends a message to the chat (requires iframe Sandbox Allow Same Origin)
        - openLink(url) function — opens a URL in a new tab
        - saveState() and loadState() function
        - copyText() function
        - downloadAsExcel(sheets, filename) — generates and downloads an .xlsx file via SheetJS.
          sheets is an array of {name, headers, rows} objects.
          Example: downloadAsExcel([{name:'Kanban', headers:['Task','Status','Owner'], rows:[['Task 1','Done','Alice']]}], 'board.xlsx')
        - downloadAsPPTX(slides, filename) — generates and downloads a .pptx via PptxGenJS.
          Each slide supports: {title, subtitle, bg, headerBg, headerH, titleColor, bodyColor,
            subtitleColor, accentColor, items:['...'], stats:[{value,label},...],
            table:[[header,...],[row,...]], footer, tableHeaderBg, tableHeaderColor}.
          bg/headerBg/titleColor etc. are hex strings WITHOUT '#'. Match your visualization colors.
          Example (IBM Carbon dark): downloadAsPPTX([{title:'Board Summary',
            bg:'1F2937', headerBg:'0062FF', titleColor:'FFFFFF', bodyColor:'F3F4F6',
            accentColor:'0062FF', stats:[{value:'71%',label:'CEOs prioritize tech'}],
            table:[['Task','Status'],['Task 1','Done']], footer:'Source: IBM IBV'}], 'board')
        - downloadAsDOCX(htmlContent, filename) — generates and downloads a .docx via html-docx-js.
          htmlContent is the HTML body string to embed; pass null to auto-export the rendered iframe content.
          Example: downloadAsDOCX('<h1>Board</h1><table>...</table>', 'board.docx')

        To add a download button in your visualization HTML (inside @@@VIZ-START):
          <button onclick="downloadAsExcel([...], 'board.xlsx')">Download Excel</button>
          <button onclick="downloadAsPPTX([...], 'board')">Download PPTX</button>
          <button onclick="downloadAsDOCX(null, 'board.docx')">Download DOCX</button>

        :param title: Short descriptive title for the visualization.
        :return: Interactive rich embed rendered in the chat, with LLM context.
        """
        # Detect UI language via parent page JS (same pattern as PDF/Gamma actions)
        lang = "en"
        if __event_call__:
            try:
                lang_result = await __event_call__({
                    "type": "execute",
                    "data": {
                        "code": """
return (() => {
  try {
    const stored = localStorage.getItem('locale')
                || localStorage.getItem('language')
                || localStorage.getItem('i18nextLng');
    if (stored) {
      const l = stored.split('-')[0].toLowerCase();
      if (l) return l;
    }
  } catch (e) {}
  try {
    return (navigator.language || navigator.userLanguage || 'en').split('-')[0].toLowerCase();
  } catch (e) {}
  return 'en';
})();
"""
                    },
                })
                if isinstance(lang_result, str) and lang_result.strip():
                    lang = lang_result.strip()
            except Exception:
                pass

        if __event_emitter__:
            await __event_emitter__({"type": "status", "data": {
                "description": "Mounting visualization wrapper...",
                "done": False,
            }})
        html = _build_html(
            self.valves.security_level,
            title,
            lang,
            chime=self.valves.chime,
        )
        if __event_emitter__:
            await __event_emitter__({"type": "status", "data": {
                "description": f'Wrapper "{title}" ready — streaming mode active.',
                "done": True,
            }})
        return HTMLResponse(content=html, headers={"Content-Disposition": "inline"})
