"""
Test parsing panes.
"""

from pathlib import Path

import pytest

from CreeDictionary.paradigm.panes import (
    ColumnLabel,
    ContentRow,
    EmptyCell,
    HeaderRow,
    InflectionCell,
    MissingForm,
    Pane,
    ParadigmTemplate,
    RowLabel,
)


def test_parse_na_paradigm(na_layout_path: Path):
    """
    Parses the Plains Cree NA paradigm.

    This paradigm has three panes:
     - basic (no header)
     - diminutive (two rows: a header and one row of content)
     - possession

    With possession having the most columns.
    """
    with na_layout_path.open(encoding="UTF-8") as layout_file:
        na_paradigm_template = ParadigmTemplate.load(layout_file)

    assert count(na_paradigm_template.panes()) == 3
    basic_pane, diminutive_pane, possession_pane = na_paradigm_template.panes()

    assert basic_pane.header is None
    assert basic_pane.num_columns == 2
    assert diminutive_pane.num_columns == 2
    assert count(diminutive_pane.rows()) == 2
    assert possession_pane.header
    assert possession_pane.num_columns == 4

    assert na_paradigm_template.max_num_columns == 4


def test_dump_equal_to_file_on_disk(na_layout_path: Path):
    """
    Dumping the file should yield the same file, modulo a trailing newline.
    """
    text = na_layout_path.read_text(encoding="UTF-8").rstrip("\n")
    paradigm = ParadigmTemplate.loads(text)
    assert paradigm.dumps() == text


@pytest.mark.parametrize("cls", [EmptyCell, MissingForm])
def test_singleton_classes(cls):
    """
    A few classes should act like singletons.
    """
    assert cls() is cls()
    assert cls() == cls()


def sample_pane():
    return Pane(
        [
            HeaderRow(("Der/Dim",)),
            ContentRow([EmptyCell(), ColumnLabel(["Sg"]), ColumnLabel(["Obv"])]),
            ContentRow([RowLabel("1Sg"), MissingForm(), InflectionCell("${lemma}+")]),
        ]
    )


@pytest.mark.parametrize(
    "component",
    [
        EmptyCell(),
        MissingForm(),
        InflectionCell("${lemma}"),
        InflectionCell("ôma+Ipc"),
        ColumnLabel(("Sg",)),
        RowLabel(("1Sg",)),
        HeaderRow(("Imp",)),
        ContentRow([EmptyCell(), ColumnLabel(["Sg"]), ColumnLabel(["Pl"])]),
        ContentRow([RowLabel("1Sg"), MissingForm(), InflectionCell("${lemma}+Pl")]),
        sample_pane(),
    ],
)
def test_str_produces_parsable_result(component):
    """
    Parsing the stringified component should result in an equal component.
    """
    stringified = str(component)
    parsed = type(component).parse(stringified)
    assert component == parsed
    assert stringified == str(parsed)


def test_produces_fst_analysis_string(na_layout: ParadigmTemplate):
    """
    It should produce a valid FST analysis string.
    """

    lemma = "minôs"
    expected_lines = {
        # Basic
        f"{lemma}+N+A+Sg",
        f"{lemma}+N+A+Pl",
        f"{lemma}+N+A+Obv",
        f"{lemma}+N+A+Loc",
        f"{lemma}+N+A+Distr",
        # Diminutive
        f"{lemma}+N+A+Der/Dim+N+A+Sg",
        # Possession
        f"{lemma}+N+A+Px1Sg+Sg",
        f"{lemma}+N+A+Px1Sg+Pl",
        f"{lemma}+N+A+Px1Sg+Obv",
        f"{lemma}+N+A+Px2Sg+Sg",
        f"{lemma}+N+A+Px2Sg+Pl",
        f"{lemma}+N+A+Px2Sg+Obv",
        f"{lemma}+N+A+Px3Sg+Obv",
        f"{lemma}+N+A+Px1Pl+Sg",
        f"{lemma}+N+A+Px1Pl+Pl",
        f"{lemma}+N+A+Px1Pl+Obv",
        f"{lemma}+N+A+Px12Pl+Sg",
        f"{lemma}+N+A+Px12Pl+Pl",
        f"{lemma}+N+A+Px12Pl+Obv",
        f"{lemma}+N+A+Px2Pl+Sg",
        f"{lemma}+N+A+Px2Pl+Pl",
        f"{lemma}+N+A+Px2Pl+Obv",
        f"{lemma}+N+A+Px3Pl+Obv",
        f"{lemma}+N+A+Px4Sg/Pl+Obv",
    }
    raw_analyses = na_layout.generate_fst_analysis_string(lemma)
    generated_analyses = raw_analyses.splitlines(keepends=False)
    assert len(expected_lines) == len(generated_analyses)
    assert expected_lines == set(generated_analyses)


@pytest.fixture
def na_layout_path(shared_datadir: Path) -> Path:
    """
    Return the path to the NA layout in the test fixture dir.
    NOTE: this is **NOT** the NA paradigm used in production!
    """
    p = shared_datadir / "paradigm-layouts" / "NA.tsv"
    assert p.exists()
    return p


@pytest.fixture
def na_layout(na_layout_path: Path) -> ParadigmTemplate:
    """
    Returns the parsed NA layout.
    """
    with na_layout_path.open(encoding="UTF-8") as layout_file:
        return ParadigmTemplate.load(layout_file)


def count(it):
    """
    Returns the number of items iterated in the paradigm
    """
    return sum(1 for _ in it)
