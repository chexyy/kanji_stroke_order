from aqt import mw
from aqt.qt import QMessageBox
from aqt import gui_hooks
import xml.etree.ElementTree as ET
import re
import urllib.parse
import urllib.request
import json

# Initialization
KANJI_REGEX = re.compile(r"[\u4E00-\u9FFF]")
debug = True

# Debug print function that only triggers if "debug" is True
def debugPrint(message):
    if debug:
        print("DEBUG:", message)

# Detect Kanji characters in the question field of the front face of a card
def detect_kanji_on_question(card):
    question_html = card.q()
    found_kanji = KANJI_REGEX.findall(question_html)
    debugPrint(question_html)

    if not found_kanji:
        return

    unique_kanji = list(dict.fromkeys(found_kanji))
    print("Detected Kanji on this card:", "".join(unique_kanji))

    # for kanji in unique_kanji:
    #     kanjiRenderer(kanji)

    # For now, just handle the first Kanji on the card
    char = unique_kanji[0]
    try:
        strokePaths = kanjiRenderer(char)
    except Exception as e:
        debugPrint(f"Error getting strokes for {char}: {e}")
        return

    # Inject stroke paths into the webview as a global JS variable
    js_data = f"window.kanjiStrokePaths = {json.dumps(strokePaths)};"
    mw.reviewer.web.eval(js_data)

    # Inject or update the canvas UI
    inject_drawing_canvas()

gui_hooks.reviewer_did_show_question.append(detect_kanji_on_question) # Adds the above function to the hook that runs when a question is shown on a card

# Combining functions
def kanjiRenderer(char):
    svgHTML = fetch_jisho_svg_html_for_kanji(char)
    strokeData = extract_stroke_paths_from_svg(svgHTML, char)

    # For debugging:
    with open("output_file.txt", "w", encoding="utf-8") as f:
        for s in strokeData:
            f.write(f"Stroke {s['index']}: d={s['d']}\n"
                    f"  label at ({s['label_x']}, {s['label_y']})\n")

    return strokeData


# Fetch HTML from Jisho.org for a given Kanji character
def fetch_jisho_svg_html_for_kanji(char):
    base_url = "https://jisho.org/search/"
    query = f"{char} #kanji"
    encoded_query = urllib.parse.quote(query)
    url = base_url + encoded_query

    with urllib.request.urlopen(url) as response:
        html_bytes = response.read()
    html_text = html_bytes.decode("utf-8", errors="ignore")

    svg_url = re.search('d1w6u4xc3l95km.cloudfront.net\/kanji-2015-03\/.*.svg', html_text)
    if not svg_url:
        raise ValueError(f"No SVG URL found for kanji {char!r}")
    svg_url = svg_url.group() 

    with urllib.request.urlopen("https://" + svg_url) as response:
        html_bytes = response.read()
    svg_html_text = html_bytes.decode("utf-8", errors="ignore")

    return svg_html_text

# Turn HTML string into XML and extract stroke paths 
def extract_stroke_paths_from_svg(svg_text, char):
    root = ET.fromstring(svg_text)

    ns = {
        'svg': "http://www.w3.org/2000/svg",
        'kvg': "http://kanjivg.tagaini.net"
    }

    # 1) Find the main <g> for this kanji by kvg:element="見"
    target_group = None
    for g in root.findall('.//svg:g', ns):
        if g.get('{http://kanjivg.tagaini.net}element') == char:
            target_group = g
            break

    if target_group is None:
        raise ValueError(f"No stroke group found for kanji {char!r}")

    # 2) Collect stroke paths in order
    path_elements = target_group.findall('.//svg:path', ns)
    d_strings = []
    for path in path_elements:
        d = path.get('d')
        if d:
            d_strings.append(d)

    # 3) Find the stroke number labels group: <g id="kvg:StrokeNumbers_...">
    numbers_group = None
    for g in root.findall('.//svg:g', ns):
        gid = g.get('id', '')
        if gid.startswith('kvg:StrokeNumbers_'):
            numbers_group = g
            break

    label_positions = []
    if numbers_group is not None:
        # Each <text> has transform="matrix(1 0 0 1 X Y)" and inner text "1", "2", ...
        for text_elem in numbers_group.findall('svg:text', ns):
            transform = text_elem.get('transform', '')
            # crude parse: look for the last two numbers in the transform
            # e.g. "matrix(1 0 0 1 26.50 23.50)"
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

    # 4) Pair strokes with label positions by stroke number.
    # In KanjiVG, paths are already in stroke order, and labels are numbered 1..N
    # so we can zip by index if counts match.
    stroke_data = []
    if label_positions and len(label_positions) == len(d_strings):
        # sort labels by number just to be safe
        label_positions.sort(key=lambda t: t[0])  # sort by num
        for idx, d in enumerate(d_strings, start=1):
            num, x, y = label_positions[idx - 1]
            stroke_data.append({
                "index": num,    # stroke number
                "d": d,          # SVG path
                "label_x": x,    # where to draw the number
                "label_y": y,
            })
    else:
        # fallback: no label positions, just stroke paths
        for idx, d in enumerate(d_strings, start=1):
            stroke_data.append({
                "index": idx,
                "d": d,
                "label_x": None,
                "label_y": None,
            })

    return stroke_data


