"""
Search box helpers for Shadows File Explorer.

QueryCompleter suggests search filters (kind:image, size:>100MB, ...) for the
word being typed, keeping the rest of the query as it is.
"""
from PyQt6.QtWidgets import QCompleter
from PyQt6.QtCore import Qt, QStringListModel

from shadows_explorer.core.query import SUGGESTIONS

SEARCH_HELP = """<b>Search tips</b> (combine any of these):<br>
<code>report</code> name contains report &nbsp; <code>"annual report"</code> exact phrase<br>
<code>*.py</code> wildcards &nbsp; <code>-draft</code> leave out names with draft<br>
<code>kind:image</code> video, audio, document, code, archive, folder...<br>
<code>ext:pdf</code> or <code>ext:jpg,png</code><br>
<code>size:&gt;10MB</code> &nbsp; <code>size:1MB..5MB</code> &nbsp; <code>size:large</code><br>
<code>modified:today</code> thisweek, lastmonth, 2024, &gt;2024-03-01<br>
<code>content:"some text"</code> text inside files<br>
<code>alldrives: ...</code> search every drive"""


class QueryCompleter(QCompleter):
    """Completes the last word of a search query with a filter keyword."""

    def __init__(self, parent=None):
        super().__init__(parent)
        # Parented, so Python doesn't delete the model while the completer uses it
        self.setModel(QStringListModel(list(SUGGESTIONS), self))
        self.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        self.setCompletionMode(QCompleter.CompletionMode.PopupCompletion)
        self.setFilterMode(Qt.MatchFlag.MatchStartsWith)

    def splitPath(self, path):
        # Only the word being typed is completed, and only once it has 2 letters
        word = path.split(" ")[-1].lstrip("-")
        return [word] if len(word) >= 2 else ["\0"]

    def pathFromIndex(self, index):
        text = self.widget().text() if self.widget() else ""
        head, _, last = text.rpartition(" ")
        prefix = "-" if last.startswith("-") else ""
        completion = prefix + (index.data() or "")
        return f"{head} {completion}" if head else completion
