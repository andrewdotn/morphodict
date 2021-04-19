"""
fill a paradigm table according to a lemma
"""
import logging
from copy import deepcopy
from pathlib import Path
from typing import Dict, List, Sequence, Set, Tuple, cast

from hfst_optimized_lookup import TransducerFile
from paradigm import (
    Cell,
    EmptyRow,
    InflectionCell,
    Layout,
    StaticCell,
    TitleRow,
    rows_to_layout,
)
from utils import ParadigmSize, WordClass, shared_res_dir
from utils.types import ConcatAnalysis

logger = logging.getLogger()

Table = List[List[str]]
LayoutTable = Dict[Tuple[WordClass, ParadigmSize], Table]
LayoutID = Tuple[WordClass, ParadigmSize]

PARADIGM_NAME_TO_WC = {
    "noun-na": WordClass.NA,
    "noun-nad": WordClass.NAD,
    "noun-ni": WordClass.NI,
    "noun-nid": WordClass.NID,
    "verb-ai": WordClass.VAI,
    "verb-ii": WordClass.VII,
    "verb-ta": WordClass.VTA,
    "verb-ti": WordClass.VTI,
}


def import_frequency() -> Dict[ConcatAnalysis, int]:
    # TODO: store this in the database, rather than as a source file
    # TODO: make a management command that updates wordform frequencies
    FILENAME = "attested-wordforms.txt"

    res: dict[ConcatAnalysis, int] = {}
    lines = (shared_res_dir / FILENAME).read_text(encoding="UTF-8").splitlines()
    for line in lines:
        line = line.strip()
        if not line:
            # Skip empty lines
            continue

        try:
            freq, _, *analyses = line.split()
        except ValueError:  # not enough value to unpack, which means the line has less than 3 values
            logger.warn(f'line "{line}" is broken in {FILENAME}')
        else:
            for analysis in analyses:
                res[ConcatAnalysis(analysis)] = int(freq)

    return res


class ParadigmFiller:
    _layout_tables: Dict[LayoutID, Layout]
    _generator: TransducerFile
    _frequency = import_frequency()

    @staticmethod
    def _import_layouts(layout_dir) -> Dict[LayoutID, Layout]:
        """
        Imports .layout files into memory.

        :param layout_dir: the directory that has .layout files and .layout.csv files
        """
        combiner = Combiner(layout_dir)

        layout_tables = {}

        for wc in WordClass:
            if not wc.has_inflections():
                continue
            for size in ParadigmSize:
                layout_tables[(wc, size)] = rows_to_layout(
                    combiner.get_combined_table(wc, size)
                )

        return layout_tables

    def __init__(self, layout_dir: Path, generator_hfstol_path: Path = None):
        """
        Combine .layout, .layout.csv, .paradigm files to paradigm tables of different sizes and store them in memory
        inits fst generator

        :param layout_dir: the directory for .layout and .layout.cvs files
        """
        self._layout_tables = self._import_layouts(layout_dir)

        if generator_hfstol_path is None:
            from shared import expensive

            self._generator = expensive.strict_generator
        else:
            self._generator = TransducerFile(generator_hfstol_path)

    @classmethod
    def default_filler(cls):
        """
        Return a filler that uses .layout files, .paradigm files and the fst from the res folder
        """
        return ParadigmFiller(shared_res_dir / "layouts")

    def fill_paradigm(
        self, lemma: str, category: WordClass, paradigm_size: ParadigmSize
    ) -> List[Layout]:
        """
        returns a paradigm table filled with words

        :returns: filled paradigm tables
        """
        # We want to lookup all of the inflections in bulk,
        # so set up some data structures that will allow us to:
        #  - store all unique things to lookup
        #  - remember which strings need to be replaced after lookups
        lookup_strings: List[ConcatAnalysis] = []
        string_locations: List[Tuple[List[Cell], int]] = []

        if category is WordClass.IPC or category is WordClass.Pron:
            return []

        layout_table = deepcopy(self._layout_tables[(category, paradigm_size)])

        tables: List[Layout] = [[]]

        for row in layout_table:
            if row is EmptyRow:
                # Create a new "pane"
                tables.append([])
            elif isinstance(row, TitleRow):
                tables[-1].append(row)
            else:
                assert isinstance(row, list)
                row_with_replacements = row.copy()
                tables[-1].append(row_with_replacements)
                for col_ind, cell in enumerate(row):
                    if isinstance(cell, StaticCell) or cell == "":
                        # We do nothing to static and empty cells.
                        continue
                    elif isinstance(cell, InflectionCell):
                        if cell.has_analysis:

                            lookup_strings.append(cell.create_concat_analysis(lemma))
                            string_locations.append((row_with_replacements, col_ind))
                    else:
                        raise ValueError("Unexpected Cell Type")

        # Generate ALL OF THE INFLECTIONS!
        results = self._generator.bulk_lookup(lookup_strings)

        # string_locations and lookup_strings have parallel indices.
        assert len(string_locations) == len(lookup_strings)
        for i, location in enumerate(string_locations):
            row, col_ind = location
            analysis = lookup_strings[i]
            results_for_cell = sorted(results[analysis])
            # TODO: this should actually produce TWO rows!
            inflection_cell = row[col_ind]
            assert isinstance(inflection_cell, InflectionCell)
            inflection_cell.inflection = " / ".join(results_for_cell)
            inflection_cell.frequency = self._frequency.get(analysis, 0)

        return tables

    def inflect_all_with_analyses(
        self, lemma: str, wordclass: WordClass
    ) -> Dict[ConcatAnalysis, Sequence[str]]:
        """
        Produces all known forms of a given word. Returns a mapping of analyses to their
        forms. Some analyses may have multiple forms. Some analyses may not generate a
        form.
        """
        analyses = self.expand_analyses(lemma, wordclass)
        return cast(
            Dict[ConcatAnalysis, Sequence[str]], self._generator.bulk_lookup(analyses)
        )

    def inflect_all(self, lemma: str, wordclass: WordClass) -> Set[str]:
        """
        Return a set of all inflections for a particular lemma.
        """
        all_inflections = self.inflect_all_with_analyses(lemma, wordclass).values()
        return set(form for word in all_inflections for form in word)

    def expand_analyses(self, lemma: str, wordclass: WordClass) -> Set[ConcatAnalysis]:
        """
        Given a lemma and its word class, return a set of all analyses that we could
        generate, but do not actually generate anything!
        """
        # I just copy-pasted the code from fill_paradigm() and edited it.
        # I'm sure we could refactor using the Template Method pattern or even Visitor
        # pattern to reduce code duplication, but I honestly think it's not worth it in
        # this situation.
        layout_table = self._layout_tables[(wordclass, ParadigmSize.LINGUISTIC)]

        # Find all of the analyses strings in the table:
        analyses: Set[ConcatAnalysis] = set()
        for row in layout_table:
            if row is EmptyRow or isinstance(row, TitleRow):
                continue

            assert isinstance(row, list)
            for cell in row:
                if isinstance(cell, StaticCell) or cell == "":
                    continue
                elif isinstance(cell, InflectionCell):
                    if not cell.has_analysis:
                        continue
                    analysis = cell.create_concat_analysis(lemma)
                    analyses.add(analysis)
                else:
                    raise ValueError("Unexpected cell type")

        return analyses


