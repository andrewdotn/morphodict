import datetime
import os
import time
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Dict, List, Tuple

import django
from colorama import Fore, init
from django.db import connection

from DatabaseManager import xml_entry_lemma_finder
from DatabaseManager.cree_inflection_generator import expand_inflections
from DatabaseManager.log import DatabaseManagerLogger
from utils.crkeng_xml_utils import extract_l_str

init()  # for windows compatibility

os.environ["DJANGO_SETTINGS_MODULE"] = "CreeDictionary.settings"
django.setup()

from API.models import Definition, Inflection

logger = DatabaseManagerLogger(__name__)


def clear_database(verbose=True):
    logger.set_print_info_on_console(verbose)
    logger.info("Deleting objects from the database")

    cursor = connection.cursor()

    # Raw SQL delete is a magnitude faster than Definition.objects.all.delete()
    cursor.execute("DELETE FROM API_definition")
    cursor.execute("DELETE FROM API_inflection")

    logger.info("All Objects deleted from Database")


def generate_as_is_analysis(pos: str, lc: str) -> str:
    """
    generate analysis for xml entries whose fst analysis cannot be determined.
    The philosophy is to show lc if possible (which is more detailed), with pos being the fall back
    >>> generate_as_is_analysis('N', 'NI-2')
    'NI'
    >>> generate_as_is_analysis('N', '')
    'N'
    >>> generate_as_is_analysis('V', 'VTI')
    'VTI'
    """

    # possible parsed pos str
    # {'', 'IPV', 'Pron', 'N', 'Ipc', 'V', '-'}

    # possible parsed lc str
    # {'', 'NDA-1', 'NDI-?', 'NA-3', 'NA-4w', 'NDA-2', 'VTI-2', 'NDI-3', 'NDI-x', 'NDA-x',
    # 'IPJ  Exclamation', 'NI-5', 'NDA-4', 'VII-n', 'NDI-4', 'VTA-2', 'IPH', 'IPC ;; IPJ',
    # 'VAI-v', 'VTA-1', 'NI-3', 'VAI-n', 'NDA-4w', 'IPJ', 'PrI', 'NA-2', 'IPN', 'PR', 'IPV',
    # 'NA-?', 'NI-1', 'VTA-3', 'NI-?', 'VTA-4', 'VTI-3', 'NI-2', 'NA-4', 'NDI-1', 'NA-1', 'IPP',
    # 'NI-4w', 'INM', 'VTA-5', 'PrA', 'NDI-2', 'IPC', 'VTI-1', 'NI-4', 'NDA-3', 'VII-v', 'Interr'}

    if lc != "":
        if "-" in lc:
            return lc.split("-")[0]
        else:
            return lc
    else:
        return pos


