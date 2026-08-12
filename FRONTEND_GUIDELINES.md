# Frontend Guidelines (YiChinese Learning App)

This document serves as a reference for AI agents and front-end developers working on the YiChinese Learning web application. It outlines the design system, layout structure, external libraries, and core components.

## 1. Theme Colors
The application uses a custom vanilla CSS design system primarily based on a soothing, nature-inspired green palette. It also defines a specific high-contrast variation for the dashboard pages.

### Core Palette
- **Background**: `#CBE2D4`
- **Card Background**: `#ffffff`
- **Text Main**: `#576856`
- **Text Muted**: `#738a72`
- **Primary**: `#576856` (Hover: `#455544`)
- **Secondary**: `#f0f4f1` (Hover: `#e0e8e1`)

### Dashboard Palette
- **Background**: `#eef6df`
- **Text Main**: `#111111`
- **Text Muted**: `#2b2b2b`
- **Primary**: `#007a61` (Hover: `#00634f`)
- **Secondary**: `#eef6df` (Hover: `#e3efcf`)
- **Border Soft**: `#d7e3c6`

### Status Colors
- **Success**: `#10b981`
- **Warning**: `#f59e0b`
- **Danger**: `#ef4444`

## 2. Layout Structure
The application relies heavily on modern CSS layout features like Flexbox and CSS Grid.

- **App Container (`.app-container`)**:
  - Max-width of `1280px`.
  - Centered in the viewport using flexbox (`display: flex; justify-content: center;`).
  - Implements a subtle glassmorphism effect: White background (`#ffffff`), `16px` border-radius, subtle shadow, and a backdrop filter (`blur(10px)`).
- **Dashboard Shell (`.site-shell`)**:
  - Sticky header (`.site-header`) with a blur effect (`backdrop-filter: blur(12px)`).
  - Main content area (`.dashboard-main`) bounded to a max-width of `1180px`.
  - Responsive Grid layout (`.dashboard-container`) using `grid-template-columns: repeat(auto-fit, minmax(260px, 1fr))`.
- **Responsive Breakpoints**:
  - `@media (max-width: 900px)`: Header items collapse, navigation becomes horizontally scrollable, dashboard grid switches to 2 columns.
  - `@media (max-width: 560px)`: Header padding reduces, dashboard grid switches to 1 column.

## 3. Libraries Used
The project deliberately avoids heavy CSS frameworks like Tailwind or Bootstrap in favor of Vanilla CSS.

- **CSS Framework**: None (Vanilla CSS with custom CSS variables in `:root`).
- **Typography**: 
  - Google Fonts: `Inter` (used heavily in the dashboard), `Roboto`, `Noto Sans` (fallback for Chinese Hanzi characters).
- **Icons**:
  - FontAwesome 6.5.2 (`all.min.css`)
  - Phosphor Icons (`@phosphor-icons/web`)
- **Data Visualization**: 
  - Chart.js (`chart.js`) for rendering dashboard analytics.

## 4. Components
- **Buttons (`.btn`)**:
  - `.btn.primary`: Uses the primary color block and white text.
  - `.btn.secondary`: Uses a light gray/green background.
  - `.btn.warning` / `.btn.danger`: Uses respective status colors.
  - Interactive states: `hover` includes smooth transforms (`translateY(-2px)`) and background color transitions.
- **Form Elements**:
  - Text and Number Inputs: `12px` padding, `8px` border-radius, with focus states highlighting the outline in the primary color.
- **Cards (`.dash-card`)**:
  - Designed for grid layouts.
  - Hover effects: The card translates upwards (`translateY(-5px)`), increases box-shadow, and changes border color to signify interactivity.
- **Navigation**:
  - Breadcrumbs (`.breadcrumb`): Small linked paths with separators for hierarchical navigation.
  - Sticky Top Nav (`.site-header`): Contains brand identity, navigation links (`.site-nav`), and user authentication/language controls (`.site-auth`).
- **Interactive States & Feedback**:
  - Progress Bar (`.progress-bar`, `.progress-fill`): Animated width transitions to indicate task completion.
  - Loaders (`.loader`): Spinning CSS animations for asynchronous loading states.
  - Modals / Overlays (`.feedback-overlay`, `.quit-modal-overlay`): Full-screen blurred backdrops focusing attention on centered content cards.
