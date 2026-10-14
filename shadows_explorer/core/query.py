"""
Search query language for Shadows File Explorer.

A search box query is a list of words and filters, all of which must match:

    report                  name contains "report"
    "annual report"         name contains the phrase
    *.py  / IMG_????.jpg    wildcards match the whole name
    -draft                  name does NOT contain "draft"
    ext:pdf  ext:jpg,png    extension (several = any of them)
    kind:image              image, video, audio, document, code, archive,
                            pdf, spreadsheet, presentation, program, folder, file
    size:>10MB  size:<1KB   size, also >=, <=, a range 1MB..5MB, or a word:
    size:large              empty, tiny, small, medium, large, huge, gigantic
    modified:today          today, yesterday, thisweek, lastweek, thismonth,
    modified:>2024-03       lastmonth, thisyear, lastyear, a date (2024,
    modified:2024-01..2024-06    2024-05 or 2024-05-17), with > < >= <= or a..b
    content:"some text"     the file contains the text (text files only)
    tag:red  tag:work,home  has the tag (see core/tags.py)

ext:, kind: and tag: can be negated too (-ext:tmp). No Qt dependency.
"""
import calendar
import codecs
import fnmatch
import json
import os
import re
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta

from shadows_explorer.core.file_types import file_kind

KIND_ALIASES = {
    "folder": {"folder"}, "folders": {"folder"}, "dir": {"folder"}, "directory": {"folder"},
    "file": {"file"}, "files": {"file"},
    "image": {"image"}, "images": {"image"}, "picture": {"image"}, "pictures": {"image"},
    "photo": {"image"}, "photos": {"image"},
    "video": {"video"}, "videos": {"video"}, "movie": {"video"}, "movies": {"video"},
    "audio": {"audio"}, "music": {"audio"}, "sound": {"audio"}, "song": {"audio"},
    "document": {"text", "pdf", "spreadsheet", "presentation"},
    "documents": {"text", "pdf", "spreadsheet", "presentation"},
    "doc": {"text", "pdf", "spreadsheet", "presentation"},
    "docs": {"text", "pdf", "spreadsheet", "presentation"},
    "text": {"text"}, "code": {"code"}, "source": {"code"},
    "archive": {"archive"}, "archives": {"archive"}, "zip": {"archive"}, "compressed": {"archive"},
    "pdf": {"pdf"}, "spreadsheet": {"spreadsheet"}, "presentation": {"presentation"},
    "program": {"executable"}, "programs": {"executable"}, "app": {"executable"},
    "executable": {"executable"},
}

KB, MB, GB, TB = 1024, 1024 ** 2, 1024 ** 3, 1024 ** 4
SIZE_UNITS = {"": 1, "b": 1, "k": KB, "kb": KB, "m": MB, "mb": MB, "g": GB, "gb": GB, "t": TB, "tb": TB}

# Windows Explorer's size words, as (smallest, largest) in bytes, both inclusive
SIZE_WORDS = {
    "empty": (0, 0),
    "tiny": (1, 16 * KB - 1),
    "small": (16 * KB, MB - 1),
    "medium": (MB, 128 * MB - 1),
    "large": (128 * MB, GB - 1),
    "huge": (GB, 4 * GB - 1),
    "gigantic": (4 * GB, None),
}

DATE_WORDS = ("today", "yesterday", "thisweek", "lastweek", "thismonth", "lastmonth", "thisyear", "lastyear")

KEY_ALIASES = {
    "ext": "ext", "extension": "ext", "type": "ext",
    "kind": "kind",
    "size": "size",
    "modified": "modified", "date": "modified", "datemodified": "modified",
    "content": "content", "contains": "content", "containing": "content",
    "name": "name",
    "tag": "tag", "tags": "tag", "label": "tag",
}

