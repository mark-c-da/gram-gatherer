"""Keyword classify + caption-sufficiency + light field extraction."""

from __future__ import annotations

import re
from dataclasses import dataclass, field

TYPE_TO_FOLDER = {
    "recipe": "recipes",
    "book": "books",
    "album": "albums",
    "workout": "workouts",
    "other": "other",
}

RECIPE_WORDS = (
    "recipe",
    "ingredients",
    "tbsp",
    "tsp",
    "tablespoon",
    "teaspoon",
    "preheat",
    "bake",
    "oven",
    "simmer",
    "whisk",
    "saute",
    "sauté",
    "cook",
    "cups",
    "clove",
    "marinade",
    "serving",
)
BOOK_WORDS = (
    "book",
    "books",
    "bookstagram",
    "bookrecs",
    "novel",
    "author",
    "memoir",
    "paperback",
    "hardcover",
    "isbn",
    "chapter",
    "pages",
    "reading",
    "currently reading",
)
ALBUM_WORDS = (
    "album",
    "vinyl",
    "tracklist",
    "spotify",
    "apple music",
    "listen to",
    "discography",
    "lp",
    "ep",
    "released",
    "stream",
)
WORKOUT_WORDS = (
    "workout",
    "workouts",
    "exercise",
    "exercises",
    "reps",
    "rounds",
    "sets",
    "plank",
    "pushups",
    "push-ups",
    "conditioning",
    "homeworkout",
    "circuit",
    "amrap",
    "emom",
    "dumbbell",
    "kettlebell",
)
ROUNDS_RE = re.compile(r"\b\d+\s*rounds?\b", re.I)
MOVE_LINE_RE = re.compile(r"^\s*\d+\s+[A-Za-z].+", re.M)

MEASURE_RE = re.compile(
    r"\b\d+([./]\d+)?\s*(cups?|tbsp|tsp|tablespoons?|teaspoons?|oz|ounces?|lbs?|g|kg|ml|l)\b",
    re.I,
)
HASHTAG_RE = re.compile(r"#\S+")
MENTION_RE = re.compile(r"@\S+")
NON_SLUG_RE = re.compile(r"[^a-z0-9]+")
TITLE_BY_AUTHOR_RE = re.compile(
    r"^\s*(?:[-*•]\s*)?(?P<title>.+?)\s+by\s+(?P<author>[A-Z][\w.'-]+(?:\s+[A-Z][\w.'-]+){0,3})\s*$"
)
BOOK_LIST_HEADING_RE = re.compile(
    r"\b(books?\s+mentioned|book\s+recs?|reading\s+list|tbr)\b",
    re.I,
)


@dataclass
class StructuredItem:
    item_type: str
    folder: str
    title: str
    author: str = ""
    fields: dict[str, str] = field(default_factory=dict)
    ingredients: list[str] = field(default_factory=list)
    steps: list[str] = field(default_factory=list)
    books: list[str] = field(default_factory=list)
    moves: list[str] = field(default_factory=list)


def classify(text: str) -> str:
    if extract_book_mentions(text) or BOOK_LIST_HEADING_RE.search(text or ""):
        return "book"
    lowered = (text or "").lower()
    scores = {
        "recipe": _score(lowered, RECIPE_WORDS) + (2 if MEASURE_RE.search(lowered) else 0),
        "book": _score(lowered, BOOK_WORDS),
        "album": _score(lowered, ALBUM_WORDS),
        "workout": _score(lowered, WORKOUT_WORDS) + (2 if ROUNDS_RE.search(lowered) else 0),
    }
    best = max(scores, key=scores.get)
    if scores[best] >= 2:
        return best
    return "other"


SWIPE_RE = re.compile(
    r"\b(swipe|slides?|carousel|see (the )?(list|slides?)|link in bio)\b",
    re.I,
)


def caption_sufficient(caption: str) -> bool:
    """True when the caption already has the item — before OCR or Whisper."""
    text = caption or ""
    if not text.strip():
        return False
    if extract_book_mentions(text):
        return True
    if _workout_in_caption(text):
        return True
    if _score(text.lower(), RECIPE_WORDS) >= 2 or bool(MEASURE_RE.search(text)):
        return True
    if _score(text.lower(), ALBUM_WORDS) >= 2:
        return True
    # "Swipe for the list" is not enough even if it talks about books.
    if SWIPE_RE.search(text):
        return False
    cleaned = _strip_tags(text)
    if len(cleaned) < 80:
        return False
    kind = classify(text)
    if kind in {"recipe", "book", "album", "workout"}:
        return True
    return len(cleaned) >= 200


def extract_workout_moves(text: str) -> list[str]:
    moves: list[str] = []
    for raw in (text or "").splitlines():
        line = raw.strip()
        if not line:
            continue
        if ROUNDS_RE.search(line) or re.search(r"conditioning|circuit|warmup|cool.?down", line, re.I):
            moves.append(line)
            continue
        if MOVE_LINE_RE.match(line) and not MEASURE_RE.search(line):
            moves.append(line)
    return moves[:40]


