"""
Bulk rename module for Shadows File Explorer.

Plain functions (no Qt) that work out new names for many files at once and
apply them safely:
- plan_renames(): computes new names from RenameOptions
- find_problems(): invalid names, duplicates and clashes with other files
- execute_renames(): renames in two phases so swaps (a->b, b->a) work, and
  rolls everything back if any rename fails
"""
import os
import re
import uuid
from dataclasses import dataclass

from shadows_explorer.core.utils import IS_WINDOWS, is_valid_filename

CASE_MODES = ("unchanged", "lower", "upper", "title")


@dataclass
class RenameOptions:
    """How to build the new names.

    Steps are applied in order: find/replace, template, prefix/suffix, case.

    Attributes:
        find: Text (or regex) to find in the name
        replace: Replacement text; with use_regex, \\1 etc. refer to groups
        use_regex: Treat find as a regular expression
        case_sensitive: Match find with exact case
        template: New name pattern, e.g. "Holiday {n}"; {name} is the current
            name and {n} the number. Empty keeps the name.
        start: First number for {n}
        padding: Minimum digits for {n} (3 gives 001, 002, ...)
        prefix: Text added before the name
        suffix: Text added after the name (before the extension)
        case: One of CASE_MODES
        include_extension: Apply the steps to the extension too
    """
    find: str = ""
    replace: str = ""
    use_regex: bool = False
    case_sensitive: bool = False
    template: str = ""
    start: int = 1
    padding: int = 1
    prefix: str = ""
    suffix: str = ""
    case: str = "unchanged"
    include_extension: bool = False


def _split(name, include_extension, is_dir):
    if include_extension or is_dir:
        return name, ""
    stem, ext = os.path.splitext(name)
    return (stem, ext) if stem else (name, "")


def _apply_case(text, case):
    if case == "lower":
        return text.lower()
    if case == "upper":
        return text.upper()
    if case == "title":
        return text.title()
    return text


def new_name_for(name, index, options, is_dir=False):
    """The new name for one item.

    Args:
        name: Current file name
        index: Position in the list (0-based), used for {n}
        options: RenameOptions
        is_dir: Folders have no extension to protect

    Raises:
        re.error: If options.find is an invalid regular expression
    """
    stem, ext = _split(name, options.include_extension, is_dir)

    if options.find:
        flags = 0 if options.case_sensitive else re.IGNORECASE
        pattern = options.find if options.use_regex else re.escape(options.find)
        replacement = options.replace if options.use_regex else options.replace.replace("\\", "\\\\")
        stem = re.sub(pattern, replacement, stem, flags=flags)

    if options.template:
        number = str(options.start + index).zfill(max(1, options.padding))
        stem = options.template.replace("{name}", stem).replace("{n}", number)

    stem = f"{options.prefix}{stem}{options.suffix}"
    # The extension is only changed when include_extension makes it part of stem
    return _apply_case(stem, options.case) + ext


def plan_renames(paths, options):
    """New names for a list of paths, in order.

    Returns:
        list: (path, new_name) pairs
    """
    return [(path, new_name_for(os.path.basename(os.path.normpath(path)), i, options, os.path.isdir(path)))
            for i, path in enumerate(paths)]


def _key(path):
    # Case-insensitive file systems treat "A.txt" and "a.txt" as the same file
    return os.path.normcase(os.path.normpath(path)) if IS_WINDOWS else os.path.normpath(path)


def find_problems(plan):
    """Problems that would stop the renames.

    Returns:
        dict: path -> message, for every item that cannot be renamed
    """
    problems = {}
    sources = {_key(path) for path, _ in plan}
    targets = {}
    for path, new_name in plan:
        if not is_valid_filename(new_name):
            problems[path] = "Invalid name"
            continue
        target = os.path.join(os.path.dirname(os.path.normpath(path)), new_name)
        key = _key(target)
        if key in targets:
            problems[path] = "Duplicate name"
            problems.setdefault(targets[key], "Duplicate name")
            continue
        targets[key] = path
        # Taken by a file that is not itself being renamed away
        if os.path.lexists(target) and key not in sources:
            problems[path] = "Name already exists"
    return problems


def execute_renames(pairs):
    """Rename (source, target) path pairs as one operation.

    Everything is first moved to a temporary name, then to its target, so
    renames that swap names work. If any step fails, completed renames are
    undone and the error is raised.

    Returns:
        list: The (source, target) pairs that were applied (unchanged ones skipped)
    """
    pairs = [(s, t) for s, t in pairs if os.path.normpath(s) != os.path.normpath(t)]
    done = []  # (from, to) steps, for rollback
    try:
        temporaries = []
        for source, target in pairs:
            temp = os.path.join(os.path.dirname(os.path.normpath(source)), f".rename-{uuid.uuid4().hex}")
            os.rename(source, temp)
            done.append((source, temp))
            temporaries.append((temp, target))
        for temp, target in temporaries:
            if os.path.lexists(target):
                raise FileExistsError(target)
            os.rename(temp, target)
            done.append((temp, target))
    except BaseException:
        for original, renamed in reversed(done):
            try:
                os.rename(renamed, original)
            except OSError:
                pass
        raise
    return pairs