# Keywords offered by the search box's autocomplete
SUGGESTIONS = (
    [f"kind:{k}" for k in ("image", "video", "audio", "document", "code", "archive", "pdf",
                           "spreadsheet", "presentation", "program", "folder", "file")]
    + [f"size:{w}" for w in SIZE_WORDS] + ["size:>100MB", "size:<1MB", "size:1MB..10MB"]
    + [f"modified:{w}" for w in DATE_WORDS] + ["modified:>2024-01-01", "modified:2024"]
    + ["ext:", "content:", "name:", "tag:"]
)

TOKEN_RE = re.compile(r'-?(?:[A-Za-z]+:)?(?:"[^"]*"?|\S+)')

MAX_CONTENT_BYTES = 50 * MB


class QueryError(ValueError):
    """A filter in the query could not be understood."""


@dataclass
class Query:
    """A parsed search query; matches() checks a file against it."""
    terms: list = field(default_factory=list)          # (text, negate)
    exts: set = field(default_factory=set)
    excluded_exts: set = field(default_factory=set)
    kinds: set = field(default_factory=set)
    excluded_kinds: set = field(default_factory=set)
    sizes: list = field(default_factory=list)          # (min, max), either may be None
    dates: list = field(default_factory=list)          # (start, end) timestamps, end exclusive
    content: str = ""
    tags: set = field(default_factory=set)             # Lowercase tag names, any of them
    excluded_tags: set = field(default_factory=set)

    def is_empty(self):
        return not (self.terms or self.exts or self.excluded_exts or self.kinds or self.excluded_kinds
                    or self.sizes or self.dates or self.content or self.tags or self.excluded_tags)

    def matches_tags(self, names):
        """Check tag: filters against a file's tag names (lowercase)."""
        if self.tags and not self.tags & set(names):
            return False
        return not self.excluded_tags & set(names)

    def matches_name(self, name):
        """Check the name words and wildcards (cheap: no file system access)."""
        name = name.lower()
        for text, negate in self.terms:
            if any(c in text for c in "*?["):
                found = fnmatch.fnmatchcase(name, text)
            else:
                found = text in name
            if found == negate:
                return False
        return True

    def matches(self, name, is_dir, size, mtime):
        """Check everything except content: name, extension, kind, size and date."""
        if not self.matches_name(name):
            return False
        ext = os.path.splitext(name)[1].lower().lstrip(".") if not is_dir else ""
        if self.exts and ext not in self.exts:
            return False
        if ext and ext in self.excluded_exts:
            return False
        kind = "folder" if is_dir else file_kind(name)
        kinds = {kind} if is_dir else {kind, "file"}
        if self.kinds and not kinds & self.kinds:
            return False
        if kinds & self.excluded_kinds:
            return False
        if self.sizes or self.content:
            if is_dir:
                return False  # Folder sizes and contents aren't searched
            for low, high in self.sizes:
                if (low is not None and size < low) or (high is not None and size > high):
                    return False
        for start, end in self.dates:
            if mtime is None or (start is not None and mtime < start) or (end is not None and mtime >= end):
                return False
        return True


# -------------------------- Parsing --------------------------

def tokenize(text):
    """Split a query into tokens, keeping "quoted phrases" together."""
    return TOKEN_RE.findall(text)


def _unquote(value):
    if value.startswith('"'):
        value = value[1:]
        if value.endswith('"'):
            value = value[:-1]
    return value


