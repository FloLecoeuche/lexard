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

## US 15.2: Document Display Width & Pinch-to-Zoom

**Status:** 🔲 Not Started

### Description

Make document content (PDF, DOCX, TXT) display at 100% width of the modal container on mobile and enable pinch-to-zoom for zooming in on document details.

### Context

The modal container already displays at the right size on mobile. The only issue is that the document content inside doesn't use the full width, and users cannot pinch-to-zoom to see details. This is a minimal, focused fix.

### Tasks

- [ ] Set document content (iframe/text container) to 100% width of modal body
- [ ] Enable pinch-to-zoom via CSS `touch-action: pinch-zoom`
- [ ] Ensure PDF iframe, text content, and images all respect 100% width

### Implementation Details

```css
@media (max-width: 768px) {
  /* Document content fills modal width */
  #preview-body iframe,
  #preview-body pre,
  #preview-body img {
    width: 100%;
    max-width: 100%;
  }

  /* Enable native pinch-to-zoom */
  #preview-body {
    touch-action: pan-x pan-y pinch-zoom;
    overflow: auto;
    -webkit-overflow-scrolling: touch;
  }
}
```

### Acceptance Criteria

- [ ] PDF iframe displays at 100% width of modal container on mobile
- [ ] Text content displays at 100% width of modal container on mobile
- [ ] Pinch-to-zoom works on document content
- [ ] Desktop preview modal unchanged

### Tests

- **Manual:** Open PDF preview on mobile - iframe fills modal width
- **Manual:** Open TXT preview on mobile - text fills modal width
- **Manual:** Pinch gesture zooms content in/out
- **Manual:** Desktop - no changes to modal behavior

### Files to Create/Modify

1. `ui/index.html` - Add mobile CSS for document width and pinch-to-zoom

---

## Definition of Done (Epic 15)

- [ ] All User Stories completed (2/2 US)
- [ ] Header and footer fixed on mobile
- [ ] Only body content scrolls on mobile
- [ ] Document content displays at 100% width of modal on mobile
- [ ] Pinch-to-zoom works on document content
- [ ] Desktop UI unchanged
- [ ] Tested on Chrome DevTools mobile emulation
- [ ] No console errors

## Test Devices (Chrome DevTools Emulation)

| Device          | Width | Why Test              |
| --------------- | ----- | --------------------- |
| iPhone SE       | 375px | Smallest common iOS   |
| iPhone 12/13/14 | 390px | Standard iOS          |
| Pixel 5         | 393px | Common Android        |
