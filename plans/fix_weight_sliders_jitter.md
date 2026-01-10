# Feature Implementation Plan: fix-weight-sliders-jitter

## 📋 Todo Checklist
- [x] ✅ Update CSS to provide stable layout for weight items.
- [x] ✅ Refactor `WeightSettings.js` to avoid full re-renders on slider input.
- [x] ✅ Verify fix with manual testing.

## 🔍 Analysis & Investigation

### Codebase Structure
- **`frontend/src/js/ui/WeightSettings.js`**: Contains the logic for rendering and updating the weights list.
- **`frontend/src/css/style.css`**: Contains the styling for the modal and weight items.

### Current Architecture
Currently, the `renderList()` method in `WeightSettings.js` is called when opening the modal or filtering the list. However, it seems the event listener for `input` on the ranges updates the `weightsMap` and the local text display. The "jitter" and "size change" likely come from:
1.  Flexible layout (`display: flex`) where elements don't have fixed widths.
2.  Potential re-renders or layout shifts when the text value length changes (e.g., "9.9" vs "10.0").
3.  Lack of specific styling for the sliders in the weight modal, causing them to use default or inherited styles that might be unstable during interaction.

### Dependencies & Integration Points
- **Vanilla JS**: DOM manipulation.
- **CSS Flexbox**: Used for layout.

### Considerations & Challenges
- Ensuring the stop names (which can be long) don't squeeze the sliders.
- Making sure the weight value display has a fixed width to prevent layout jumps.
- Improving the look and feel of the sliders to match the rest of the UI.

## 📝 Implementation Plan

### Prerequisites
- None.

### Step-by-Step Implementation

1. **Step 1: Improve CSS for stable layout**
   - Files to modify: `frontend/src/css/style.css`
   - Changes needed:
     - Add specific styles for `.weight-item` to ensure fixed proportions.
     - Give `.weight-name` a flexible but stable width (e.g., `flex: 1` with `min-width`).
     - Give `.weight-control` a fixed width or stable flex basis.
     - Ensure `.weight-value` has a fixed width (e.g., `min-width: 40px`) and `text-align: right` to prevent shifting when numbers change.
     - Style the range input specifically for the weights modal to ensure it doesn't "jitter" on interaction.

2. **Step 2: Update `WeightSettings.js` for smoother updates**
   - Files to modify: `frontend/src/js/ui/WeightSettings.js`
   - Changes needed:
     - Ensure `renderList` is efficient.
     - Verify that only the text value is updated on `input`, not a full re-render (which it currently seems to do correctly, but let's double check).

### Testing Strategy
- Open the Weight Configuration modal.
- Move sliders for various stops (short and long names).
- Verify that the layout remains stable and sliders don't change size or jitter.

## 🎯 Success Criteria
- Sliders are stable during interaction.
- Layout doesn't jump when weight values change.
- Stop names are truncated or handled gracefully without affecting slider width.
