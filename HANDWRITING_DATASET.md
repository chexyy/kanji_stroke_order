# Handwriting Dataset Collection

## Overview

Your Anki plugin now automatically collects handwriting samples when you use the dictionary OCR feature. This data will be used to train a personalized handwriting recognition model.

## How It Works

### Automatic Collection

When you:
1. Draw a character in the practice canvas
2. Click "Recognize" (dictionary mode)
3. OCR successfully recognizes the character

The plugin automatically:
- Captures the canvas image (300x300 PNG)
- Stores stroke data (sequence of points)
- Records the recognized character
- Saves timestamp
- Marks as successful

### Data Storage

**File**: `handwriting_dataset.json`

**Structure**:
```json
{
  "学": [
    {
      "image": "data:image/png;base64,...",
      "timestamp": "2026-02-04T12:34:56.789",
      "strokes": [[{x, y}, ...], ...],
      "success": true
    },
    ...
  ],
  "生": [...],
  ...
}
```

### What Gets Saved

✅ **Canvas Image** - 300x300 PNG with your handwriting
✅ **Stroke Data** - Sequence of all strokes (for advanced training)
✅ **Character** - The kanji/kana that was recognized
✅ **Timestamp** - When it was drawn
✅ **Success Flag** - Whether it was correctly recognized

## Training Requirements

### Minimum Data Needed

For basic model training:
- **10-20 samples per character** (minimum)
- **50+ samples per character** (recommended)
- **100+ total samples across all characters** (to start)

### Optimal Data

For best accuracy:
- **100+ samples per character**
- **Variety in writing** (different speeds, sizes, styles)
- **Multiple sessions** (collect over days/weeks)

## Current Dataset Stats

To check your current dataset size, the plugin logs:
```
Added handwriting sample for '学' (15 samples for this character, 247 total)
```

Look for these messages in the Anki console when using OCR.

## Next Steps

### Phase 1: Data Collection (Current)
- ✅ Auto-save successful OCR recognitions
- 🔄 Collect 10-20 samples for frequently used characters
- 🔄 Collect 100+ samples total

### Phase 2: Model Training (Coming Next)
- Train initial model on collected data
- Test accuracy on held-out samples
- Fine-tune hyperparameters

### Phase 3: Deployment
- Integrate model into OCR server
- Use personal model for predictions
- Fall back to OCR/AI if character not in dataset

### Phase 4: Continuous Learning
- Continue collecting samples
- Periodically retrain model (weekly/monthly)
- Improve accuracy over time

## Privacy & Data

### What's Stored
- Only your handwriting images and strokes
- Character labels
- No personal information

### Where It's Stored
- Locally in your Anki addon directory
- `handwriting_dataset.json` file
- Never uploaded anywhere

### Data Control
- You own all the data
- Can delete the file anytime
- Can export for backup

## Tips for Better Data

### Vary Your Writing
- ✓ Draw at different speeds
- ✓ Vary stroke thickness
- ✓ Different hand positions
- ✓ Practice same character multiple times

### Ensure Quality
- ✓ Complete all strokes
- ✓ Draw clearly
- ✓ Follow proper stroke order
- ✓ Let OCR confirm correct recognition

### Collect Systematically
- Focus on characters you use most
- Practice high-frequency kanji first
- Aim for balanced dataset

## Future Enhancements

1. **Manual labeling** - Save drawings even when OCR fails
2. **Stroke-level data** - Train on individual strokes
3. **Data augmentation** - Generate variations automatically
4. **Export/Import** - Share datasets with others
5. **Privacy mode** - Optional encryption

## Technical Details

### Image Format
- **Size**: 300x300 pixels
- **Format**: PNG
- **Encoding**: Base64
- **Background**: White
- **Stroke Color**: Black
- **Line Width**: 3px

### Stroke Data
- Array of strokes
- Each stroke is array of {x, y} points
- Preserves temporal order
- Includes all user-drawn points

### File Size
- ~50KB per sample (image + stroke data)
- 100 samples ≈ 5MB
- 1000 samples ≈ 50MB

## FAQs

**Q: Does this slow down my addon?**
A: No, saving happens in background. Adds <10ms per recognition.

**Q: Can I delete old samples?**
A: Yes, edit `handwriting_dataset.json` or delete the entire file.

**Q: Will this work for hiragana/katakana?**
A: Yes! Any character recognized by OCR gets saved.

**Q: What if OCR recognizes wrong character?**
A: The sample gets saved with wrong label. During training, we'll add validation.

**Q: Can I train on someone else's handwriting?**
A: Not recommended - model should match YOUR writing style.

## Monitoring Progress

Check the Anki console output for:
- "Saved handwriting sample for '学' (X samples for this character, Y total)"
- Look for steady growth in sample count
- Aim for balanced distribution across characters

## Support

For issues or questions about the dataset:
1. Check `handwriting_dataset.json` exists in addon folder
2. Verify console shows "Saved handwriting sample" messages
3. Ensure OCR recognition is working
4. Check file size is growing (samples being added)
