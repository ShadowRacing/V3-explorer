from shadows_explorer.ui.preview_pane import MAX_TEXT_CHARS, highlight_code, looks_binary, read_text


def test_read_text_truncates(tmp_path):
    path = tmp_path / "big.txt"
    path.write_text("a" * (MAX_TEXT_CHARS + 10))
    text, truncated = read_text(str(path))
    assert len(text) == MAX_TEXT_CHARS and truncated
    path.write_text("short")
    assert read_text(str(path)) == ("short", False)


def test_looks_binary(tmp_path):
    (tmp_path / "t.txt").write_text("hello")
    (tmp_path / "b.bin").write_bytes(b"\x00\x01")
    assert not looks_binary(str(tmp_path / "t.txt"))
    assert looks_binary(str(tmp_path / "b.bin"))
    assert looks_binary(str(tmp_path / "missing"))


def test_highlight_code():
    result = highlight_code("def f():\n    return 1\n", "x.py", dark=True)
    if result is not None:  # Pygments is optional
        assert "def" in result and "style=" in result
    assert highlight_code("hello", "file.unknownext", dark=False) is None