def _workout_in_caption(text: str) -> bool:
    if _score(text.lower(), WORKOUT_WORDS) >= 2:
        return True
    numbered = MOVE_LINE_RE.findall(text or "")
    return bool(ROUNDS_RE.search(text or "")) and len(numbered) >= 3


def extract_book_mentions(text: str) -> list[tuple[str, str]]:
    found: list[tuple[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for raw in (text or "").splitlines():
        match = TITLE_BY_AUTHOR_RE.match(raw.strip())
        if not match:
            continue
        title = match.group("title").strip(" -–—:").strip()
        author = match.group("author").strip()
        if len(title) < 3 or title.lower() in {"books mentioned", "book", "books"}:
            continue
        key = (title.lower(), author.lower())
        if key in seen:
            continue
        seen.add(key)
        found.append((title, author))
    return found


def structure_item(text: str, fallback_author: str = "") -> StructuredItem:
    item_type = classify(text)
    title = title_from_text(text)
    author = fallback_author.strip()
    item = StructuredItem(
        item_type=item_type,
        folder=TYPE_TO_FOLDER[item_type],
        title=title,
        author=author,
    )
    if item_type == "recipe":
        item.ingredients = _extract_list_section(text, ("ingredient",))
        item.steps = _extract_list_section(text, ("instruction", "method", "steps", "directions"))
        if not item.ingredients:
            item.ingredients = [line for line in _meaningful_lines(text) if MEASURE_RE.search(line)][:20]
    elif item_type == "book":
        item.books = [f"{title} — {author}" for title, author in extract_book_mentions(text)]
        item.fields["why_save"] = _first_sentence(text)
        if not item.author:
            item.author = _author_guess(text)
    elif item_type == "album":
        item.fields["artist"] = author or _author_guess(text)
        item.fields["notes"] = _first_sentence(text)
    elif item_type == "workout":
        item.moves = extract_workout_moves(text)
        item.fields["why_save"] = _first_sentence(text)
    else:
        item.fields["summary"] = _first_sentence(text)
    return item


def title_from_text(text: str, max_len: int = 80) -> str:
    for line in (text or "").splitlines():
        cleaned = _strip_tags(line).strip(" -–—")
        if len(cleaned) >= 3:
            sentence = re.split(r"(?<=[.!?])\s+", cleaned, maxsplit=1)[0]
            return sentence[:max_len].rstrip()
    return "Untitled"


def slugify(text: str, max_len: int = 40) -> str:
    slug = NON_SLUG_RE.sub("-", (text or "").lower()).strip("-")
    slug = slug[:max_len].strip("-")
    return slug or "item"


def _score(text: str, words: tuple[str, ...]) -> int:
    return sum(1 for word in words if re.search(rf"\b{re.escape(word)}\b", text))


def _strip_tags(text: str) -> str:
    cleaned = HASHTAG_RE.sub("", text or "")
    cleaned = MENTION_RE.sub("", cleaned)
    return re.sub(r"\s+", " ", cleaned).strip()


def _meaningful_lines(text: str) -> list[str]:
    lines: list[str] = []
    for raw in (text or "").splitlines():
        line = raw.strip().lstrip("-*•").strip()
        if len(_strip_tags(line)) >= 3:
            lines.append(line)
    return lines


def _extract_list_section(text: str, headings: tuple[str, ...]) -> list[str]:
    lines = (text or "").splitlines()
    collecting = False
    collected: list[str] = []
    heading_re = re.compile(
        rf"^\s*(?:#+\s*)?(?:{'|'.join(headings)})s?\b",
        re.I,
    )
    stop_re = re.compile(r"^\s*(?:#+\s*)?(ingredients?|instructions?|method|steps|directions|notes)\b", re.I)
    for raw in lines:
        if heading_re.match(raw):
            collecting = True
            continue
        if collecting and stop_re.match(raw) and not heading_re.match(raw):
            break
        if collecting:
            line = raw.strip().lstrip("-*•0123456789.) ").strip()
            if line:
                collected.append(line)
    return collected[:30]


def _first_sentence(text: str) -> str:
    cleaned = _strip_tags(text)
    if not cleaned:
        return ""
    parts = re.split(r"(?<=[.!?])\s+", cleaned, maxsplit=1)
    return parts[0][:280]


def _author_guess(text: str) -> str:
    match = re.search(r"\bby\s+([A-Z][\w.'-]+(?:\s+[A-Z][\w.'-]+){0,3})", text or "")
    if match:
        return match.group(1).strip()
    mention = re.search(r"@([A-Za-z0-9_.]+)", text or "")
    if mention:
        return mention.group(1)
    return ""
