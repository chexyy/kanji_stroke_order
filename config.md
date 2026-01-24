# Kanji Stroke Trainer - Configuration Guide

This document describes all available configuration options for the Kanji Stroke Trainer add-on.

## Basic Settings

### `enable_on_front`
- **Type:** Boolean
- **Default:** `true`
- **Description:** Enable the stroke trainer UI on the front (question) side of cards.

### `enable_on_back`
- **Type:** Boolean
- **Default:** `false`
- **Description:** Enable the stroke trainer UI on the back (answer) side of cards.

---

## Stroke Validation Settings

### `stroke_hit_ratio`
- **Type:** Float (0.0 - 1.0)
- **Default:** `0.6`
- **Description:** The minimum ratio of drawn stroke points that must fall within the corridor to be considered correct. Higher values require more precision.
  - `0.5` = 50% of points must match (lenient)
  - `0.6` = 60% of points must match (balanced)
  - `0.8` = 80% of points must match (strict)

### `stroke_corridor_width`
- **Type:** Integer
- **Default:** `10`
- **Description:** The width (in pixels) of the corridor around the canonical stroke path. Larger values are more forgiving.
  - `5` = Very strict
  - `10` = Balanced
  - `15` = Lenient

### `check_direction`
- **Type:** Boolean
- **Default:** `true`
- **Description:** Require strokes to be drawn in the correct direction (start → end). When enabled, backwards strokes will be rejected even if the shape is correct.
  - `true` = Enforce proper stroke direction
  - `false` = Accept strokes drawn in either direction

---

## Stroke Order Settings

### `strict_stroke_order`
- **Type:** Boolean
- **Default:** `true`
- **Description:** Control whether strokes must be drawn in the correct order.
  - `true` = Must draw strokes in order (1 → 2 → 3 → ...)
  - `false` = Can draw strokes in any order (all must still be completed)

### `auto_advance_kanji`
- **Type:** Boolean
- **Default:** `false`
- **Description:** Automatically advance to the next kanji when all strokes are completed.
  - `true` = Auto-advance after completing all strokes
  - `false` = Stay on current kanji (use Next button to advance)

---

## Due Card Modes

### `due_mode`
- **Type:** Integer (1, 2, or 3)
- **Default:** `1`
- **Description:** Controls visibility and hints for review/relearning cards (type 2 or 3). New and learning cards always use Mode 2 behavior.

#### Mode 1 - Minimal Help (Default)
**Best for:** Testing your memory with minimal assistance.
- Initially shows only the first stroke (silhouette + number + animation)
- After completing the first stroke, all help disappears
- Only completed strokes remain visible
- Press "Hint" button to temporarily reveal current stroke (3 seconds)
- Hint button is always available

#### Mode 2 - Full Help
**Best for:** Learning new kanji or reviewing with full guidance.
- All strokes always visible (silhouettes + numbers)
- Animated stroke for current stroke
- Same behavior as new/learning cards
- No restrictions

#### Mode 3 - Procedural (Most Challenging)
**Best for:** Advanced practice with minimal hints.
- Shows only completed strokes + current stroke silhouette
- Current stroke has animated demonstration
- **No stroke numbers displayed at all**
- No hint button
- Must rely on visual stroke order understanding

---

## Performance Tracking

The add-on automatically tracks performance statistics per kanji using browser localStorage:

**Tracked Metrics:**
- Total attempts
- Consecutive correct completions
- Total stroke errors (shape failures)
- Total direction errors
- Total redraws (Clear button presses)
- Total time spent

**Display:**
- Shows current kanji name
- Shows performance message:
  - First time: "First time practicing this kanji"
  - Success streak: "✓ Drawn correctly X times in a row"
  - Otherwise: "Attempts: X | Errors: Y"

**Reset Stats:** Use the "Reset Stats" button to clear statistics for the current kanji.

---

## Example Configurations

### Beginner (Lenient)
```json
{
    "enable_on_front": true,
    "enable_on_back": false,
    "stroke_hit_ratio": 0.5,
    "stroke_corridor_width": 15,
    "auto_advance_kanji": false,
    "check_direction": false,
    "strict_stroke_order": true,
    "due_mode": 2
}
```

### Intermediate (Balanced)
```json
{
    "enable_on_front": true,
    "enable_on_back": false,
    "stroke_hit_ratio": 0.6,
    "stroke_corridor_width": 10,
    "auto_advance_kanji": false,
    "check_direction": true,
    "strict_stroke_order": true,
    "due_mode": 1
}
```

### Advanced (Strict)
```json
{
    "enable_on_front": true,
    "enable_on_back": false,
    "stroke_hit_ratio": 0.7,
    "stroke_corridor_width": 8,
    "auto_advance_kanji": true,
    "check_direction": true,
    "strict_stroke_order": true,
    "due_mode": 3
}
```

### Free Practice (Flexible Order)
```json
{
    "enable_on_front": true,
    "enable_on_back": false,
    "stroke_hit_ratio": 0.6,
    "stroke_corridor_width": 10,
    "auto_advance_kanji": false,
    "check_direction": true,
    "strict_stroke_order": false,
    "due_mode": 2
}
```

---

## Tips

1. **New Learners:** Start with Mode 2 and lenient validation settings
2. **Review Cards:** Use Mode 1 or 3 to test your memory
3. **Direction Practice:** Enable `check_direction` once you're comfortable with stroke shapes
4. **Speed Practice:** Enable `auto_advance_kanji` and `strict_stroke_order: false`
5. **Performance:** Monitor your consecutive correct streak to track improvement

---

## Troubleshooting

**Strokes aren't being accepted:**
- Increase `stroke_corridor_width` (try 12-15)
- Decrease `stroke_hit_ratio` (try 0.5)
- Disable `check_direction` temporarily

**Too easy:**
- Decrease `stroke_corridor_width` (try 6-8)
- Increase `stroke_hit_ratio` (try 0.7-0.8)
- Use `due_mode: 3` for maximum challenge

**Need to restart Anki after config changes:**
- Yes, configuration changes require a full Anki restart to take effect
