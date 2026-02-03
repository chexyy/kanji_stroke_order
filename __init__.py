from aqt import mw
from aqt import gui_hooks
from aqt.qt import QMessageBox, QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QListWidget, QListWidgetItem, QLineEdit, QAction, QAbstractItemView, QComboBox, QCalendarWidget, QTextEdit, QFileDialog, QGroupBox, QTimer, Qt
import xml.etree.ElementTree as ET
import re
import urllib.parse
import urllib.request
import json
import os
import sys
import base64
import io
from datetime import datetime, timedelta
from confettiJS import confettiJs

# Debug flag and function (defined early so it can be used during imports)
debug = True

def debugPrint(message):
    if debug:
        print("DEBUG:", message)

KANJI_REGEX = re.compile(r"[\u4E00-\u9FFF]")
HIRAGANA_REGEX = re.compile(r"[\u3040-\u309F]")
KATAKANA_REGEX = re.compile(r"[\u30A0-\u30FF]")

CONFIG = mw.addonManager.getConfig(__name__)

# Cache file path in the addon directory
CACHE_FILE = os.path.join(os.path.dirname(__file__), "kanji_cache.json")
STATS_FILE = os.path.join(os.path.dirname(__file__), "kanji_stats.json")
CARD_STATS_FILE = os.path.join(os.path.dirname(__file__), "card_stats.json")
AI_CONFIG_FILE = os.path.join(os.path.dirname(__file__), "ai_config.json")

