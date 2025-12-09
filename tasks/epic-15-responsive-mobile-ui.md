# Epic 15: Responsive Mobile UI

## Overview

Make the main Lexard web UI (`ui/index.html`) fully responsive for mobile devices (iPhone, Android) following UX/UI best practices. This includes a collapsible sidebar navigation, touch-optimized interactions, and mobile-friendly file uploads.

**Target:** Portrait-only smartphone usage (no landscape/tablet optimization needed).

## Prerequisites

- Epic 5 (Interfaces) completed - Web UI exists
- Epic 11-13 completed - All UI features in place

## Design Decisions

- **Breakpoint:** 768px (standard mobile/desktop split)
- **Touch targets:** 48px minimum (Google recommendation)
- **Sidebar pattern:** Left drawer, slides in from left, below header
- **No landscape:** Users will only use portrait mode on smartphones

## CSS Variables (to be added)

```css
:root {
  --header-height: 56px;
  --header-height-safe: calc(56px + env(safe-area-inset-top));
  --mobile-breakpoint: 768px;
}
```

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

- [ ] Add CSS variables for header height and breakpoint
- [ ] Add CSS media query breakpoint at 768px for mobile
- [ ] Create hamburger menu button (3-line icon, hidden on desktop, visible on mobile)
- [ ] Add close (X) button inside sidebar header
- [ ] Implement sidebar slide-in animation with CSS transforms (below header)
- [ ] Add overlay backdrop when sidebar is open (click to close)
- [ ] Add body scroll lock when sidebar is open
- [ ] Make main panel full-width on mobile
- [ ] Ensure header is responsive (hamburger left, logo center, status/logout right)
- [ ] Make footer responsive (stack on mobile)

### Implementation Details

```css
/* CSS Variables */
:root {
  --header-height: 56px;
}

/* Mobile breakpoint */
@media (max-width: 768px) {
  /* Hamburger button */
  .hamburger-btn {
    display: flex;
    align-items: center;
    justify-content: center;
    width: 48px;
    height: 48px;
    background: none;
    border: none;
    cursor: pointer;
    padding: 0;
  }

  .hamburger-btn span {
    display: block;
    width: 24px;
    height: 2px;
    background: white;
    position: relative;
  }

  .hamburger-btn span::before,
  .hamburger-btn span::after {
    content: '';
    position: absolute;
    width: 24px;
    height: 2px;
    background: white;
    left: 0;
  }

  .hamburger-btn span::before {
    top: -7px;
  }
  .hamburger-btn span::after {
    top: 7px;
  }

  /* Sidebar positioning - below header */
  #documents-panel {
    position: fixed;
    left: 0;
    top: var(--header-height);
    bottom: 0;
    width: 85%;
    max-width: 320px;
    transform: translateX(-100%);
    transition: transform 0.3s ease;
    z-index: 1000;
    background: white;
    box-shadow: 2px 0 8px rgba(0, 0, 0, 0.15);
  }

  #documents-panel.open {
    transform: translateX(0);
  }

  /* Close button in sidebar */
  .sidebar-close {
    position: absolute;
    top: 0.5rem;
    right: 0.5rem;
    width: 44px;
    height: 44px;
    background: none;
    border: none;
    font-size: 1.5rem;
    color: #64748b;
    cursor: pointer;
    display: flex;
    align-items: center;
    justify-content: center;
    border-radius: 8px;
  }

  .sidebar-close:active {
    background: #f1f5f9;
  }

  /* Overlay backdrop */
  .sidebar-overlay {
    position: fixed;
    inset: 0;
    top: var(--header-height);
    background: rgba(0, 0, 0, 0.5);
    z-index: 999;
    opacity: 0;
    visibility: hidden;
    transition: opacity 0.3s;
  }

  .sidebar-overlay.active {
    opacity: 1;
    visibility: visible;
  }

  /* Body scroll lock */
  body.sidebar-open {
    overflow: hidden;
  }

  /* Main panel full width */
  main {
    flex-direction: column;
  }

  #main-panel {
    width: 100%;
  }

  /* Footer stacked */
  footer {
    flex-direction: column;
    gap: 0.5rem;
    text-align: center;
    padding: 1rem;
  }
}

/* Desktop: hide mobile elements */
@media (min-width: 769px) {
  .hamburger-btn,
  .sidebar-close,
  .sidebar-overlay {
    display: none !important;
  }
}
```

