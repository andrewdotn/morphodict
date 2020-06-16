"""
separate test files need to be created for the tests in this file.
todo: delete this file
"""
import xml.etree.ElementTree as ET

import pytest

from utils import WordClass, extract_word_class, fst_analysis_parser
from utils.crkeng_xml_utils import extract_l_str


@pytest.mark.parametrize(
    "analysis, real_lemma",
    [
        ("nôhkom+N+A+D+Px1Sg+Sg", "nôhkom"),
        ("wâhkwa+N+A+Sg", "wâhkwa"),
        ("PV/yikate+tihtipinêw+V+TA+Ind+Prs+3Sg+4Sg/PlO", "tihtipinêw"),
        ("yîkatê-tihtipinam+V+TI+Ind+Prs+3Sg", "yîkatê-tihtipinam"),
        ("yîkatêpayin+V+II+Ind+Prs+3Sg", "yîkatêpayin"),
        ("tânisi+Ipc", "tânisi"),
        ("mitêh+N+I+D+PxX+Sg", "mitêh"),
        ("ôma+Pron+Def+Med+IN+Pl", "ôma"),
        ("ayinânêw+Num+Ipc", "ayinânêw"),
    ],
)
def test_hfstol_analysis_lemma_extraction(analysis, real_lemma):
    claimed = fst_analysis_parser.extract_lemma(analysis)
    assert claimed == real_lemma


@pytest.mark.parametrize(
    "analysis, category",
    [
        ("nôhkom+N+A+D+Px1Sg+Sg", WordClass("NAD")),
        ("wâhkwa+N+A+Sg", WordClass("NA")),
        ("maskwa +N+A+Der/Dim+N+A+Sg", WordClass("NA")),
        ("PV/yikate+tihtipinêw+V+TA+Ind+Prs+3Sg+4Sg/PlO", WordClass("VTA")),
        ("yîkatê-tihtipinam+V+TI+Ind+Prs+3Sg", WordClass("VTI")),
        ("yîkatêpayin+V+II+Ind+Prs+3Sg", WordClass("VII")),
        ("tânisi+Ipc", WordClass("IPC")),
        ("mitêh+N+I+D+PxX+Sg", WordClass("NID")),
        ("ôma+Pron+Def+Med+IN+Pl", WordClass("PRON")),
    ],
)
def test_hfstol_analysis_category_extraction(analysis, category):
    actual = extract_word_class(analysis)
    assert actual == category


def test_l_text_extraction(shared_datadir):
    elements = (
        ET.parse(str(shared_datadir / "crkeng-missing-l-0.xml"))
        .getroot()
        .findall(".//e")
    )
    for element in elements:
        with pytest.raises(ValueError):
            extract_l_str(element)

    elements = (
        ET.parse(str(shared_datadir / "crkeng-nice-0.xml")).getroot().findall(".//e")
    )
    results = []
    for element in elements:
        results.append(extract_l_str(element))

    assert results == ["yôwamêw", "yôtinipahtâw"]