def import_crkeng_xml(filename: Path, multi_processing: int, verbose=True):
    """
    CLEARS the database and import from an xml file
    """
    start_time = time.time()
    logger.set_print_info_on_console(verbose)
    clear_database()
    logger.info("Database cleared")

    root = ET.parse(str(filename)).getroot()

    source_ids = [s.get("id") for s in root.findall(".//source")]

    logger.info("Sources parsed: " + str(source_ids))

    # value is definition object and its source as string
    xml_lemma_pos_lc_to_str_definitions = (
        {}
    )  # type: Dict[Tuple[str,str,str], List[Tuple[str, List[str]]]]

    # One lemma could have multiple entries with different pos and lc
    xml_lemma_to_pos_lc = {}  # type: Dict[str, List[Tuple[str,str]]]

    elements = root.findall(".//e")
    logger.info("%d dictionary entries found" % len(elements))

    duplicate_xml_lemma_pos_lc_count = 0
    logger.info("extracting (xml_lemma, pos, lc) tuples")
    tuple_count = 0
    for element in elements:

        str_definitions_for_entry = []  # type: List[Tuple[str, List[str]]]
        for t in element.findall(".//mg//tg//t"):
            sources = t.get("sources")
            assert (
                sources is not None
            ), f"<t> does not have a source attribute in entry \n {ET.tostring(element)}"
            assert (
                t.text is not None
            ), f"<t> has empty content in entry \n {ET.tostring(element)}"
            str_definitions_for_entry.append((t.text, sources.split(" ")))
        # yôwamêw
        l_element = element.find("lg/l")
        assert (
            l_element is not None
        ), f"Missing <l> element in entry \n {ET.tostring(element)}"
        lc_element = element.find("lg/lc")
        assert (
            lc_element is not None
        ), f"Missing <lc> element in entry \n {ET.tostring(element)}"
        lc_str = lc_element.text

        if lc_str is None:
            lc_str = ""
        xml_lemma = extract_l_str(element)
        pos_attr = l_element.get("pos")
        assert (
            pos_attr is not None
        ), f"<l> lacks pos attribute in entry \n {ET.tostring(element)}"
        pos_str = pos_attr

        duplicate_lemma_pos_lc = False

        if xml_lemma in xml_lemma_to_pos_lc:

            if (pos_str, lc_str) in xml_lemma_to_pos_lc[xml_lemma]:
                duplicate_xml_lemma_pos_lc_count += 1
                duplicate_lemma_pos_lc = True
            else:
                tuple_count += 1
                xml_lemma_to_pos_lc[xml_lemma].append((pos_str, lc_str))
        else:
            tuple_count += 1
            xml_lemma_to_pos_lc[xml_lemma] = [(pos_str, lc_str)]

        if duplicate_lemma_pos_lc:
            xml_lemma_pos_lc_to_str_definitions[(xml_lemma, pos_str, lc_str)].extend(
                str_definitions_for_entry
            )
        else:
            xml_lemma_pos_lc_to_str_definitions[
                (xml_lemma, pos_str, lc_str)
            ] = str_definitions_for_entry

    logger.info(
        f"{Fore.BLUE}%d entries have (lemma, pos, lc) duplicate to others. Their definition will be merged{Fore.RESET}"
        % duplicate_xml_lemma_pos_lc_count
    )
    logger.info("%d (xml_lemma, pos, lc) tuples extracted" % tuple_count)

    xml_lemma_pos_lc_to_analysis = xml_entry_lemma_finder.extract_fst_lemmas(
        xml_lemma_to_pos_lc, multi_processing
    )

    # these two will be imported to the database
    as_is_xml_lemma_pos_lc = []  # type: List[Tuple[str, str, str]]
    true_lemma_analyses_to_xml_lemma_pos_lc = (
        dict()
    )  # type: Dict[str, List[Tuple[str, str, str]]]

    dup_analysis_xml_lemma_pos_lc_count = 0

    for (xml_lemma, pos, lc), analysis in xml_lemma_pos_lc_to_analysis.items():
        if analysis != "":
            if analysis in true_lemma_analyses_to_xml_lemma_pos_lc:
                dup_analysis_xml_lemma_pos_lc_count += 1

                # merge definition to the first (lemma, pos, lc)
                xml_lemma_pos_lc_to_str_definitions[
                    true_lemma_analyses_to_xml_lemma_pos_lc[analysis][0]
                ].extend(xml_lemma_pos_lc_to_str_definitions[(xml_lemma, pos, lc)])

                true_lemma_analyses_to_xml_lemma_pos_lc[analysis].append(
                    (xml_lemma, pos, lc)
                )
            else:
                true_lemma_analyses_to_xml_lemma_pos_lc[analysis] = [
                    (xml_lemma, pos, lc)
                ]
        else:
            as_is_xml_lemma_pos_lc.append((xml_lemma, pos, lc))

    logger.info(
        f"{Fore.BLUE}%d (lemma, pos, lc) have duplicate fst lemma analysis to others.\nTheir definition will be merged{Fore.RESET}"
        % dup_analysis_xml_lemma_pos_lc_count
    )

    inflection_counter = 1
    definition_counter = 1

    db_inflections = []  # type: List[Inflection]
    db_definitions = []  # type: List[Definition]

    for xml_lemma, pos, lc in as_is_xml_lemma_pos_lc:
        db_inflection = Inflection(
            id=inflection_counter,
            text=xml_lemma,
            analysis=generate_as_is_analysis(pos, lc),
            is_lemma=True,
            as_is=True,
        )
        inflection_counter += 1
        db_inflections.append(db_inflection)

        str_definitions_source_strings = xml_lemma_pos_lc_to_str_definitions[
            (xml_lemma, pos, lc)
        ]
        for str_definition, source_strings in str_definitions_source_strings:
            db_definition = Definition(
                id=definition_counter,
                text=str_definition,
                sources=" ".join(source_strings),
                lemma=db_inflection,
            )
            definition_counter += 1
            db_definitions.append(db_definition)

    expanded = expand_inflections(
        true_lemma_analyses_to_xml_lemma_pos_lc.keys(), multi_processing
    )

    for (
        true_lemma_analysis,
        xml_lemma_pos_lcs,
    ) in true_lemma_analyses_to_xml_lemma_pos_lc.items():
        for generated_analysis, generated_inflections in expanded[true_lemma_analysis]:
            # db_lemmas could be of length more than one
            # for example peepeepoopoo+N+A+Sg may generate two spellings: pepepopo / peepeepoopoo
            db_lemmas = []
            if generated_analysis != true_lemma_analysis:
                is_lemma = False
            else:
                is_lemma = True

            for generated_inflection in generated_inflections:
                db_inflection = Inflection(
                    id=inflection_counter,
                    text=generated_inflection,
                    analysis=generated_analysis,
                    is_lemma=is_lemma,
                    as_is=False,
                )

                inflection_counter += 1
                db_inflections.append(db_inflection)

                if is_lemma:
                    db_lemmas.append(db_inflection)

            if is_lemma:
                for db_lemma in db_lemmas:
                    str_definitions_source_strings = xml_lemma_pos_lc_to_str_definitions[
                        xml_lemma_pos_lcs[0]
                    ]

                    for (
                        str_definition,
                        source_strings,
                    ) in str_definitions_source_strings:
                        db_definition = Definition(
                            id=definition_counter,
                            text=str_definition,
                            sources=" ".join(source_strings),
                            lemma=db_lemma,
                        )
                        definition_counter += 1
                        db_definitions.append(db_definition)

                    # for db_lemma in db_lemmas:
                    #     db_lemma.definitions.add(db_definition)

    logger.info("Inserting %d inflections to database..." % len(db_inflections))
    Inflection.objects.bulk_create(db_inflections)
    logger.info("Done inserting.")

    logger.info("Inserting definition to database...")
    Definition.objects.bulk_create(db_definitions)
    logger.info("Done inserting.")

    seconds = datetime.timedelta(seconds=time.time() - start_time).seconds

    logger.info(
        f"{Fore.GREEN}Import finished in %d min %d sec{Fore.RESET}"
        % (seconds // 60, seconds % 60)
    )