```javascript
// Sidebar toggle functionality
const hamburgerBtn = document.getElementById('hamburger-btn');
const sidebarClose = document.getElementById('sidebar-close');
const sidebar = document.getElementById('documents-panel');
const overlay = document.getElementById('sidebar-overlay');

function openSidebar() {
  sidebar.classList.add('open');
  overlay.classList.add('active');
  document.body.classList.add('sidebar-open');
}

function closeSidebar() {
  sidebar.classList.remove('open');
  overlay.classList.remove('active');
  document.body.classList.remove('sidebar-open');
}

hamburgerBtn.addEventListener('click', openSidebar);
sidebarClose.addEventListener('click', closeSidebar);
overlay.addEventListener('click', closeSidebar);
```

### Acceptance Criteria

- [ ] On screens <= 768px, sidebar is hidden by default
- [ ] Hamburger button (3 lines) appears in header on mobile
- [ ] Tapping hamburger opens sidebar with slide animation (from below header)
- [ ] Close (X) button visible inside sidebar
- [ ] Tapping overlay closes sidebar
- [ ] Tapping X button closes sidebar
- [ ] Background content does not scroll when sidebar is open
- [ ] Main content uses full width on mobile
- [ ] Desktop layout unchanged (sidebar always visible, no hamburger)
- [ ] No horizontal scroll on any mobile viewport
- [ ] Footer stacks vertically on mobile

### Tests

- **Manual:** Test on Chrome DevTools mobile emulation (iPhone SE 375px, iPhone 12 390px, Pixel 5 393px)
- **Manual:** Test on real device if available
- **Visual:** No layout breaking at any width from 320px to 768px
- **Visual:** Test at 320px width (minimum supported - Galaxy Fold closed)
- **Interaction:** Verify body scroll lock when sidebar open

### Files to Create/Modify

1. `ui/index.html` - Add hamburger button, close button, overlay div, CSS variables, mobile CSS, toggle JS

---

## US 15.2: Touch-Optimized Interactions

**Status:** 🔲 Not Started

### Description

Optimize all interactive elements for touch devices with proper touch targets, disable drag-and-drop on mobile, and improve the native file picker experience.

### Context

Mobile users interact with fingers, not cursors. Current touch targets are mostly 44px which is Apple's minimum. Google recommends 48px. Also, drag-and-drop is confusing on mobile - we should use native file picker instead.

### Tasks

- [ ] Increase all button/interactive touch targets to 48px minimum
- [ ] Add `touch-action: manipulation` to interactive elements (removes 300ms delay)
- [ ] Add `-webkit-tap-highlight-color: transparent` (removes blue flash)
- [ ] Set input font-size to 16px (prevents iOS auto-zoom on focus)
- [ ] Disable drag-and-drop zone styling on mobile (keep tap-to-upload)
- [ ] Ensure document list items have adequate touch spacing (add margin-bottom)
- [ ] Add `:active` states for touch feedback (vs `:hover`)
- [ ] Increase tab navigation touch targets on mobile
- [ ] Ensure modals are touch-scrollable
- [ ] Fix compare panel grid for mobile (stack vertically)
- [ ] Ensure disabled buttons don't animate on tap

### Implementation Details

```css
@media (max-width: 768px) {
  /* Remove tap highlight */
  .btn,
  .tab,
  .document-item,
  .actions-toggle,
  button {
    -webkit-tap-highlight-color: transparent;
    touch-action: manipulation;
  }

  /* Larger touch targets */
  .btn,
  .tab,
  #upload-btn {
    min-height: 48px;
    padding: 0.875rem 1.25rem;
  }

  .document-item {
    padding: 1rem;
    min-height: 64px;
    margin-bottom: 0.5rem; /* Spacing between items */
  }

  /* Input font size - prevents iOS zoom */
  input[type='text'],
  select,
  textarea {
    font-size: 16px;
  }

  /* Touch feedback */
  .btn:active:not(:disabled) {
    transform: scale(0.98);
    opacity: 0.9;
  }

  .tab:active {
    background: #f1f5f9;
  }

  .document-item:active {
    background: #e2e8f0;
  }

  /* Disabled buttons - no animation */
  .btn:disabled:active {
    transform: none;
    opacity: 1;
  }

  /* Disable drag visual on mobile */
  #upload-zone {
    border-style: solid;
  }

  #upload-zone.dragover {
    /* No visual change - drag doesn't work well on mobile */
    border-color: #cbd5e1;
    background: transparent;
  }

  /* Upload zone touch-friendly */
  #upload-zone {
    min-height: 120px;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
  }

  /* Compare panel - stack vertically on mobile */
  .diff-content {
    grid-template-columns: 1fr;
    gap: 0.75rem;
  }

  .compare-selectors {
    grid-template-columns: 1fr;
    gap: 0.5rem;
  }

  .compare-selectors span {
    text-align: center;
  }

  /* Tab navigation - horizontal scroll if needed */
  nav {
    overflow-x: auto;
    -webkit-overflow-scrolling: touch;
  }

  .tab {
    white-space: nowrap;
    min-width: fit-content;
  }
}
```

