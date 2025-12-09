# Epic 15: Mobile UX Refinements

## Overview

Minimal mobile UX improvements to make the current UI fully usable on mobile devices. This epic addresses two specific issues: scrolling behavior (only body content should scroll while header/footer stay fixed) and preview modal experience (fullscreen with pinch-to-zoom support).

**Scope:** Small, focused changes. Not a full mobile redesign.

## Prerequisites

- Epic 5 (Interfaces) completed - Web UI exists
- Epic 11 (Document Preview) completed - Preview modal exists

## User Stories

---

## US 15.1: Fixed Header & Footer on Mobile

**Status:** ✅ Completed

### Description

Make the header and footer fixed/sticky on mobile so only the main body content scrolls. This provides consistent navigation access while browsing documents.

### Context

Currently on mobile, the entire page scrolls including header and footer. Users lose access to navigation and status information when scrolling through content. Fixing these elements improves usability.

### Tasks

- [ ] Add CSS to make header position fixed on mobile (<=768px)
- [ ] Add CSS to make footer position fixed at bottom on mobile
- [ ] Add appropriate padding/margin to main content to prevent overlap with fixed elements
- [ ] Ensure main content area is the only scrollable region
- [ ] Handle safe-area-inset for notched phones (iPhone X+)
- [ ] Test that all content remains accessible (not hidden behind fixed elements)

### Implementation Details

```css
@media (max-width: 768px) {
  :root {
    --header-height: 56px;
    --footer-height: 60px;
  }

  /* Fixed header */
  header {
    position: fixed;
    top: 0;
    left: 0;
    right: 0;
    z-index: 100;
    padding-top: env(safe-area-inset-top);
  }

  /* Fixed footer */
  footer {
    position: fixed;
    bottom: 0;
    left: 0;
    right: 0;
    z-index: 100;
    padding-bottom: env(safe-area-inset-bottom);
  }

  /* Main content scrollable area */
  main {
    padding-top: calc(var(--header-height) + env(safe-area-inset-top));
    padding-bottom: calc(var(--footer-height) + env(safe-area-inset-bottom));
    min-height: 100vh;
    overflow-y: auto;
  }

  /* Prevent body scroll, only main scrolls */
  body {
    overflow: hidden;
    height: 100vh;
  }
}
```

### Acceptance Criteria

- [ ] On mobile (<=768px), header stays visible at top when scrolling
- [ ] On mobile (<=768px), footer stays visible at bottom when scrolling
- [ ] Only the main content area scrolls
- [ ] No content is hidden behind fixed header or footer
- [ ] Works correctly on notched phones (safe-area-inset applied)
- [ ] Desktop layout unchanged (no fixed positioning)

### Tests

- **Manual:** Test on Chrome DevTools mobile emulation (iPhone SE 375px, iPhone 12 390px)
- **Manual:** Scroll through long content - header/footer remain fixed
- **Manual:** Verify all content accessible (first and last items visible)
- **Manual:** Test on iPhone X+ emulation (notch handling)

### Files to Create/Modify

1. `ui/index.html` - Add mobile CSS for fixed header/footer positioning

---

## US 15.2: Fullscreen Preview Modal with Pinch-to-Zoom

**Status:** 🔲 Not Started

### Description

On mobile devices, make the document preview modal fullscreen (100% viewport) with pinch-to-zoom support for all document types (PDF, TXT, images).

### Context

The current preview modal is sized for desktop and doesn't provide a good mobile viewing experience. Users need to see documents at full size and zoom in on details. Pinch-to-zoom is the standard mobile interaction for this.

### Tasks

- [ ] Detect mobile viewport and apply fullscreen modal styles
- [ ] Make modal cover entire viewport (100vw x 100vh) on mobile
- [ ] Position close button in accessible location (top-right, large touch target)
- [ ] Implement pinch-to-zoom using CSS touch-action and transform
- [ ] Add double-tap to reset zoom functionality
- [ ] Ensure PDF iframe is zoomable (may need wrapper approach)
- [ ] Ensure text content is zoomable
- [ ] Ensure images are zoomable
- [ ] Prevent body scroll when modal is open (already may exist)
- [ ] Test zoom limits (min 1x, max 4x suggested)