class Combiner:
    """
    Ties together the paradigm layouts and a generator to create "pre-filled" layouts.
    """

    _layout_tables: Dict[Tuple[WordClass, ParadigmSize], Table]

    def __init__(self, layout_dir: Path):
        """
        Reads ALL of the .tsv layout files into memory and initializes the FST generator

        :param layout_dir: the absolute directory of your .tsv layout files
        """
        self._layout_tables = import_layouts(layout_dir)

    def get_combined_table(
        self, category: WordClass, paradigm_size: ParadigmSize
    ) -> List[List[str]]:
        """
        Return the appropriate layout.
        """

        if category is WordClass.IPC or category is WordClass.Pron:
            return []

        # Can be returned unchanged!
        return self._layout_tables[(category, paradigm_size)]


def import_layouts(layout_file_dir: Path) -> LayoutTable:
    layout_tables: LayoutTable = {}

    files = list(layout_file_dir.glob("*.layout.tsv"))

    if len(files) == 0:
        raise ValueError(
            f"Could not find any applicable layout files in {layout_file_dir}"
        )

    for layout_file in files:
        # Get rid of .layout
        stem, _dot, _extensions = layout_file.name.partition(".")
        *wc_str, size_str = stem.split("-")

        # Figure out if it's worth converting layout this layout.
        try:
            size = ParadigmSize(size_str.upper())
        except ValueError:
            # Unsupported "sizes" include: nehiyawewin, extended
            logger.info("unsupported paradigm size for %s", layout_file)
            continue

        wc = PARADIGM_NAME_TO_WC["-".join(wc_str)]
        table = parse_layout(layout_file)

        if (wc, size) in layout_tables:
            logger.warning(
                "%s-%s already in table; replacing with %s", wc, size, layout_file
            )
        layout_tables[(wc, size)] = table

    return layout_tables


def parse_layout(layout_file: Path) -> Table:
    """
    Parses a layout in the TSV format.
    """
    assert layout_file.match("*.tsv")

    file_text = layout_file.read_text(encoding="UTF-8")

    if "\n--\n" in file_text:
        raise NotImplementedError("NDS YAML header not supported")

    table: Table = []

    lines = file_text.splitlines()
    for row_no, line in enumerate(lines, start=1):
        line = line.rstrip()
        row = [cell.strip() for cell in line.split("\t")]
        table.append(row)

    return table
