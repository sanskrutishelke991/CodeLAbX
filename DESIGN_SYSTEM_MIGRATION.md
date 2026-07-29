# CodeLabX Design System Migration Guide

## Overview
This document outlines the new design system implementation and provides guidance for migrating existing templates to the new professional, minimal aesthetic inspired by Linear, Vercel, and Cursor.

## What Changed

### 1. Color System
**Old:** Purple gradients (#6C63FF, #4a90e2) throughout
**New:** Monochromatic base with single electric blue accent (#0055FF)

**Dark Mode:**
- Background: #0A0A0A (pure near-black)
- Secondary: #111111
- Tertiary: #1A1A1A
- Text Primary: #FAFAFA
- Text Secondary: #A1A1A1
- Accent: #0055FF

**Light Mode:**
- Background: #FAFAF9 (warm off-white)
- Secondary: #FFFFFF
- Tertiary: #F5F5F4
- Text Primary: #0A0A0A
- Text Secondary: #525252
- Accent: #0055FF

### 2. Typography
**New Font Stack:**
- Headings: 'Instrument Serif' (editorial, sophisticated)
- Body: 'Inter' (clean, modern)
- Code: 'JetBrains Mono' (developer aesthetic)

**Font Scale:**
- xs: 0.75rem
- sm: 0.875rem
- base: 1rem
- lg: 1.125rem
- xl: 1.25rem
- 2xl: 1.5rem
- 3xl: 1.875rem
- 4xl: 2.25rem
- 5xl: 3rem
- 6xl: 4rem

### 3. Border Radius
**Old:** 12-20px (very rounded)
**New:** 4-6px default (sharp, professional)
- sm: 4px
- md: 6px (default)
- lg: 8px (rare)
- xl: 12px (only for images/large elements)
- No rounded-full except avatars/pills

### 4. Navigation
**Old:** Top navbar with Bootstrap
**New:** Fixed sidebar (260px) with icon + label layout
- Active state: left border accent color
- Collapses on mobile with overlay
- Hamburger menu on mobile

### 5. Icons
**Old:** Bootstrap Icons + Emojis in UI
**New:** Lucide Icons (SVG-based, consistent)
- Load via CDN: `<script src="https://unpkg.com/lucide@latest/dist/umd/lucide.js"></script>`
- Initialize: `lucide.createIcons()`
- Usage: `<i data-lucide="icon-name"></i>`

## Icon Replacement Strategy

### Bootstrap Icons → Lucide Icons Mapping

| Bootstrap Icon | Lucide Icon | Usage |
|---------------|-------------|-------|
| bi-house | layout-dashboard | Dashboard |
| bi-map | map | Roadmaps |
| bi-book | book-open | Content Library |
| bi-clipboard-check | clipboard-check | Assessments |
| bi-code | code | Practice |
| bi-trophy | trophy | Achievements |
| bi-robot | bot | AI Tools |
| bi-person | user | Profile |
| bi-gear | settings | Settings |
| bi-box-arrow-right | log-out | Logout |
| bi-moon-fill | moon | Dark theme |
| bi-sun-fill | sun | Light theme |
| bi-plus-lg | plus | Add/Create |
| bi-arrow-right | arrow-right | Navigation |
| bi-fire | flame | Streak |
| bi-check-circle | check-circle | Success |
| bi-calendar3 | calendar | Calendar |
| bi-star-fill | star | Rating/Level |
| bi-lightning | zap | Quick actions |
| bi-award | award | Badges |

### Emoji Replacement Guidelines

**Remove ALL emojis from UI elements:**
- ❌ 🚀 in welcome messages
- ❌ 🤖 in AI features
- ❌ 🏆 in achievements
- ❌ ⚡ in XP notifications
- ❌ 👑 in level ups

**Replace with Lucide Icons:**
- 🚀 → `<i data-lucide="rocket"></i>`
- 🤖 → `<i data-lucide="bot"></i>`
- 🏆 → `<i data-lucide="trophy"></i>`
- ⚡ → `<i data-lucide="zap"></i>`
- 👑 → `<i data-lucide="crown"></i>`

## Template Migration Steps

### Step 1: Remove Gradient Backgrounds
**Find and replace:**
```css
/* Old */
background: linear-gradient(135deg, #6C63FF 0%, #4a90e2 100%);

/* New */
background: var(--bg-secondary);
border: 1px solid var(--border-default);
```

### Step 2: Update Border Radius
**Find and replace:**
```css
/* Old */
border-radius: 12px;
border-radius: 16px;
border-radius: 20px;

/* New */
border-radius: var(--radius-md); /* 6px */
border-radius: var(--radius-lg); /* 8px, rare */
```

### Step 3: Replace Colors
**Find and replace:**
```css
/* Old */
color: #6C63FF;
background: rgba(108, 99, 255, 0.2);
border-color: rgba(108, 99, 255, 0.3);

/* New */
color: var(--accent);
background: rgba(0, 85, 255, 0.1);
border-color: var(--border-default);
```

### Step 4: Replace Icons
**Bootstrap Icons:**
```html
<!-- Old -->
<i class="bi bi-house"></i>

<!-- New -->
<i data-lucide="layout-dashboard"></i>
```

**Emojis:**
```html
<!-- Old -->
<span>🚀 Welcome</span>

<!-- New -->
<span><i data-lucide="rocket" style="width: 16px; height: 16px; vertical-align: middle;"></i> Welcome</span>
```

### Step 5: Update Button Styles
**Old gradient buttons:**
```html
<!-- Old -->
<button class="btn btn-primary" style="background: linear-gradient(135deg, #6C63FF, #4a90e2);">
```

**New solid buttons:**
```html
<!-- New -->
<button class="btn btn-primary">
```

### Step 6: Update Card Styles
**Old:**
```html
<div class="card" style="background: linear-gradient(135deg, #1a1a2e, #16213e); border: 1px solid rgba(108, 99, 255, 0.2); border-radius: 16px;">
```

**New:**
```html
<div class="card">
```

### Step 7: Update Typography
**Old:**
```html
<h2 style="color: white; font-size: 2rem;">Title</h2>
```

**New:**
```html
<h2>Title</h2>
<!-- Uses Instrument Serif automatically -->
```

## Component-Specific Migration

### Buttons
```html
<!-- Primary -->
<button class="btn btn-primary">Action</button>

<!-- Secondary -->
<button class="btn btn-secondary">Cancel</button>

<!-- Ghost -->
<button class="btn btn-ghost">Link</button>
```

### Cards
```html
<div class="card">
    <div class="card-header">
        <h3 class="card-title">Card Title</h3>
    </div>
    <div class="card-body">
        <p>Card content</p>
    </div>
</div>
```

### Inputs
```html
<label class="form-label">Label</label>
<input type="text" class="form-control" placeholder="Placeholder">
```

### Alerts
```html
<div class="alert alert-success">
    Success message
</div>
```

### Badges
```html
<span class="badge badge-primary">Primary</span>
<span class="badge badge-success">Success</span>
<span class="badge badge-warning">Warning</span>
<span class="badge badge-error">Error</span>
```

## CSS Variables Reference

### Colors
```css
--bg-primary: #0A0A0A
--bg-secondary: #111111
--bg-tertiary: #1A1A1A
--border-subtle: #2A2A2A
--border-default: #333333
--text-primary: #FAFAFA
--text-secondary: #A1A1A1
--text-tertiary: #6E6E6E
--accent: #0055FF
--success: #00D084
--warning: #FFB800
--error: #FF4444
```

### Spacing
```css
--space-1: 4px
--space-2: 8px
--space-3: 12px
--space-4: 16px
--space-6: 24px
--space-8: 32px
```

### Border Radius
```css
--radius-sm: 4px
--radius-md: 6px
--radius-lg: 8px
--radius-xl: 12px
```

## Testing Checklist

After migrating each template:
- [ ] No purple gradients remain
- [ ] No emojis in UI elements
- [ ] Border radius ≤ 8px (except avatars)
- [ ] Typography uses new fonts
- [ ] Icons are Lucide SVGs
- [ ] Colors use CSS variables
- [ ] Responsive on mobile (sidebar collapses)
- [ ] Theme toggle works
- [ ] No inline styles where possible

## Priority Migration Order

1. **templates/base.html** ✅ (completed)
2. **templates/dashboard/home.html**
3. **templates/learning/** (roadmap_list, roadmap_detail, day_detail)
4. **templates/assessments/** (quiz_list, create_test, take_test)
5. **templates/practice/** (code_examiner)
6. **templates/progress/** (achievements, leaderboard)
7. **templates/accounts/** (login, register, profile, settings)
8. **templates/landing.html**

## Notes

- Bootstrap 5 CSS is still included for grid/utilities only
- Will phase out Bootstrap completely in future iterations
- All new components should use the design system CSS variables
- Custom inline styles should be avoided - use CSS classes instead
- The design system is built to be extensible - add new variables as needed

## Resources

- Lucide Icons: https://lucide.dev/icons/
- Design Tokens: See `static/css/style.css`
- Typography: Google Fonts (Instrument Serif, Inter, JetBrains Mono)