def inject_drawing_canvas():
    js = r"""
    (function() {
        if (document.getElementById('kanji-draw-container')) {
            return;
        }

        const container = document.createElement('div');
        container.id = 'kanji-draw-container';
        container.style.marginTop = '20px';
        container.style.display = 'flex';
        container.style.flexDirection = 'column';
        container.style.alignItems = 'center';

        const label = document.createElement('div');
        label.textContent = 'Draw the kanji here:';
        label.style.marginBottom = '8px';
        container.appendChild(label);

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
        container.appendChild(clearBtn);

        document.body.appendChild(container);

        const ctx = canvas.getContext('2d');

        // ---- Build stroke structures from window.kanjiStrokePaths ----
        const rawStrokes = window.kanjiStrokePaths || [];
        const strokePaths = rawStrokes.map(s => ({
            index: s.index,
            path: new Path2D(s.d),
            label_x: s.label_x,
            label_y: s.label_y,
        }));

        const scaleX = canvas.width / 109;
        const scaleY = canvas.height / 109;

        // Always animate the current stroke until correct
        let completedStrokes = 0;

        // ---- NEW: Two independent animation timers ----
        let drawProgress = 0;          // 0→1: drawing speed
        let repeatProgress = 0;        // 0→1: loop frequency

        const drawDuration = 12000;     // slow stroke drawing (4.5 seconds)
        const repeatDuration = 1600;    // fast repeat (0.8 seconds)

        const dashLength = 1000;
        let lastTime = null;
        let animationFrameId = null;

        let userStrokes = [];
        let currentStroke = null;

        function drawBase() {
            ctx.save();
            ctx.scale(scaleX, scaleY);

            const current = strokePaths[completedStrokes];

            ctx.lineWidth = 3;
            ctx.setLineDash([]);

            // ---- Draw stroke outlines (same as before) ----
            for (const s of strokePaths) {
                if (s === current) {
                    ctx.strokeStyle = 'rgba(0, 0, 0, 0.18)';
                } else {
                    ctx.strokeStyle = 'rgba(0, 0, 0, 0.05)';
                }
                ctx.stroke(s.path);
            }

            // ---- UPDATED: draw stroke numbers with variable transparency ----
            ctx.font = '8px sans-serif';

            for (const s of strokePaths) {
                if (s.label_x == null) continue;

                if (s === current) {
                    // Current stroke → more visible red
                    ctx.fillStyle = 'rgba(255, 0, 0, 0.75)';
                } else {
                    // Other strokes → very transparent red
                    ctx.fillStyle = 'rgba(255, 0, 0, 0.25)';
                }

                ctx.fillText(String(s.index), s.label_x, s.label_y);
            }

            ctx.restore();
        }


        function drawAnimatedStroke() {
            const current = strokePaths[completedStrokes];
            if (!current) return;

            ctx.save();
            ctx.scale(scaleX, scaleY);
            ctx.lineWidth = 4;
            ctx.strokeStyle = 'rgba(0, 0, 0, 0.25)'; // transparent black

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

        function drawScene(timestamp) {
            if (lastTime === null) lastTime = timestamp;
            const dt = timestamp - lastTime;
            lastTime = timestamp;

            // Slow stroke animation
            drawProgress += dt / drawDuration;
            if (drawProgress > 1) drawProgress = 1;

            // Fast looping timer
            repeatProgress += dt / repeatDuration;
            if (repeatProgress >= 1) {
                repeatProgress = 0;
                drawProgress = 0;  // restart stroke drawing
            }

            ctx.clearRect(0, 0, canvas.width, canvas.height);

            drawBase();
            drawAnimatedStroke();
            drawUserStrokes();

            animationFrameId = requestAnimationFrame(drawScene);
        }

        animationFrameId = requestAnimationFrame(drawScene);

        // ---- Input handling (user drawing) ----
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
            userStrokes.push(currentStroke);
        }

        function moveDraw(evt) {
            if (!drawing) return;
            evt.preventDefault();
            const pos = getOffsetPos(evt);
            currentStroke.push({ x: pos.x, y: pos.y });
        }

        function endDraw(evt) {
            if (!drawing) return;
            evt.preventDefault();
            drawing = false;
            currentStroke = null;

            // TODO: evaluate correctness here later
        }

        canvas.addEventListener('mousedown', startDraw);
        canvas.addEventListener('mousemove', moveDraw);
        canvas.addEventListener('mouseup', endDraw);
        canvas.addEventListener('mouseleave', endDraw);

        canvas.addEventListener('touchstart', startDraw, { passive: false });
        canvas.addEventListener('touchmove', moveDraw, { passive: false });
        canvas.addEventListener('touchend', endDraw, { passive: false });
        canvas.addEventListener('touchcancel', endDraw, { passive: false });

        clearBtn.addEventListener('click', function() {
            userStrokes = [];
            currentStroke = null;
            drawProgress = 0;
            repeatProgress = 0;
        });

    })();
    """
    mw.reviewer.web.eval(js)


# Show a message box when the add-on is loaded
# def on_start():
#     QMessageBox.information(mw, "Hello", "Your add-on loaded!")

# on_start()