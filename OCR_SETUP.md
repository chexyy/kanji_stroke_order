# OCR Setup with OpenRouter

This add-on now uses OpenRouter AI for handwriting recognition instead of local OCR libraries.

## Setup Instructions

1. **Get an OpenRouter API key:**
   - Visit https://openrouter.ai/
   - Sign up for an account
   - Get your API key from the settings

2. **Configure the add-on:**
   - In Anki, go to: Tools → Add-ons
   - Select "Kanji Stroke Order"
   - Click "Config" button
   - Add your API key to the `openrouter_api_key` field:
     ```json
     {
       "openrouter_api_key": "sk-or-v1-your-api-key-here",
       "openrouter_model": "google/gemini-flash-1.5"
     }
     ```
   - Click "OK" to save
   - Restart Anki

3. **Test OCR:**
   - Open stroke order practice
   - Draw a Japanese character
   - Click "Check" to see if it recognizes your drawing

## Default Model

The default model is `google/gemini-flash-1.5` which:
- Supports vision/image inputs
- Works well with Japanese character recognition
- Is cost-effective for OCR tasks

## Alternative Models

You can change the model in the config to any OpenRouter vision model:
- `google/gemini-pro-1.5` - More powerful, slower
- `anthropic/claude-3-haiku` - Fast and accurate
- `openai/gpt-4-vision-preview` - Very accurate but more expensive

## Cost

OpenRouter charges per API call. Typical costs for handwriting recognition are minimal (fractions of a cent per request). Check OpenRouter's pricing page for current rates.

## Troubleshooting

If OCR doesn't work:
1. Check that your API key is correct
2. Make sure you have credits in your OpenRouter account
3. Check the Anki console (anki-console.exe) for error messages
4. Verify the model name is correct and supports vision inputs