def load_cache():
    """Load kanji stroke data from cache file."""
    if os.path.exists(CACHE_FILE):
        try:
            with open(CACHE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            debugPrint(f"Error loading cache: {e}")
    return {}

def save_cache(cache):
    """Save kanji stroke data to cache file."""
    try:
        with open(CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(cache, f, ensure_ascii=False, indent=2)
    except Exception as e:
        debugPrint(f"Error saving cache: {e}")

def load_stats():
    """Load kanji stats from stats file."""
    if os.path.exists(STATS_FILE):
        try:
            with open(STATS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            debugPrint(f"Error loading stats: {e}")
    return {}

def save_stats(stats):
    """Save kanji stats to stats file."""
    try:
        with open(STATS_FILE, "w", encoding="utf-8") as f:
            json.dump(stats, f, ensure_ascii=False, indent=2)
    except Exception as e:
        debugPrint(f"Error saving stats: {e}")

def load_card_stats():
    """Load card stats from card stats file."""
    if os.path.exists(CARD_STATS_FILE):
        try:
            with open(CARD_STATS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            debugPrint(f"Error loading card stats: {e}")
    return {}

def save_card_stats(stats):
    """Save card stats to card stats file."""
    try:
        with open(CARD_STATS_FILE, "w", encoding="utf-8") as f:
            json.dump(stats, f, ensure_ascii=False, indent=2)
    except Exception as e:
        debugPrint(f"Error saving card stats: {e}")

def load_ai_config():
    """Load AI configuration from file."""
    if os.path.exists(AI_CONFIG_FILE):
        try:
            with open(AI_CONFIG_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            debugPrint(f"Error loading AI config: {e}")
    return {
        'api_url': '',
        'api_key': '',
        'model': '',
        'ocr_model': '',
        'instructions': '',
        'pdf_path': ''
    }

def save_ai_config(config):
    """Save AI configuration to file."""
    try:
        with open(AI_CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(config, f, ensure_ascii=False, indent=2)
    except Exception as e:
        debugPrint(f"Error saving AI config: {e}")

# Load cache and stats at startup
KANJI_CACHE = load_cache()
KANJI_STATS = load_stats()
CARD_STATS = load_card_stats()

# OpenRouter API configuration for OCR (using ai_config.json)
AI_CONFIG = load_ai_config()
OPENROUTER_API_KEY = AI_CONFIG.get('api_key', '')
OPENROUTER_API_URL = AI_CONFIG.get('api_url', 'https://openrouter.ai/api/v1/chat/completions')
OPENROUTER_MODEL = AI_CONFIG.get('ocr_model') or 'google/gemini-2.0-flash-001'
OCR_AVAILABLE = bool(OPENROUTER_API_KEY)

def recognize_handwriting(image_data_base64):
    """Recognize Japanese handwritten characters from image based on the following argument
    
    Args:
        image_data_base64: Base64 encoded PNG image from canvas
        
    Returns:
        tuple: (recognized_text, confidence, all_results) or (None, 0, [])
    """
    # Reload config to get latest API key and settings
    ai_config = load_ai_config()
    api_key = ai_config.get('api_key', '')
    api_url = ai_config.get('api_url') or 'https://openrouter.ai/api/v1/chat/completions'
    ocr_model = ai_config.get('ocr_model') or 'google/gemini-2.0-flash-001'
    
    if not api_key:
        debugPrint("OCR not available - OpenRouter API key not configured")
        return None, 0, []
    
    try:
        debugPrint("Recognizing drawing with OpenRouter API...")
        
        # Remove data URL prefix if present
        if ',' in image_data_base64:
            image_data_base64 = image_data_base64.split(',', 1)[1]
        
        # Prepare API request
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "model": ocr_model,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": """Based on this image of Japanese handwriting, what are these Japanese character(s)? Return a JSON formatted as:
{
    "characters": "<characters>",
    "confidence": <confidenceScore>
}

1. the characters as a string, with no explanation or thought process
2. a percentage score for 0-100 rating confidence of character identification"""
                        },
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/png;base64,{image_data_base64}"
                            }
                        }
                    ]
                }
            ]
        }
        
        # Make API request
        request = urllib.request.Request(
            api_url,
            data=json.dumps(payload).encode('utf-8'),
            headers=headers
        )
        
        with urllib.request.urlopen(request, timeout=30) as response:
            result = json.loads(response.read().decode('utf-8'))
            
        debugPrint(f"API response: {result}")
        
        # Extract recognized text
        if result.get('choices') and len(result['choices']) > 0:
            content = result['choices'][0]['message']['content'].strip()
            debugPrint(f"OCR raw response: '{content}'")
            
            # Try to parse JSON response
            try:
                # Remove markdown code blocks if present
                cleaned_content = content
                if content.startswith('```'):
                    cleaned_content = re.sub(r'^```(?:json)?\s*\n', '', content)
                    cleaned_content = re.sub(r'\n```\s*$', '', cleaned_content)
                    debugPrint(f"Cleaned content: '{cleaned_content}'")
                
                ocr_result = json.loads(cleaned_content)
                recognized_text = ocr_result.get('characters', '').strip()
                confidence_score = ocr_result.get('confidence', 50) / 100.0  # Convert 0-100 to 0.0-1.0
                
                debugPrint(f"OCR detected: '{recognized_text}' with confidence {confidence_score:.2f}")
                
                return recognized_text, confidence_score, [(recognized_text, confidence_score)]
            except (json.JSONDecodeError, KeyError, TypeError) as e:
                # Fallback: treat entire response as the characters
                debugPrint(f"Failed to parse JSON response, using raw text: {e}")
                recognized_text = content
                return recognized_text, 0.5, [(recognized_text, 0.5)]
        
        return None, 0, []
        
    except urllib.error.HTTPError as e:
        error_body = e.read().decode('utf-8') if e.fp else str(e)
        debugPrint(f"HTTP Error in OCR recognition: {e.code} - {error_body}")
        return None, 0, []
    except Exception as e:
        debugPrint(f"Error in OCR recognition: {e}")
        import traceback
        traceback.print_exc()
        return None, 0, []


def kanaRenderer(char):
    """Render hiragana or katakana stroke data from KanjiVG."""
    global KANJI_CACHE
    
    # Check cache first
    if char in KANJI_CACHE:
        debugPrint(f"Loading kana {char} from cache")
        return KANJI_CACHE[char]
    
    # Fetch from KanjiVG if not in cache
    debugPrint(f"Fetching kana {char} from KanjiVG")
    try:
        svgHTML = fetch_kanjivg_svg(char)
        strokeData = extract_stroke_paths_from_svg(svgHTML, char)
        
        # Save to cache
        KANJI_CACHE[char] = strokeData
        save_cache(KANJI_CACHE)
        
        return strokeData
    except Exception as e:
        debugPrint(f"Error fetching kana {char} from KanjiVG: {e}")
        return []


def fetch_kanjivg_svg(char):
    """Fetch SVG from KanjiVG GitHub repository."""
    # Convert character to Unicode hex (5 digits, lowercase)
    code_point = format(ord(char), '05x')
    url = f"https://raw.githubusercontent.com/KanjiVG/kanjivg/master/kanji/{code_point}.svg"
    
    try:
        with urllib.request.urlopen(url) as response:
            svg_bytes = response.read()
        return svg_bytes.decode("utf-8", errors="ignore")
    except urllib.error.HTTPError as e:
        raise ValueError(f"Character {char} (U+{code_point.upper()}) not found in KanjiVG: {e}")


def kanjiRenderer(char):
    global KANJI_CACHE
    
    # Check cache first
    if char in KANJI_CACHE:
        debugPrint(f"Loading {char} from cache")
        return KANJI_CACHE[char]
    
    # Fetch from internet if not in cache
    debugPrint(f"Fetching {char} from Jisho.org")
    svgHTML = fetch_jisho_svg_html_for_kanji(char)
    strokeData = extract_stroke_paths_from_svg(svgHTML, char)

    # Save to cache
    KANJI_CACHE[char] = strokeData
    save_cache(KANJI_CACHE)

    # Optional debug – you can comment this out if you don't need it
    with open("output_file.txt", "w", encoding="utf-8") as f:
        for s in strokeData:
            f.write(
                f"Stroke {s['index']}: d={s['d']}\n"
                f"  label at ({s['label_x']}, {s['label_y']})\n"
                f"  start=({s['start_x']}, {s['start_y']}), "
                f"end=({s['end_x']}, {s['end_y']})\n"
            )

    return strokeData


def fetch_jisho_svg_html_for_kanji(char):
    base_url = "https://jisho.org/search/"
    query = f"{char} #kanji"
    encoded_query = urllib.parse.quote(query)
    url = base_url + encoded_query

    with urllib.request.urlopen(url) as response:
        html_bytes = response.read()
    html_text = html_bytes.decode("utf-8", errors="ignore")

    svg_url = re.search(r'd1w6u4xc3l95km\.cloudfront\.net/kanji-2015-03/.*\.svg', html_text)
    if not svg_url:
        raise ValueError(f"No SVG URL found for kanji {char!r}")
    svg_url = svg_url.group()

    with urllib.request.urlopen("https://" + svg_url) as response:
        html_bytes = response.read()
    svg_html_text = html_bytes.decode("utf-8", errors="ignore")

    return svg_html_text


def extract_stroke_paths_from_svg(svg_text, char):
    root = ET.fromstring(svg_text)

    ns = {
        'svg': "http://www.w3.org/2000/svg",
        'kvg': "http://kanjivg.tagaini.net"
    }

    target_group = None
    for g in root.findall('.//svg:g', ns):
        if g.get('{http://kanjivg.tagaini.net}element') == char:
            target_group = g
            break

    if target_group is None:
        raise ValueError(f"No stroke group found for kanji {char!r}")

    path_elements = target_group.findall('.//svg:path', ns)

    d_strings = []
    start_end = []
    for path in path_elements:
        d = path.get('d')
        if not d:
            continue
        d_strings.append(d)

        # Parse SVG path to get actual start and end points
        # Split by command letters to get segments
        commands = re.findall(r'[MmLlHhVvCcSsQqTtAaZz][^MmLlHhVvCcSsQqTtAaZz]*', d)
        
        sx, sy, ex, ey = None, None, None, None
        current_x, current_y = 0, 0
        
        for cmd in commands:
            cmd_letter = cmd[0]
            params = re.findall(r'(-?\d+(?:\.\d+)?)', cmd[1:])
            
            if not params:
                continue
                
            # M/m = move to (absolute/relative) - this is the start
            if cmd_letter in 'Mm':
                if len(params) >= 2:
                    if cmd_letter == 'M':
                        current_x, current_y = float(params[0]), float(params[1])
                    else:  # relative
                        current_x += float(params[0])
                        current_y += float(params[1])
                    if sx is None:  # First move is the start point
                        sx, sy = current_x, current_y
            
            # L/l = line to
            elif cmd_letter in 'Ll':
                if len(params) >= 2:
                    if cmd_letter == 'L':
                        current_x, current_y = float(params[-2]), float(params[-1])
                    else:
                        current_x += float(params[-2])
                        current_y += float(params[-1])
            
            # C/c = cubic bezier (last pair is endpoint)
            elif cmd_letter in 'Cc':
                if len(params) >= 6:
                    if cmd_letter == 'C':
                        current_x, current_y = float(params[-2]), float(params[-1])
                    else:
                        current_x += float(params[-2])
                        current_y += float(params[-1])
            
            # S/s = smooth cubic bezier
            elif cmd_letter in 'Ss':
                if len(params) >= 4:
                    if cmd_letter == 'S':
                        current_x, current_y = float(params[-2]), float(params[-1])
                    else:
                        current_x += float(params[-2])
                        current_y += float(params[-1])
            
            # Q/q = quadratic bezier
            elif cmd_letter in 'Qq':
                if len(params) >= 4:
                    if cmd_letter == 'Q':
                        current_x, current_y = float(params[-2]), float(params[-1])
                    else:
                        current_x += float(params[-2])
                        current_y += float(params[-1])
            
            # T/t = smooth quadratic bezier
            elif cmd_letter in 'Tt':
                if len(params) >= 2:
                    if cmd_letter == 'T':
                        current_x, current_y = float(params[-2]), float(params[-1])
                    else:
                        current_x += float(params[-2])
                        current_y += float(params[-1])
        
        ex, ey = current_x, current_y
        
        if sx is not None and ex is not None:
            start_end.append((sx, sy, ex, ey))
        else:
            start_end.append((None, None, None, None))

    numbers_group = None
    for g in root.findall('.//svg:g', ns):
        gid = g.get('id', '')
        if gid.startswith('kvg:StrokeNumbers_'):
            numbers_group = g
            break

    label_positions = []
    if numbers_group is not None:
        for text_elem in numbers_group.findall('svg:text', ns):
            transform = text_elem.get('transform', '')
            m = re.search(r'matrix\([^)]* ([\d\.\-]+) ([\d\.\-]+)\)', transform)
            if not m:
                continue
            x = float(m.group(1))
            y = float(m.group(2))
            try:
                num = int((text_elem.text or '').strip())
            except ValueError:
                continue
            label_positions.append((num, x, y))

    stroke_data = []
    if label_positions and len(label_positions) == len(d_strings):
        label_positions.sort(key=lambda t: t[0])
        for idx, d in enumerate(d_strings, start=1):
            num, x, y = label_positions[idx - 1]
            sx, sy, ex, ey = start_end[idx - 1]
            stroke_data.append({
                "index": num,
                "d": d,
                "label_x": x,
                "label_y": y,
                "start_x": sx,
                "start_y": sy,
                "end_x": ex,
                "end_y": ey,
            })
    else:
        for idx, d in enumerate(d_strings, start=1):
            sx, sy, ex, ey = start_end[idx - 1]
            stroke_data.append({
                "index": idx,
                "d": d,
                "label_x": None,
                "label_y": None,
                "start_x": sx,
                "start_y": sy,
                "end_x": ex,
                "end_y": ey,
            })

    return stroke_data


def _clear_canvas_ui():
    js = """
    (function() {
        const el = document.getElementById('kanji-draw-container');
        if (el) {
            el.remove();
        }
    })();
    """
    mw.reviewer.web.eval(js)


def _handle_side(card, use_answer: bool):
    """Common logic for front/back depending on config."""
    html = card.a() if use_answer else card.q()
    
    # Find all Japanese characters (kanji, hiragana, katakana)
    found_kanji = KANJI_REGEX.findall(html)
    found_hiragana = HIRAGANA_REGEX.findall(html)
    found_katakana = KATAKANA_REGEX.findall(html)
    
    all_chars = found_kanji + found_hiragana + found_katakana
    debugPrint(html)

    if not all_chars:
        return

    unique_chars = list(dict.fromkeys(all_chars))
    print("Detected Japanese characters on this card:", "".join(unique_chars))
    
    # Store card front text for practice menu (only on question side)
    if not use_answer:
        card_text = "".join(unique_chars)
        card_id = str(card.id)
        global CARD_STATS
        if card_id not in CARD_STATS:
            CARD_STATS[card_id] = {
                'frontText': card_text,
                'lastReviewed': datetime.now().isoformat()
            }
        else:
            CARD_STATS[card_id]['frontText'] = card_text
            CARD_STATS[card_id]['lastReviewed'] = datetime.now().isoformat()
        save_card_stats(CARD_STATS)

    char_list = []
    for ch in unique_chars:
        try:
            # Determine character type and get appropriate stroke data
            if KANJI_REGEX.match(ch):
                strokes = kanjiRenderer(ch)
            elif HIRAGANA_REGEX.match(ch) or KATAKANA_REGEX.match(ch):
                strokes = kanaRenderer(ch)
            else:
                continue
            
            if strokes:  # Only add if we have stroke data
                char_list.append({
                    "char": ch,
                    "strokes": strokes,
                })
        except Exception as e:
            debugPrint(f"Error getting strokes for {ch}: {e}")

    if not char_list:
        return

    # Detect card type: 0=new, 1=learning, 2=review, 3=relearning
    card_type = card.type if hasattr(card, 'type') else 0
    
    js_data = f"window.kanjiData = {json.dumps(char_list)};"
    js_card_type = f"window.kanjiCardType = {card_type};"
    mw.reviewer.web.eval(js_data)
    mw.reviewer.web.eval(js_card_type)
    inject_drawing_canvas()


def _on_show_question(card):
    # Always clear any old canvas from the previous card/side
    _clear_canvas_ui()

    if CONFIG.get("enable_on_front", True):
        _handle_side(card, use_answer=False)


def _on_show_answer(card):
    # Either show on back or explicitly remove it
    if CONFIG.get("enable_on_back", False):
        _handle_side(card, use_answer=True)
    else:
        _clear_canvas_ui()


gui_hooks.reviewer_did_show_question.append(_on_show_question)
gui_hooks.reviewer_did_show_answer.append(_on_show_answer)


def _handle_webview_message(handled, message, context):
    """Handle messages from the webview (pycmd calls from JavaScript)"""
    global KANJI_STATS
    
    if message.startswith("saveKanjiStats:"):
        # Format: saveKanjiStats:KANJI:JSON_STATS
        parts = message[15:].split(":", 1)  # Remove "saveKanjiStats:" prefix
        if len(parts) == 2:
            kanji = parts[0]
            try:
                stats = json.loads(parts[1])
                KANJI_STATS[kanji] = stats
                save_stats(KANJI_STATS)
                debugPrint(f"Saved stats for {kanji}: {stats}")
            except Exception as e:
                debugPrint(f"Error saving stats: {e}")
        return (True, "")
    
    elif message.startswith("recognizeDrawing:"):
        # Format: recognizeDrawing:<base64_image_data>
        image_data = message.split(":", 1)[1]
        debugPrint("Recognizing drawing with OpenRouter API...")
        
        text, confidence, all_results = recognize_handwriting(image_data)
        
        if text:
            # Send results back to JavaScript
            result_data = {
                'text': text,
                'confidence': confidence,
                'alternatives': [{'text': t, 'conf': c} for t, c in all_results[:5]]
            }
            result_json = json.dumps(result_data, ensure_ascii=False)
            mw.reviewer.web.eval(f"window.handleOCRResult && window.handleOCRResult({result_json});")
        else:
            mw.reviewer.web.eval("window.handleOCRResult && window.handleOCRResult(null);")
        
        return (True, "")
    
    return handled


gui_hooks.webview_did_receive_js_message.append(_handle_webview_message)


def inject_drawing_canvas():
    # Read config from Anki
    cfg = mw.addonManager.getConfig(__name__)
    hit_ratio = cfg.get("stroke_hit_ratio", 0.6)
    corridor = cfg.get("stroke_corridor_width", 10)
    auto_adv = "true" if cfg.get("auto_advance_kanji", False) else "false"
    validate_dir = "true" if cfg.get("check_direction", True) else "false"
    strict_order = "true" if cfg.get("strict_stroke_order", True) else "false"
    due_mode = cfg.get("due_mode", 1)

    # Inject config and stats into the webview
    stats_json = json.dumps(KANJI_STATS)
    js_cfg = f"""
    (function() {{
        window.KSO_CONFIG = {{
            hitRatio: {hit_ratio},
            corridorWidth: {corridor},
            autoAdvanceKanji: {auto_adv},
            validateDirection: {validate_dir},
            strictStrokeOrder: {strict_order},
            dueMode: {due_mode}
        }};
        window.KSO_STATS = {stats_json};
    }})();
    """
    mw.reviewer.web.eval(js_cfg)

    # Main UI/logic script
    js = r"""
    (function() {
        console.log('[Init] Starting kanji drawing UI...');
        
        // Remove any existing container to ensure fresh start
        const existingContainer = document.getElementById('kanji-draw-container');
        if (existingContainer) {
            console.log('[Init] Removing existing container');
            existingContainer.remove();
        }

        console.log('[Init] Reading config...');
        const cfg = window.KSO_CONFIG || {
            hitRatio: 0.6,
            corridorWidth: 10,
            autoAdvanceKanji: false,
            validateDirection: false,
            strictStrokeOrder: true,
            dueMode: 1,
        };
        const HIT_RATIO = cfg.hitRatio;
        const CORRIDOR_WIDTH = cfg.corridorWidth;
        const AUTO_ADVANCE_KANJI = cfg.autoAdvanceKanji;
        const VALIDATE_DIRECTION = !!cfg.validateDirection;
        const STRICT_STROKE_ORDER = !!cfg.strictStrokeOrder;
        const DUE_MODE = cfg.dueMode;
        
        console.log('[Config] STRICT_STROKE_ORDER:', STRICT_STROKE_ORDER);
        
        // Card type: 0=new, 1=learning, 2=review, 3=relearning
        const cardType = window.kanjiCardType || 0;
        const isDueCard = (cardType === 2 || cardType === 3);
        
        console.log('[Card] Type:', cardType, 'IsDue:', isDueCard, 'DueMode:', DUE_MODE);

        const rawKanjiData = window.kanjiData || [];
        if (!rawKanjiData.length) {
            console.log('[Init] No kanji data available');
            return;
        }

        console.log('[Init] Creating UI container...');
        
        // --- theme detection ---
        function getLuminance(r, g, b) {
            return (0.2126 * r + 0.7152 * g + 0.0722 * b) / 255;
        }

        function parseRGB(str) {
            const m = str.match(/rgba?\((\d+),\s*(\d+),\s*(\d+)/i);
            if (!m) return { r: 255, g: 255, b: 255 };
            return { r: parseInt(m[1], 10), g: parseInt(m[2], 10), b: parseInt(m[3], 10) };
        }

        const bodyStyle = getComputedStyle(document.body);
        const bg = parseRGB(bodyStyle.backgroundColor || 'rgb(255,255,255)');
        const isDark = getLuminance(bg.r, bg.g, bg.b) < 0.5;

        const baseStrokeCurrentColor = isDark
            ? 'rgba(255, 255, 255, 0.18)'
            : 'rgba(0, 0, 0, 0.18)';

        const baseStrokeOtherColor = isDark
            ? 'rgba(255, 255, 255, 0.05)'
            : 'rgba(0, 0, 0, 0.05)';

        const gridColor = isDark
            ? 'rgba(255, 255, 255, 0.15)'
            : 'rgba(0, 0, 0, 0.15)';

        const animatedStrokeColor = isDark
            ? 'rgba(255, 255, 255, 0.25)'
            : 'rgba(0, 0, 0, 0.25)';
        
        const container = document.createElement('div');
        container.id = 'kanji-draw-container';
        container.style.marginTop = '20px';
        container.style.display = 'flex';
        container.style.flexDirection = 'column';
        container.style.alignItems = 'center';

        const kanjiDisplay = document.createElement('div');
        kanjiDisplay.id = 'current-kanji-display';
        kanjiDisplay.style.fontSize = '24px';
        kanjiDisplay.style.fontWeight = 'bold';
        kanjiDisplay.style.marginBottom = '8px';
        kanjiDisplay.style.fontFamily = '-apple-system, BlinkMacSystemFont, "Segoe UI", system-ui, sans-serif';
        container.appendChild(kanjiDisplay);

        const statsDisplay = document.createElement('div');
        statsDisplay.id = 'kanji-stats-display';
        statsDisplay.style.fontSize = '12px';
        statsDisplay.style.marginBottom = '8px';
        statsDisplay.style.fontFamily = '-apple-system, BlinkMacSystemFont, "Segoe UI", system-ui, sans-serif';
        statsDisplay.style.color = isDark ? 'rgba(255, 255, 255, 0.7)' : 'rgba(0, 0, 0, 0.7)';
        container.appendChild(statsDisplay);

        const canvas = document.createElement('canvas');
        canvas.id = 'kanjiCanvas';
        canvas.width = 300;
        canvas.height = 300;
        canvas.style.border = '1px solid #ccc';
        canvas.style.touchAction = 'none';
        container.appendChild(canvas);

        const clearBtn = document.createElement('button');
        clearBtn.textContent = 'Clear';
        clearBtn.style.marginTop = '8px';
        clearBtn.style.fontFamily = '-apple-system, BlinkMacSystemFont, "Segoe UI", system-ui, sans-serif';
        clearBtn.style.fontWeight = '600';
        container.appendChild(clearBtn);

        const hintBtn = document.createElement('button');
        hintBtn.textContent = 'Hint';
        hintBtn.style.marginTop = '8px';
        hintBtn.style.marginLeft = '8px';
        hintBtn.style.fontFamily = clearBtn.style.fontFamily;
        hintBtn.style.fontWeight = clearBtn.style.fontWeight;
        hintBtn.style.display = (isDueCard && DUE_MODE === 1) ? 'inline-block' : 'none';
        container.appendChild(hintBtn);

        const navContainer = document.createElement('div');
        navContainer.style.marginTop = '8px';
        navContainer.style.display = 'flex';
        navContainer.style.gap = '8px';

        let prevBtn = document.createElement('button');
        prevBtn.textContent = 'Previous';
        prevBtn.style.fontFamily = clearBtn.style.fontFamily;
        prevBtn.style.fontWeight = clearBtn.style.fontWeight;

        let restartBtn = document.createElement('button');
        restartBtn.textContent = 'Restart';
        restartBtn.style.fontFamily = clearBtn.style.fontFamily;
        restartBtn.style.fontWeight = clearBtn.style.fontWeight;

        let nextBtn = document.createElement('button');
        nextBtn.textContent = 'Next';
        nextBtn.style.fontFamily = clearBtn.style.fontFamily;
        nextBtn.style.fontWeight = clearBtn.style.fontWeight;

        let resetStatsBtn = document.createElement('button');
        resetStatsBtn.textContent = 'Reset Stats';
        resetStatsBtn.style.fontFamily = clearBtn.style.fontFamily;
        resetStatsBtn.style.fontWeight = clearBtn.style.fontWeight;
        resetStatsBtn.style.fontSize = '11px';

        navContainer.appendChild(prevBtn);
        navContainer.appendChild(restartBtn);
        navContainer.appendChild(nextBtn);
        navContainer.appendChild(resetStatsBtn);
        container.appendChild(navContainer);

        document.body.appendChild(container);

        const ctx = canvas.getContext('2d');

        // Offscreen canvas for similarity checking (SVG 109x109)
        const offscreen = document.createElement('canvas');
        offscreen.width = 109;
        offscreen.height = 109;
        const offctx = offscreen.getContext('2d');

        const scaleX = canvas.width / 109;
        const scaleY = canvas.height / 109;

        let currentKanjiIndex = 0;
        let strokePaths = [];
        let completedStrokes = STRICT_STROKE_ORDER ? 0 : new Set();
        let currentStrokeIndex = 0;
        let previousStrokeIndex = 0;

        let drawProgress = 0;
        let repeatProgress = 0;
        const drawDuration = 12000;
        const repeatDuration = 1600;
        const dashLength = 1000;
        let lastTime = null;
        let animationFrameId = null;

        let userStrokes = [];
        let currentStroke = null;
        let currentStrokeSvg = null;
        let hintActive = false;

        // Store user strokes per kanji (only for current card session)
        let userStrokesPerKanji = {};

        // Performance tracking
        let sessionStartTime = null;
        let strokeErrors = 0;
        let directionErrors = 0;
        let totalRedraws = 0;

        // Stats storage (loaded from Python, synced back on save)
        let statsCache = window.KSO_STATS || {};

        // Load kanji stats from cache
        function loadKanjiStats(kanji) {
            if (statsCache[kanji]) {
                return statsCache[kanji];
            }
            return {
                totalAttempts: 0,
                consecutiveCorrect: 0,
                totalErrors: 0,
                totalDirectionErrors: 0,
                totalRedraws: 0,
                totalTime: 0,
                lastAttempt: null
            };
        }

        // Save kanji stats to Python backend
        function saveKanjiStats(kanji, stats) {
            // Update local cache
            statsCache[kanji] = stats;
            // Send to Python for persistent storage
            pycmd('saveKanjiStats:' + kanji + ':' + JSON.stringify(stats));
        }

        // Update stats display
        function updateStatsDisplay() {
            const currentKanji = rawKanjiData[currentKanjiIndex];
            if (!currentKanji) return;

            const char = currentKanji.char;
            const stats = loadKanjiStats(char);

            kanjiDisplay.textContent = 'Kanji: ' + char;

            let statsText = '';
            if (stats.totalAttempts > 0) {
                if (stats.consecutiveCorrect > 0) {
                    statsText = '\u2713 Drawn correctly ' + stats.consecutiveCorrect + ' time' + 
                                (stats.consecutiveCorrect > 1 ? 's' : '') + ' in a row';
                } else {
                    statsText = 'Attempts: ' + stats.totalAttempts + ' | Errors: ' + stats.totalErrors;
                }
            } else {
                statsText = 'First time practicing this kanji';
            }
            statsDisplay.textContent = statsText;
        }

        function saveCurrentKanjiState() {
            // Save current kanji's state to preserve strokes
            if (strokePaths.length > 0 && currentKanjiIndex >= 0) {
                userStrokesPerKanji[currentKanjiIndex] = {
                    strokes: userStrokes.slice(),
                    completedStrokes: STRICT_STROKE_ORDER ? completedStrokes : new Set(completedStrokes),
                    currentStrokeIndex: currentStrokeIndex
                };
            }
        }

        function loadCurrentKanji() {
            const currentKanji = rawKanjiData[currentKanjiIndex] || { strokes: [] };

            strokePaths = (currentKanji.strokes || []).map(s => ({
                index: s.index,
                path: new Path2D(s.d),
                label_x: s.label_x,
                label_y: s.label_y,
                start_x: s.start_x,
                start_y: s.start_y,
                end_x: s.end_x,
                end_y: s.end_y,
            }));

            // Restore previous strokes if they exist
            if (userStrokesPerKanji[currentKanjiIndex]) {
                const saved = userStrokesPerKanji[currentKanjiIndex];
                userStrokes = saved.strokes.slice(); // Deep copy
                completedStrokes = STRICT_STROKE_ORDER ? saved.completedStrokes : new Set(saved.completedStrokes);
                currentStrokeIndex = saved.currentStrokeIndex;
            } else {
                // Fresh kanji - initialize empty state
                completedStrokes = STRICT_STROKE_ORDER ? 0 : new Set();
                currentStrokeIndex = 0;
                userStrokes = [];
                
                // Save this initial empty state
                userStrokesPerKanji[currentKanjiIndex] = {
                    strokes: [],
                    completedStrokes: STRICT_STROKE_ORDER ? 0 : new Set(),
                    currentStrokeIndex: 0
                };
            }
            
            previousStrokeIndex = currentStrokeIndex;
            currentStroke = null;
            currentStrokeSvg = null;
            drawProgress = 0;
            repeatProgress = 0;

            // Reset session stats only for new kanji
            if (!userStrokesPerKanji[currentKanjiIndex]) {
                sessionStartTime = Date.now();
                strokeErrors = 0;
                directionErrors = 0;
                totalRedraws = 0;
            }

            prevBtn.disabled = currentKanjiIndex === 0;
            nextBtn.disabled = currentKanjiIndex === rawKanjiData.length - 1;

            updateStatsDisplay();
        }

        loadCurrentKanji();

        function drawBase() {
            ctx.save();
            ctx.scale(scaleX, scaleY);

            const current = strokePaths[currentStrokeIndex];

            ctx.lineWidth = 4;
            ctx.lineCap = 'round';
            ctx.lineJoin = 'round';
            ctx.setLineDash([]);

            // Determine which strokes to show based on mode
            let showStroke = (s, idx) => true;
            let showNumber = (s, idx) => true;
            
            if (isDueCard) {
                if (DUE_MODE === 1) {
                    // Mode 1: Minimal Help
                    // Show completed strokes + first stroke initially + current stroke when hint pressed
                    const numCompleted = STRICT_STROKE_ORDER ? completedStrokes : completedStrokes.size;
                    
                    showStroke = (s, idx) => {
                        const isComplete = STRICT_STROKE_ORDER ? idx < completedStrokes : completedStrokes.has(idx);
                        const isCurrent = (s === current);
                        const isFirstStroke = (idx === 0);
                        
                        if (isComplete) return true;  // Always show completed
                        if (isFirstStroke && numCompleted === 0) return true;  // Show first stroke initially
                        if (isCurrent && hintActive) return true;  // Show current when hint pressed
                        return false;
                    };
                    showNumber = (s, idx) => {
                        const isComplete = STRICT_STROKE_ORDER ? idx < completedStrokes : completedStrokes.has(idx);
                        const isCurrent = (s === current);
                        const isFirstStroke = (idx === 0);
                        
                        if (isComplete) return true;
                        if (isFirstStroke && numCompleted === 0) return true;
                        if (isCurrent && hintActive) return true;
                        return false;
                    };
                } else if (DUE_MODE === 2) {
                    // Mode 2: Full Help - show everything (like learning cards)
                    showStroke = () => true;
                    showNumber = () => true;
                } else if (DUE_MODE === 3) {
                    // Mode 3: Procedural - no numbers, show completed + current stroke
                    showStroke = (s, idx) => {
                        const isComplete = STRICT_STROKE_ORDER ? idx < completedStrokes : completedStrokes.has(idx);
                        const isCurrent = (s === current);
                        return isComplete || isCurrent;
                    };
                    showNumber = () => false;  // Never show numbers in mode 3
                }
            }

            // Draw strokes
            for (let idx = 0; idx < strokePaths.length; idx++) {
                const s = strokePaths[idx];
                if (!showStroke(s, idx)) continue;
                
                if (s === current) {
                    ctx.strokeStyle = baseStrokeCurrentColor;
                } else {
                    ctx.strokeStyle = baseStrokeOtherColor;
                }
                ctx.stroke(s.path);
            }

            // Draw stroke numbers
            ctx.font = '8px sans-serif';
            for (let idx = 0; idx < strokePaths.length; idx++) {
                const s = strokePaths[idx];
                if (s.label_x == null) continue;
                if (!showNumber(s, idx)) continue;
                
                if (s === current) {
                    ctx.fillStyle = 'rgba(255, 0, 0, 0.75)';
                } else {
                    ctx.fillStyle = 'rgba(255, 0, 0, 0.20)';
                }
                ctx.fillText(String(s.index), s.label_x, s.label_y);
            }

            ctx.restore();
        }

        function drawAnimatedStroke() {
            const current = strokePaths[currentStrokeIndex];
            if (!current) return;

            // Check if we should show the animated stroke based on mode
            if (isDueCard && DUE_MODE === 1) {
                const numCompleted = STRICT_STROKE_ORDER ? completedStrokes : completedStrokes.size;
                const isFirstStroke = (currentStrokeIndex === 0);
                
                // In Mode 1, only show animation for first stroke initially or when hint is active
                if (!(isFirstStroke && numCompleted === 0) && !hintActive) {
                    return;
                }
            }

            ctx.save();
            ctx.scale(scaleX, scaleY);
            ctx.lineWidth = 5;
            ctx.lineCap = 'round';
            ctx.lineJoin = 'round';
            ctx.strokeStyle = animatedStrokeColor;

            ctx.setLineDash([dashLength, dashLength]);
            ctx.lineDashOffset = dashLength * (1 - drawProgress);

            ctx.stroke(current.path);
            ctx.restore();
        }

        function drawUserStrokes() {
            ctx.save();
            ctx.lineWidth = 4;
            ctx.lineCap = 'round';
            ctx.strokeStyle = '#000';

            for (const stroke of userStrokes) {
                if (!stroke || stroke.length < 2) continue;
                ctx.beginPath();
                ctx.moveTo(stroke[0].x, stroke[0].y);
                for (let i = 1; i < stroke.length; i++) {
                    ctx.lineTo(stroke[i].x, stroke[i].y);
                }
                ctx.stroke();
            }
            ctx.restore();
        }

        function drawGrid() {
            ctx.save();
            ctx.scale(scaleX, scaleY);

            const W = 109, H = 109;

            ctx.strokeStyle = gridColor;
            ctx.lineWidth = 2;
            ctx.setLineDash([]);
            ctx.strokeRect(0, 0, W, H);

            ctx.lineWidth = 1;
            ctx.strokeStyle = gridColor;
            ctx.setLineDash([3, 4]);

            ctx.beginPath();
            ctx.moveTo(W / 2, 0);
            ctx.lineTo(W / 2, H);
            ctx.stroke();

            ctx.beginPath();
            ctx.moveTo(0, H / 2);
            ctx.lineTo(W, H / 2);
            ctx.stroke();

            ctx.restore();
        }

        function isStrokeCloseEnough(svgPoints, canonicalPath) {
            if (!canonicalPath || !svgPoints || svgPoints.length < 5) {
                return false;
            }

            const W = 109, H = 109;

            // 1) Render canonical stroke into offscreen
            offctx.clearRect(0, 0, W, H);
            offctx.save();
            offctx.lineWidth = CORRIDOR_WIDTH;
            offctx.lineCap = 'round';
            offctx.strokeStyle = '#ffffff';
            offctx.setLineDash([]);
            offctx.stroke(canonicalPath);
            offctx.restore();

            const img = offctx.getImageData(0, 0, W, H);
            const data = img.data;

            // 2) Canonical stroke bounding box
            let minCX = W, maxCX = -1;
            let minCY = H, maxCY = -1;

            for (let y = 0; y < H; y++) {
                for (let x = 0; x < W; x++) {
                    const idx = (y * W + x) * 4;
                    const alpha = data[idx + 3];
                    if (alpha > 0) {
                        if (x < minCX) minCX = x;
                        if (x > maxCX) maxCX = x;
                        if (y < minCY) minCY = y;
                        if (y > maxCY) maxCY = y;
                    }
                }
            }
            if (maxCX < minCX || maxCY < minCY) {
                return false;
            }

            const canonW = maxCX - minCX + 1;
            const canonH = maxCY - minCY + 1;
            const canonDiag = Math.hypot(canonW, canonH); // overall stroke size

            // 3) User stroke length + bounding box in SVG coords
            let userLen = 0;
            let minUX = Infinity, maxUX = -Infinity;
            let minUY = Infinity, maxUY = -Infinity;

            for (let i = 0; i < svgPoints.length; i++) {
                const p = svgPoints[i];
                if (i > 0) {
                    const prev = svgPoints[i - 1];
                    userLen += Math.hypot(p.x - prev.x, p.y - prev.y);
                }
                if (p.x < minUX) minUX = p.x;
                if (p.x > maxUX) maxUX = p.x;
                if (p.y < minUY) minUY = p.y;
                if (p.y > maxUY) maxUY = p.y;
            }
            if (!isFinite(minUX) || !isFinite(minUY)) {
                return false;
            }

            const userW = maxUX - minUX;
            const userH = maxUY - minUY;

            // 4) Corridor hit ratio
            let hits = 0;
            let total = 0;
            const step = Math.max(1, Math.floor(svgPoints.length / 40));

            for (let i = 0; i < svgPoints.length; i += step) {
                const p = svgPoints[i];
                const x = Math.round(p.x);
                const y = Math.round(p.y);
                if (x < 0 || x >= W || y < 0 || y >= H) {
                    continue;
                }
                total++;
                const idx = (y * W + x) * 4;
                const alpha = data[idx + 3];
                if (alpha > 0) {
                    hits++;
                }
            }
            if (total === 0) {
                return false;
            }
            const ratio = hits / total;

            // 5) Size-dependent thresholds
            const SMALL_DIAG = 20;
            const LARGE_DIAG = 80;

            let t = 0;
            if (canonDiag <= SMALL_DIAG) {
                t = 0;
            } else if (canonDiag >= LARGE_DIAG) {
                t = 1;
            } else {
                t = (canonDiag - SMALL_DIAG) / (LARGE_DIAG - SMALL_DIAG);
            }

            const MIN_LENGTH_FRAC_SMALL = 0.50;
            const MIN_LENGTH_FRAC_LARGE = 0.85;

            const MIN_MAIN_FRAC_SMALL = 0.50;
            const MIN_MAIN_FRAC_LARGE = 0.80;

            const MIN_ABS_LENGTH_SMALL = 5;
            const MIN_ABS_LENGTH_LARGE = 10;

            const MIN_LENGTH_FRAC =
                MIN_LENGTH_FRAC_SMALL + t * (MIN_LENGTH_FRAC_LARGE - MIN_LENGTH_FRAC_SMALL);
            const MIN_MAIN_FRAC =
                MIN_MAIN_FRAC_SMALL + t * (MIN_MAIN_FRAC_LARGE - MIN_MAIN_FRAC_SMALL);
            const MIN_ABS_LENGTH =
                MIN_ABS_LENGTH_SMALL + t * (MIN_ABS_LENGTH_LARGE - MIN_ABS_LENGTH_SMALL);

            const hasEnoughLength =
                userLen >= MIN_ABS_LENGTH &&
                (canonDiag <= 0 || userLen / canonDiag >= MIN_LENGTH_FRAC);

            // main axis coverage: compare coverage along whichever axis the stroke is "longer" in
            const canonMain = canonW >= canonH ? canonW : canonH;
            const userMain  = canonW >= canonH ? userW  : userH;
            const mainFrac  = canonMain > 0 ? userMain / canonMain : 1;
            const hasEnoughExtent = mainFrac >= MIN_MAIN_FRAC;

            return hasEnoughLength && hasEnoughExtent && ratio >= HIT_RATIO;
        }

        function isDirectionCorrect(svgPoints, strokeMeta) {
            // If direction checking is off, always accept.
            if (!VALIDATE_DIRECTION) {
                console.log('[Direction] Validation disabled');
                return true;
            }
            if (!strokeMeta || !svgPoints || svgPoints.length < 2) {
                console.log('[Direction] Missing metadata or insufficient points');
                return true; // don't block on missing meta
            }

            const sx = strokeMeta.start_x;
            const sy = strokeMeta.start_y;
            const ex = strokeMeta.end_x;
            const ey = strokeMeta.end_y;

            console.log('[Direction] Canonical endpoints: start=(' + sx + ',' + sy + ') end=(' + ex + ',' + ey + ')');

            // If we don't have canonical endpoints, skip direction enforcement
            if (sx == null || sy == null || ex == null || ey == null) {
                console.log('[Direction] Missing canonical endpoints - skipping validation');
                return true;
            }

            const first = svgPoints[0];
            const last  = svgPoints[svgPoints.length - 1];

            // User stroke vector
            const ux = last.x - first.x;
            const uy = last.y - first.y;
            const ulen = Math.hypot(ux, uy);
            
            console.log('[Direction] User stroke: start=(' + first.x.toFixed(1) + ',' + first.y.toFixed(1) + ') end=(' + last.x.toFixed(1) + ',' + last.y.toFixed(1) + ') vector=(' + ux.toFixed(1) + ',' + uy.toFixed(1) + ')');
            
            if (ulen < 5) {
                // Very short stroke; direction is noisy, don't enforce
                console.log('[Direction] Stroke too short - skipping validation');
                return true;
            }

            // Canonical stroke vector
            const cx = ex - sx;
            const cy = ey - sy;
            const clen = Math.hypot(cx, cy);
            
            console.log('[Direction] Canonical vector: (' + cx.toFixed(1) + ',' + cy.toFixed(1) + ') length=' + clen.toFixed(1));
            
            if (clen < 1) {
                console.log('[Direction] Canonical stroke too short');
                return true;
            }

            const dot = (ux * cx + uy * cy) / (ulen * clen);
            const passed = dot >= 0.3;
            
            console.log('[Direction] Dot product: ' + dot.toFixed(3) + ' Passed: ' + passed);
            
            // dot = 1   => same direction
            // dot = 0   => perpendicular
            // dot = -1  => exact opposite
            // Allow up to ~70° deviation; reverse (dot ~ -1) will fail.
            return passed;
        }


        function drawScene(timestamp) {
            if (lastTime === null) lastTime = timestamp;
            const dt = timestamp - lastTime;
            lastTime = timestamp;

            // Reset animation if current stroke changed
            if (currentStrokeIndex !== previousStrokeIndex) {
                drawProgress = 0;
                repeatProgress = 0;
                previousStrokeIndex = currentStrokeIndex;
            }

            drawProgress += dt / drawDuration;
            if (drawProgress > 1) drawProgress = 1;

            repeatProgress += dt / repeatDuration;
            if (repeatProgress >= 1) {
                repeatProgress = 0;
                drawProgress = 0;
            }

            ctx.clearRect(0, 0, canvas.width, canvas.height);

            drawGrid();
            drawBase();
            drawAnimatedStroke();
            drawUserStrokes();

            animationFrameId = requestAnimationFrame(drawScene);
        }

        animationFrameId = requestAnimationFrame(drawScene);

        let drawing = false;

        function getOffsetPos(evt) {
            const rect = canvas.getBoundingClientRect();
            let cx, cy;
            if (evt.touches && evt.touches.length > 0) {
                cx = evt.touches[0].clientX;
                cy = evt.touches[0].clientY;
            } else {
                cx = evt.clientX;
                cy = evt.clientY;
            }
            return { x: cx - rect.left, y: cy - rect.top };
        }

        function startDraw(evt) {
            evt.preventDefault();
            const pos = getOffsetPos(evt);
            drawing = true;

            currentStroke = [{ x: pos.x, y: pos.y }];
            currentStrokeSvg = [{ x: pos.x / scaleX, y: pos.y / scaleY }];
            userStrokes.push(currentStroke);
        }

        function moveDraw(evt) {
            if (!drawing) return;
            evt.preventDefault();
            const pos = getOffsetPos(evt);
            if (currentStroke) {
                currentStroke.push({ x: pos.x, y: pos.y });
            }
            if (currentStrokeSvg) {
                currentStrokeSvg.push({ x: pos.x / scaleX, y: pos.y / scaleY });
            }
        }

        function endDraw(evt) {
            if (!drawing) return;
            evt.preventDefault();
            drawing = false;

            if (!currentStrokeSvg || currentStrokeSvg.length < 5) {
                userStrokes.pop();
                currentStroke = null;
                currentStrokeSvg = null;
                return;
            }

            let matchedStroke = null;
            let matchedIndex = -1;

            if (STRICT_STROKE_ORDER) {
                // Strict mode: only check the current expected stroke
                const canonical = strokePaths[completedStrokes];
                console.log('[Validation] Strict mode - checking stroke', completedStrokes);
                if (canonical) {
                    const okShape = isStrokeCloseEnough(currentStrokeSvg, canonical.path);
                    const okDirection = isDirectionCorrect(currentStrokeSvg, canonical);
                    if (okShape && okDirection) {
                        matchedStroke = canonical;
                        matchedIndex = completedStrokes;
                    } else if (okShape && !okDirection) {
                        directionErrors++;
                    }
                }
            } else {
                // Non-strict mode: check against all incomplete strokes
                console.log('[Validation] Non-strict mode - checking all incomplete strokes');
                console.log('[Validation] Completed strokes:', Array.from(completedStrokes));
                for (let i = 0; i < strokePaths.length; i++) {
                    if (completedStrokes.has(i)) continue;
                    
                    const canonical = strokePaths[i];
                    console.log('[Validation] Trying stroke', i);
                    const okShape = isStrokeCloseEnough(currentStrokeSvg, canonical.path);
                    const okDirection = isDirectionCorrect(currentStrokeSvg, canonical);
                    
                    console.log('[Validation] Stroke', i, 'shape:', okShape, 'direction:', okDirection);
                    
                    if (okShape && okDirection) {
                        matchedStroke = canonical;
                        matchedIndex = i;
                        console.log('[Validation] Matched stroke', i);
                        break;
                    } else if (okShape && !okDirection) {
                        // Track direction errors separately
                        directionErrors++;
                    }
                }
            }

            if (matchedStroke) {
                // Mark stroke as completed
                if (STRICT_STROKE_ORDER) {
                    completedStrokes = Math.min(completedStrokes + 1, strokePaths.length);
                } else {
                    completedStrokes.add(matchedIndex);
                }

                // Update currentStrokeIndex to next incomplete stroke
                currentStrokeIndex = 0;
                while (currentStrokeIndex < strokePaths.length) {
                    if (STRICT_STROKE_ORDER) {
                        if (currentStrokeIndex >= completedStrokes) break;
                    } else {
                        if (!completedStrokes.has(currentStrokeIndex)) break;
                    }
                    currentStrokeIndex++;
                }

                // Save state after successful stroke
                saveCurrentKanjiState();

                // Check if all strokes completed
                const allComplete = STRICT_STROKE_ORDER 
                    ? completedStrokes >= strokePaths.length
                    : completedStrokes.size >= strokePaths.length;

                if (allComplete) {
                    // Save stats when kanji is completed
                    const currentKanji = rawKanjiData[currentKanjiIndex];
                    if (currentKanji) {
                        const stats = loadKanjiStats(currentKanji.char);
                        const sessionTime = Date.now() - sessionStartTime;
                        
                        stats.totalAttempts++;
                        stats.totalErrors += strokeErrors;
                        stats.totalDirectionErrors += directionErrors;
                        stats.totalRedraws += totalRedraws;
                        stats.totalTime += sessionTime;
                        stats.lastAttempt = Date.now();
                        stats.lastReviewDate = new Date().toISOString();
                        
                        // Update consecutive correct
                        if (strokeErrors === 0 && directionErrors === 0) {
                            stats.consecutiveCorrect++;
                        } else {
                            stats.consecutiveCorrect = 0;
                        }
                        
                        saveKanjiStats(currentKanji.char, stats);
                        updateStatsDisplay();
                    }
                    
                    if (AUTO_ADVANCE_KANJI && currentKanjiIndex < rawKanjiData.length - 1) {
                        currentKanjiIndex++;
                        loadCurrentKanji();
                    }
                }
            } else {
                userStrokes.pop();
                strokeErrors++;
            }

            currentStroke = null;
            currentStrokeSvg = null;
        }

        if (window.PointerEvent) {
            canvas.addEventListener('pointerdown', startDraw);
            canvas.addEventListener('pointermove', moveDraw);
            canvas.addEventListener('pointerup', endDraw);
            canvas.addEventListener('pointercancel', endDraw);
        } else {
            canvas.addEventListener('mousedown', startDraw);
            canvas.addEventListener('mousemove', moveDraw);
            canvas.addEventListener('mouseup', endDraw);
            canvas.addEventListener('mouseleave', endDraw);

            canvas.addEventListener('touchstart', startDraw, { passive: false });
            canvas.addEventListener('touchmove', moveDraw, { passive: false });
            canvas.addEventListener('touchend', endDraw, { passive: false });
            canvas.addEventListener('touchcancel', endDraw, { passive: false });
        }

        clearBtn.addEventListener('click', function() {
            if (userStrokes.length > 0) {
                totalRedraws++;
            }
            // Clear only current kanji's strokes
            userStrokes = [];
            currentStroke = null;
            currentStrokeSvg = null;
            completedStrokes = STRICT_STROKE_ORDER ? 0 : new Set();
            currentStrokeIndex = 0;
            previousStrokeIndex = 0;
            drawProgress = 0;
            repeatProgress = 0;
            
            // Update the stored state for current kanji
            userStrokesPerKanji[currentKanjiIndex] = {
                strokes: [],
                completedStrokes: STRICT_STROKE_ORDER ? 0 : new Set(),
                currentStrokeIndex: 0
            };
        });

        hintBtn.addEventListener('click', function() {
            hintActive = true;
            setTimeout(() => {
                hintActive = false;
            }, 3000); // Show hint for 3 seconds
        });

        resetStatsBtn.addEventListener('click', function() {
            const currentKanji = rawKanjiData[currentKanjiIndex];
            if (currentKanji && confirm('Reset stats for ' + currentKanji.char + '?')) {
                // Reset stats in cache and save to Python
                delete statsCache[currentKanji.char];
                pycmd('saveKanjiStats:' + currentKanji.char + ':' + JSON.stringify({
                    totalAttempts: 0,
                    consecutiveCorrect: 0,
                    totalErrors: 0,
                    totalDirectionErrors: 0,
                    totalRedraws: 0,
                    totalTime: 0,
                    lastAttempt: null
                }));
                updateStatsDisplay();
            }
        });

        prevBtn.addEventListener('click', function() {
            if (currentKanjiIndex > 0) {
                saveCurrentKanjiState();
                currentKanjiIndex--;
                loadCurrentKanji();
            }
        });

        nextBtn.addEventListener('click', function() {
            if (currentKanjiIndex < rawKanjiData.length - 1) {
                saveCurrentKanjiState();
                currentKanjiIndex++;
                loadCurrentKanji();
            }
        });

        restartBtn.addEventListener('click', function() {
            // Clear all kanji strokes and start from first kanji
            userStrokesPerKanji = {};
            currentKanjiIndex = 0;
            loadCurrentKanji();
        });

    })();
    """
    mw.reviewer.web.eval(js)


# ============================================================================
# Phase 2A: Practice Menu UI
# ============================================================================

class AIConfigDialog(QDialog):
    """Dialog for configuring AI sentence generation."""
    
    def __init__(self, config, parent=None):
        super().__init__(parent)
        self.setWindowTitle("AI Configuration")
        self.setMinimumSize(600, 500)
        
        self.config = config.copy()
        self.setup_ui()
    
    def setup_ui(self):
        """Create the AI config dialog UI."""
        layout = QVBoxLayout()
        
        # Title
        title = QLabel("<h2>AI Sentence Generation Configuration</h2>")
        layout.addWidget(title)
        
        # API URL
        api_group = QGroupBox("API Settings")
        api_layout = QVBoxLayout()
        
        url_layout = QHBoxLayout()
        url_label = QLabel("API URL:")
        self.url_input = QLineEdit()
        self.url_input.setPlaceholderText("https://api.openai.com/v1/chat/completions")
        self.url_input.setText(self.config.get('api_url', ''))
        url_layout.addWidget(url_label)
        url_layout.addWidget(self.url_input)
        api_layout.addLayout(url_layout)
        
        # API Key
        key_layout = QHBoxLayout()
        key_label = QLabel("API Key:")
        self.key_input = QLineEdit()
        self.key_input.setPlaceholderText("sk-...")
        self.key_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.key_input.setText(self.config.get('api_key', ''))
        key_layout.addWidget(key_label)
        key_layout.addWidget(self.key_input)
        api_layout.addLayout(key_layout)
        
        # Model for sentence generation
        model_layout = QHBoxLayout()
        model_label = QLabel("Sentence Generation & Feedback Model:")
        self.model_input = QLineEdit()
        self.model_input.setPlaceholderText("google/gemini-2.5-flash")
        self.model_input.setText(self.config.get('model', ''))
        model_layout.addWidget(model_label)
        model_layout.addWidget(self.model_input)
        api_layout.addLayout(model_layout)
        
        # Model for OCR
        ocr_model_layout = QHBoxLayout()
        ocr_model_label = QLabel("Handwriting Recognition Model:")
        self.ocr_model_input = QLineEdit()
        self.ocr_model_input.setPlaceholderText("google/gemini-2.0-flash-001")
        self.ocr_model_input.setText(self.config.get('ocr_model', ''))
        ocr_model_layout.addWidget(ocr_model_label)
        ocr_model_layout.addWidget(self.ocr_model_input)
        api_layout.addLayout(ocr_model_layout)
        
        api_group.setLayout(api_layout)
        layout.addWidget(api_group)
        
        # Instructions
        instr_group = QGroupBox("Instructions && Context")
        instr_layout = QVBoxLayout()
        
        instr_label = QLabel("Extra instructions for sentence generation:")
        instr_layout.addWidget(instr_label)
        
        self.instructions_input = QTextEdit()
        self.instructions_input.setPlaceholderText(
            "Enter any specific instructions for generating sentences...\n"
            "For example:\n"
            "- Use JLPT N3 vocabulary\n"
            "- Focus on daily conversation\n"
            "- Include formal and informal examples"
        )
        self.instructions_input.setText(self.config.get('instructions', ''))
        self.instructions_input.setMinimumHeight(150)
        instr_layout.addWidget(self.instructions_input)
        
        # PDF attachment
        pdf_layout = QHBoxLayout()
        pdf_label = QLabel("Attach PDF (optional):")
        self.pdf_path_label = QLabel(self.config.get('pdf_path', 'No file selected'))
        if self.config.get('pdf_path', ''):
            self.pdf_path_label.setStyleSheet("color: black; background-color: #f0f0f0; padding: 5px; border-radius: 3px;")
        else:
            self.pdf_path_label.setStyleSheet("color: gray; font-style: italic; background-color: #f0f0f0; padding: 5px; border-radius: 3px;")
        
        browse_btn = QPushButton("Browse...")
        browse_btn.clicked.connect(self.browse_pdf)
        
        clear_pdf_btn = QPushButton("Clear")
        clear_pdf_btn.clicked.connect(self.clear_pdf)
        
        pdf_layout.addWidget(pdf_label)
        pdf_layout.addWidget(self.pdf_path_label, 1)
        pdf_layout.addWidget(browse_btn)
        pdf_layout.addWidget(clear_pdf_btn)
        instr_layout.addLayout(pdf_layout)
        
        instr_group.setLayout(instr_layout)
        layout.addWidget(instr_group)
        
        # Buttons
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        
        save_btn = QPushButton("Save")
        save_btn.clicked.connect(self.accept)
        save_btn.setStyleSheet("QPushButton { background-color: #4CAF50; color: white; font-weight: bold; padding: 8px; }")
        button_layout.addWidget(save_btn)
        
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(cancel_btn)
        
        layout.addLayout(button_layout)
        
        self.setLayout(layout)
    
    def browse_pdf(self):
        """Open file dialog to select PDF."""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select PDF File",
            "",
            "PDF Files (*.pdf);;All Files (*)"
        )
        
        if file_path:
            self.config['pdf_path'] = file_path
            self.pdf_path_label.setText(file_path)
            self.pdf_path_label.setStyleSheet("color: black; background-color: #f0f0f0; padding: 5px; border-radius: 3px;")
    
    def clear_pdf(self):
        """Clear selected PDF."""
        self.config['pdf_path'] = ''
        self.pdf_path_label.setText('No file selected')
        self.pdf_path_label.setStyleSheet("color: gray; font-style: italic; background-color: #f0f0f0; padding: 5px; border-radius: 3px;")
    
    def get_config(self):
        """Get the current configuration."""
        self.config['api_url'] = self.url_input.text()
        self.config['api_key'] = self.key_input.text()
        self.config['model'] = self.model_input.text()
        self.config['ocr_model'] = self.ocr_model_input.text()
        self.config['instructions'] = self.instructions_input.toPlainText()
        # Save to file
        save_ai_config(self.config)
        return self.config


class KanjiPracticeDialog(QDialog):
    """Standalone practice interface for kanji stroke order practice."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Kanji Stroke Order Practice")
        self.setMinimumSize(800, 600)
        
        # Available cards from card stats
        global CARD_STATS
        self.all_cards = CARD_STATS
        self.selected_cards = []
        self.date_range_start = None
        self.date_range_end = None
        
        # Sentence source configuration
        self.ai_config = load_ai_config()
        self.sentence_source = self.ai_config.get('sentence_source', 'fields')  # "fields" or "ai"
        
        self.setup_ui()
        
        # Restore saved sentence source selection
        if self.sentence_source == "ai":
            self.source_combo.setCurrentIndex(1)
        else:
            self.source_combo.setCurrentIndex(0)
    
    def setup_ui(self):
        """Create the dialog UI."""
        layout = QVBoxLayout()
        
        # Title
        title = QLabel("<h2>Kanji Stroke Order Practice</h2>")
        layout.addWidget(title)
        
        # Info label
        self.info_label = QLabel(f"Available cards: {len(self.all_cards)} (from your review history)")
        layout.addWidget(self.info_label)
        
        # Time range filter
        time_layout = QHBoxLayout()
        time_label = QLabel("Filter by last review:")
        self.time_range_combo = QComboBox()
        self.time_range_combo.addItems([
            "All time",
            "Last 1 day",
            "Last 2 days",
            "Last 3 days",
            "Last 1 week",
            "Last 2 weeks",
            "Last 1 month",
            "Custom..."
        ])
        self.time_range_combo.currentTextChanged.connect(self.on_time_range_changed)
        time_layout.addWidget(time_label)
        time_layout.addWidget(self.time_range_combo)
        time_layout.addStretch()
        layout.addLayout(time_layout)
        
        # Sentence source selection
        source_layout = QHBoxLayout()
        source_label = QLabel("Sentence source:")
        self.source_combo = QComboBox()
        self.source_combo.addItems([
            "Card fields (Expression, Reading, etc.)",
            "AI-generated sentences"
        ])
        self.source_combo.currentIndexChanged.connect(self.on_source_changed)
        
        self.config_ai_btn = QPushButton("Configure AI")
        self.config_ai_btn.clicked.connect(self.open_ai_config)
        
        source_layout.addWidget(source_label)
        source_layout.addWidget(self.source_combo)
        source_layout.addWidget(self.config_ai_btn)
        source_layout.addStretch()
        layout.addLayout(source_layout)
        
        # Date range display (shown when time range selected)
        self.date_range_label = QLabel("")
        self.date_range_label.setVisible(False)
        self.date_range_label.setStyleSheet("padding: 5px; background-color: #4CAF50; border-radius: 3px;")
        layout.addWidget(self.date_range_label)
        layout.addWidget(self.date_range_label)
        
        # Search box
        search_layout = QHBoxLayout()
        search_label = QLabel("Search:")
        self.search_box = QLineEdit()
        self.search_box.setPlaceholderText("Type to filter cards...")
        self.search_box.textChanged.connect(self.filter_cards)
        search_layout.addWidget(search_label)
        search_layout.addWidget(self.search_box)
        layout.addLayout(search_layout)
        
        # Card list
        list_label = QLabel("Select cards to practice:")
        layout.addWidget(list_label)
        
        self.card_list = QListWidget()
        self.card_list.setSelectionMode(QAbstractItemView.SelectionMode.MultiSelection)
        self.populate_card_list()
        layout.addWidget(self.card_list)
        
        # Buttons
        button_layout = QHBoxLayout()
        
        select_all_btn = QPushButton("Select All")
        select_all_btn.clicked.connect(self.select_all)
        button_layout.addWidget(select_all_btn)
        
        clear_btn = QPushButton("Clear Selection")
        clear_btn.clicked.connect(self.clear_selection)
        button_layout.addWidget(clear_btn)
        
        button_layout.addStretch()
        
        start_btn = QPushButton("Start Practice")
        start_btn.clicked.connect(self.start_practice)
        start_btn.setStyleSheet("QPushButton { background-color: #4CAF50; color: white; font-weight: bold; padding: 8px; }")
        button_layout.addWidget(start_btn)
        
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(cancel_btn)
        
        layout.addLayout(button_layout)
        
        self.setLayout(layout)
    
    def populate_card_list(self, filter_text=""):
        """Populate the list with available cards."""
        self.card_list.clear()
        
        filtered_cards = self.get_filtered_cards_by_date()
        
        # Sort cards by last reviewed date (most recent first)
        sorted_cards = sorted(
            filtered_cards.items(),
            key=lambda x: x[1].get('lastReviewed', ''),
            reverse=True
        )
        
        for card_id, card_data in sorted_cards:
            front_text = card_data.get('frontText', '')
            
            # Apply text filter
            if filter_text and filter_text not in front_text:
                continue
            
            # Get last reviewed date
            last_reviewed = card_data.get('lastReviewed', None)
            review_text = ""
            
            if last_reviewed:
                try:
                    review_date = datetime.fromisoformat(last_reviewed)
                    days_ago = (datetime.now() - review_date).days
                    if days_ago == 0:
                        review_text = " - reviewed today"
                    elif days_ago == 1:
                        review_text = " - reviewed yesterday"
                    else:
                        review_text = f" - reviewed {days_ago} days ago"
                except:
                    pass
            
            item_text = f"{front_text}{review_text}"
            
            item = QListWidgetItem(item_text)
            item.setData(256, card_id)  # Store card ID in user role
            item.setData(257, front_text)  # Store front text
            self.card_list.addItem(item)
        
        # Update info label
        total_cards = len(filtered_cards)
        self.info_label.setText(f"Showing {self.card_list.count()} of {total_cards} cards")
    
    def get_filtered_cards_by_date(self):
        """Filter cards using Anki's rated search."""
        # Use Anki's search functionality to find rated cards
        col = mw.col
        
        # Calculate days for rated search (add 1 to include the start day)
        if self.date_range_start is None:
            # "All time" - use a very large number to get all reviewed cards
            days = 36500  # ~100 years
        else:
            days = (datetime.now() - self.date_range_start).days + 1
            if days < 1:
                days = 1
        
        # Search for cards rated in the last N days
        search_query = f"rated:{days}"
        
        try:
            debugPrint(f"Searching with query: {search_query}")
            # Get card IDs from search
            card_ids = col.find_cards(search_query)
            debugPrint(f"Found {len(card_ids)} cards from rated search")
            
            # Build filtered dict by getting card data directly from Anki
            filtered = {}
            for card_id in card_ids:
                try:
                    card = col.get_card(card_id)
                    note = card.note()
                    
                    # Get the question (front) of the card
                    question_html = card.question()
                    
                    # Extract Japanese characters
                    found_kanji = KANJI_REGEX.findall(question_html)
                    found_hiragana = HIRAGANA_REGEX.findall(question_html)
                    found_katakana = KATAKANA_REGEX.findall(question_html)
                    
                    all_chars = found_kanji + found_hiragana + found_katakana
                    
                    if all_chars:
                        unique_chars = list(dict.fromkeys(all_chars))
                        front_text = "".join(unique_chars)
                        
                        card_id_str = str(card_id)
                        
                        # Get the actual last review date from the card's review history
                        # card.id is in milliseconds, card.mod is last modified timestamp
                        # We need to get from revlog
                        revlog_entries = col.db.all(
                            "SELECT id FROM revlog WHERE cid = ? ORDER BY id DESC LIMIT 1",
                            card_id
                        )
                        
                        if revlog_entries:
                            # revlog.id is timestamp in milliseconds
                            last_review_ms = revlog_entries[0][0]
                            last_review_date = datetime.fromtimestamp(last_review_ms / 1000.0)
                            last_reviewed = last_review_date.isoformat()
                        else:
                            last_reviewed = datetime.now().isoformat()
                        
                        # Check if we have it in CARD_STATS, otherwise create entry
                        if card_id_str in self.all_cards:
                            # Update with actual review date
                            filtered[card_id_str] = {
                                'frontText': front_text,
                                'lastReviewed': last_reviewed
                            }
                        else:
                            # Create new entry with card data from Anki
                            filtered[card_id_str] = {
                                'frontText': front_text,
                                'lastReviewed': last_reviewed
                            }
                except Exception as e:
                    debugPrint(f"Error processing card {card_id}: {e}")
                    continue
            
            debugPrint(f"Filtered to {len(filtered)} cards with Japanese characters")
            return filtered
        except Exception as e:
            debugPrint(f"Error searching rated cards: {e}")
            import traceback
            debugPrint(traceback.format_exc())
            return self.all_cards
    
    def on_time_range_changed(self, text):
        """Handle time range dropdown selection."""
        if text == "All time":
            self.date_range_start = None
            self.date_range_label.setVisible(False)
        elif text == "Custom...":
            # Show calendar popup
            self.show_calendar_popup()
            return  # Don't repopulate yet, wait for calendar selection
        else:
            # Preset time ranges - calculate start date for rated search
            today = datetime.now()
            
            if "1 day" in text:
                self.date_range_start = today - timedelta(days=1)
                self.date_range_label.setText("Showing cards reviewed in the last 1 day")
            elif "2 days" in text:
                self.date_range_start = today - timedelta(days=2)
                self.date_range_label.setText("Showing cards reviewed in the last 2 days")
            elif "3 days" in text:
                self.date_range_start = today - timedelta(days=3)
                self.date_range_label.setText("Showing cards reviewed in the last 3 days")
            elif "1 week" in text:
                self.date_range_start = today - timedelta(weeks=1)
                self.date_range_label.setText("Showing cards reviewed in the last week")
            elif "2 weeks" in text:
                self.date_range_start = today - timedelta(weeks=2)
                self.date_range_label.setText("Showing cards reviewed in the last 2 weeks")
            elif "1 month" in text:
                self.date_range_start = today - timedelta(days=30)
                self.date_range_label.setText("Showing cards reviewed in the last month")
            
            self.date_range_label.setVisible(True)
        
        self.populate_card_list(self.search_box.text())
    
    def show_calendar_popup(self):
        """Show a popup calendar dialog for selecting a single date."""
        dialog = QDialog(self)
        dialog.setWindowTitle("Select Date")
        dialog.setModal(True)
        
        layout = QVBoxLayout()
        
        info = QLabel("Click a date to show cards reviewed from that day to today")
        info.setStyleSheet("padding: 10px; background-color: #4CAF50; border-radius: 3px;")
        layout.addWidget(info)
        
        calendar = QCalendarWidget()
        calendar.setMaximumDate(calendar.selectedDate())  # Can't select future dates
        layout.addWidget(calendar)
        
        btn_layout = QHBoxLayout()
        ok_btn = QPushButton("OK")
        cancel_btn = QPushButton("Cancel")
        btn_layout.addStretch()
        btn_layout.addWidget(ok_btn)
        btn_layout.addWidget(cancel_btn)
        layout.addLayout(btn_layout)
        
        dialog.setLayout(layout)
        
        def on_ok():
            selected_date = calendar.selectedDate()
            self.date_range_start = datetime(selected_date.year(), selected_date.month(), selected_date.day())
            days_ago = (datetime.now() - self.date_range_start).days
            day_text = "day" if days_ago == 1 else "days"
            self.date_range_label.setText(f"Showing cards reviewed from {self.date_range_start.strftime('%Y-%m-%d')} to today ({days_ago} {day_text})")
            self.date_range_label.setVisible(True)
            self.populate_card_list(self.search_box.text())
            dialog.accept()
        
        def on_cancel():
            # Reset to "All time"
            self.time_range_combo.setCurrentText("All time")
            dialog.reject()
        
        ok_btn.clicked.connect(on_ok)
        cancel_btn.clicked.connect(on_cancel)
        
        dialog.exec()
    
    def on_source_changed(self, index):
        """Handle sentence source selection change."""
        if index == 0:
            self.sentence_source = "fields"
        else:
            self.sentence_source = "ai"
        
        # Save selection to config
        self.ai_config['sentence_source'] = self.sentence_source
        save_ai_config(self.ai_config)
    
    def open_ai_config(self):
        """Open AI configuration dialog."""
        dialog = AIConfigDialog(self.ai_config, self)
        if dialog.exec():
            self.ai_config = dialog.get_config()
    
    def filter_cards(self, text):
        """Filter card list based on search text."""
        self.populate_card_list(text)
    
    def select_all(self):
        """Select all visible items."""
        for i in range(self.card_list.count()):
            self.card_list.item(i).setSelected(True)
    
    def clear_selection(self):
        """Clear all selections."""
        self.card_list.clearSelection()
    
    def start_practice(self):
        """Start practice with selected cards."""
        try:
            debugPrint("start_practice called")
            
            selected_items = self.card_list.selectedItems()
            debugPrint(f"Selected items: {len(selected_items)}")
            
            if not selected_items:
                QMessageBox.warning(self, "No Selection", "Please select at least one card to practice.")
                return
            
            # Get card data for practice
            card_data_list = []
            for item in selected_items:
                card_id = item.data(256)
                try:
                    card = mw.col.get_card(int(card_id))
                    note = card.note()
                    
                    # Extract fields
                    fields = {field: note[field] for field in note.keys()}
                    card_data_list.append({
                        'card_id': card_id,
                        'fields': fields,
                        'front_text': item.data(257)
                    })
                except Exception as e:
                    debugPrint(f"Error loading card {card_id}: {e}")
            
            if not card_data_list:
                QMessageBox.warning(self, "Error", "Could not load any card data.")
                return
            
            debugPrint(f"Starting practice with {len(card_data_list)} cards")
            
            # Close this dialog
            self.accept()
            
            # Open practice window (separate window, not in main reviewer)
            # Pass None as parent to make it completely independent
            practice_window = KanjiPracticeWindow(card_data_list, self.sentence_source, None)
            practice_window.show()
            
            # Keep a reference to prevent garbage collection
            mw._practice_window = practice_window
            
        except Exception as e:
            debugPrint(f"Error in start_practice: {e}")
            import traceback
            debugPrint(traceback.format_exc())
            QMessageBox.critical(self, "Error", f"Failed to start practice: {str(e)}")


# NOTE: Duplicate KanjiPracticeWindow class removed
# The working implementation with OpenRouter API OCR support is integrated above


def inject_drawing_canvas_to_webview(webview):
    """Inject the drawing canvas into a standalone webview."""
    # Same JS as inject_drawing_canvas() but adapted for standalone use
    js = r"""
    (function() {
        console.log('[Practice] Starting kanji drawing UI...');
        
        const existingContainer = document.getElementById('kanji-draw-container');
        if (existingContainer) {
            existingContainer.remove();
        }

        const cfg = window.KSO_CONFIG || {
            hitRatio: 0.6,
            corridorWidth: 10,
            autoAdvanceKanji: false,
            validateDirection: false,
            strictStrokeOrder: true,
            dueMode: 2,
        };
        const HIT_RATIO = cfg.hitRatio;
        const CORRIDOR_WIDTH = cfg.corridorWidth;
        const AUTO_ADVANCE_KANJI = cfg.autoAdvanceKanji;
        const VALIDATE_DIRECTION = !!cfg.validateDirection;
        const STRICT_STROKE_ORDER = !!cfg.strictStrokeOrder;
        const DUE_MODE = cfg.dueMode;
        
        const cardType = window.kanjiCardType || 0;
        const isDueCard = (cardType === 2 || cardType === 3);

        const rawKanjiData = window.kanjiData || [];
        if (!rawKanjiData.length) {
            console.log('[Practice] No kanji data available');
            return;
        }

        const bodyStyle = getComputedStyle(document.body);
        const isDark = false; // Default to light theme for practice window

        const baseStrokeCurrentColor = 'rgba(0, 0, 0, 0.18)';
        const baseStrokeOtherColor = 'rgba(0, 0, 0, 0.05)';
        const gridColor = 'rgba(0, 0, 0, 0.15)';
        const animatedStrokeColor = 'rgba(0, 0, 0, 0.25)';
    """ + """
        const container = document.createElement('div');
        container.id = 'kanji-draw-container';
        container.style.marginTop = '20px';
        container.style.display = 'flex';
        container.style.flexDirection = 'column';
        container.style.alignItems = 'center';

        const kanjiDisplay = document.createElement('div');
        kanjiDisplay.id = 'current-kanji-display';
        kanjiDisplay.style.fontSize = '32px';
        kanjiDisplay.style.fontWeight = 'bold';
        kanjiDisplay.style.marginBottom = '12px';
        kanjiDisplay.style.fontFamily = '-apple-system, BlinkMacSystemFont, "Segoe UI", system-ui, sans-serif';
        container.appendChild(kanjiDisplay);

        const statsDisplay = document.createElement('div');
        statsDisplay.id = 'kanji-stats-display';
        statsDisplay.style.fontSize = '14px';
        statsDisplay.style.marginBottom = '12px';
        statsDisplay.style.fontFamily = '-apple-system, BlinkMacSystemFont, "Segoe UI", system-ui, sans-serif';
        statsDisplay.style.color = 'rgba(0, 0, 0, 0.7)';
        container.appendChild(statsDisplay);

        const canvas = document.createElement('canvas');
        canvas.id = 'kanjiCanvas';
        canvas.width = 400;
        canvas.height = 400;
        canvas.style.border = '2px solid #333';
        canvas.style.borderRadius = '8px';
        canvas.style.touchAction = 'none';
        container.appendChild(canvas);

        const clearBtn = document.createElement('button');
        clearBtn.textContent = 'Clear';
        clearBtn.style.marginTop = '12px';
        clearBtn.style.padding = '10px 20px';
        clearBtn.style.fontSize = '16px';
        clearBtn.style.fontFamily = '-apple-system, BlinkMacSystemFont, "Segoe UI", system-ui, sans-serif';
        clearBtn.style.fontWeight = '600';
        clearBtn.style.cursor = 'pointer';
        container.appendChild(clearBtn);

        const navContainer = document.createElement('div');
        navContainer.style.marginTop = '12px';
        navContainer.style.display = 'flex';
        navContainer.style.gap = '12px';

        let prevBtn = document.createElement('button');
        prevBtn.textContent = 'Previous';
        prevBtn.style.padding = '8px 16px';
        prevBtn.style.cursor = 'pointer';
        prevBtn.style.fontFamily = clearBtn.style.fontFamily;
        prevBtn.style.fontWeight = clearBtn.style.fontWeight;

        let nextBtn = document.createElement('button');
        nextBtn.textContent = 'Next';
        nextBtn.style.padding = '8px 16px';
        nextBtn.style.cursor = 'pointer';
        nextBtn.style.fontFamily = clearBtn.style.fontFamily;
        nextBtn.style.fontWeight = clearBtn.style.fontWeight;

        navContainer.appendChild(prevBtn);
        navContainer.appendChild(nextBtn);
        container.appendChild(navContainer);

        document.body.appendChild(container);
    """ + inject_drawing_canvas.__code__.co_consts[1][2000:]  # Reuse the rest of the canvas logic
    
    webview.eval(js)


class KanjiPracticeWindow(QDialog):
    """Separate window for kanji practice."""
    
    def __init__(self, card_data_list, sentence_source, parent=None):
        super().__init__(parent)
        
        # Import AnkiWebView
        from aqt.webview import AnkiWebView
        
        self.card_data_list = card_data_list
        self.sentence_source = sentence_source
        self.current_index = 0
        
        # Cache for storing answers and feedback across navigation
        self.card_cache = {}
        
        # Track completion status
        self.answered_cards = set()  # Set of card indices that have been answered
        self.correct_cards = set()   # Set of card indices that were correct
        self.on_completion_screen = False  # Track if we're showing completion screen
        self.completion_summary = None  # Cache AI summary for the session
        
        self.setWindowTitle("Kanji Practice")
        self.setMinimumSize(900, 700)
        
        # Make window non-modal so user can interact with main Anki window
        self.setModal(False)
        
        # Set window flags to show minimize/maximize buttons
        from aqt.qt import Qt
        self.setWindowFlags(Qt.WindowType.Window | Qt.WindowType.WindowMinMaxButtonsHint | Qt.WindowType.WindowCloseButtonHint)
        
        # Create layout
        layout = QVBoxLayout()
        self.setLayout(layout)
        
        # Create web view
        self.web = AnkiWebView(parent=self)
        layout.addWidget(self.web)
        
        # Set up message handler
        gui_hooks.webview_did_receive_js_message.append(self.handle_message)
        
        # Load first card
        self.load_current_card()
    
    def handle_message(self, handled, message, context):
        """Handle messages from JavaScript."""
        # Accept messages from our webview or with None context (some Anki versions)
        if context is not None and context != self.web:
            return (handled, None)
        
        try:
            # print(f"[KanjiPracticeWindow] Received message: {message}")
            
            if message.startswith("charRecognized:"):
                char = message.split(":", 1)[1]
                print(f"[KanjiPracticeWindow] Character recognized: {char}")
                return (True, None)
            
            elif message.startswith("recognizeDrawing:"):
                # Format: recognizeDrawing:<base64_image_data>
                image_data = message.split(":", 1)[1]
                print(f"[KanjiPracticeWindow] Recognizing drawing...")
                
                text, confidence, all_results = recognize_handwriting(image_data)
                
                if text:
                    # Send results back to JavaScript
                    result_data = {
                        'text': text,
                        'confidence': confidence,
                        'alternatives': [{'text': t, 'conf': c} for t, c in all_results[:5]]
                    }
                    result_json = json.dumps(result_data, ensure_ascii=False)
                    self.web.eval(f"window.handleOCRResult({result_json});")
                else:
                    self.web.eval("window.handleOCRResult(null);")
                
                return (True, None)
            
            elif message.startswith("lookupKanji:"):
                char = message.split(":", 1)[1]
                print(f"[KanjiPracticeWindow] Looking up kanji: {char}")
                self.inject_kanji_strokes(char)
                return (True, None)
            
            elif message == "nextCard":
                self.next_card()
                return (True, None)
            
            elif message == "prevCard":
                self.prev_card()
                return (True, None)
            
            elif message == "closePractice":
                self.close()
                return (True, None)
            
            elif message == "finishPractice":
                self.show_completion_screen()
                return (True, None)
            
            elif message.startswith('saveCache:'):
                try:
                    cache_data = json.loads(message.split(':', 1)[1])
                    card_idx = cache_data.get('cardIndex')
                    if card_idx is not None:
                        self.card_cache[card_idx] = {
                            'answer': cache_data.get('answer', ''),
                            'feedback': cache_data.get('feedback', ''),
                            'feedbackClass': cache_data.get('feedbackClass', '')
                        }
                        debugPrint(f"Cached data for card {card_idx}")
                        
                        # Track answered and correct cards
                        if cache_data.get('feedback'):
                            self.answered_cards.add(card_idx)
                            if cache_data.get('feedbackClass') == 'result correct':
                                self.correct_cards.add(card_idx)
                except Exception as e:
                    debugPrint(f"Error saving cache: {e}")
                return (True, None)
            
            elif message.startswith("getFeedback:"):
                # Format: getFeedback:{"english":"...","accepted":"...","submitted":"..."}
                try:
                    feedback_data = json.loads(message.split(":", 1)[1])
                    english = feedback_data.get('english', '')
                    accepted = feedback_data.get('accepted', '')
                    submitted = feedback_data.get('submitted', '')
                    
                    print(f"[KanjiPracticeWindow] Getting feedback for: '{submitted}' vs '{accepted}'")
                    
                    # Get AI feedback
                    feedback = self.get_ai_feedback(english, accepted, submitted)
                    
                    if feedback:
                        # Send feedback back to JavaScript
                        feedback_json = json.dumps(feedback, ensure_ascii=False)
                        self.web.eval(f"window.handleFeedback({feedback_json});")
                    else:
                        self.web.eval("window.handleFeedback(null);")
                    
                    return (True, None)
                except Exception as e:
                    print(f"[KanjiPracticeWindow] Error processing feedback request: {e}")
                    self.web.eval("window.handleFeedback(null);")
                    return (True, None)
                
        except Exception as e:
            print(f"[KanjiPracticeWindow] Error handling message: {e}")
            import traceback
            traceback.print_exc()
            
            # Show error in UI
            error_js = f"""
            var status = document.getElementById('status');
            if (status) {{
                status.textContent = '❌ Error: {str(e).replace("'", "\\'")}';
                status.style.backgroundColor = '#f44336';
                status.style.color = 'white';
                status.style.display = 'block';
            }}
            """
            try:
                self.web.eval(error_js)
            except:
                pass
        
        return (handled, None)
    
    def get_ai_feedback(self, english, accepted, submitted):
        """Get AI feedback on the submitted answer."""
        try:
            # Load AI config
            ai_config = load_ai_config()
            api_key = ai_config.get('api_key', '')
            api_url = ai_config.get('api_url') or 'https://openrouter.ai/api/v1/chat/completions'
            model = ai_config.get('model') or 'google/gemini-2.5-flash'
            
            if not api_key:
                debugPrint("AI feedback not available - API key not configured")
                return None
            
            debugPrint(f"Using API key: {api_key[:10]}... (length: {len(api_key)})")
            debugPrint(f"API URL: {api_url}")
            debugPrint(f"Model: {model}")
            
            # Build prompt
            prompt = f"""English: {english}
Japanese translation: {accepted}
Attempted Japanese translation: {submitted}

If the attempted translation is correct AND matches the given Japanese sentence, immediately return ✅ Correct

If the attempted translation is incorrect, focus on conceptually why the translation is not correct in a markdown format and include the GIVEN Japanese translation as part of the feedback.

When showing Japanese text with kanji, use furigana format: 漢字[かんじ] (kanji followed by reading in square brackets)."""
            
            # Prepare API request
            headers = {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json"
            }
            
            payload = {
                "model": model,
                "messages": [
                    {
                        "role": "user",
                        "content": prompt
                    }
                ]
            }
            
            debugPrint(f"Requesting AI feedback for: '{submitted}' vs '{accepted}'")
            
            # Make API request
            request = urllib.request.Request(
                api_url,
                data=json.dumps(payload).encode('utf-8'),
                headers=headers
            )
            
            with urllib.request.urlopen(request, timeout=30) as response:
                result = json.loads(response.read().decode('utf-8'))
            
            # Extract feedback
            if result.get('choices') and len(result['choices']) > 0:
                feedback = result['choices'][0]['message']['content'].strip()
                debugPrint(f"AI feedback: {feedback[:100]}...")
                
                # Extract kanji characters from the accepted answer
                import re
                kanji_pattern = re.compile(r'[\u4E00-\u9FFF]')
                kanji_chars = kanji_pattern.findall(accepted)
                
                # Bold and italicize each unique kanji in the feedback
                if kanji_chars:
                    unique_kanji = list(dict.fromkeys(kanji_chars))  # Preserve order, remove duplicates
                    for kanji in unique_kanji:
                        # Replace kanji with bold+italic version (***kanji***)
                        # Skip if already formatted with ** or ***
                        # Use negative lookbehind/lookahead to avoid:
                        # - kanji inside furigana brackets
                        # - kanji already surrounded by ** or ***
                        feedback = re.sub(
                            f'(?<!\\*)(?<![\\[])({re.escape(kanji)})(?![\\]])(?!\\*)',
                            r'***\1***',
                            feedback
                        )
                
                return feedback
            
            return None
            
        except urllib.error.HTTPError as e:
            if e.code == 401:
                debugPrint(f"Error getting AI feedback: HTTP 401 Unauthorized")
                debugPrint(f"Your API key may be invalid or expired. Please check your configuration.")
                debugPrint(f"API URL: {api_url}")
                return "⚠️ **API Authentication Error**: Your API key appears to be invalid or expired. Please check your AI configuration settings."
            else:
                debugPrint(f"Error getting AI feedback: HTTP Error {e.code}: {e.reason}")
                import traceback
                traceback.print_exc()
                return None
        except Exception as e:
            debugPrint(f"Error getting AI feedback: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    def load_current_card(self):
        """Load the current card into the web view."""
        current_card = self.card_data_list[self.current_index]
        fields = current_card['fields']
        
        # Get English sentence
        english = fields.get('Sentence-English', fields.get('English', ''))
        if not english:
            for key in fields:
                if 'english' in key.lower():
                    english = fields[key]
                    break
        
        if not english:
            english = "(No English sentence found in card)"
        
        # Build HTML for practice interface
        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <style>
                body {{
                    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", system-ui, sans-serif;
                    padding: 20px;
                    max-width: 900px;
                    margin: 0 auto;
                }}
                .progress {{
                    padding: 10px;
                    background-color: #2196F3;
                    color: white;
                    font-weight: bold;
                    border-radius: 5px;
                    margin-bottom: 15px;
                }}
                .english {{
                    padding: 15px;
                    font-size: 16px;
                    background-color: #e8e8e8;
                    border-radius: 5px;
                    margin: 10px 0;
                    color: #000;
                }}
                .input-group {{
                    border: 1px solid #ddd;
                    padding: 15px;
                    border-radius: 5px;
                    margin: 10px 0 25px 0;
                }}
                input[type="text"] {{
                    width: 100%;
                    font-size: 14px;
                    padding: 6px 10px;
                    border: 1px solid #ccc;
                    border-radius: 3px;
                    font-family: 'Yu Gothic', 'MS Gothic', sans-serif;
                    line-height: 1.4;
                    height: auto;
                    box-sizing: border-box;
                }}
                .dict-group {{
                    border: 1px solid #ddd;
                    padding: 15px;
                    border-radius: 5px;
                    margin: 10px 0;
                }}
                .dict-search {{
                    display: flex;
                    gap: 10px;
                    align-items: center;
                    margin-bottom: 10px;
                }}
                .dict-search input {{
                    flex: 1;
                    font-family: 'Yu Gothic', 'MS Gothic', sans-serif;
                    font-size: 14px;
                    padding: 6px 10px;
                }}
                .status {{
                    padding: 8px;
                    font-weight: bold;
                    border-radius: 3px;
                    margin: 10px 0;
                    display: none;
                }}
                .canvas-group {{
                    border: 1px solid #ddd;
                    padding: 15px;
                    border-radius: 5px;
                    margin: 10px 0;
                    text-align: center;
                }}
                .canvas-info {{
                    color: #666;
                    font-style: italic;
                    padding: 5px;
                    margin-bottom: 10px;
                }}
                .controls {{
                    display: flex;
                    gap: 10px;
                    justify-content: center;
                    margin: 10px 0;
                }}
                .btn-primary {{
                    background-color: #4CAF50;
                    color: white;
                    padding: 8px 16px;
                    border: none;
                    border-radius: 3px;
                    cursor: pointer;
                    font-weight: bold;
                }}
                .btn-primary:hover {{
                    background-color: #45a049;
                }}
                .result {{
                    padding: 15px;
                    font-size: 14px;
                    border-radius: 5px;
                    margin: 10px 0;
                    display: none;
                    line-height: 1.6;
                }}
                .result.correct {{
                    background-color: #4CAF50;
                    color: white;
                    border: 2px solid #45a049;
                }}
                .result.incorrect {{
                    background-color: #2196F3;
                    color: white;
                    border: 2px solid #1976D2;
                }}
                .result h1, .result h2, .result h3 {{
                    margin-top: 0.5em;
                    margin-bottom: 0.5em;
                }}
                .result ul, .result ol {{
                    margin-left: 20px;
                }}
                .result code {{
                    background-color: rgba(0,0,0,0.05);
                    padding: 2px 4px;
                    border-radius: 3px;
                    font-family: 'Courier New', monospace;
                }}
                .result strong {{
                    color: #00f5d5;
                }}
                .nav-controls {{
                    display: flex;
                    gap: 10px;
                    justify-content: center;
                    margin-top: 20px;
                    padding-top: 15px;
                    border-top: 1px solid #ddd;
                }}
            </style>
        </head>
        <body>
            <div class="progress">Card {self.current_index + 1} of {len(self.card_data_list)}</div>
            <div class="english">{english}</div>
            
            <div class="input-group">
                <label><b>Your Answer</b></label>
                <input type="text" id="japanese-input" placeholder="Type or draw Japanese characters...">
            </div>
            
            <div class="dict-group">
                <label><b>Dictionary Lookup</b></label>
                <div class="dict-search">
                    <span>Search kanji:</span>
                    <input type="text" id="dict-search" placeholder="Enter word/kanji to practice...">
                    <button onclick="lookupDictionary()">Look Up</button>
                </div>
            </div>
            
            <div class="status" id="status"></div>
            
            <div class="canvas-group">
                <div class="canvas-info" id="canvas-info">Free drawing mode - draw any character</div>
                <div id="canvas-container"></div>
                <div class="controls">
                    <button onclick="window.undoStroke()" id="undo-btn" disabled>← Undo</button>
                    <button onclick="window.redoStroke()" id="redo-btn" disabled>→ Redo</button>
                    <button onclick="window.submitDrawing()">Submit Drawing</button>
                    <button onclick="window.clearCanvas()">Clear Canvas</button>
                </div>
            </div>
            
            <div class="controls">
                <button class="btn-primary" onclick="submitAnswer()">Submit Answer</button>
                <button onclick="skipCard()">Skip</button>
            </div>
            
            <div class="result" id="result"></div>
            
            <div class="nav-controls">
                <button onclick="pycmd('prevCard')" {"disabled" if self.current_index == 0 else ""}>Previous Card</button>
                <button id="next-button" onclick="pycmd('nextCard')" {"disabled" if self.current_index >= len(self.card_data_list) - 1 else ""}>Next Card</button>
                <button onclick="pycmd('closePractice')">Close Practice</button>
            </div>
        </body>
        </html>
        """
        
        # Get accepted Japanese translation
        japanese = fields.get('Expression', fields.get('Sentence-Japanese', fields.get('Japanese', '')))
        if not japanese:
            for key in fields:
                if 'japanese' in key.lower() or 'expression' in key.lower():
                    japanese = fields[key]
                    break
        if not japanese:
            japanese = ''
        
        # Trim whitespace from accepted answer
        japanese = japanese.strip()
        
        # Add JavaScript for drawing and interaction
        js_code = self.get_practice_js()
        
        # Get cached data for this card from Python
        cached = self.card_cache.get(self.current_index, {})
        
        # Inject card data into JavaScript
        card_data_js = f"""
        <script>
        window.cardEnglish = {json.dumps(english)};
        window.cardJapanese = {json.dumps(japanese)};
        window.currentCardIndex = {self.current_index};
        window.totalCards = {len(self.card_data_list)};
        window.answeredCards = {json.dumps(list(self.answered_cards))};
        
        // Function to update Next button to Finish button when appropriate
        window.updateNextButton = function() {{
            var nextButton = document.getElementById('next-button');
            if (!nextButton) return;
            
            // Check if we're on last card and all cards are answered
            var isLastCard = window.currentCardIndex >= window.totalCards - 1;
            var allAnswered = window.answeredCards.length >= window.totalCards;
            
            if (isLastCard && allAnswered) {{
                // Convert to Finish button
                nextButton.textContent = 'Finish';
                nextButton.className = 'btn-primary';
                nextButton.onclick = function() {{ pycmd('finishPractice'); }};
                nextButton.disabled = false;
            }} else if (isLastCard) {{
                // On last card but not all answered - keep disabled
                nextButton.disabled = true;
            }} else {{
                // Not on last card - keep as Next Card, enabled
                nextButton.textContent = 'Next Card';
                nextButton.className = '';
                nextButton.onclick = function() {{ pycmd('nextCard'); }};
                nextButton.disabled = false;
            }}
        }};
        
        // Restore cached answer and feedback for this card from Python cache
        setTimeout(function() {{
            var cache = {json.dumps(cached)};
            if (cache && Object.keys(cache).length > 0) {{
                var input = document.getElementById('japanese-input');
                var result = document.getElementById('result');
                if (input && cache.answer !== undefined && cache.answer !== '') {{
                    input.value = cache.answer;
                }}
                if (result && cache.feedback !== undefined && cache.feedback !== '') {{
                    result.innerHTML = cache.feedback;
                    result.className = cache.feedbackClass || 'result';
                    result.style.display = 'block';
                }}
            }}
            
            // Update button state on page load
            window.updateNextButton();
        }}, 100);
        </script>
        """
        
        full_html = html + card_data_js + "<script>" + js_code + "</script>"
        
        self.web.stdHtml(full_html, css=[], js=[])
    
    def next_card(self):
        """Move to next card or show completion screen."""
        if self.on_completion_screen:
            # Already on completion, do nothing or could cycle back to first card
            return
        
        if self.current_index < len(self.card_data_list) - 1:
            self.current_index += 1
            self.load_current_card()
    
    def prev_card(self):
        """Move to previous card."""
        if self.on_completion_screen:
            # Go back to last card from completion screen
            self.on_completion_screen = False
            self.current_index = len(self.card_data_list) - 1
            self.load_current_card()
        elif self.current_index > 0:
            self.current_index -= 1
            self.load_current_card()
    
    def get_practice_js(self):
        """Get JavaScript code for practice interface."""
        return """
        // Initialize undo/redo functionality
        window.undoHistory = [];
        window.updateUndoRedoButtons = function() {
            var undoBtn = document.getElementById('undo-btn');
            var redoBtn = document.getElementById('redo-btn');
            if (undoBtn) undoBtn.disabled = !window.currentStrokes || window.currentStrokes.length === 0;
            if (redoBtn) redoBtn.disabled = !window.undoHistory || window.undoHistory.length === 0;
        };
        
        window.undoStroke = function() {
            if (!window.currentStrokes || window.currentStrokes.length === 0) return;
            
            // Remove last stroke and add to redo history
            var lastStroke = window.currentStrokes.pop();
            window.undoHistory.push(lastStroke);
            
            // Update stroke index if in dictionary mode
            if (window.dictionaryMode && window.currentStrokeIndex > 0) {
                window.currentStrokeIndex--;
            }
            
            window.updateUndoRedoButtons();
            if (window.redrawCanvas) window.redrawCanvas();
        };
        
        window.redoStroke = function() {
            if (window.undoHistory.length === 0) return;
            
            // Restore last undone stroke
            var stroke = window.undoHistory.pop();
            window.currentStrokes.push(stroke);
            
            // Update stroke index if in dictionary mode
            if (window.dictionaryMode && window.currentStrokeIndex < window.ghostStrokes.length) {
                window.currentStrokeIndex++;
            }
            
            window.updateUndoRedoButtons();
            if (window.redrawCanvas) window.redrawCanvas();
        };
        
        // Initialize canvas on page load
        (function() {
            function initCanvas() {
                var container = document.getElementById('canvas-container');
                if (!container) {
                    console.error('Canvas container not found');
                    return;
                }
                
                // Create canvas
                var canvas = document.createElement('canvas');
                canvas.id = 'drawing-canvas';
                canvas.width = 300;
                canvas.height = 300;
                canvas.style.border = '2px solid #333';
                canvas.style.cursor = 'crosshair';
                canvas.style.touchAction = 'none';
                container.appendChild(canvas);
                
                window.ctx = canvas.getContext('2d');
                window.isDrawing = false;
                window.currentStrokes = [];
                window.currentStroke = null;
                window.currentStrokeIndex = 0;
                window.ghostStrokes = [];
                window.dictionaryMode = false;
                window.animationStartTime = null;
                
                // Set up event listeners for drawing
                canvas.addEventListener('pointerdown', window.startDrawing);
                canvas.addEventListener('pointermove', window.draw);
                canvas.addEventListener('pointerup', window.endDrawing);
                canvas.addEventListener('pointercancel', window.endDrawing);
                
                // Draw initial grid
                window.drawGrid();
                
                // Initialize undo/redo button states
                window.updateUndoRedoButtons();
                
                console.log('Canvas initialized');
            }
            
            // Drawing helper functions
            function getPos(evt) {
                var canvas = document.getElementById('drawing-canvas');
                if (!canvas) return {x: 0, y: 0};
                var rect = canvas.getBoundingClientRect();
                var cx, cy;
                if (evt.touches && evt.touches.length > 0) {
                    cx = evt.touches[0].clientX;
                    cy = evt.touches[0].clientY;
                } else {
                    cx = evt.clientX;
                    cy = evt.clientY;
                }
                return { x: cx - rect.left, y: cy - rect.top };
            }
            
            // Offscreen canvas for stroke validation
            var offscreenCanvas = document.createElement('canvas');
            offscreenCanvas.width = 109;
            offscreenCanvas.height = 109;
            var offctx = offscreenCanvas.getContext('2d');
            
            window.isStrokeCloseEnough = function(svgPoints, canonicalPath) {
                if (!canonicalPath || !svgPoints || svgPoints.length < 5) {
                    return false;
                }
                
                var W = 109, H = 109;
                var HIT_RATIO = 0.6;
                var CORRIDOR_WIDTH = 10;
                
                // Render canonical stroke
                offctx.clearRect(0, 0, W, H);
                offctx.save();
                offctx.lineWidth = CORRIDOR_WIDTH;
                offctx.lineCap = 'round';
                offctx.strokeStyle = '#ffffff';
                offctx.setLineDash([]);
                offctx.stroke(canonicalPath);
                offctx.restore();
                
                var img = offctx.getImageData(0, 0, W, H);
                var data = img.data;
                
                // Get canonical bounding box
                var minCX = W, maxCX = -1, minCY = H, maxCY = -1;
                for (var y = 0; y < H; y++) {
                    for (var x = 0; x < W; x++) {
                        var idx = (y * W + x) * 4;
                        if (data[idx + 3] > 0) {
                            if (x < minCX) minCX = x;
                            if (x > maxCX) maxCX = x;
                            if (y < minCY) minCY = y;
                            if (y > maxCY) maxCY = y;
                        }
                    }
                }
                if (maxCX < minCX || maxCY < minCY) return false;
                
                var canonW = maxCX - minCX + 1;
                var canonH = maxCY - minCY + 1;
                var canonDiag = Math.hypot(canonW, canonH);
                
                // Get user stroke metrics
                var userLen = 0;
                var minUX = Infinity, maxUX = -Infinity, minUY = Infinity, maxUY = -Infinity;
                for (var i = 0; i < svgPoints.length; i++) {
                    var p = svgPoints[i];
                    if (i > 0) {
                        var prev = svgPoints[i - 1];
                        userLen += Math.hypot(p.x - prev.x, p.y - prev.y);
                    }
                    if (p.x < minUX) minUX = p.x;
                    if (p.x > maxUX) maxUX = p.x;
                    if (p.y < minUY) minUY = p.y;
                    if (p.y > maxUY) maxUY = p.y;
                }
                if (!isFinite(minUX) || !isFinite(minUY)) return false;
                
                var userW = maxUX - minUX;
                var userH = maxUY - minUY;
                
                // Check corridor hit ratio
                var hits = 0, total = 0;
                var step = Math.max(1, Math.floor(svgPoints.length / 40));
                for (var i = 0; i < svgPoints.length; i += step) {
                    var p = svgPoints[i];
                    var x = Math.round(p.x);
                    var y = Math.round(p.y);
                    if (x < 0 || x >= W || y < 0 || y >= H) continue;
                    total++;
                    var idx = (y * W + x) * 4;
                    if (data[idx + 3] > 0) hits++;
                }
                if (total === 0) return false;
                var ratio = hits / total;
                
                // Size-dependent thresholds
                var SMALL_DIAG = 20, LARGE_DIAG = 80;
                var t = canonDiag <= SMALL_DIAG ? 0 : (canonDiag >= LARGE_DIAG ? 1 : (canonDiag - SMALL_DIAG) / (LARGE_DIAG - SMALL_DIAG));
                var MIN_LENGTH_FRAC = 0.50 + t * (0.85 - 0.50);
                var MIN_MAIN_FRAC = 0.50 + t * (0.80 - 0.50);
                var MIN_ABS_LENGTH = 5 + t * (10 - 5);
                
                var hasEnoughLength = userLen >= MIN_ABS_LENGTH && (canonDiag <= 0 || userLen / canonDiag >= MIN_LENGTH_FRAC);
                var canonMain = canonW >= canonH ? canonW : canonH;
                var userMain = canonW >= canonH ? userW : userH;
                var mainFrac = canonMain > 0 ? userMain / canonMain : 1;
                var hasEnoughExtent = mainFrac >= MIN_MAIN_FRAC;
                
                return hasEnoughLength && hasEnoughExtent && ratio >= HIT_RATIO;
            };
            
            window.isDirectionCorrect = function(svgPoints, strokeMeta) {
                if (!strokeMeta || !svgPoints || svgPoints.length < 2) return true;
                var sx = strokeMeta.start_x, sy = strokeMeta.start_y;
                var ex = strokeMeta.end_x, ey = strokeMeta.end_y;
                if (sx == null || sy == null || ex == null || ey == null) return true;
                
                var first = svgPoints[0];
                var last = svgPoints[svgPoints.length - 1];
                var ux = last.x - first.x, uy = last.y - first.y;
                var ulen = Math.hypot(ux, uy);
                if (ulen < 5) return true;
                
                var cx = ex - sx, cy = ey - sy;
                var clen = Math.hypot(cx, cy);
                if (clen < 1) return true;
                
                var dot = (ux * cx + uy * cy) / (ulen * clen);
                return dot >= 0.3;
            };
            
            window.drawGrid = function() {
                if (!window.ctx) return;
                var ctx = window.ctx;
                
                ctx.save();
                ctx.scale(300 / 109, 300 / 109);
                
                var W = 109, H = 109;
                
                ctx.strokeStyle = 'rgba(0, 0, 0, 0.15)';
                ctx.lineWidth = 2;
                ctx.setLineDash([]);
                ctx.strokeRect(0, 0, W, H);
                
                ctx.lineWidth = 1;
                ctx.strokeStyle = 'rgba(0, 0, 0, 0.15)';
                ctx.setLineDash([3, 4]);
                
                ctx.beginPath();
                ctx.moveTo(W / 2, 0);
                ctx.lineTo(W / 2, H);
                ctx.stroke();
                
                ctx.beginPath();
                ctx.moveTo(0, H / 2);
                ctx.lineTo(W, H / 2);
                ctx.stroke();
                
                ctx.restore();
            }
            
            window.redrawCanvas = function() {
                if (!window.ctx) return;
                var ctx = window.ctx;
                
                ctx.clearRect(0, 0, 300, 300);
                window.drawGrid();
                
                // Draw ghost strokes if in dictionary mode
                if (window.dictionaryMode && window.ghostStrokes && window.ghostStrokes.length > 0) {
                    window.drawGhostStrokes();
                }
                
                // Draw user strokes
                ctx.save();
                ctx.strokeStyle = '#000';
                ctx.lineWidth = 3;
                ctx.lineCap = 'round';
                ctx.lineJoin = 'round';
                ctx.setLineDash([]);
                
                for (var i = 0; i < window.currentStrokes.length; i++) {
                    var stroke = window.currentStrokes[i];
                    if (!stroke || stroke.length < 2) continue;
                    ctx.beginPath();
                    ctx.moveTo(stroke[0].x, stroke[0].y);
                    for (var j = 1; j < stroke.length; j++) {
                        ctx.lineTo(stroke[j].x, stroke[j].y);
                    }
                    ctx.stroke();
                }
                
                // Draw current stroke being drawn
                if (window.currentStroke && window.currentStroke.length > 1) {
                    ctx.beginPath();
                    ctx.moveTo(window.currentStroke[0].x, window.currentStroke[0].y);
                    for (var j = 1; j < window.currentStroke.length; j++) {
                        ctx.lineTo(window.currentStroke[j].x, window.currentStroke[j].y);
                    }
                    ctx.stroke();
                }
                
                ctx.restore();
            }
            
            window.drawGhostStrokes = function() {
                // Draw ghost strokes for dictionary mode
                if (!window.ghostStrokes || window.ghostStrokes.length === 0) return;
                
                var ctx = window.ctx;
                
                ctx.save();
                ctx.scale(300 / 109, 300 / 109);
                
                ctx.lineWidth = 4;
                ctx.lineCap = 'round';
                ctx.lineJoin = 'round';
                ctx.setLineDash([]);
                
                // Draw all ghost strokes
                for (var i = 0; i < window.ghostStrokes.length; i++) {
                    var s = window.ghostStrokes[i];
                    
                    // Current stroke is less transparent
                    if (i === window.currentStrokeIndex) {
                        ctx.strokeStyle = 'rgba(255, 255, 255, 0.18)';
                    } else {
                        ctx.strokeStyle = 'rgba(255, 255, 255, 0.05)';
                    }
                    
                    ctx.stroke(s.path);
                    
                    // Draw stroke numbers
                    if (s.label_x != null) {
                        if (i === window.currentStrokeIndex) {
                            ctx.fillStyle = 'rgba(255, 0, 0, 0.75)';
                        } else {
                            ctx.fillStyle = 'rgba(255, 0, 0, 0.20)';
                        }
                        ctx.font = '8px sans-serif';
                        ctx.fillText(String(s.index), s.label_x, s.label_y);
                    }
                }
                
                ctx.restore();
            };
            
            window.startDrawing = function(evt) {
                evt.preventDefault();
                var pos = getPos(evt);
                window.isDrawing = true;
                window.currentStroke = [{ x: pos.x, y: pos.y }];
            };
            
            window.draw = function(evt) {
                if (!window.isDrawing) return;
                evt.preventDefault();
                var pos = getPos(evt);
                if (window.currentStroke) {
                    window.currentStroke.push({ x: pos.x, y: pos.y });
                    window.redrawCanvas();
                }
            };
            
            window.endDrawing = function(evt) {
                if (!window.isDrawing) return;
                evt.preventDefault();
                window.isDrawing = false;
                
                if (!window.currentStroke || window.currentStroke.length < 2) {
                    window.currentStroke = null;
                    return;
                }
                
                // Clear redo history when a new stroke is added
                window.undoHistory = [];
                
                // In dictionary mode, validate stroke against ghost strokes
                if (window.dictionaryMode && window.ghostStrokes && window.ghostStrokes.length > 0) {
                    // Convert current stroke to SVG coordinates
                    var svgStroke = window.currentStroke.map(function(p) {
                        return { x: p.x / (300 / 109), y: p.y / (300 / 109) };
                    });
                    
                    // Check if stroke matches current expected stroke using proper validation
                    var expectedStroke = window.ghostStrokes[window.currentStrokeIndex];
                    if (expectedStroke) {
                        var okShape = window.isStrokeCloseEnough(svgStroke, expectedStroke.path);
                        var okDirection = window.isDirectionCorrect(svgStroke, expectedStroke);
                        
                        console.log('[Dictionary] Validating stroke', window.currentStrokeIndex, 'shape:', okShape, 'direction:', okDirection);
                        
                        if (okShape && okDirection) {
                            // Valid stroke - keep it and move to next
                            window.currentStrokes.push(window.currentStroke);
                            window.currentStrokeIndex++;
                            window.updateUndoRedoButtons();
                            
                            // Check if current character is complete
                            if (window.currentStrokeIndex >= window.ghostStrokes.length) {
                                console.log('[Dictionary] Character complete:', window.currentKanjiChar);
                                
                                // Add completed character to answer box
                                var answerBox = document.getElementById('japanese-input');
                                if (answerBox) {
                                    answerBox.value += window.currentKanjiChar;
                                }
                                
                                // Move to next character if available
                                if (window.kanjiCharList && window.currentKanjiCharIndex < window.kanjiCharList.length - 1) {
                                    window.currentKanjiCharIndex++;
                                    var nextChar = window.kanjiCharList[window.currentKanjiCharIndex];
                                    console.log('[Dictionary] Loading next character:', nextChar);
                                    
                                    // Clear user strokes and undo history before loading next character
                                    window.currentStrokes = [];
                                    window.undoHistory = [];
                                    window.updateUndoRedoButtons();
                                    
                                    pycmd('lookupKanji:' + nextChar);
                                } else {
                                    // All characters complete - return to free-draw mode
                                    console.log('[Dictionary] All characters complete - returning to free-draw mode');
                                    
                                    // Clear ghost strokes and reset dictionary mode
                                    window.ghostStrokes = [];
                                    window.dictionaryMode = false;
                                    window.currentKanjiChar = '';
                                    window.kanjiCharList = [];
                                    window.currentKanjiCharIndex = 0;
                                    
                                    // Clear user strokes and undo history
                                    window.currentStrokes = [];
                                    window.undoHistory = [];
                                    window.updateUndoRedoButtons();
                                    
                                    // Update info display
                                    var info = document.getElementById('canvas-info');
                                    if (info) {
                                        info.textContent = 'All characters completed! Free drawing mode resumed.';
                                        info.style.color = '#4CAF50';
                                        
                                        // Reset to normal message after 3 seconds
                                        setTimeout(function() {
                                            info.textContent = 'Free drawing mode - draw any character';
                                            info.style.color = '';
                                        }, 3000);
                                    }
                                    
                                    // Clear the canvas and redraw grid
                                    window.redrawCanvas();
                                }
                            } else {
                                // Update progress for current character
                                var info = document.getElementById('canvas-info');
                                if (info) {
                                    info.textContent = 'Dictionary Mode: Drawing ' + window.currentKanjiChar + 
                                                      ' (stroke ' + (window.currentStrokeIndex + 1) + 
                                                      ' of ' + window.ghostStrokes.length + ')';
                                }
                            }
                        } else {
                            // Invalid stroke - don't keep it
                            console.log('[Dictionary] Stroke validation failed');
                        }
                    }
                    
                    window.currentStroke = null;
                    window.redrawCanvas();
                } else {
                    // Normal mode - just add stroke
                    window.currentStrokes.push(window.currentStroke);
                    window.updateUndoRedoButtons();
                    window.currentStroke = null;
                    window.redrawCanvas();
                }
            };
            
            var startDrawing = window.startDrawing;
            var draw = window.draw;
            var endDrawing = window.endDrawing;
            
            // Initialize when DOM is ready
            if (document.readyState === 'loading') {
                document.addEventListener('DOMContentLoaded', initCanvas);
            } else {
                initCanvas();
            }
        })();
        
        window.submitAnswer = function() {
            var input = document.getElementById('japanese-input');
            var result = document.getElementById('result');
            var submittedAnswer = input.value.trim();
            var acceptedAnswer = (window.cardJapanese || '').trim();
            
            // Cache the answer
            pycmd('saveCache:' + JSON.stringify({
                cardIndex: window.currentCardIndex,
                answer: input.value,
                feedback: '',
                feedbackClass: ''
            }));
            
            if (!submittedAnswer) {
                result.innerHTML = '⚠️ Please enter an answer first.';
                result.className = 'result incorrect';
                result.style.display = 'block';
                return;
            }
            
            // Show loading state
            result.innerHTML = '🔍 Checking your answer...';
            result.className = 'result';
            result.style.display = 'block';
            
            // Check for exact match
            if (submittedAnswer === acceptedAnswer) {
                result.innerHTML = '<h2>✅ Correct</h2>';
                result.className = 'result correct';
                
                // Cache the feedback via pycmd
                pycmd('saveCache:' + JSON.stringify({
                    cardIndex: window.currentCardIndex,
                    answer: document.getElementById('japanese-input').value,
                    feedback: result.innerHTML,
                    feedbackClass: 'result correct'
                }));
                
                return;
            }
            
            // Request AI feedback for incorrect answer
            var feedbackRequest = {
                english: window.cardEnglish || '',
                accepted: acceptedAnswer,
                submitted: submittedAnswer
            };
            
            pycmd('getFeedback:' + JSON.stringify(feedbackRequest));
        };
        
        // Handler for AI feedback response
        window.handleFeedback = function(feedback) {
            var result = document.getElementById('result');
            if (!feedback) {
                result.innerHTML = '❌ Error getting feedback. Please try again.';
                result.className = 'result incorrect';
                return;
            }
            
            // Render markdown feedback
            result.innerHTML = window.renderMarkdown(feedback);
            
            // Check if feedback indicates correct answer
            if (feedback.includes('✅ Correct') || feedback.includes('✅Correct')) {
                result.className = 'result correct';
            } else {
                result.className = 'result incorrect';
            }
            
            result.style.display = 'block';
            
            // Cache the feedback via pycmd
            var input = document.getElementById('japanese-input');
            pycmd('saveCache:' + JSON.stringify({
                cardIndex: window.currentCardIndex,
                answer: input ? input.value : '',
                feedback: result.innerHTML,
                feedbackClass: result.className
            }));
            
            // Update answered cards tracking
            if (!window.answeredCards.includes(window.currentCardIndex)) {
                window.answeredCards.push(window.currentCardIndex);
            }
            
            // Update Next/Finish button
            window.updateNextButton();
        };
        
        // Simple markdown renderer with furigana support
        window.renderMarkdown = function(text) {
            if (!text) return '';
            
            var html = text;
            
            // Handle furigana format: 漢字[かんじ] -> <ruby>漢字<rt>かんじ</rt></ruby>
            html = html.replace(/([一-龯ぁ-ゔァ-ヴー々〆〤]+)\\[([ぁ-んァ-ヴー]+)\\]/g, '<ruby>$1<rt>$2</rt></ruby>');
            
            // Handle code blocks first
            html = html.replace(/```([\\s\\S]*?)```/g, '<pre><code>$1</code></pre>');
            
            // Headers
            html = html.replace(/^### (.*$)/gim, '<h3>$1</h3>');
            html = html.replace(/^## (.*$)/gim, '<h2>$1</h2>');
            html = html.replace(/^# (.*$)/gim, '<h1>$1</h1>');
            
            // Bold
            html = html.replace(/\\*\\*([^*]+)\\*\\*/g, '<strong>$1</strong>');
            html = html.replace(/__([^_]+)__/g, '<strong>$1</strong>');
            
            // Italic  
            html = html.replace(/\\*([^*]+)\\*/g, '<em>$1</em>');
            html = html.replace(/_([^_]+)_/g, '<em>$1</em>');
            
            // Inline code
            html = html.replace(/`([^`]+)`/g, '<code>$1</code>');
            
            // Lists - process line by line
            var lines = html.split('\\n');
            var inList = false;
            var result = [];
            for (var i = 0; i < lines.length; i++) {
                var line = lines[i];
                if (line.match(/^[\\*-] /)) {
                    if (!inList) {
                        result.push('<ul>');
                        inList = true;
                    }
                    result.push('<li>' + line.substring(2) + '</li>');
                } else {
                    if (inList) {
                        result.push('</ul>');
                        inList = false;
                    }
                    result.push(line);
                }
            }
            if (inList) result.push('</ul>');
            html = result.join('\\n');
            
            // Line breaks
            html = html.replace(/\\n\\n/g, '</p><p>');
            html = '<p>' + html + '</p>';
            
            return html;
        };
        
        window.skipCard = function() {
            pycmd('nextCard');
        };
        
        window.lookupDictionary = function() {
            console.log('lookupDictionary called');
            var searchInput = document.getElementById('dict-search');
            console.log('Search input:', searchInput);
            var kanji = searchInput ? searchInput.value.trim() : '';
            console.log('Kanji value:', kanji);
            
            // Show status immediately
            var status = document.getElementById('status');
            if (status) {
                status.textContent = 'Looking up: ' + (kanji || '(no input)');
                status.style.backgroundColor = '#2196F3';
                status.style.color = 'white';
                status.style.display = 'block';
            }
            
            if (kanji) {
                console.log('Calling pycmd with:', 'lookupKanji:' + kanji);
                pycmd('lookupKanji:' + kanji);
            } else {
                console.log('No kanji entered');
                if (status) {
                    status.textContent = '⚠ Please enter a character to look up';
                    status.style.backgroundColor = '#f44336';
                }
            }
        };
        
        // Add Enter key support for dictionary lookup
        var dictSearch = document.getElementById('dict-search');
        if (dictSearch) {
            dictSearch.addEventListener('keypress', function(event) {
                if (event.key === 'Enter') {
                    event.preventDefault();
                    window.lookupDictionary();
                }
            });
        };
        
        window.undoStroke = function() {
            if (window.currentStrokes.length === 0) return;
            
            // Remove last stroke and add to redo history
            var lastStroke = window.currentStrokes.pop();
            window.undoHistory.push(lastStroke);
            
            // Update stroke index if in dictionary mode
            if (window.dictionaryMode && window.currentStrokeIndex > 0) {
                window.currentStrokeIndex--;
            }
            
            window.updateUndoRedoButtons();
            window.redrawCanvas();
        };
        
        window.redoStroke = function() {
            if (window.undoHistory.length === 0) return;
            
            // Restore last undone stroke
            var stroke = window.undoHistory.pop();
            window.currentStrokes.push(stroke);
            
            // Update stroke index if in dictionary mode
            if (window.dictionaryMode && window.currentStrokeIndex < window.ghostStrokes.length) {
                window.currentStrokeIndex++;
            }
            
            window.updateUndoRedoButtons();
            window.redrawCanvas();
        };
        
        // Add keyboard shortcuts for undo/redo
        document.addEventListener('keydown', function(e) {
            // Only handle if no input/textarea is focused
            var activeElement = document.activeElement;
            if (activeElement && (activeElement.tagName === 'INPUT' || activeElement.tagName === 'TEXTAREA')) {
                return;
            }
            
            // Ctrl+Z for undo (without shift)
            if (e.ctrlKey && e.key === 'z' && !e.shiftKey) {
                e.preventDefault();
                window.undoStroke();
            }
            // Ctrl+Y or Ctrl+Shift+Z for redo
            else if (e.ctrlKey && (e.key === 'y' || (e.key === 'z' && e.shiftKey))) {
                e.preventDefault();
                window.redoStroke();
            }
        });
        
        window.submitDrawing = function() {
            // In free draw mode, try to recognize character using OpenRouter API
            if (!window.currentStrokes || window.currentStrokes.length === 0) {
                var status = document.getElementById('status');
                if (status) {
                    status.textContent = '⚠ Draw something first before submitting';
                    status.style.backgroundColor = '#f44336';
                    status.style.color = 'white';
                    status.style.display = 'block';
                }
                return;
            }
            
            var status = document.getElementById('status');
            if (status) {
                status.textContent = '🔍 Recognizing... (using AI)';
                status.style.backgroundColor = '#2196F3';
                status.style.color = 'white';
                status.style.display = 'block';
            }
            
            // Get canvas image data
            var canvas = document.getElementById('drawing-canvas');
            if (!canvas) {
                console.error('[OCR] Canvas not found');
                if (status) {
                    status.textContent = '❌ Error: Canvas not found';
                    status.style.backgroundColor = '#f44336';
                }
                return;
            }
            
            try {
                // Create a clean image for OCR: white background with black strokes
                var tempCanvas = document.createElement('canvas');
                tempCanvas.width = canvas.width;
                tempCanvas.height = canvas.height;
                var tempCtx = tempCanvas.getContext('2d');
                
                // Fill with white background
                tempCtx.fillStyle = '#FFFFFF';
                tempCtx.fillRect(0, 0, tempCanvas.width, tempCanvas.height);
                
                // Draw user strokes in black
                tempCtx.strokeStyle = '#000000';
                tempCtx.lineWidth = 3;
                tempCtx.lineCap = 'round';
                tempCtx.lineJoin = 'round';
                
                for (var i = 0; i < window.currentStrokes.length; i++) {
                    var stroke = window.currentStrokes[i];
                    if (!stroke || stroke.length < 2) continue;
                    tempCtx.beginPath();
                    tempCtx.moveTo(stroke[0].x, stroke[0].y);
                    for (var j = 1; j < stroke.length; j++) {
                        tempCtx.lineTo(stroke[j].x, stroke[j].y);
                    }
                    tempCtx.stroke();
                }
                
                // Convert to base64 image
                var imageData = tempCanvas.toDataURL('image/png');
                
                // Send to Python backend for OCR processing
                console.log('[OCR] Sending image to OpenRouter API...');
                pycmd('recognizeDrawing:' + imageData);
            } catch (error) {
                console.error('[OCR] Error capturing canvas:', error);
                if (status) {
                    status.textContent = '❌ Error: ' + error.message;
                    status.style.backgroundColor = '#f44336';
                }
            }
        };
        
        // Handler for OCR results from Python
        window.handleOCRResult = function(result) {
            var status = document.getElementById('status');
            var answerBox = document.getElementById('japanese-input');
            
            if (!result) {
                // No character recognized
                console.log('[OCR] No character recognized');
                if (status) {
                    status.textContent = '❌ Could not recognize character. Try drawing more clearly.';
                    status.style.backgroundColor = '#f44336';
                    status.style.color = 'white';
                }
                return;
            }
            
            var recognized = result.text;
            var confidence = result.confidence;
            var alternatives = result.alternatives || [];
            
            console.log('[OCR] Recognized:', recognized, 'Confidence:', confidence);
            
            // Add to answer box
            if (answerBox) {
                answerBox.value += recognized;
            }
            
            // Send recognition event
            pycmd('charRecognized:' + recognized);
            
            // Show success message with alternatives
            if (status) {
                var altText = '';
                if (alternatives.length > 1) {
                    var altChars = alternatives.slice(1, 6).map(function(a) { return a.text; }).join(', ');
                    if (altChars) {
                        altText = ' | Also: ' + altChars;
                    }
                }
                
                var confPercent = (confidence * 100).toFixed(0);
                status.textContent = '✓ Recognized: ' + recognized + ' (' + confPercent + '% confident)' + altText;
                status.style.backgroundColor = '#4CAF50';
                status.style.color = 'white';
                status.style.display = 'block';
            }
            
            // Clear canvas after recognition
            window.currentStrokes = [];
            window.redrawCanvas();
        };
        
        // Fallback recognition using stroke count (if OCR fails)
        window.fallbackRecognition = function() {
            if (!window.currentStrokes || window.currentStrokes.length === 0) {
                return null;
            }
            
            var strokeCount = window.currentStrokes.length;
            var candidates = [];
            
            if (strokeCount === 1) {
                candidates = ['一', 'の', 'つ', 'し', 'ー'];
            } else if (strokeCount === 2) {
                candidates = ['二', '十', '人', '入', 'リ', 'ニ'];
            } else if (strokeCount === 3) {
                candidates = ['三', '山', '川', '女', '大', '子', '小', '口'];
            } else {
                candidates = [];
            }
            
            if (candidates.length > 0) {
                return candidates[0];
            } else {
                console.log('[Recognition] No match for', strokeCount, 'strokes');
                var status = document.getElementById('status');
                if (status) {
                    status.textContent = '⚠ No character recognized with ' + strokeCount + ' stroke(s). Use dictionary lookup for accurate results.';
                    status.style.backgroundColor = '#ff9800';
                    status.style.color = 'white';
                    status.style.display = 'block';
                }
                return null;
            }
        };
        
        window.clearCanvas = function() {
            if (!window.ctx) return;
            
            // Clear canvas
            window.ctx.clearRect(0, 0, 300, 300);
            
            // Reset drawing state
            window.currentStrokes = [];
            window.currentStroke = null;
            window.currentStrokeIndex = 0;
            window.animationStartTime = null;
            window.undoHistory = [];
            
            // Update undo/redo button states
            window.updateUndoRedoButtons();
            
            // Redraw grid
            if (window.drawGrid) {
                window.drawGrid();
            }
            
            // Redraw ghost strokes if in dictionary mode
            if (window.dictionaryMode && window.ghostStrokes && window.ghostStrokes.length > 0) {
                window.redrawCanvas();
            }
            
            // Hide status message
            var status = document.getElementById('status');
            if (status) {
                status.style.display = 'none';
            }
        };
        """
    
    def inject_kanji_strokes(self, char):
        """Load and display ghost strokes for a kanji character in the practice window."""
        try:
            # Handle multi-character strings (e.g., 今日)
            if len(char) > 1:
                debugPrint(f"Multiple characters entered: {char}")
                # Set up the character list and load the first one
                char_list_js = f"""
                window.kanjiCharList = {json.dumps(list(char))};
                window.currentKanjiCharIndex = 0;
                """
                self.web.eval(char_list_js)
                # Process only the first character now
                char = char[0]
            else:
                # Single character - reset the list
                char_list_js = f"""
                window.kanjiCharList = {json.dumps([char])};
                window.currentKanjiCharIndex = 0;
                """
                self.web.eval(char_list_js)
            
            # Fetch stroke data
            if KANJI_REGEX.match(char):
                stroke_data = kanjiRenderer(char)
            elif HIRAGANA_REGEX.match(char) or KATAKANA_REGEX.match(char):
                stroke_data = kanaRenderer(char)
            else:
                debugPrint(f"Character '{char}' not recognized as kanji or kana")
                # Show error in UI
                error_js = """
                var status = document.getElementById('status');
                if (status) {
                    status.textContent = '⚠ Not a valid Japanese character';
                    status.style.backgroundColor = '#f44336';
                    status.style.color = 'white';
                    status.style.display = 'block';
                }
                """
                self.web.eval(error_js)
                return
            
            if not stroke_data:
                debugPrint(f"No stroke data found for {char}")
                return
            
            # stroke_data is already a list of stroke dictionaries
            strokes = stroke_data
            debugPrint(f"Loaded {len(strokes)} strokes for {char}")
            
            # Update canvas info
            js = f"""
            var info = document.getElementById('canvas-info');
            if (info) {{
                info.textContent = 'Dictionary Mode: Drawing {char} (stroke 1 of {len(strokes)})';
                info.style.color = '#2196F3';
                info.style.fontWeight = 'bold';
            }}
            """
            self.web.eval(js)
            
            # Load stroke data and integrate with existing drawing system
            js = f"""
            (function() {{
                // Ensure canvas is initialized
                if (!window.ctx) {{
                    console.error('Canvas not initialized yet');
                    return;
                }}
                
                console.log('Setting up dictionary mode for {char}');
                
                // Load stroke data and create Path2D objects
                var rawStrokes = {json.dumps(strokes)};
                window.ghostStrokes = rawStrokes.map(function(s) {{
                    return {{
                        index: s.index,
                        path: new Path2D(s.d),
                        label_x: s.label_x,
                        label_y: s.label_y,
                        start_x: s.start_x,
                        start_y: s.start_y,
                        end_x: s.end_x,
                        end_y: s.end_y
                    }};
                }});
            
            // Enable dictionary mode
            window.dictionaryMode = true;
            window.currentKanjiChar = '{char}';
            
            // Reset drawing state for new kanji (clear previous strokes)
            window.currentStrokes = [];
            window.currentStroke = null;
            window.currentStrokeIndex = 0;
            
            // Redraw canvas to show new ghost strokes
            window.redrawCanvas();
            
            console.log('Loaded', {len(strokes)}, 'strokes for {char} in dictionary mode');
            console.log('Ghost strokes:', window.ghostStrokes);
            }})();
            """
            
            self.web.eval(js)
            
            # Show success message with delay to ensure element exists
            success_js = f"""
            setTimeout(function() {{
                var status = document.getElementById('status');
                if (status) {{
                    status.textContent = '✓ Loaded {len(strokes)} strokes for {char} - try drawing!';
                    status.style.backgroundColor = '#4CAF50';
                    status.style.color = 'white';
                    status.style.display = 'block';
                }}
            }}, 100);
            """
            self.web.eval(success_js)
            
        except Exception as e:
            debugPrint(f"Error loading kanji strokes: {e}")
            import traceback
            debugPrint(traceback.format_exc())
    
    def closeEvent(self, event):
        """Clean up when window is closed."""
        try:
            gui_hooks.webview_did_receive_js_message.remove(self.handle_message)
        except (ValueError, AttributeError):
            pass
        super().closeEvent(event)
    
    def show_completion_screen(self):
        """Show completion screen with results and confetti if perfect score."""
        self.on_completion_screen = True
        total = len(self.card_data_list)
        correct = len(self.correct_cards)
        all_correct = (correct == total)
        
        debugPrint(f"Showing completion screen: {correct}/{total} correct, all_correct={all_correct}")
        
        # Get incorrect feedbacks for AI summary
        incorrect_feedbacks = []
        for idx in self.answered_cards:
            if idx not in self.correct_cards:
                cache = self.card_cache.get(idx, {})
                feedback = cache.get('feedback', '')
                if feedback and '✅ Correct' not in feedback:
                    incorrect_feedbacks.append(feedback)
        
        # Generate AI summary if there are incorrect answers (or use cached)
        summary = ""
        if incorrect_feedbacks and len(incorrect_feedbacks) > 0:
            if self.completion_summary is None:
                self.completion_summary = self.generate_completion_summary(incorrect_feedbacks)
            summary = self.completion_summary
        
        # Build completion HTML
        confetti_script = confettiJs if all_correct else ""
        
        completion_html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <style>
                body {{
                    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", system-ui, sans-serif;
                    padding: 40px;
                    text-align: center;
                    max-width: 800px;
                    margin: 0 auto;
                }}
                h1 {{
                    font-size: 48px;
                    margin-bottom: 20px;
                    color: {'#4CAF50' if all_correct else '#2196F3'};
                }}
                .score {{
                    font-size: 64px;
                    font-weight: bold;
                    margin: 30px 0;
                    color: {'#4CAF50' if all_correct else '#FF9800'};
                }}
                .message {{
                    font-size: 24px;
                    margin: 20px 0;
                    color: #666;
                }}
                .summary {{
                    background-color: #2196F3;
                    border-left: 4px solid #1976D2;
                    padding: 20px;
                    margin: 30px 0;
                    text-align: left;
                    border-radius: 4px;
                    color: #ffffff;
                }}
                .summary h2 {{
                    margin-top: 0;
                    color: #ffffff;
                }}
                .summary strong {{
                    color: #00f5d5;
                }}
                .buttons {{
                    margin-top: 40px;
                }}
                button {{
                    background-color: #4CAF50;
                    color: white;
                    padding: 15px 30px;
                    font-size: 18px;
                    border: none;
                    border-radius: 5px;
                    cursor: pointer;
                    margin: 0 10px;
                }}
                button:hover {{
                    background-color: #45a049;
                }}
                ruby {{
                    font-size: 18px;
                }}
                rt {{
                    font-size: 12px;
                }}
            </style>
        </head>
        <body>
            <h1>{'🎉 Perfect Score! 🎉' if all_correct else '📊 Practice Complete'}</h1>
            <div class="score">{correct}/{total}</div>
            <div class="message">
                {'Excellent work! You got all answers correct!' if all_correct else f'You got {correct} out of {total} correct.'}
            </div>
            
            {f'''
            <div class="summary">
                <h2>📚 Areas to Focus On</h2>
                <div id="summary-content">{summary}</div>
            </div>
            ''' if summary else ''}
            
            <div class="buttons">
                <button onclick="pycmd('prevCard')">← Back to Cards</button>
                <button onclick="pycmd('closePractice')">Close</button>
            </div>
            
            <canvas id="confetti-canvas" style="position: fixed; top: 0; left: 0; width: 100%; height: 100%; pointer-events: none; z-index: 9999;"></canvas>
            
            <script>
            {confetti_script if all_correct else ''}
            </script>
            
            {f'''
            <script>
            // Trigger confetti animation
            console.log('Initializing confetti for perfect score');
            setTimeout(function() {{
                try {{
                    const canvas = document.getElementById('confetti-canvas');
                    console.log('Canvas element:', canvas);
                    const jsConfetti = new JSConfetti({{canvas: canvas}});
                    console.log('JSConfetti initialized:', jsConfetti);
                    
                    jsConfetti.addConfetti({{
                        emojis: ['🎉', '✨', '🎊', '🌟'],
                        emojiSize: 50,
                        confettiNumber: 100,
                    }});
                    
                    // Add more confetti bursts
                    setTimeout(function() {{
                        jsConfetti.addConfetti({{
                            confettiColors: ['#4CAF50', '#45a049', '#66BB6A', '#81C784'],
                            confettiNumber: 150,
                        }});
                    }}, 300);
                }} catch(e) {{
                    console.error('Confetti error:', e);
                }}
            }}, 100);
            </script>
            ''' if all_correct else ''}
        </body>
        </html>
        """
        
        self.web.stdHtml(completion_html, css=[], js=[])
    
    def generate_completion_summary(self, incorrect_feedbacks):
        """Generate AI summary of trends in incorrect answers."""
        try:
            # Load AI config
            ai_config = load_ai_config()
            api_key = ai_config.get('api_key', '')
            api_url = ai_config.get('api_url') or 'https://openrouter.ai/api/v1/chat/completions'
            model = ai_config.get('model') or 'google/gemini-2.5-flash'
            
            if not api_key:
                debugPrint("AI summary not available - API key not configured")
                return "<p>Review the incorrect answers above to identify areas for improvement.</p>"
            
            # Build prompt
            feedbacks_text = "\n\n---\n\n".join(incorrect_feedbacks)
            prompt = f"""Based on these feedback messages from incorrect Japanese translation attempts, identify the main trends, common mistakes, and concepts/topics the student should focus on. Be concise but helpful.

When showing Japanese text with kanji, use furigana format: 漢字[かんじ] (kanji followed by reading in square brackets; no space between the kanji and the square brackets).

Feedbacks:
{feedbacks_text}

Provide a brief summary in markdown format with:
- Main patterns in the mistakes
- Key grammar points or vocabulary to review
- Specific recommendations for improvement"""
            
            # Prepare API request
            headers = {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json"
            }
            
            payload = {
                "model": model,
                "messages": [
                    {
                        "role": "user",
                        "content": prompt
                    }
                ]
            }
            
            debugPrint(f"Requesting completion summary from AI...")
            
            # Make API request
            request = urllib.request.Request(
                api_url,
                data=json.dumps(payload).encode('utf-8'),
                headers=headers
            )
            
            with urllib.request.urlopen(request, timeout=30) as response:
                result = json.loads(response.read().decode('utf-8'))
            
            # Extract summary
            if result.get('choices') and len(result['choices']) > 0:
                summary = result['choices'][0]['message']['content'].strip()
                debugPrint(f"AI summary generated")
                
                # Render markdown to HTML
                return self.render_markdown_python(summary)
            
            return "<p>Review the incorrect answers to identify areas for improvement.</p>"
            
        except Exception as e:
            debugPrint(f"Error generating completion summary: {{e}}")
            import traceback
            traceback.print_exc()
            return "<p>Review the incorrect answers to identify areas for improvement.</p>"
    
    def render_markdown_python(self, text):
        """Simple markdown to HTML renderer in Python."""
        import re
        html = text
        
        # Furigana
        html = re.sub(r'([一-龯ぁ-ゔァ-ヴー々〆〤]+)\[([ぁ-んァ-ヴー]+)\]', r'<ruby>\1<rt>\2</rt></ruby>', html)
        
        # Headers
        html = re.sub(r'^### (.+)$', r'<h3>\1</h3>', html, flags=re.MULTILINE)
        html = re.sub(r'^## (.+)$', r'<h2>\1</h2>', html, flags=re.MULTILINE)
        html = re.sub(r'^# (.+)$', r'<h1>\1</h1>', html, flags=re.MULTILINE)
        
        # Bold
        html = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', html)
        html = re.sub(r'__(.+?)__', r'<strong>\1</strong>', html)
        
        # Italic
        html = re.sub(r'\*(.+?)\*', r'<em>\1</em>', html)
        html = re.sub(r'_(.+?)_', r'<em>\1</em>', html)
        
        # Inline code
        html = re.sub(r'`([^`]+)`', r'<code>\1</code>', html)
        
        # Lists (simple processing)
        lines = html.split('\n')
        result = []
        in_list = False
        for line in lines:
            if re.match(r'^[\*\-] ', line):
                if not in_list:
                    result.append('<ul>')
                    in_list = True
                result.append(f'<li>{line[2:]}</li>')
            else:
                if in_list:
                    result.append('</ul>')
                    in_list = False
                result.append(line)
        if in_list:
            result.append('</ul>')
        html = '\n'.join(result)
        
        # Paragraphs
        html = re.sub(r'\n\n+', '</p><p>', html)
        html = f'<p>{html}</p>'
        
        return html


def inject_practice_session(card_data_list, sentence_source):
    """DEPRECATED: Use KanjiPracticeWindow instead."""
    # This function is kept for compatibility but should not be used
    pass
    
    english = fields.get('Sentence-English', fields.get('English', ''))
    if not english:
        for key in fields:
            if 'english' in key.lower():
                english = fields[key]
                break
    
    if not english:
        english = "(No English sentence found in card)"
    
    # Build HTML for practice interface
    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <style>
            body {{
                font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", system-ui, sans-serif;
                padding: 20px;
                max-width: 900px;
                margin: 0 auto;
            }}
            .progress {{
                padding: 10px;
                background-color: #2196F3;
                color: white;
                font-weight: bold;
                border-radius: 5px;
                margin-bottom: 15px;
            }}
            .english {{
                padding: 15px;
                font-size: 16px;
                background-color: #e8e8e8;
                border-radius: 5px;
                margin: 10px 0;
                color: #000;
            }}
            .input-group {{
                border: 1px solid #ddd;
                padding: 15px;
                border-radius: 5px;
                margin: 10px 0;
            }}
            input[type="text"] {{
                width: 100%;
                font-size: 14px;
                padding: 6px 10px;
                border: 1px solid #ccc;
                border-radius: 3px;
                font-family: 'Yu Gothic', 'MS Gothic', sans-serif;
                line-height: 1.4;
                height: auto;
                box-sizing: border-box;
            }}
            .dict-group {{
                border: 1px solid #ddd;
                padding: 15px;
                border-radius: 5px;
                margin: 10px 0;
            }}
            .dict-search {{
                display: flex;
                gap: 10px;
                align-items: center;
                margin-bottom: 10px;
            }}
            .dict-search input {{
                flex: 1;
                font-family: 'Yu Gothic', 'MS Gothic', sans-serif;
                font-size: 14px;
                padding: 6px 10px;
            }}
            .status {{
                padding: 8px;
                font-weight: bold;
                border-radius: 3px;
                margin: 10px 0;
                display: none;
            }}
            .canvas-group {{
                border: 1px solid #ddd;
                padding: 15px;
                border-radius: 5px;
                margin: 10px 0;
                text-align: center;
            }}
            .canvas-info {{
                color: #666;
                font-style: italic;
                padding: 5px;
                margin-bottom: 10px;
            }}
            .controls {{
                display: flex;
                gap: 10px;
                justify-content: center;
                margin: 10px 0;
            }}
            .btn-primary {{
                background-color: #4CAF50;
                color: white;
                padding: 8px 16px;
                border: none;
                border-radius: 3px;
                cursor: pointer;
                font-weight: bold;
            }}
            .btn-primary:hover {{
                background-color: #45a049;
            }}
            .result {{
                padding: 15px;
                font-size: 16px;
                background-color: #E3F2FD;
                border-radius: 5px;
                margin: 10px 0;
                display: none;
            }}
        </style>
    </head>
    <body>
        <div class="progress">Card 1 of {len(card_data_list)}</div>
        <div class="english">{english}</div>
        
        <div class="input-group">
            <label><b>Your Answer</b></label>
            <input type="text" id="japanese-input" placeholder="Type or draw Japanese characters...">
        </div>
        
        <div class="dict-group">
            <label><b>Dictionary Lookup</b></label>
            <div class="dict-search">
                <span>Search kanji:</span>
                <input type="text" id="dict-search" placeholder="Enter word/kanji to practice...">
                <button onclick="lookupDictionary()">Look Up</button>
            </div>
        </div>
        
        <div class="status" id="status"></div>
        
        <div class="canvas-group">
            <div class="canvas-info" id="canvas-info">Free drawing mode - draw any character</div>
            <div id="canvas-container"></div>
            <div class="controls">
                <button onclick="window.submitDrawing()">Submit Drawing</button>
                <button onclick="window.clearCanvas()">Clear Canvas</button>
            </div>
        </div>
        
        <div class="controls">
            <button class="btn-primary" onclick="submitAnswer()">Submit Answer</button>
            <button onclick="skipCard()">Skip</button>
            <button onclick="closePractice()">Close</button>
        </div>
        
        <div class="result" id="result"></div>
        <div class="controls">
            <button class="btn-primary" id="next-btn" onclick="nextCard()" style="display:none;">Next Card</button>
        </div>
    </body>
    </html>
    """
    
    # Set up message handler BEFORE injecting HTML
    def handle_practice_message(handled, message, context):
        debugPrint(f"Practice message received: {message}, context: {context}, our web: {mw.reviewer.web}")
        
        if message.startswith('charRecognized:'):
            char = message.split(':', 1)[1]
            # Insert into input field
            js = f"document.getElementById('japanese-input').value += '{char}';"
            mw.reviewer.web.eval(js)
            # Show status
            js = f"var s = document.getElementById('status'); s.textContent = '✓ Matched: {char}'; s.style.backgroundColor = '#4CAF50'; s.style.color = 'white'; s.style.display = 'block';"
            mw.reviewer.web.eval(js)
            # Clear canvas
            QTimer.singleShot(500, lambda: mw.reviewer.web.eval('window.clearCanvas && window.clearCanvas()'))
            return (True, None)
        elif message.startswith('noMatch'):
            # Show error
            js = "var s = document.getElementById('status'); s.textContent = '⚠ No character matched - try again'; s.style.backgroundColor = '#f44336'; s.style.color = 'white'; s.style.display = 'block';"
            mw.reviewer.web.eval(js)
            # Clear canvas
            QTimer.singleShot(100, lambda: mw.reviewer.web.eval('window.clearCanvas && window.clearCanvas()'))
            return (True, None)
        elif message.startswith('lookupKanji:'):
            kanji = message.split(':', 1)[1]
            debugPrint(f"Looking up kanji: {kanji}")
            # Split into individual characters
            kanji_list = [c for c in kanji if KANJI_REGEX.match(c) or HIRAGANA_REGEX.match(c) or KATAKANA_REGEX.match(c)]
            if kanji_list:
                # Store the list in JavaScript
                kanji_list_js = json.dumps(kanji_list)
                js = f"""
                window.dictionaryKanjiList = {kanji_list_js};
                window.currentKanjiIndex = 0;
                """
                mw.reviewer.web.eval(js)
                # Load first character
                inject_kanji_strokes(kanji_list[0])
            return (True, None)
        elif message.startswith('closePractice'):
            mw.moveToState("overview")
            return (True, None)
        
        return handled
    
    from aqt import gui_hooks
    # Remove any existing handlers first
    try:
        gui_hooks.webview_did_receive_js_message.remove(handle_practice_message)
    except ValueError:
        pass
    gui_hooks.webview_did_receive_js_message.append(handle_practice_message)
    
    # Set HTML content with embedded canvas JavaScript
    full_html = html + inject_practice_canvas_js(card_data_list[0])
    mw.reviewer.web.stdHtml(full_html, css=[], js=[])


def inject_kanji_strokes(char):
    """DEPRECATED: Load and display ghost strokes for a kanji character.
    This function is kept for compatibility but should not be used.
    Use KanjiPracticeWindow.inject_kanji_strokes() instead.
    """
    pass


def inject_practice_canvas_js(card_data):
    """DEPRECATED: Use KanjiPracticeWindow.get_practice_js() instead."""
    pass


def open_practice_dialog():
    """Open the practice dialog."""
    dialog = KanjiPracticeDialog(mw)
    dialog.exec()


# Register menu item
def setup_menu():
    """Add Practice menu to Anki's Tools menu."""
    from aqt.qt import QKeySequence
    
    action = QAction("&Kanji Sentence Practice...", mw)
    action.setShortcut(QKeySequence("K"))
    action.triggered.connect(open_practice_dialog)
    mw.form.menuTools.addAction(action)


setup_menu()


# Show a message box when the add-on is loaded
# def on_start():
#     QMessageBox.information(mw, "Hello", "Your add-on loaded!")
# on_start()
