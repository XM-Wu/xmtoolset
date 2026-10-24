"""Rename file extensions inside a chosen folder."""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
import os
from pathlib import Path
import stat
import uuid

_INVALID = set('\\/:*?"<>|')
_REPARSE_POINT = 0x400


@dataclass(frozen=True)
class RenamePlan:
    source: Path
    destination: Path
    status: str
    reason: str


def normalize_extension(text: str) -> str:
    """Accept ``png`` or ``.png`` and return a single suffix such as ``.png``."""
    raw = text.strip()
    body = raw[1:] if raw.startswith('.') else raw
    if not body or body.startswith('.') or '.' in body:
        raise ValueError('请填写一段后缀名，例如 png')
    if any(ord(char) < 32 or char in _INVALID for char in body) or body.endswith((' ', '.')):
        raise ValueError('后缀名包含不能用于文件名的字符')
    return '.' + body


def plan_renames(directory: Path, extension: str, *, recursive: bool = False) -> list[RenamePlan]:
    """Preview extension changes. Nothing is renamed."""
    folder = Path(directory)
    if not folder.is_dir():
        raise ValueError('请选择一个文件夹')
    suffix = normalize_extension(extension)
    files = _list_files(folder, recursive)
    pairs = [(source, source.with_suffix(suffix)) for source in files]
    changing = [(source, dest) for source, dest in pairs if source.name != dest.name]
    counts = Counter(_dest_key(dest) for _, dest in changing)
    entries: dict[str, dict[str, Path]] = {}

    def occupants(parent: Path) -> dict[str, Path]:
        key = os.path.normcase(str(parent))
        if key not in entries:
            found: dict[str, Path] = {}
            try:
                children = list(parent.iterdir())
            except OSError:
                children = []
            for child in children:
                found.setdefault(os.path.normcase(child.name), child)
            entries[key] = found
        return entries[key]

    plans: list[RenamePlan] = []
    for source, dest in pairs:
        if source.name == dest.name:
            plans.append(RenamePlan(source, dest, 'unchanged', '已是该后缀'))
            continue
        if counts[_dest_key(dest)] > 1:
            plans.append(RenamePlan(source, dest, 'conflict', '多个文件会变成同名'))
            continue
        occupant = occupants(dest.parent).get(os.path.normcase(dest.name))
        if occupant is not None and os.path.normcase(str(occupant)) != os.path.normcase(str(source)):
            plans.append(RenamePlan(source, dest, 'conflict', '目标已存在'))
            continue
        plans.append(RenamePlan(source, dest, 'ready', '将改名'))
    return plans


def apply_renames(plans: list[RenamePlan]) -> list[tuple[Path, Path]]:
    """Rename ready items in place. Conflicting and unchanged items are skipped.

    Files are first moved aside, then given their final names, so a case-only
    suffix change works on Windows. A failure restores everything from this call.
    """
    ready = [item for item in plans if item.status == 'ready']
    if not ready:
        return []
    token = uuid.uuid4().hex[:8]
    staged: list[tuple[Path, Path, Path]] = []
    try:
        for item in ready:
            if not _exists(item.source):
                raise FileNotFoundError(f'文件不存在：{item.source}')
            same = os.path.normcase(str(item.source)) == os.path.normcase(str(item.destination))
            if _exists(item.destination) and not same:
                raise FileExistsError(f'目标已存在：{item.destination}')
        for index, item in enumerate(ready):
            temporary = item.source.with_name(f'.{item.source.name}.{token}.{index}.xmrename')
            if _exists(temporary):
                raise FileExistsError(f'临时名称已被占用：{temporary.name}')
            item.source.rename(temporary)
            staged.append((temporary, item.destination, item.source))
        finished: list[tuple[Path, Path]] = []
        for temporary, destination, source in staged:
            temporary.rename(destination)
            finished.append((source, destination))
        return finished
    except Exception as exc:
        errors = _restore(staged)
        if errors:
            raise OSError(f'{exc}；部分文件未能恢复：' + '；'.join(errors)) from exc
        raise


def _list_files(directory: Path, recursive: bool) -> list[Path]:
    if not recursive:
        files = [child for child in directory.iterdir() if _is_file_entry(child)]
    else:
        files = []
        for root, dirs, names in os.walk(directory, followlinks=False):
            root_path = Path(root)
            dirs[:] = [name for name in dirs if not _is_reparse_point(root_path / name)]
            for name in names:
                path = root_path / name
                if _is_file_entry(path):
                    files.append(path)
    return sorted(files, key=lambda path: str(path).casefold())


def _is_file_entry(path: Path) -> bool:
    try:
        info = path.lstat()
    except OSError:
        return False
    if stat.S_ISDIR(info.st_mode):
        return False
    if _is_reparse_point(path) and not stat.S_ISREG(info.st_mode) and not stat.S_ISLNK(info.st_mode):
        return False
    return True


def _is_reparse_point(path: Path) -> bool:
    try:
        info = path.lstat()
    except OSError:
        return False
    if stat.S_ISLNK(info.st_mode):
        return True
    return bool(getattr(info, 'st_file_attributes', 0) & _REPARSE_POINT)


def _dest_key(path: Path) -> tuple[str, str]:
    return os.path.normcase(str(path.parent)), os.path.normcase(path.name)


def _exists(path: Path) -> bool:
    try:
        path.lstat()
        return True
    except OSError:
        return False


def _restore(staged: list[tuple[Path, Path, Path]]) -> list[str]:
    errors: list[str] = []
    for temporary, destination, source in reversed(staged):
        try:
            if _exists(temporary):
                temporary.rename(source)
            elif _exists(destination) and destination.name != source.name:
                destination.rename(source)
        except OSError as exc:
            errors.append(f'{source.name}（{exc}）')
    return errors