```javascript
// Detect touch device
const isTouchDevice = 'ontouchstart' in window || navigator.maxTouchPoints > 0;

if (isTouchDevice) {
  document.body.classList.add('touch-device');

  // Prevent drag events from showing confusing UI on mobile
  const uploadZone = document.getElementById('upload-zone');
  uploadZone.addEventListener(
    'dragover',
    (e) => {
      e.preventDefault();
      // Don't add dragover class on touch devices
    },
    { passive: false }
  );

  uploadZone.addEventListener(
    'dragenter',
    (e) => {
      e.preventDefault();
    },
    { passive: false }
  );
}
```

### Acceptance Criteria

- [ ] All buttons have minimum 48px touch target
- [ ] Document items have comfortable tap spacing (no mis-taps)
- [ ] No 300ms tap delay (touch-action: manipulation applied)
- [ ] No blue tap highlight flash
- [ ] Tap-to-upload works and opens native file picker
- [ ] Inputs don't trigger iOS zoom (font-size 16px)
- [ ] No drag-and-drop visual feedback on touch devices
- [ ] Active states provide visual feedback on tap
- [ ] Tabs are easy to tap on mobile
- [ ] Compare panel stacks vertically on mobile
- [ ] Disabled buttons don't animate

### Tests

- **Manual:** Test tap accuracy on mobile emulator - no accidental taps
- **Manual:** Test file upload flow on mobile - native picker opens
- **Manual:** Verify no iOS zoom when tapping input fields
- **Manual:** Verify compare panel is readable on 375px width
- **Manual:** Test tab switching - responsive and easy to tap

### Files to Create/Modify

1. `ui/index.html` - Touch CSS, touch detection JS, active states, compare layout fix

---

## US 15.3: Mobile Header & Sticky Navigation

**Status:** 🔲 Not Started

### Description

Make the header sticky on mobile scroll and add a selected document indicator integrated into the header.

### Context

On mobile, users scroll through content frequently. A sticky header keeps navigation accessible. Also, when the sidebar is closed, users lose context of which document is selected - we need a visible indicator.

### Tasks

- [ ] Make header sticky/fixed on mobile
- [ ] Add padding-top to main content to account for fixed header
- [ ] Integrate "selected document" indicator into header (below title line)
- [ ] Make the indicator tappable to open sidebar
- [ ] Handle safe-area-inset for notched phones (iPhone X+)
- [ ] Ensure preview modal works correctly with fixed header (z-index hierarchy)
- [ ] Test with virtual keyboard open (input fields)

### Implementation Details

```css
@media (max-width: 768px) {
  /* Fixed header */
  header {
    position: fixed;
    top: 0;
    left: 0;
    right: 0;
    z-index: 100;
    padding-top: env(safe-area-inset-top);
  }

  /* Main content offset */
  main {
    padding-top: calc(
      var(--header-height) + env(safe-area-inset-top) + 40px
    ); /* header + doc indicator */
  }

  /* Selected document indicator - integrated into header area */
  .mobile-doc-indicator {
    position: fixed;
    top: calc(var(--header-height) + env(safe-area-inset-top));
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
    min-height: 40px;
    cursor: pointer;
    touch-action: manipulation;
    -webkit-tap-highlight-color: transparent;
  }

  .mobile-doc-indicator:active {
    background: #e2e8f0;
  }

  .mobile-doc-indicator .doc-icon {
    font-size: 1rem;
  }

  .mobile-doc-indicator .doc-name {
    flex: 1;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
    color: #1e293b;
    font-weight: 500;
  }

  .mobile-doc-indicator .doc-name.empty {
    color: #64748b;
    font-weight: 400;
    font-style: italic;
  }

  .mobile-doc-indicator .chevron {
    color: #64748b;
    font-size: 0.75rem;
  }

  /* Footer safe area */
  footer {
    padding-bottom: calc(1rem + env(safe-area-inset-bottom));
  }

  /* Z-index hierarchy (prevent conflicts) */
  /* header: 100 */
  /* .mobile-doc-indicator: 99 */
  /* .preview-modal: 500 */
  /* .sidebar-overlay: 999 */
  /* #documents-panel: 1000 */

  .preview-modal {
    z-index: 500;
  }
}

/* Hide doc indicator on desktop */
@media (min-width: 769px) {
  .mobile-doc-indicator {
    display: none !important;
  }
}
```