### Implementation Details

```css
@media (max-width: 768px) {
  /* Fullscreen modal on mobile */
  .preview-modal-content {
    width: 100vw;
    height: 100vh;
    max-width: none;
    max-height: none;
    border-radius: 0;
    margin: 0;
  }

  .preview-modal-body {
    height: calc(100vh - 50px); /* Subtract header */
    overflow: auto;
    -webkit-overflow-scrolling: touch;
  }

  /* Zoomable content wrapper */
  .preview-zoom-container {
    touch-action: pan-x pan-y pinch-zoom;
    transform-origin: 0 0;
    min-width: 100%;
    min-height: 100%;
  }

  /* Close button - larger touch target */
  .preview-modal-close {
    width: 48px;
    height: 48px;
    font-size: 1.5rem;
  }
}
```

```javascript
// Pinch-to-zoom implementation for mobile
function initMobilePreviewZoom() {
  const isMobile = window.innerWidth <= 768;
  if (!isMobile) return;

  const previewBody = document.getElementById('preview-body');
  let scale = 1;
  let lastScale = 1;
  let startDistance = 0;

  previewBody.addEventListener('touchstart', (e) => {
    if (e.touches.length === 2) {
      startDistance = getDistance(e.touches[0], e.touches[1]);
      lastScale = scale;
    }
  }, { passive: true });

  previewBody.addEventListener('touchmove', (e) => {
    if (e.touches.length === 2) {
      const currentDistance = getDistance(e.touches[0], e.touches[1]);
      scale = Math.min(Math.max(lastScale * (currentDistance / startDistance), 1), 4);
      previewBody.style.transform = `scale(${scale})`;
    }
  }, { passive: true });

  // Double-tap to reset
  let lastTap = 0;
  previewBody.addEventListener('touchend', (e) => {
    const now = Date.now();
    if (now - lastTap < 300 && e.touches.length === 0) {
      scale = 1;
      previewBody.style.transform = 'scale(1)';
    }
    lastTap = now;
  });

  function getDistance(touch1, touch2) {
    return Math.hypot(touch1.clientX - touch2.clientX, touch1.clientY - touch2.clientY);
  }
}
```

### Acceptance Criteria

- [ ] On mobile, preview modal covers full screen (100% width and height)
- [ ] Close button is easily tappable (48px minimum touch target)
- [ ] Pinch gesture zooms content in/out
- [ ] Zoom range is 1x to 4x
- [ ] Double-tap resets zoom to 1x
- [ ] PDF documents are zoomable
- [ ] Text content is zoomable
- [ ] Image previews are zoomable
- [ ] Can pan/scroll when zoomed in
- [ ] Desktop preview modal unchanged

### Tests

- **Manual:** Test on Chrome DevTools with touch emulation enabled
- **Manual:** Open preview modal - should be fullscreen on mobile
- **Manual:** Pinch gesture - content zooms in/out smoothly
- **Manual:** Double-tap - zoom resets to 1x
- **Manual:** Test with PDF, TXT, and image files
- **Manual:** Verify panning works when zoomed in
- **Manual:** Desktop - modal should be unchanged (not fullscreen)

### Files to Create/Modify

1. `ui/index.html` - Fullscreen modal CSS, pinch-to-zoom JavaScript

---

## Definition of Done (Epic 15)

- [ ] All User Stories completed (2/2 US)
- [ ] Header and footer fixed on mobile
- [ ] Only body content scrolls on mobile
- [ ] Preview modal is fullscreen on mobile
- [ ] Pinch-to-zoom works on all document types
- [ ] Double-tap resets zoom
- [ ] Desktop UI unchanged
- [ ] Tested on Chrome DevTools mobile emulation
- [ ] No console errors

## Test Devices (Chrome DevTools Emulation)

| Device          | Width | Why Test              |
| --------------- | ----- | --------------------- |
| iPhone SE       | 375px | Smallest common iOS   |
| iPhone 12/13/14 | 390px | Standard iOS          |
| Pixel 5         | 393px | Common Android        |
