import json
import math
import re
from collections import Counter
from html import unescape
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

TIME = r"(?:\d{1,3}:)?\d{1,3}:[0-5]\d(?:[.,]\d{1,3})?"
CUE = re.compile(rf"^\s*({TIME})\s*-->\s*({TIME})(?:\s.*)?$")
LINE = re.compile(rf"^\s*\[?({TIME})\]?\s+(.+)$")
STOP = set("""about after again also and are because been before being but can could did
does each from had has have here how into its just like more most now only other our
out over really said see should some than that the their them then there these they
thing things this those through time today too very want was way were what when where
which while who will with would you your gonna going let's welcome okay actually""".split())


def seconds(value):
    total = 0
    for field in value.replace(",", ".").split(":"):
        total = total * 60 + float(field)
    return total


def clean(value):
    return unescape(re.sub(r"<[^>]*>", "", value)).strip()


def parse(text):
    cues = []
    if "-->" in text:
        for block in re.split(r"\n[ \t]*\n", text.lstrip("\ufeff")):
            lines = block.splitlines()
            if lines and lines[0].startswith(("NOTE", "STYLE", "REGION")):
                continue
            for index, line in enumerate(lines[:2]):
                match = CUE.match(line)
                if match:
                    start, end = map(seconds, match.groups())
                    caption = clean(" ".join(lines[index + 1:]))
                    if caption and end > start:
                        cues.append((start, end, caption))
                    break
    else:
        for line in text.splitlines():
            match = LINE.match(line)
            if match:
                start = seconds(match[1])
                cues.append((start, start, clean(match[2])))
    return sorted(cues)


def tokens(text):
    return [word for word in re.findall(r"[a-z][a-z'-]{2,}", text.lower())
            if word not in STOP]


def similarity(left, right):
    norm = math.sqrt(sum(v*v for v in left.values()) * sum(v*v for v in right.values()))
    return sum(v * right[k] for k, v in left.items()) / norm if norm else 1


def chapters(cues):
    # Compare 30-second blocks using neighboring vocabulary.
    buckets = {}
    for start, _, text in cues:
        buckets.setdefault(int(start // 30), []).append(text)
    blocks = sorted(buckets)
    vectors = [Counter(tokens(" ".join(buckets[key]))) for key in blocks]
    duration = max(end for _, end, _ in cues)
    candidates = []
    for i in range(1, len(blocks)):
        cut = blocks[i] * 30
        left = sum(vectors[max(0, i-2):i], Counter())
        right = sum(vectors[i:i+2], Counter())
        score = 1 - similarity(left, right)
        if cut >= 30 and duration - cut >= 10 and score >= 0.42:
            candidates.append((score, cut))
    starts = [0]
    for _, cut in sorted(candidates, reverse=True):
        if len(starts) >= 12:
            break
        if all(abs(cut - existing) >= 30 for existing in starts):
            starts.append(cut)
    starts.sort()
    sections = [[] for _ in starts]
    index = 0
    for start, _, caption in cues:
        while index + 1 < len(starts) and start >= starts[index + 1]:
            index += 1
        sections[index].extend(tokens(caption))
    counts = [Counter(section) for section in sections]
    return [
        {"start": start, "title": " / ".join(
            word.capitalize() for word in sorted(
                counts[i],
                key=lambda word: (-counts[i][word] / (1 + sum(word in group for group in counts)), word)
            )[:3]
        ) or ("Introduction" if i == 0 else f"Section {i + 1}")}
        for i, start in enumerate(starts)
    ]


class ChapterHandler(BaseHTTPRequestHandler):
    def respond(self, status, content, content_type):
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(content)))
        self.end_headers()
        self.wfile.write(content)

    def send_json(self, status, **payload):
        self.respond(status, json.dumps(payload).encode(), "application/json")

    def do_GET(self):
        if self.path != "/":
            return self.send_error(404)
        page = Path(__file__).with_name("index.html")
        self.respond(200, page.read_bytes(), "text/html; charset=utf-8")

    def do_POST(self):
        if self.path != "/generate":
            return self.send_error(404)
        try:
            size = int(self.headers.get("Content-Length", "0"))
            if size > 2 * 1024 * 1024:
                return self.send_json(413, error="The transcript is too large.")
            if size <= 0:
                raise ValueError
            payload = json.loads(self.rfile.read(size))
        except (ValueError, UnicodeError):
            return self.send_json(400, error="Invalid request.")
        transcript = payload.get("transcript") if isinstance(payload, dict) else None
        if not isinstance(transcript, str) or not transcript.strip():
            return self.send_json(400, error="Upload captions or paste a timestamped transcript.")
        cues = parse(transcript.replace("\r\n", "\n").replace("\r", "\n"))
        if not cues:
            return self.send_json(400, error="No captions found. Try SRT, VTT, or lines like 1:42 Project setup.")
        self.send_json(200, chapters=chapters(cues))


if __name__ == "__main__":
    print("ChapterCraft is running at http://127.0.0.1:5000")
    with ThreadingHTTPServer(("127.0.0.1", 5000), ChapterHandler) as server:
        server.serve_forever()