```javascript
// Mobile document indicator
const mobileDocIndicator = document.getElementById('mobile-doc-indicator');

function updateMobileDocIndicator() {
  if (!mobileDocIndicator) return;

  const docNameEl = mobileDocIndicator.querySelector('.doc-name');

  if (selectedDocumentId) {
    const doc = documents.find((d) => d.id === selectedDocumentId);
    if (doc) {
      docNameEl.textContent = doc.title || doc.filename;
      docNameEl.classList.remove('empty');
    } else {
      docNameEl.textContent = 'Select a document';
      docNameEl.classList.add('empty');
    }
  } else {
    docNameEl.textContent = 'Select a document';
    docNameEl.classList.add('empty');
  }
}

// Tap indicator to open sidebar
mobileDocIndicator?.addEventListener('click', openSidebar);

// Call updateMobileDocIndicator() in selectDocument() and loadDocuments()
```

```html
<!-- Add below header -->
<div id="mobile-doc-indicator" class="mobile-doc-indicator">
  <span class="doc-icon">📄</span>
  <span class="doc-name empty">Select a document</span>
  <span class="chevron">▼</span>
</div>
```

### Acceptance Criteria

- [ ] Header stays visible when scrolling on mobile
- [ ] No content hidden behind fixed header
- [ ] Selected document name visible in indicator when sidebar closed
- [ ] "Select a document" shown when no document selected
- [ ] Tapping document indicator opens sidebar
- [ ] Works correctly on notched phones (no content under notch)
- [ ] Preview modal appears above content but below sidebar (z-index correct)
- [ ] Input fields not obscured by fixed elements when keyboard opens
- [ ] Footer has safe area padding at bottom

### Tests

- **Manual:** Scroll test on mobile emulator - header stays fixed
- **Manual:** Test on iPhone X+ emulation (notch handling via safe-area-inset)
- **Manual:** Test input focus and virtual keyboard behavior
- **Manual:** Verify document indicator updates when selecting documents
- **Manual:** Verify tapping indicator opens sidebar
- **Manual:** Test z-index: open preview modal, then try to open sidebar

### Files to Create/Modify

1. `ui/index.html` - Sticky header CSS, document indicator HTML/CSS/JS, safe-area handling, z-index fixes

---

## Definition of Done (Epic 15)

- [ ] All User Stories completed (3/3 US)
- [ ] UI works on mobile viewports 320px - 768px
- [ ] UI works on desktop viewports 769px+
- [ ] No horizontal scrolling on any viewport
- [ ] All touch targets >= 48px
- [ ] No iOS input zoom (inputs are 16px font)
- [ ] Sidebar toggle works smoothly
- [ ] Body scroll locked when sidebar open
- [ ] File upload works on mobile (tap, not drag)
- [ ] Selected document visible when sidebar closed
- [ ] Compare panel readable on mobile (stacked layout)
- [ ] Safe area insets handled for notched phones
- [ ] Z-index hierarchy prevents modal/sidebar conflicts
- [ ] Tested on Chrome DevTools mobile emulation
- [ ] No console errors on mobile

## Test Devices (Chrome DevTools Emulation)

| Device               | Width | Why Test                 |
| -------------------- | ----- | ------------------------ |
| Galaxy Fold (closed) | 280px | Extreme narrow edge case |
| iPhone SE            | 375px | Smallest common iOS      |
| iPhone 12/13/14      | 390px | Standard iOS             |
| iPhone 14 Pro        | 393px | Dynamic Island           |
| Pixel 5              | 393px | Common Android           |
