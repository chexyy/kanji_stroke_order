from aqt import mw
from aqt import gui_hooks
from aqt.qt import QMessageBox
import xml.etree.ElementTree as ET
import re
import urllib.parse
import urllib.request
import json
import os

KANJI_REGEX = re.compile(r"[\u4E00-\u9FFF]")
debug = True

CONFIG = mw.addonManager.getConfig(__name__)

# Cache file path in the addon directory
CACHE_FILE = os.path.join(os.path.dirname(__file__), "kanji_cache.json")
STATS_FILE = os.path.join(os.path.dirname(__file__), "kanji_stats.json")

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

# Load cache and stats at startup
KANJI_CACHE = load_cache()
KANJI_STATS = load_stats()

def debugPrint(message):
    if debug:
        print("DEBUG:", message)


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
    found_kanji = KANJI_REGEX.findall(html)
    debugPrint(html)

    if not found_kanji:
        return

    unique_kanji = list(dict.fromkeys(found_kanji))
    print("Detected Kanji on this card:", "".join(unique_kanji))

    kanji_list = []
    for ch in unique_kanji:
        try:
            strokes = kanjiRenderer(ch)
            kanji_list.append({
                "char": ch,
                "strokes": strokes,
            })
        except Exception as e:
            debugPrint(f"Error getting strokes for {ch}: {e}")

    if not kanji_list:
        return

    # Detect card type: 0=new, 1=learning, 2=review, 3=relearning
    card_type = card.type if hasattr(card, 'type') else 0
    
    js_data = f"window.kanjiData = {json.dumps(kanji_list)};"
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


# Show a message box when the add-on is loaded
# def on_start():
#     QMessageBox.information(mw, "Hello", "Your add-on loaded!")
# on_start()
