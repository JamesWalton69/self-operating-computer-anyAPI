# GUI Overhaul Plan

## Overview
Modernize the Self-Operating Computer Studio GUI with improved aesthetics, layout, and user experience while maintaining all existing functionality.

## Design Goals
- **Modern aesthetic**: Use a refined dark theme with consistent spacing, rounded corners, and subtle shadows
- **Better hierarchy**: Clear visual hierarchy with improved section separation
- **Improved UX**: Better button feedback, input focus states, and status indicators
- **Responsive layout**: Maintain current sizing but improve internal spacing
- **Accessibility**: Better contrast ratios and focus indicators

---

## Color Palette Improvements

| Element | Current | Improved |
|---------|---------|----------|
| Background | `#09090b` | `#121214` (deeper, more premium) |
| Card BG | `#18181b` | `#1e1e24` (slightly lighter for depth) |
| Card Border | `#27272a` | `#2a2a30` (more subtle) |
| Primary | `#3b82f6` | `#6366f1` (indigo, more unique) |
| Primary Hover | `#2563eb` | `#818cf8` (lighter, softer) |
| Success | `#4ade80` | `#34d399` (finer green) |
| Error | `#ef4444` | `#f87171` (softer red) |
| Accent/Cyan | `#06b6d4` | `#06b6d4` (keep for variety) |

## Spacing Improvements
- Increase card padding from 10-12px to 14-16px
- Increase vertical spacing between sections from 12px to 16px
- Button padding: increase to 10-12px (y) and 16-18px (x)

## Typography Improvements
- Add font-weight variations (semibold for section headers)
- Increase log font from 8 to 9pt for readability
- Add letter-spacing to badges

## Visual Enhancements

### 1. Header Bar
- Add subtle gradient or border
- Better spacing around title
- Animated status badge with smooth transitions

### 2. Provider & Model Configuration Card
- Better iconography for provider selector
- Cleaner input field styling with proper focus states
- Add hover effects on buttons

### 3. Objective Prompt Card
- Larger, more prominent textarea
- Better visual separation between prompt and action bar
- Improved run/stop button styling

### 4. Live Activity Log
- Better log message categorization with icons
- Improved scrollbar styling
- Add subtle background animation when running

### 5. Google OAuth Panel
- Better button hierarchy (Connect = primary, Exchange = secondary)
- Improved placeholder text styling
- Better status indicator

---

## Implementation Priority
✅ **Phase 1**: Update theme constants and improve existing colors
✅ **Phase 2**: Modernize buttons with hover effects and animations
✅ **Phase 3**: Improve input fields with focus states
✅ **Phase 4**: Polish spacing and layout
✅ **Phase 5**: Add visual polish (badges, icons, gradients)

## Summary of Changes
- **Colors**: Deeper background (`#121214`), refined card colors, indigo primary (`#6366f1`)
- **Spacing**: Increased card padding to 14-16px, section spacing to 16px
- **Typography**: Bigger title (13pt), improved log font (9pt), bold step labels
- **Buttons**: Increased padding (16x10px), consistent hover effects
- **Inputs**: Better padding, improved visual consistency
- **Overlay**: Updated colors, larger status dot, improved button spacing
- **All changes maintain full backward compatibility with existing functionality**