def parse_query(text, today=None):
    """Parse a search box query into a Query.

    Args:
        text: The query text
        today: date used for "today", "thisweek", ... (default: the real today)

    Raises:
        QueryError: A filter value is not valid (the message says which)
    """
    today = today or date.today()
    query = Query()
    for token in tokenize(text):
        negate = token.startswith("-") and len(token) > 1
        body = token[1:] if negate else token
        key, sep, value = body.partition(":")
        key = KEY_ALIASES.get(key.lower()) if sep and not key.startswith('"') else None
        if key is None:
            # A plain word, phrase or wildcard pattern ("C:" and the like stay words)
            word = _unquote(body).lower()
            if word:
                query.terms.append((word, negate))
            continue

        value = _unquote(value).strip()
        if not value:
            continue  # "ext:" while still typing
        lowered = value.lower()
        if key == "name":
            query.terms.append((lowered, negate))
        elif key == "ext":
            exts = {e.strip().lstrip(".").lstrip("*.") for e in lowered.split(",")} - {""}
            (query.excluded_exts if negate else query.exts).update(exts)
        elif key == "kind":
            kinds = set()
            for name in lowered.split(","):
                if name.strip() not in KIND_ALIASES:
                    raise QueryError(f"Unknown kind \"{name.strip()}\". Try image, video, audio, document, "
                                     f"code, archive, pdf, program, folder or file.")
                kinds |= KIND_ALIASES[name.strip()]
            (query.excluded_kinds if negate else query.kinds).update(kinds)
        elif key == "tag":
            tags = {t.strip() for t in lowered.split(",")} - {""}
            (query.excluded_tags if negate else query.tags).update(tags)
        elif negate:
            raise QueryError(f"\"-{key}:\" can't be negated; use the opposite comparison instead.")
        elif key == "size":
            query.sizes.append(parse_size_filter(lowered))
        elif key == "modified":
            query.dates.append(parse_date_filter(lowered, today))
        elif key == "content":
            query.content = lowered
    return query


def parse_size(text):
    """"10MB" -> bytes (KB = 1024 bytes). Raises QueryError."""
    match = re.fullmatch(r"(\d+(?:\.\d+)?)\s*([a-z]*)", text.strip())
    if not match or match.group(2) not in SIZE_UNITS:
        raise QueryError(f"\"{text}\" is not a size. Use a number with KB, MB or GB, like 10MB.")
    return int(float(match.group(1)) * SIZE_UNITS[match.group(2)])


def parse_size_filter(text):
    """">10mb", "1mb..5mb", "large" -> (min, max) in bytes, inclusive."""
    if text in SIZE_WORDS:
        return SIZE_WORDS[text]
    if ".." in text:
        low, _, high = text.partition("..")
        return (parse_size(low) if low else None, parse_size(high) if high else None)
    for op in (">=", "<=", ">", "<", "="):
        if text.startswith(op):
            value = parse_size(text[len(op):])
            return {">=": (value, None), "<=": (None, value), ">": (value + 1, None),
                    "<": (None, value - 1), "=": (value, value)}[op]
    value = parse_size(text)
    return (value, value)


def _period(text, today):
    """A date word or partial date -> (first day, day after the last day)."""
    if text == "today":
        return today, today + timedelta(days=1)
    if text == "yesterday":
        return today - timedelta(days=1), today
    if text in ("thisweek", "lastweek"):
        monday = today - timedelta(days=today.weekday())
        if text == "lastweek":
            monday -= timedelta(days=7)
        return monday, monday + timedelta(days=7)
    if text in ("thismonth", "lastmonth"):
        year, month = today.year, today.month
        if text == "lastmonth":
            year, month = (year - 1, 12) if month == 1 else (year, month - 1)
        return _month(year, month)
    if text in ("thisyear", "lastyear"):
        year = today.year - (text == "lastyear")
        return date(year, 1, 1), date(year + 1, 1, 1)
    try:
        if re.fullmatch(r"\d{4}", text):
            return date(int(text), 1, 1), date(int(text) + 1, 1, 1)
        if re.fullmatch(r"\d{4}-\d{1,2}", text):
            year, month = map(int, text.split("-"))
            return _month(year, month)
        if re.fullmatch(r"\d{4}-\d{1,2}-\d{1,2}", text):
            day = date(*map(int, text.split("-")))
            return day, day + timedelta(days=1)
    except ValueError:
        pass
    raise QueryError(f"\"{text}\" is not a date. Use today, thisweek, lastmonth, 2024, 2024-05 or 2024-05-17.")


def _month(year, month):
    if not 1 <= month <= 12:
        raise ValueError(month)
    days = calendar.monthrange(year, month)[1]
    return date(year, month, 1), date(year, month, days) + timedelta(days=1)


