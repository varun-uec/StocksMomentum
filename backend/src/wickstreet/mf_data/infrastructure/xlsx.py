"""Workbook reading: XLSX on the standard library, old binary XLS through ``xlrd``.

Cells come back as text by column letter, sheet by sheet.
"""

from __future__ import annotations

import io
import re
import zipfile
from xml.etree import ElementTree

import xlrd  # type: ignore[import-untyped]

_M = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
_R = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}"
_COLUMN = re.compile(r"[A-Z]+")

Row = dict[str, str]


def _rows(book: zipfile.ZipFile, path: str, shared: list[str]) -> list[Row]:
    rows = []
    for row in ElementTree.fromstring(book.read(path)).iter(_M + "row"):
        cells = {}
        for cell in row.iter(_M + "c"):
            column = _COLUMN.match(cell.get("r", ""))
            if column is None:
                continue
            if cell.get("t") == "inlineStr":
                text = "".join(t.text or "" for t in cell.iter(_M + "t"))
            else:
                value = cell.find(_M + "v")
                if value is None or value.text is None:
                    continue
                text = shared[int(value.text)] if cell.get("t") == "s" else value.text
            cells[column.group()] = text.strip()
        rows.append(cells)
    return rows


def sheets(content: bytes) -> list[tuple[str, list[Row]]]:
    """Every sheet in workbook order, as (name, rows)."""
    book = zipfile.ZipFile(io.BytesIO(content))
    names = set(book.namelist())
    shared = (
        [
            "".join(t.text or "" for t in item.iter(_M + "t"))
            for item in ElementTree.fromstring(book.read("xl/sharedStrings.xml")).iter(_M + "si")
        ]
        if "xl/sharedStrings.xml" in names
        else []
    )
    targets = {}
    if "xl/_rels/workbook.xml.rels" in names:
        for rel in ElementTree.fromstring(book.read("xl/_rels/workbook.xml.rels")):
            target = rel.get("Target", "").lstrip("/")
            targets[rel.get("Id")] = target if target.startswith("xl/") else f"xl/{target}"
    found = []
    if "xl/workbook.xml" in names and targets:
        for sheet in ElementTree.fromstring(book.read("xl/workbook.xml")).iter(_M + "sheet"):
            path = targets.get(sheet.get(_R + "id"))
            if path in names:
                found.append((sheet.get("name", ""), _rows(book, path, shared)))
    if not found:
        paths = sorted(n for n in names if n.startswith("xl/worksheets/sheet"))
        found = [(p.rsplit("/", 1)[-1], _rows(book, p, shared)) for p in paths]
    return found


def first_sheet(content: bytes) -> list[Row]:
    """The first sheet's rows."""
    found = sheets(content)
    return found[0][1] if found else []


# The OLE2 signature of an old binary XLS file.
XLS_SIGNATURE = bytes.fromhex("d0cf11e0a1b11ae1")


def _letters(index: int) -> str:
    name = ""
    index += 1
    while index:
        index, rest = divmod(index - 1, 26)
        name = chr(ord("A") + rest) + name
    return name


def _xls_text(cell: xlrd.sheet.Cell) -> str:
    if cell.ctype == xlrd.XL_CELL_NUMBER:
        value = float(cell.value)
        return str(int(value)) if value.is_integer() else repr(value)
    return str(cell.value).strip()


def xls_sheets(content: bytes) -> list[tuple[str, list[Row]]]:
    """Every sheet of an old binary XLS workbook, as :func:`sheets` gives them."""
    book = xlrd.open_workbook(file_contents=content, on_demand=True)
    found = []
    for sheet in book.sheets():
        rows = []
        for r in range(sheet.nrows):
            cells = {}
            for c, cell in enumerate(sheet.row(r)):
                text = _xls_text(cell)
                if text:
                    cells[_letters(c)] = text
            rows.append(cells)
        found.append((sheet.name, rows))
    return found


def any_sheets(content: bytes) -> list[tuple[str, list[Row]]]:
    """Every sheet of an XLSX or an old binary XLS workbook; ``[]`` for anything else."""
    if content[:2] == b"PK":
        return sheets(content)
    if content[:8] == XLS_SIGNATURE:
        return xls_sheets(content)
    return []
