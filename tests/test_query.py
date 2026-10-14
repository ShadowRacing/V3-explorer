from datetime import date, datetime

import pytest

from shadows_explorer.core.query import (QueryError, SavedSearches, find_in_file, parse_query,
                                         parse_size_filter, tokenize)

TODAY = date(2024, 5, 15)  # A Wednesday


def ts(*args):
    return datetime(*args).timestamp()


def matches(query, name, is_dir=False, size=100, mtime=None):
    return parse_query(query, TODAY).matches(name, is_dir, size, mtime or ts(2024, 5, 15, 12))


def test_tokenize_keeps_quoted_phrases():
    assert tokenize('annual "big report" content:"two words" -draft') == \
        ['annual', '"big report"', 'content:"two words"', '-draft']


def test_words_phrases_and_negation():
    assert matches("report", "Annual Report.pdf")
    assert matches("annual report", "report-annual.txt")  # Every word, any order
    assert not matches('"annual report"', "report-annual.txt")
    assert matches('"annual report"', "My Annual Report.docx")
    assert not matches("report -draft", "report draft.txt")
    assert matches("report -draft", "report final.txt")


def test_wildcards_match_the_whole_name():
    assert matches("*.py", "main.py")
    assert not matches("*.py", "main.pyc")
    assert matches("img_????.jpg", "IMG_1234.JPG")
    assert not matches("img_????.jpg", "IMG_12345.JPG")


def test_ext_and_kind():
    assert matches("ext:pdf", "a.PDF")
    assert matches("ext:jpg,png", "a.png")
    assert matches("ext:.jpg", "a.jpg")
    assert not matches("ext:jpg", "a.png")
    assert not matches("-ext:tmp", "a.tmp")
    assert matches("kind:image", "photo.heic")
    assert matches("kind:document", "sheet.xlsx")
    assert not matches("kind:document", "song.mp3")
    assert matches("kind:folder", "stuff", is_dir=True)
    assert not matches("kind:folder", "stuff.txt")
    assert matches("kind:file", "stuff.txt")
    assert not matches("kind:file", "stuff", is_dir=True)
    assert not matches("-kind:folder", "stuff", is_dir=True)
    assert not matches("kind:image", "pics", is_dir=True)


def test_size_filters():
    assert parse_size_filter(">10mb") == (10 * 1024 ** 2 + 1, None)
    assert parse_size_filter("<=1kb") == (None, 1024)
    assert parse_size_filter("1.5k..2m") == (1536, 2 * 1024 ** 2)
    assert parse_size_filter("large") == (128 * 1024 ** 2, 1024 ** 3 - 1)
    assert matches("size:>1kb", "big.bin", size=5000)
    assert not matches("size:>1kb", "small.bin", size=10)
    assert matches("size:empty", "e.txt", size=0)
    assert not matches("size:>1kb", "dir", is_dir=True)  # Folders have no measured size
    assert matches("size:>1kb size:<10kb", "mid.bin", size=5000)
    assert not matches("size:>1kb size:<10kb", "big.bin", size=50000)


def test_date_filters():
    assert matches("modified:today", "f", mtime=ts(2024, 5, 15, 8))
    assert not matches("modified:today", "f", mtime=ts(2024, 5, 14, 23))
    assert matches("modified:yesterday", "f", mtime=ts(2024, 5, 14, 23))
    assert matches("modified:thisweek", "f", mtime=ts(2024, 5, 13, 0))   # Monday
    assert not matches("modified:thisweek", "f", mtime=ts(2024, 5, 12, 23))
    assert matches("modified:lastweek", "f", mtime=ts(2024, 5, 6, 1))
    assert matches("modified:lastmonth", "f", mtime=ts(2024, 4, 30, 1))
    assert matches("modified:2023", "f", mtime=ts(2023, 7, 1))
    assert matches("modified:2024-02", "f", mtime=ts(2024, 2, 29))
    assert matches("modified:>2024-03", "f", mtime=ts(2024, 4, 1))
    assert not matches("modified:>2024-03", "f", mtime=ts(2024, 3, 31))
    assert matches("modified:<2024-03", "f", mtime=ts(2024, 2, 28))
    assert not matches("modified:<2024-03", "f", mtime=ts(2024, 3, 1))
    assert matches("modified:2024-01..2024-03", "f", mtime=ts(2024, 3, 31, 23))
    assert not matches("modified:2024-01..2024-03", "f", mtime=ts(2024, 4, 1))


def test_lastmonth_in_january():
    query = parse_query("modified:lastmonth", date(2024, 1, 10))
    assert query.matches("f", False, 1, ts(2023, 12, 31))


def test_invalid_filters_explain_themselves():
    for text in ("kind:spaceship", "size:big", "modified:someday", "modified:2024-13", "-size:>1mb"):
        with pytest.raises(QueryError):
            parse_query(text, TODAY)


def test_unknown_keys_and_unfinished_filters_stay_harmless():
    query = parse_query("c:\\users ext:", TODAY)
    assert query.terms == [("c:\\users", False)] and not query.exts
    assert parse_query("", TODAY).is_empty()
    assert not parse_query("size:large", TODAY).is_empty()


def test_content_search(tmp_path):
    text = tmp_path / "notes.txt"
    text.write_text("first line\nThe Secret Plan is here\nlast", encoding="utf-8")
    binary = tmp_path / "data.bin"
    binary.write_bytes(b"\0\0secret plan")
    utf16 = tmp_path / "win.txt"
    utf16.write_text("hello secret plan", encoding="utf-16")
    assert find_in_file(str(text), "secret plan") == "The Secret Plan is here"
    assert find_in_file(str(text), "missing") is None
    assert find_in_file(str(binary), "secret plan") is None
    assert find_in_file(str(utf16), "secret plan") == "hello secret plan"
    assert find_in_file(str(text), "secret", max_bytes=5) is None
    # Content searches only look at files
    assert not parse_query('content:"x"', TODAY).matches("dir", True, 0, ts(2024, 1, 1))


class FakeSettings(dict):
    def value(self, key, default=None):
        return self.get(key, default)

    def setValue(self, key, value):
        self[key] = value


def test_saved_searches_round_trip():
    settings = FakeSettings()
    saved = SavedSearches(settings)
    saved.add("Big videos", "kind:video size:>1GB", "")
    saved.add("Notes", "*.md", "/home/me")
    saved.add("Notes", "*.txt", "/home/me")  # Same name replaces
    assert [s["query"] for s in SavedSearches(settings).items] == ["kind:video size:>1GB", "*.txt"]
    assert not saved.rename("Notes", "Big videos")
    assert saved.rename("Notes", "Text files")
    saved.remove("Big videos")
    assert SavedSearches(settings).items == [{"name": "Text files", "query": "*.txt", "location": "/home/me"}]
    assert SavedSearches(FakeSettings(saved_searches="not json")).items == []


def test_content_search_across_chunks(tmp_path):
    big = tmp_path / "big.log"
    # The first read is 8192 bytes, so the phrase starts in it and ends in the next chunk
    big.write_text("x" * 8185 + " needle in the haystack\n" + "y" * 50000, encoding="utf-8")
    snippet = find_in_file(str(big), "needle in the haystack", chunk_size=4096)
    assert snippet is not None and "needle in the haystack" in snippet and len(snippet) < 130
    assert find_in_file(str(big), "not there", chunk_size=4096) is None
