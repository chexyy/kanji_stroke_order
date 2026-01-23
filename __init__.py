from aqt import mw
from aqt.qt import QMessageBox
from aqt import gui_hooks
from html.parser import HTMLParser
import xml.etree.ElementTree as ET
import re
import urllib.parse
import urllib.request

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

    for kanji in unique_kanji:
        kanjiRenderer(kanji)

gui_hooks.reviewer_did_show_question.append(detect_kanji_on_question) # Adds the above function to the hook that runs when a question is shown on a card

# Combining functions
def kanjiRenderer(char):
    svgHTML = fetch_jisho_svg_html_for_kanji(char)
    strokePaths = extract_stroke_paths_from_svg(svgHTML, char)

    # For debugging:
    with open("output_file.txt", "w", encoding="utf-8") as f:
        for i, d in enumerate(strokePaths, start=1):
            f.write(f"Stroke {i}: {d}\n")

    return strokePaths


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
    # Parse XML
    root = ET.fromstring(svg_text)

    # Namespaces
    ns = {
        'svg': "http://www.w3.org/2000/svg",
        'kvg': "http://kanjivg.tagaini.net"
    }

    # Find the main <g> for this kanji, by its kvg:element attr
    # <g id="kvg:0898b" kvg:element="見" ...>
    target_group = None
    for g in root.findall('.//svg:g', ns):
        if g.get('{http://kanjivg.tagaini.net}element') == char:
            target_group = g
            break

    if target_group is None:
        raise ValueError(f"No stroke group found for kanji {char!r}")

    # Now find all <path> elements under that group, in order
    d_strings = []
    for path in target_group.findall('.//svg:path', ns):
        d = path.get('d')
        if d:
            d_strings.append(d)

    return d_strings

# Show a message box when the add-on is loaded
# def on_start():
#     QMessageBox.information(mw, "Hello", "Your add-on loaded!")

# on_start()