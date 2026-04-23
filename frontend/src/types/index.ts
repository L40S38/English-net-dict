export type RelationType = "synonym" | "confusable" | "cognate" | "antonym";
export type ComponentDisplayMode = "auto" | "word" | "morpheme" | "both";
export type WordSortBy = "last_viewed_at" | "created_at" | "updated_at" | "word";
export type SortOrder = "desc" | "asc";
export type InflectionAction = "merge" | "link" | "register_as_is";

export interface ComponentMeaningItem {
  text: string;
  meaning: string;
}

export interface Phrase {
  id: number;
  text: string;
  meaning: string;
  created_at: string;
  updated_at: string;
  definitions?: PhraseDefinition[];
  images?: PhraseImage[];
  words?: WordSummary[];
  chat_session_count?: number;
  wiktionary_synonyms?: string[];
  wiktionary_antonyms?: string[];
  wiktionary_see_also?: string[];
  wiktionary_derived_terms?: string[];
  wiktionary_phrases?: string[];
}

export interface PhraseDefinition {
  id: number;
  part_of_speech: string;
  meaning_en: string;
  meaning_ja: string;
  example_en: string;
  example_ja: string;
  sort_order: number;
}

export interface PhraseImage {
  id: number;
  file_path: string;
  prompt: string;
  is_active: boolean;
  created_at: string;
}

export interface WordSummary {
  id: number;
  word: string;
  phonetic?: string | null;
}

export interface WordForms {
  third_person_singular?: string;
  present_participle?: string;
  past_tense?: string;
  past_participle?: string;
  plural?: string;
  comparative?: string;
  superlative?: string;
  uncountable?: boolean;
}

export interface EtymologyComponent {
  text: string;
  meaning: string;
  type?: string;
  sort_order?: number;
  component_id?: number | null;
  linked_word_id?: number | null;
  candidate_word?: boolean;
  auto_modes?: ComponentDisplayMode[];
  display_mode?: ComponentDisplayMode;
}

export interface EtymologyBranch {
  label: string;
  meaning_en?: string;
}

export interface LanguageChainLink {
  lang: string;
  lang_name?: string;
  word: string;
  relation?: string;
}

export interface EtymologyVariant {
  label?: string;
  excerpt?: string;
  components?: EtymologyComponent[];
  component_meanings?: ComponentMeaningItem[];
  language_chain?: LanguageChainLink[];
}

export interface Definition {
  id: number;
  part_of_speech: string;
  meaning_en: string;
  meaning_ja: string;
  example_en: string;
  example_ja: string;
  sort_order: number;
}

export interface Etymology {
  id?: number;
  components: EtymologyComponent[];
  origin_word?: string | null;
  origin_language?: string | null;
  core_image?: string | null;
  branches: EtymologyBranch[];
  language_chain?: LanguageChainLink[];
  component_meanings?: ComponentMeaningItem[];
  etymology_variants?: EtymologyVariant[];
  raw_description?: string | null;
}

export interface Derivation {
  id: number;
  derived_word: string;
  part_of_speech: string;
  meaning_ja: string;
  sort_order: number;
  linked_word_id?: number | null;
}

export interface RelatedWord {
  id: number;
  related_word: string;
  relation_type: RelationType;
  note: string;
  linked_word_id?: number | null;
}

export interface WordImage {
  id: number;
  file_path: string;
  prompt: string;
  is_active: boolean;
  created_at: string;
}

export interface Word {
  id: number;
  word: string;
  phonetic?: string | null;
  forms?: WordForms;
  created_at: string;
  updated_at: string;
  last_viewed_at?: string | null;
  definitions: Definition[];
  etymology?: Etymology | null;
  derivations: Derivation[];
  related_words: RelatedWord[];
  phrases: Phrase[];
  images: WordImage[];
  /** 単語に紐づくチャットセッション数（一覧APIで返る） */
  chat_session_count?: number;
  lemma_word_id?: number | null;
  inflection_type?: string | null;
  lemma_word_text?: string | null;
  inflected_forms?: Array<{
    word_id: number;
    word: string;
    inflection_type?: string | null;
  }>;
}

export interface WordListResponse {
  items: Word[];
  total: number;
}

export interface WordSummaryForGroup {
  id: number;
  word: string;
  phonetic?: string | null;
  definitions: Definition[];
}

export interface GroupSearchResponse {
  items: WordSummaryForGroup[];
  total: number;
  phrases: Phrase[];
  phrases_total: number;
}

export interface EtymologyComponentSearchResponse {
  component_text: string;
  resolved_meaning?: string | null;
  wiktionary: {
    meanings: string[];
    related_terms: string[];
    derived_terms: string[];
    source_url?: string | null;
  };
  aggregated: {
    related_words: Array<{
      related_word: string;
      relation_type: RelationType;
      note: string;
      linked_word_id?: number | null;
      count: number;
    }>;
    derivations: Array<{
      derived_word: string;
      part_of_speech: string;
      meaning_ja: string;
      linked_word_id?: number | null;
      count: number;
    }>;
  };
  items: Word[];
  total: number;
}

