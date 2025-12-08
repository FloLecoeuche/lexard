# Epic 15: Responsive Mobile UI

## Overview

Make the main Lexard web UI (`ui/index.html`) fully responsive for mobile devices (iPhone, Android) following UX/UI best practices. This includes a collapsible sidebar navigation, touch-optimized interactions, and mobile-friendly file uploads.

## Prerequisites

- Epic 5 (Interfaces) completed - Web UI exists
- Epic 11-13 completed - All UI features in place

## User Stories

---

## US 15.1: Mobile Layout & Collapsible Sidebar

**Status:** 🔲 Not Started

### Description

Implement responsive CSS breakpoints and a collapsible hamburger menu for the documents sidebar on mobile devices.

### Context

The current UI uses a fixed 300px sidebar which doesn't work on mobile screens. We need to:
- Hide the sidebar by default on mobile
- Add a hamburger menu button to toggle it
- Use CSS transitions for smooth open/close animation
- Ensure the main content area uses full width on mobile

### Tasks

- [ ] Add CSS media query breakpoint at 768px for mobile
- [ ] Create hamburger menu button (hidden on desktop, visible on mobile)
- [ ] Implement sidebar slide-in animation with CSS transforms
- [ ] Add overlay backdrop when sidebar is open (click to close)
- [ ] Make main panel full-width on mobile
- [ ] Ensure header is responsive (stack elements if needed)
- [ ] Make footer responsive (stack on mobile)

### Implementation Details

```css
/* Mobile breakpoint */
@media (max-width: 768px) {
    #documents-panel {
        position: fixed;
        left: 0;
        top: 0;
        bottom: 0;
        width: 85%;
        max-width: 320px;
        transform: translateX(-100%);
        transition: transform 0.3s ease;
        z-index: 1000;
    }

    #documents-panel.open {
        transform: translateX(0);
    }

    .sidebar-overlay {
        position: fixed;
        inset: 0;
        background: rgba(0,0,0,0.5);
        z-index: 999;
        opacity: 0;
        visibility: hidden;
        transition: opacity 0.3s;
    }

    .sidebar-overlay.active {
        opacity: 1;
        visibility: visible;
    }
}
```

### Acceptance Criteria

- [ ] On screens <= 768px, sidebar is hidden by default
- [ ] Hamburger button appears in header on mobile
- [ ] Tapping hamburger opens sidebar with slide animation
- [ ] Tapping overlay or X closes sidebar
- [ ] Main content uses full width on mobile
- [ ] Desktop layout unchanged (sidebar always visible)
- [ ] No horizontal scroll on any mobile viewport

### Tests

- **Manual:** Test on Chrome DevTools mobile emulation (iPhone SE, iPhone 12, Pixel 5)
- **Manual:** Test on real device if available
- **Visual:** No layout breaking at any width from 320px to 768px

### Files to Create/Modify

1. `ui/index.html` - Add hamburger button, overlay div, mobile CSS, toggle JS

---

## US 15.2: Touch-Optimized Interactions

**Status:** 🔲 Not Started

### Description

Optimize all interactive elements for touch devices with proper touch targets, disable drag-and-drop on mobile, and improve the native file picker experience.

### Context

Mobile users interact with fingers, not cursors. Current touch targets are mostly 44px which is Apple's minimum. Google recommends 48px. Also, drag-and-drop is confusing on mobile - we should use native file picker instead.

### Tasks

- [ ] Increase all button/interactive touch targets to 48px minimum
- [ ] Disable drag-and-drop zone styling on mobile (keep tap-to-upload)
- [ ] Make file input trigger native picker with `capture` attribute consideration
- [ ] Ensure document list items have adequate touch spacing
- [ ] Add `:active` states for touch feedback (vs `:hover`)
- [ ] Increase tab navigation touch targets on mobile
- [ ] Ensure modals are touch-scrollable (momentum scrolling)

### Implementation Details

