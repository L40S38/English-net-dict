import type { InflectionAction } from "../types";
import type { InflectionBatchItem } from "../components/InflectionBatchModal";

type CsvRow = {
  word: string;
  lemma: string;
  lemma_word_id: string;
  inflection_type: string;
  has_own_content: string;
  suggestion: string;
  action: string;
};

const BATCH_INFLECTION_REPORT_ROWS: CsvRow[] = [
  {
    word: "test",
    lemma: "the root",
    lemma_word_id: "",
    inflection_type: "past_participle",
    has_own_content: "True",
    suggestion: "link",
    action: "register_as_is",
  },
  {
    word: "tests",
    lemma: "test",
    lemma_word_id: "",
    inflection_type: "inflection",
    has_own_content: "False",
    suggestion: "merge",
    action: "",
  },
  {
    word: "tested",
    lemma: "test",
    lemma_word_id: "",
    inflection_type: "inflection",
    has_own_content: "False",
    suggestion: "merge",
    action: "",
  },
  {
    word: "testimonial",
    lemma: "",
    lemma_word_id: "",
    inflection_type: "",
    has_own_content: "",
    suggestion: "register_as_is",
    action: "",
  },
  {
    word: "testimonials",
    lemma: "testimonial",
    lemma_word_id: "124",
    inflection_type: "plural",
    has_own_content: "False",
    suggestion: "merge",
    action: "",
  },
];

function toAction(value: string): InflectionAction {
  if (value === "merge" || value === "link" || value === "register_as_is") {
    return value;
  }
  return "register_as_is";
}

export const DEV_INFLECTION_SAMPLE_ITEMS: InflectionBatchItem[] = BATCH_INFLECTION_REPORT_ROWS.map(
  (row) => ({
    word: row.word,
    selectedLemma: row.lemma || null,
    selectedInflectionType: row.inflection_type || null,
    lemmaCandidates: row.lemma
      ? [
          {
            lemma: row.lemma,
            lemmaWordId: row.lemma_word_id ? Number(row.lemma_word_id) : null,
            inflectionType: row.inflection_type || null,
          },
        ]
      : [],
    suggestion: toAction(row.suggestion),
  }),
);
