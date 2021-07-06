import assert from "assert";
import { minBy } from "lodash";
import { DefaultMap, makePrettierJson, stringDistance } from "./util";

export type Analysis = [string[], string, string[]];
type DefinitionList = {
  definition: string;
  sources: string[];
}[];

class DictionaryEntry {
  head?: string;
  analysis?: Analysis;
  paradigm?: string;
  senses?: DefinitionList;
  slug?: string;

  addDefinition(definition: string) {
    if (!definition.trim()) {
      return;
    }

    if (this.senses === undefined) {
      this.senses = [];
    }
    for (const k of this.senses) {
      if (k.definition === definition) {
        return;
      }
    }
    this.senses.push({ definition, sources: ["OS"] });
  }

  fstLemma() {
    assert(this.analysis);
    return this.analysis[1];
  }
}

class Wordform {
  head?: string;
  analysis?: Analysis;
  senses?: DefinitionList;
  formOf?: DictionaryEntry;
}

type ExportableWordform = Required<Omit<Wordform, "formOf">> & {
  formOf: string;
};

export class Dictionary {
  /**
   * FST tags which distinguish the lexeme, e.g., +N and +V, as opposed to tags
   * that distinguish the wordform within a lexeme, e.g., +Sg and +Pl.
   */
  readonly lexicalTags: Set<string>;
  _entries: (DictionaryEntry | Wordform)[];
  _byText: Map<string, DictionaryEntry>;

  constructor(lexicalTags: string[]) {
    this.lexicalTags = new Set(lexicalTags);
    this._entries = [];
    this._byText = new Map();
  }

  // This is a quick-and-dirty version; the git history has a slug_disambiguator
  // function with a fairly general-purpose algorithm that could be ported to
  // js.
  assignSlugs() {
    const used = new Set<string>();
    for (const e of this._entries) {
      if (!(e instanceof DictionaryEntry)) {
        continue;
      }

      if (e.slug) {
        assert(used.has(e.slug));
        used.add(e.slug);
      } else {
        let saferHeadWord = e.head!.replace(/[/\\ ]+/g, "_");

        let newSlug;
        if (!used.has(saferHeadWord)) {
          newSlug = saferHeadWord;
        } else {
          for (let i = 1; ; i++) {
            let proposed = `${saferHeadWord}@${i}`;
            if (!used.has(proposed)) {
              newSlug = proposed;
              break;
            }
          }
        }
        used.add(newSlug!);
        e.slug = newSlug;
      }
    }
  }

  /**
   * Group entries by FST lemma, elect one entry to be the lemma, and demote the
   * rest to wordforms.
   */
  determineLemmas() {
    // Save locations for replacing with Wordform objects
    const entryIndices = new Map<DictionaryEntry, number>();
    for (let i = 0; i < this._entries.length; i++) {
      const e = this._entries[i];
      if (e instanceof DictionaryEntry) {
        entryIndices.set(e, i);
      }
    }

    // Group by lemma and lexical tags
    const byFstLemmaAndLexicalTags = new DefaultMap<string, DictionaryEntry[]>(
      () => Array()
    );
    for (const e of this._entries) {
      if (e instanceof DictionaryEntry) {
        if (!e.analysis) {
          continue;
        }
        const fstLemma = e.fstLemma();
        const lexicalTags = this._extractLexicalTags(e.analysis);
        const key = JSON.stringify({ fstLemma, lexicalTags });
        byFstLemmaAndLexicalTags.get(key).push(e);
      }
    }

    // replace non-lemmas with wordform referring to lemmas
    for (const [key, entries] of byFstLemmaAndLexicalTags.entries()) {
      const { fstLemma } = JSON.parse(key);
      const lemmaEntry = minBy(entries, (e) =>
        stringDistance(fstLemma, e.head!)
      );
      assert(lemmaEntry);

      // FIXME: don’t overwrite the lemma headword; requires dictionary code to
      // first support having headword ≠ FST lemma
      lemmaEntry.head = fstLemma;

      for (const e of entries) {
        if (e === lemmaEntry) {
          continue;
        }
        const wordform = new Wordform();
        wordform.head = e.head;
        wordform.analysis = e.analysis;
        wordform.senses = e.senses;
        wordform.formOf = lemmaEntry;

        const index = entryIndices.get(e);
        assert(index);
        entryIndices.delete(e);
        this._entries[index] = wordform;
      }
    }
  }

  /**
   * Return the set of lexical tags, suitable for use as a lookup key.
   */
  private _extractLexicalTags(analysis: Analysis) {
    const tags = [...analysis[0], ...analysis[2]];
    const ret = [];
    for (const t of tags) {
      if (this.lexicalTags.has(t)) {
        ret.push(t);
      }
    }
    return [...new Set(ret)].sort();
  }

  getOrCreate(text: string) {
    assert(text);

    let existing = this._byText.get(text);
    if (existing) {
      return existing;
    }

    const entry = new DictionaryEntry();
    entry.head = text;
    this._entries.push(entry);
    this._byText.set(text, entry);
    return entry;
  }

  toJson() {
    this.assignSlugs();
    this.determineLemmas();

    const entriesToExport: (DictionaryEntry | ExportableWordform)[] = [];
    for (const e of this._entries) {
      if (!e.senses || e.senses.length === 0) {
        console.log(`Warning: no definitions for ${JSON.stringify(e)}`);
      } else {
        if (e instanceof Wordform) {
          const { head, analysis, senses } = e;
          assert(head);
          assert(analysis);
          const formOf = e.formOf!.slug;
          assert(formOf);
          entriesToExport.push({
            head,
            analysis,
            senses,
            formOf,
          });
        } else {
          entriesToExport.push(e);
        }
      }
    }
    return makePrettierJson(entriesToExport);
  }
}