```css
@media (max-width: 768px) {
    /* Larger touch targets */
    .btn, .tab, #upload-btn {
        min-height: 48px;
        padding: 0.875rem 1.25rem;
    }

    .document-item {
        padding: 1rem;
        min-height: 64px;
    }

    /* Touch feedback */
    .btn:active {
        transform: scale(0.98);
        opacity: 0.9;
    }

    /* Disable drag visual on mobile */
    #upload-zone {
        border-style: solid;
    }

    #upload-zone.dragover {
        /* No visual change - drag doesn't work well on mobile */
    }

    /* Momentum scrolling */
    .result-box, #document-list, .preview-modal-body {
        -webkit-overflow-scrolling: touch;
    }
}
```

```javascript
// Detect touch device
const isTouchDevice = ('ontouchstart' in window) || (navigator.maxTouchPoints > 0);

if (isTouchDevice) {
    uploadZone.classList.add('touch-device');
    // Prevent drag events from showing confusing UI
    uploadZone.addEventListener('dragover', (e) => e.preventDefault(), { passive: true });
}
```

### Acceptance Criteria

- [ ] All buttons have minimum 48px touch target
- [ ] Document items have comfortable tap spacing (no mis-taps)
- [ ] Tap-to-upload works and opens native file picker
- [ ] No drag-and-drop visual feedback on touch devices
- [ ] Touch scrolling is smooth in all scrollable areas
- [ ] Active states provide visual feedback on tap
- [ ] Tabs are easy to tap on mobile

### Tests

- **Manual:** Test tap accuracy on mobile emulator
- **Manual:** Test file upload flow on mobile
- **Manual:** Verify scroll momentum in document list and results

### Files to Create/Modify

1. `ui/index.html` - Touch CSS, touch detection JS, active states

---

## US 15.3: Mobile Header & Sticky Navigation

**Status:** 🔲 Not Started

### Description

Make the header sticky on mobile scroll and add a floating action indicator for the currently selected document.

### Context

On mobile, users scroll through content frequently. A sticky header keeps navigation accessible. Also, when the sidebar is closed, users lose context of which document is selected - we need a visible indicator.

### Tasks

- [ ] Make header sticky/fixed on mobile
- [ ] Add padding-top to main content to account for fixed header
- [ ] Create "selected document" indicator below header (shows current doc name)
- [ ] Make the indicator tappable to open sidebar
- [ ] Ensure preview modal works correctly with fixed header
- [ ] Handle safe-area-inset for notched phones (iPhone X+)
- [ ] Test with virtual keyboard open (input fields)

### Implementation Details

```css
@media (max-width: 768px) {
    header {
        position: fixed;
        top: 0;
        left: 0;
        right: 0;
        z-index: 100;
    }

    main {
        padding-top: 4rem; /* Account for fixed header */
    }

    /* Selected document indicator */
    .mobile-doc-indicator {
        position: fixed;
        top: 56px; /* Below header */
        left: 0;
        right: 0;
        background: #f1f5f9;
        padding: 0.5rem 1rem;
        font-size: 0.875rem;
        display: flex;
        align-items: center;
        gap: 0.5rem;
        z-index: 99;
        border-bottom: 1px solid #e2e8f0;
    }

    /* Safe area for notched phones */
    header {
        padding-top: env(safe-area-inset-top);
    }

    footer {
        padding-bottom: env(safe-area-inset-bottom);
    }
}
```

### Acceptance Criteria

- [ ] Header stays visible when scrolling on mobile
- [ ] No content hidden behind fixed header
- [ ] Selected document name visible when sidebar closed
- [ ] Tapping document indicator opens sidebar
- [ ] Works correctly on notched phones (no content under notch)
- [ ] Preview modal appears above fixed header correctly
- [ ] Input fields not obscured by fixed elements when keyboard opens

### Tests

- **Manual:** Scroll test on mobile emulator
- **Manual:** Test on iPhone X+ emulation (notch handling)
- **Manual:** Test input focus and virtual keyboard behavior

### Files to Create/Modify

1. `ui/index.html` - Sticky header CSS, document indicator HTML/CSS/JS, safe-area handling

---

## Definition of Done (Epic 15)

- [ ] All User Stories completed (3/3 US)
- [ ] UI works on mobile viewports 320px - 768px
- [ ] UI works on desktop viewports 769px+
- [ ] No horizontal scrolling on any viewport
- [ ] All touch targets >= 48px
- [ ] Sidebar toggle works smoothly
- [ ] File upload works on mobile
- [ ] Tested on Chrome DevTools mobile emulation
- [ ] No console errors on mobile