export interface EtymologyComponentCache {
  id: number;
  component_text: string;
  resolved_meaning?: string | null;
  wiktionary_meanings?: string[];
  wiktionary_related_terms?: string[];
  wiktionary_derived_terms?: string[];
  wiktionary_source_url?: string | null;
  updated_at?: string;
  created_at?: string;
}

export interface EtymologyComponentListItem extends EtymologyComponentCache {
  word_count: number;
}

export interface EtymologyComponentListResponse {
  items: EtymologyComponentListItem[];
  total: number;
}

export interface ChatSession {
  id: number;
  word_id?: number | null;
  component_text?: string | null;
  component_id?: number | null;
  group_id?: number | null;
  phrase_id?: number | null;
  title: string;
  created_at: string;
  updated_at: string;
}

export interface ChatMessage {
  id: number;
  session_id: number;
  role: "user" | "assistant";
  content: string;
  citations: Array<Record<string, unknown>>;
  created_at: string;
}

export interface ChatReply {
  user_message: ChatMessage;
  assistant_message: ChatMessage;
}

export type GroupItemType = "word" | "phrase" | "example";

export interface WordGroupItem {
  id: number;
  item_type: GroupItemType;
  word_id?: number | null;
  definition_id?: number | null;
  phrase_id?: number | null;
  phrase_text?: string | null;
  phrase_meaning?: string | null;
  sort_order: number;
  created_at: string;
  word?: string | null;
  definition_part_of_speech?: string | null;
  definition_meaning_ja?: string | null;
  example_en?: string | null;
  example_ja?: string | null;
}

export interface WordGroup {
  id: number;
  name: string;
  description: string;
  item_count: number;
  created_at: string;
  updated_at: string;
  items: WordGroupItem[];
  images: GroupImage[];
}

export interface GroupImage {
  id: number;
  group_id: number;
  file_path: string;
  prompt: string;
  is_active: boolean;
  created_at: string;
}

export interface WordGroupListResponse {
  items: WordGroup[];
  total: number;
}

export interface GroupSuggestCandidate {
  item_type: GroupItemType;
  word_id?: number | null;
  definition_id?: number | null;
  phrase_id?: number | null;
  phrase_text?: string | null;
  phrase_meaning?: string | null;
  word?: string | null;
  definition_part_of_speech?: string | null;
  definition_meaning_ja?: string | null;
  example_en?: string | null;
  example_ja?: string | null;
  score: number;
}

export interface GroupSuggestResponse {
  keywords: string[];
  candidates: GroupSuggestCandidate[];
}

export interface WordCheckFound {
  id: number;
  word: string;
}

export interface WordCheckResponse {
  found: WordCheckFound[];
  not_found: string[];
}

export interface PhraseCheckFound {
  id: number;
  text: string;
}

export interface PhraseCheckResponse {
  found: PhraseCheckFound[];
  not_found: string[];
}

export interface InflectionCheckResult {
  word: string;
  is_inflected: boolean;
  selected_lemma?: string | null;
  selected_lemma_word_id?: number | null;
  selected_spelling?: string | null;
  lemma_resolution?: "direct" | "resolved_from_inflection" | "manual" | null;
  selected_inflection_type?: string | null;
  selected_has_own_content?: boolean | null;
  selected_confidence?: "high" | "medium" | "low" | null;
  selected_source?: "db_forms" | "possessive" | "wiktionary" | "nltk" | null;
  selected_score?: number | null;
  lemma_candidates?: Array<{
    lemma: string;
    lemma_word_id?: number | null;
    inflection_type?: string | null;
    has_own_content?: boolean | null;
    confidence?: "high" | "medium" | "low" | null;
    source?: "db_forms" | "possessive" | "wiktionary" | "nltk" | null;
    score?: number | null;
  }>;
  spelling_candidates?: Array<{
    spelling: string;
    source?: string | null;
    selected_lemma?: string | null;
    lemma_resolution?: "direct" | "resolved_from_inflection" | "manual" | null;
    lemma_candidates?: Array<{
      lemma: string;
      lemma_word_id?: number | null;
      inflection_type?: string | null;
      has_own_content?: boolean | null;
      confidence?: "high" | "medium" | "low" | null;
      source?: "db_forms" | "possessive" | "wiktionary" | "nltk" | null;
      score?: number | null;
    }>;
  }>;
  suggestion?: InflectionAction | null;
}

export interface InflectionCheckResponse {
  result?: InflectionCheckResult | null;
  results?: InflectionCheckResult[];
}

export interface MigrationInflectionTarget {
  id: number;
  word: string;
}

export interface MigrationInflectionTargetsResponse {
  words: MigrationInflectionTarget[];
  total: number;
}

export interface MigrationInflectionApplyDecision {
  word_id: number;
  action: "merge" | "link";
  lemma_word_id: number;
  inflection_type?: string | null;
}

export interface MigrationInflectionApplyResult {
  word_id: number;
  action: "merge" | "link";
  status: "applied" | "skipped" | "error";
  detail: string;
}

export interface MigrationInflectionApplyResponse {
  applied: number;
  skipped: number;
  errors: number;
  results: MigrationInflectionApplyResult[];
}

export interface GroupBulkAddItemsResponse {
  added: number;
  skipped: number;
}
