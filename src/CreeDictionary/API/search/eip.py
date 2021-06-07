# EIP: English Inflected Phrase search
from dataclasses import dataclass

from CreeDictionary.API.models import Wordform
from CreeDictionary.API.search.eip_crk import get_noun_tags, crkeng_tag_dict
from CreeDictionary.API.search.types import Result
from CreeDictionary.phrase_translate.translate import eng_phrase_to_crk_features_fst
import re

from CreeDictionary.shared import expensive


@dataclass
class _EipResult:
    """Tiny class to connect inflected text to original search result"""

    inflected_text: str
    original_result: Result


class EipSearch:
    """An English Inflected Phrase search.

    There are two phases:
     1. analyzing the original query to determine if is a phrase search
     2. using tags extracted from phase #1 to inflect search results obtained by
        other methods.
    """

    def __init__(self, search_run):
        self.search_run = search_run

    def analyze_query(self):
        """Analyze this search’s search_run query, possibly updating it.

        If the phrase-parsing FST returns an analysis, e.g., “ crawls
        +V+AI+Prt+3Pl” for “they crawled”, then the tags are saved for
        inflecting search results later, and the query is updated to only
        include content words, e.g., “they crawled” → “crawls”.
        """
        self.new_tags = []
        analyzed_query = PhraseAnalyzedQuery(self.search_run.query.query_string)
        if analyzed_query.has_tags:
            self.search_run.query.replace_query(analyzed_query.filtered_query)
            for tag in analyzed_query.tags:
                if tag in crkeng_tag_dict:
                    for i in crkeng_tag_dict[tag]:
                        self.new_tags.append(i)
                else:
                    self.new_tags.append(tag)
        self.search_run.add_verbose_message(
            dict(
                filtered_query=analyzed_query.filtered_query,
                tags=analyzed_query.tags,
                new_tags=self.new_tags,
            )
        )

    def inflect_search_results(self):
        inflected_results = self._generate_inflected_results()

        # FIXME: get all wordforms in a single query?
        for result in inflected_results:
            exactly_matched_wordform = Wordform.objects.filter(
                text=result.inflected_text, lemma=result.original_result.wordform
            ).first()

            if exactly_matched_wordform:
                self.search_run.remove_result(result.original_result)
                self.search_run.add_result(
                    result.original_result.create_related_result(
                        exactly_matched_wordform, is_eip_result=True
                    )
                )

    def _generate_inflected_results(self) -> list[_EipResult]:
        """
        Of the results, sort out the verbs, then inflect them
        using the new set of tags.
        Return the inflected verbs.
        """

        words = []
        for r in self.search_run.unsorted_results():
            if "+V" in self.new_tags and r.is_lemma and r.lemma_wordform.pos == "V":
                words.append(r)
            if "+N" in self.new_tags and r.is_lemma and r.lemma_wordform.pos == "N":
                words.append(r)

        orig_tags_starting_with_plus = []
        tags_ending_with_plus = []
        for t in self.new_tags:
            (
                orig_tags_starting_with_plus
                if t.startswith("+")
                else tags_ending_with_plus
            ).append(t)

        results = []
        for word in words:
            # This is sometimes mutated
            tags_starting_with_plus = orig_tags_starting_with_plus[:]

            noun_tags = ""
            if "N" in word.wordform.inflectional_category:
                noun_tags = get_noun_tags(word.wordform.inflectional_category)
                if "+N" in tags_starting_with_plus:
                    tags_starting_with_plus.remove("+N")
                if "+Der/Dim" in tags_starting_with_plus:
                    # noun tags need to be repeated in this case
                    index = tags_starting_with_plus.index("+Der/Dim")
                    tags_starting_with_plus.insert(index + 1, noun_tags)

            text = (
                "".join(tags_ending_with_plus)
                + word.lemma_wordform.text
                + noun_tags
                + "".join(tags_starting_with_plus)
            )

            generated_wordforms = expensive.strict_generator.lookup(text)
            for w in generated_wordforms:
                results.append(
                    _EipResult(
                        original_result=word,
                        inflected_text=w,
                    )
                )
        return results


# e.g., " swim +V+AI+Prt+3Pl"
PHRASE_ANALYSIS_OUTPUT_RE = re.compile(
    r"""
                        \s*             # leading blank space(s) from flag diacritics
                        (?P<query>.*)
                        \s
                        (?P<tags>\+[^\ ]+)
                    """,
    re.VERBOSE,
)


class PhraseAnalyzedQuery:
    """A structured object holding pieces of, and info about, a phrase query.

    >>> PhraseAnalyzedQuery("they swam").filtered_query
    'swim'
    >>> PhraseAnalyzedQuery("they swam").has_tags
    True
    >>> PhraseAnalyzedQuery("they swam").tags
    ['+V', '+AI', '+Prt', '+3Pl']
    >>> PhraseAnalyzedQuery("excellent").has_tags
    False
    """

    def __init__(self, query: str):
        self.query = query
        self.has_tags = False
        self.filtered_query = None
        self.tags = None
        phrase_analysis = [
            r.decode("UTF-8") for r in eng_phrase_to_crk_features_fst()[query]
        ]

        if len(phrase_analysis) != 1:
            return

        phrase_analysis = phrase_analysis[0]
        if "+?" in phrase_analysis:
            return

        match = PHRASE_ANALYSIS_OUTPUT_RE.fullmatch(phrase_analysis)
        if not match:
            return

        self.filtered_query = match["query"]
        self.has_tags = True
        self.tags = ["+" + t for t in match["tags"].split("+") if t]