def _timestamp(day):
    return datetime(day.year, day.month, day.day).timestamp() if day is not None else None


def parse_date_filter(text, today):
    """"thisweek", ">2024-03", "2024-01..2024-06" -> (start, end) local timestamps, end exclusive."""
    if ".." in text:
        low, _, high = text.partition("..")
        start = _period(low, today)[0] if low else None
        end = _period(high, today)[1] if high else None
    else:
        for op in (">=", "<=", ">", "<"):
            if text.startswith(op):
                first, after_last = _period(text[len(op):], today)
                start, end = {">=": (first, None), ">": (after_last, None),
                              "<=": (None, after_last), "<": (None, first)}[op]
                break
        else:
            start, end = _period(text, today)
    return _timestamp(start), _timestamp(end)


# -------------------------- Content --------------------------

def find_in_file(path, needle, max_bytes=MAX_CONTENT_BYTES, chunk_size=1024 * 1024):
    """Look for needle (lowercase) in a text file, reading it in chunks.

    Binary files (a NUL byte near the start) and files over max_bytes are skipped.

    Returns:
        str or None: The matching line (shortened), or None if not found
    """
    try:
        if os.path.getsize(path) > max_bytes:
            return None
        with open(path, "rb") as f:
            head = f.read(8192)
            if head.startswith((b"\xff\xfe", b"\xfe\xff")):
                encoding = "utf-16"
            elif b"\0" in head:
                return None
            else:
                encoding = "utf-8"
            decoder = codecs.getincrementaldecoder(encoding)(errors="ignore")
            text = decoder.decode(head)
            while True:
                position = text.lower().find(needle)
                if position >= 0:
                    # Read on to the end of the line for the snippet
                    while "\n" not in text[position:] and len(text) - position < 1000:
                        more = f.read(4096)
                        if not more:
                            break
                        text += decoder.decode(more)
                    return _snippet(text, position)
                chunk = f.read(chunk_size)
                if not chunk:
                    return None
                # Keep the end of the previous chunk: the match may span both
                keep = max(len(needle) + 200, 1)
                text = text[-keep:] + decoder.decode(chunk)
    except OSError:
        return None


def _snippet(text, position):
    """The line around position, shortened to about 120 characters."""
    start = text.rfind("\n", 0, position) + 1
    end = text.find("\n", position)
    line = text[start:end if end >= 0 else len(text)].strip()
    if len(line) > 120:
        offset = position - start
        line = ("..." if offset > 40 else "") + line[max(0, offset - 40):offset + 80].strip() + "..."
    return line


# -------------------------- Saved searches --------------------------

class SavedSearches:
    """Searches the user saved, as {"name", "query", "location"} dicts.

    location is the folder searched, or "" for all drives. Stored as JSON in
    QSettings (or any object with value()/setValue()).
    """

    SETTINGS_KEY = "saved_searches"

    def __init__(self, settings):
        self.settings = settings
        raw = settings.value(self.SETTINGS_KEY, "[]")
        try:
            data = json.loads(raw) if isinstance(raw, str) else []
        except ValueError:
            data = []
        self.items = [s for s in data if isinstance(s, dict)
                      and all(isinstance(s.get(k), str) for k in ("name", "query", "location"))] \
            if isinstance(data, list) else []

    def _save(self):
        self.settings.setValue(self.SETTINGS_KEY, json.dumps(self.items))

    def add(self, name, query, location):
        """Save a search; one with the same name is replaced."""
        self.items = [s for s in self.items if s["name"] != name]
        self.items.append({"name": name, "query": query, "location": location})
        self._save()

    def rename(self, old, new):
        if new != old and any(s["name"] == new for s in self.items):
            return False
        for s in self.items:
            if s["name"] == old:
                s["name"] = new
        self._save()
        return True

    def remove(self, name):
        self.items = [s for s in self.items if s["name"] != name]
        self._save()

    def get(self, name):
        return next((s for s in self.items if s["name"] == name), None)
