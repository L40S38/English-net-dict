from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, model_validator

from core.constants import GROUP_NAME_MAX_LENGTH


class DefinitionExampleBase(BaseModel):
    example_en: str = ""
    example_ja: str = ""
    sort_order: int = 0

    model_config = {"from_attributes": True}


class DefinitionExampleCreate(DefinitionExampleBase):
    pass


class DefinitionExampleUpdate(DefinitionExampleBase):
    pass


class DefinitionExampleRead(DefinitionExampleBase):
    id: int
    audio_path: str | None = None

    model_config = {"from_attributes": True}


class DefinitionBase(BaseModel):
    part_of_speech: str
    meaning_en: str
    meaning_ja: str
    examples: list[DefinitionExampleBase] = Field(default_factory=list)
    sort_order: int = 0


class DefinitionCreate(DefinitionBase):
    pass


class DefinitionUpdate(DefinitionBase):
    pass


class DefinitionRead(DefinitionBase):
    id: int
    examples: list[DefinitionExampleRead] = Field(default_factory=list)

    model_config = {"from_attributes": True}


class EtymologyComponentItemBase(BaseModel):
    text: str = ""
    meaning: str = ""
    type: str = "root"
    sort_order: int = 0
    display_mode: str | None = None

    model_config = {"extra": "ignore"}


class EtymologyComponentItemCreate(EtymologyComponentItemBase):
    component_id: int | None = None


class EtymologyComponentItemRead(EtymologyComponentItemBase):
    component_id: int | None = None
    linked_word_id: int | None = None
    candidate_word: bool | None = None
    auto_modes: list[str] | None = None


class EtymologyBranchBase(BaseModel):
    label: str = ""
    meaning_en: str | None = None
    meaning_ja: str | None = None


class EtymologyBranchCreate(EtymologyBranchBase):
    pass


class EtymologyBranchRead(EtymologyBranchBase):
    model_config = {"from_attributes": True}


class EtymologyLanguageChainLinkBase(BaseModel):
    lang: str = ""
    lang_name: str | None = None
    word: str = ""
    relation: str | None = None


class EtymologyLanguageChainLinkCreate(EtymologyLanguageChainLinkBase):
    pass


class EtymologyLanguageChainLinkRead(EtymologyLanguageChainLinkBase):
    model_config = {"from_attributes": True}


class EtymologyComponentMeaningBase(BaseModel):
    text: str = ""
    meaning: str = ""


class EtymologyComponentMeaningCreate(EtymologyComponentMeaningBase):
    pass


class EtymologyComponentMeaningRead(EtymologyComponentMeaningBase):
    model_config = {"from_attributes": True}


class EtymologyVariantBase(BaseModel):
    label: str | None = None
    excerpt: str | None = None
    components: list[EtymologyComponentItemCreate] = Field(default_factory=list)
    component_meanings: list[EtymologyComponentMeaningCreate] = Field(default_factory=list)
    language_chain: list[EtymologyLanguageChainLinkCreate] = Field(default_factory=list)


class EtymologyVariantCreate(EtymologyVariantBase):
    pass


class EtymologyVariantRead(EtymologyVariantBase):
    components: list[EtymologyComponentItemRead] = Field(default_factory=list)
    component_meanings: list[EtymologyComponentMeaningRead] = Field(default_factory=list)
    language_chain: list[EtymologyLanguageChainLinkRead] = Field(default_factory=list)


class EtymologyRead(BaseModel):
    id: int | None = None
    components: list[EtymologyComponentItemRead] = Field(default_factory=list)
    origin_word: str | None = None
    origin_language: str | None = None
    core_image: str | None = None
    branches: list[EtymologyBranchRead] = Field(default_factory=list)
    language_chain: list[EtymologyLanguageChainLinkRead] = Field(default_factory=list)
    component_meanings: list[EtymologyComponentMeaningRead] = Field(default_factory=list)
    etymology_variants: list[EtymologyVariantRead] = Field(default_factory=list)
    raw_description: str | None = None

    model_config = {"from_attributes": True}


class EtymologyUpdate(BaseModel):
    components: list[EtymologyComponentItemCreate] = Field(default_factory=list)
    origin_word: str | None = None
    origin_language: str | None = None
    core_image: str | None = None
    branches: list[EtymologyBranchCreate] = Field(default_factory=list)
    language_chain: list[EtymologyLanguageChainLinkCreate] = Field(default_factory=list)
    component_meanings: list[EtymologyComponentMeaningCreate] = Field(default_factory=list)
    etymology_variants: list[EtymologyVariantCreate] = Field(default_factory=list)
    raw_description: str | None = None


class DerivationRead(BaseModel):
    id: int
    derived_word: str
    part_of_speech: str
    meaning_ja: str
    sort_order: int
    linked_word_id: int | None = None

    model_config = {"from_attributes": True}


class RelatedWordRead(BaseModel):
    id: int
    related_word: str
    relation_type: Literal["synonym", "confusable", "cognate", "antonym"]
    note: str
    linked_word_id: int | None = None

    model_config = {"from_attributes": True}


class WordImageRead(BaseModel):
    id: int
    file_path: str
    prompt: str
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class GroupImageRead(BaseModel):
    id: int
    group_id: int
    file_path: str
    prompt: str
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}

class WordCreateRequest(BaseModel):
    word: str
    inflection_action: Literal["merge", "link", "register_as_is"] | None = None
    lemma_word: str | None = None


class BulkWordRequest(BaseModel):
    words: list[str]


class BulkWordIdsRequest(BaseModel):
    word_ids: list[int] = Field(default_factory=list)


class WordCheckFound(BaseModel):
    id: int
    word: str


class WordCheckResponse(BaseModel):
    found: list[WordCheckFound] = Field(default_factory=list)
    not_found: list[str] = Field(default_factory=list)


class PhraseCheckRequest(BaseModel):
    texts: list[str]


class PhraseCheckFound(BaseModel):
    id: int
    text: str


class PhraseCheckResponse(BaseModel):
    found: list[PhraseCheckFound] = Field(default_factory=list)
    not_found: list[str] = Field(default_factory=list)


class InflectionCheckRequest(BaseModel):
    word: str | None = None
    words: list[str] = Field(default_factory=list)
    use_db_near: bool = False
    spellchecker_merge_db: bool = False


class InflectionCheckResult(BaseModel):
    word: str
    is_inflected: bool
    word_has_own_content: bool | None = None
    selected_lemma: str | None = None
    selected_lemma_word_id: int | None = None
    selected_inflection_type: str | None = None
    selected_has_own_content: bool | None = None
    selected_confidence: Literal["high", "medium", "low"] | None = None
    selected_source: Literal["db_forms", "possessive", "wiktionary", "nltk"] | None = None
    selected_score: int | None = None
    selected_spelling: str | None = None
    lemma_resolution: Literal["direct", "resolved_from_inflection", "manual"] | None = None
    lemma_candidates: list[dict] = Field(default_factory=list)
    spelling_candidates: list[dict] = Field(default_factory=list)
    suggestion: Literal["merge", "link", "register_as_is"] | None = None


class InflectionCheckResponse(BaseModel):
    result: InflectionCheckResult | None = None
    results: list[InflectionCheckResult] = Field(default_factory=list)


class MigrationInflectionTarget(BaseModel):
    id: int
    word: str


class MigrationInflectionTargetsResponse(BaseModel):
    words: list[MigrationInflectionTarget] = Field(default_factory=list)
    total: int = 0


class MigrationInflectionApplyDecision(BaseModel):
    word_id: int
    action: Literal["merge", "link"]
    lemma_word_id: int
    inflection_type: str | None = None


class MigrationInflectionApplyRequest(BaseModel):
    decisions: list[MigrationInflectionApplyDecision] = Field(default_factory=list)


class MigrationInflectionApplyResult(BaseModel):
    word_id: int
    action: Literal["merge", "link"]
    status: Literal["applied", "skipped", "error"]
    detail: str = ""


class MigrationInflectionApplyResponse(BaseModel):
    applied: int = 0
    skipped: int = 0
    errors: int = 0
    results: list[MigrationInflectionApplyResult] = Field(default_factory=list)


class PhraseBase(BaseModel):
    text: str
    meaning: str = ""


class PhraseCreate(PhraseBase):
    pass


class PhraseUpdate(BaseModel):
    meaning: str = ""


class PhraseDefinitionBase(BaseModel):
    part_of_speech: str = "phrase"
    meaning_en: str = ""
    meaning_ja: str = ""
    example_en: str = ""
    example_ja: str = ""
    sort_order: int = 0


class PhraseDefinitionWrite(PhraseDefinitionBase):
    id: int | None = None


class PhraseDefinitionRead(PhraseDefinitionBase):
    id: int
    audio_path: str | None = None

    model_config = {"from_attributes": True}


class PhraseImageRead(BaseModel):
    id: int
    file_path: str
    prompt: str
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class WordSummary(BaseModel):
    id: int
    word: str
    phonetic: str | None = None
    audio_path: str | None = None

    model_config = {"from_attributes": True}


class PhraseRead(PhraseBase):
    id: int
    created_at: datetime
    updated_at: datetime
    audio_path: str | None = None
    definitions: list[PhraseDefinitionRead] = Field(default_factory=list)
    images: list[PhraseImageRead] = Field(default_factory=list)
    words: list[WordSummary] = Field(default_factory=list)
    chat_session_count: int = 0
    wiktionary_synonyms: list[str] = Field(default_factory=list)
    wiktionary_antonyms: list[str] = Field(default_factory=list)
    wiktionary_see_also: list[str] = Field(default_factory=list)
    wiktionary_derived_terms: list[str] = Field(default_factory=list)
    wiktionary_phrases: list[str] = Field(default_factory=list)

    model_config = {"from_attributes": True}


class PhraseFullUpdate(BaseModel):
    text: str
    meaning: str = ""
    definitions: list[PhraseDefinitionWrite] = Field(default_factory=list)
    word_ids: list[int] = Field(default_factory=list)
    wiktionary_synonyms: list[str] = Field(default_factory=list)
    wiktionary_antonyms: list[str] = Field(default_factory=list)
    wiktionary_see_also: list[str] = Field(default_factory=list)
    wiktionary_derived_terms: list[str] = Field(default_factory=list)
    wiktionary_phrases: list[str] = Field(default_factory=list)


class WordRead(BaseModel):
    id: int
    word: str
    phonetic: str | None = None
    audio_path: str | None = None
    forms: dict = Field(default_factory=dict)
    created_at: datetime
    updated_at: datetime
    last_viewed_at: datetime | None = None
    definitions: list[DefinitionRead] = Field(default_factory=list)
    etymology: EtymologyRead | None = None
    derivations: list[DerivationRead] = Field(default_factory=list)
    related_words: list[RelatedWordRead] = Field(default_factory=list)
    phrases: list[PhraseRead] = Field(default_factory=list)
    images: list[WordImageRead] = Field(default_factory=list)
    chat_session_count: int = 0
    lemma_word_id: int | None = None
    inflection_type: str | None = None
    lemma_word_text: str | None = None
    inflected_forms: list[dict] = Field(default_factory=list)

    model_config = {"from_attributes": True}


class WordListResponse(BaseModel):
    items: list[WordRead]
    total: int


class WordCreateResponse(BaseModel):
    """POST /api/words のレスポンス。
    熟語入力時には `phrase_id` に作成／取得した熟語の ID を返す。"""

    words: list[WordRead] = Field(default_factory=list)
    phrase_id: int | None = None


class WordSummaryForGroup(BaseModel):
    id: int
    word: str
    phonetic: str | None = None
    definitions: list[DefinitionRead] = Field(default_factory=list)


class GroupSearchResponse(BaseModel):
    items: list[WordSummaryForGroup] = Field(default_factory=list)
    total: int = 0
    phrases: list[PhraseRead] = Field(default_factory=list)
    phrases_total: int = 0


class SearchSuggestItem(BaseModel):
    type: Literal["word", "phrase"]
    id: int
    text: str


class EtymologyComponentWiktionaryInfo(BaseModel):
    meanings: list[str] = Field(default_factory=list)
    related_terms: list[str] = Field(default_factory=list)
    derived_terms: list[str] = Field(default_factory=list)
    source_url: str | None = None


class EtymologyComponentAggregatedRelatedWord(BaseModel):
    related_word: str
    relation_type: Literal["synonym", "confusable", "cognate", "antonym"]
    note: str = ""
    linked_word_id: int | None = None
    count: int = 1


class EtymologyComponentAggregatedDerivation(BaseModel):
    derived_word: str
    part_of_speech: str
    meaning_ja: str
    linked_word_id: int | None = None
    count: int = 1


class EtymologyComponentAggregatedInfo(BaseModel):
    related_words: list[EtymologyComponentAggregatedRelatedWord] = Field(default_factory=list)
    derivations: list[EtymologyComponentAggregatedDerivation] = Field(default_factory=list)


class EtymologyComponentSearchResponse(BaseModel):
    component_text: str
    resolved_meaning: str | None = None
    wiktionary: EtymologyComponentWiktionaryInfo = Field(default_factory=EtymologyComponentWiktionaryInfo)
    aggregated: EtymologyComponentAggregatedInfo = Field(default_factory=EtymologyComponentAggregatedInfo)
    items: list[WordRead]
    total: int


class EtymologyComponentRead(BaseModel):
    id: int
    component_text: str
    resolved_meaning: str | None = None
    wiktionary_meanings: list[str] = Field(default_factory=list)
    wiktionary_related_terms: list[str] = Field(default_factory=list)
    wiktionary_derived_terms: list[str] = Field(default_factory=list)
    wiktionary_source_url: str | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class EtymologyComponentListItem(EtymologyComponentRead):
    word_count: int = 0


class EtymologyComponentListResponse(BaseModel):
    items: list[EtymologyComponentListItem]
    total: int


class WordGroupCreate(BaseModel):
    name: str = Field(..., max_length=GROUP_NAME_MAX_LENGTH)
    description: str = ""


class WordGroupUpdate(BaseModel):
    name: str = Field(..., max_length=GROUP_NAME_MAX_LENGTH)
    description: str = ""


class WordGroupItemCreate(BaseModel):
    item_type: Literal["word", "phrase", "example"]
    word_id: int | None = None
    definition_id: int | None = None
    phrase_id: int | None = None
    phrase_text: str | None = None
    phrase_meaning: str | None = None
    sort_order: int = 0


class WordGroupItemRead(BaseModel):
    id: int
    item_type: Literal["word", "phrase", "example"]
    word_id: int | None = None
    definition_id: int | None = None
    phrase_id: int | None = None
    phrase_text: str | None = None
    phrase_meaning: str | None = None
    sort_order: int
    created_at: datetime
    word: str | None = None
    definition_part_of_speech: str | None = None
    definition_meaning_ja: str | None = None
    example_en: str | None = None
    example_ja: str | None = None


class WordGroupRead(BaseModel):
    id: int
    name: str
    description: str = ""
    item_count: int = 0
    created_at: datetime
    updated_at: datetime
    items: list[WordGroupItemRead] = Field(default_factory=list)
    images: list[GroupImageRead] = Field(default_factory=list)

    model_config = {"from_attributes": True}


class WordGroupListResponse(BaseModel):
    items: list[WordGroupRead]
    total: int


class GroupSuggestRequest(BaseModel):
    keywords: list[str] = Field(default_factory=list)
    limit: int = 20


class GroupSuggestCandidate(BaseModel):
    item_type: Literal["word", "phrase", "example"]
    word_id: int | None = None
    definition_id: int | None = None
    phrase_id: int | None = None
    phrase_text: str | None = None
    phrase_meaning: str | None = None
    word: str | None = None
    definition_part_of_speech: str | None = None
    definition_meaning_ja: str | None = None
    example_en: str | None = None
    example_ja: str | None = None
    score: float = 0.0


class GroupSuggestResponse(BaseModel):
    keywords: list[str] = Field(default_factory=list)
    candidates: list[GroupSuggestCandidate] = Field(default_factory=list)


class GenerateImageRequest(BaseModel):
    prompt: str | None = None


class DefinitionPayload(DefinitionBase):
    id: int | None = None


class EtymologyPayload(BaseModel):
    components: list[EtymologyComponentItemCreate] = Field(default_factory=list)
    origin_word: str | None = None
    origin_language: str | None = None
    core_image: str | None = None
    branches: list[EtymologyBranchCreate] = Field(default_factory=list)
    language_chain: list[EtymologyLanguageChainLinkCreate] = Field(default_factory=list)
    component_meanings: list[EtymologyComponentMeaningCreate] = Field(default_factory=list)
    etymology_variants: list[EtymologyVariantCreate] = Field(default_factory=list)
    raw_description: str | None = None


class DerivationPayload(BaseModel):
    id: int | None = None
    derived_word: str
    part_of_speech: str
    meaning_ja: str
    sort_order: int = 0


class RelatedWordPayload(BaseModel):
    id: int | None = None
    related_word: str
    relation_type: Literal["synonym", "confusable", "cognate", "antonym"]
    note: str = ""


class WordFullUpdate(BaseModel):
    word: str | None = None
    phonetic: str | None = None
    forms: dict = Field(default_factory=dict)
    phrases: list[PhraseCreate] = Field(default_factory=list)
    definitions: list[DefinitionPayload] = Field(default_factory=list)
    etymology: EtymologyPayload | None = None
    derivations: list[DerivationPayload] = Field(default_factory=list)
    related_words: list[RelatedWordPayload] = Field(default_factory=list)


class DerivationCreate(BaseModel):
    derived_word: str
    part_of_speech: str
    meaning_ja: str
    sort_order: int = 0


class DerivationUpdate(DerivationCreate):
    pass


class RelatedWordCreate(BaseModel):
    related_word: str
    relation_type: Literal["synonym", "confusable", "cognate", "antonym"]
    note: str = ""


class RelatedWordUpdate(RelatedWordCreate):
    pass


class ChatSessionCreate(BaseModel):
    title: str | None = None


class ChatSessionUpdate(BaseModel):
    title: str


class ChatSessionRead(BaseModel):
    id: int
    word_id: int | None = None
    component_text: str | None = None
    component_id: int | None = None
    group_id: int | None = None
    phrase_id: int | None = None
    title: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ChatMessageCreate(BaseModel):
    content: str


class ChatMessageRead(BaseModel):
    id: int
    session_id: int
    role: str
    content: str
    citations: list[dict] = Field(default_factory=list)
    created_at: datetime

    model_config = {"from_attributes": True}


class ChatReply(BaseModel):
    user_message: ChatMessageRead
    assistant_message: ChatMessageRead


class StructuredDefinition(BaseModel):
    part_of_speech: str = "noun"
    meaning_en: str = ""
    meaning_ja: str = ""
    examples_en: list[str] = Field(default_factory=list)
    examples_ja: list[str] = Field(default_factory=list)
    sort_order: int = 0

    @model_validator(mode="after")
    def _validate_examples_len(self) -> "StructuredDefinition":
        if len(self.examples_en) != len(self.examples_ja):
            raise ValueError("examples_en and examples_ja must have same length")
        return self


class StructuredDerivation(BaseModel):
    derived_word: str = ""
    part_of_speech: str = "noun"
    meaning_ja: str = ""
    sort_order: int = 0


class StructuredRelatedWord(BaseModel):
    related_word: str = ""
    relation_type: str = "synonym"
    note: str = ""


class StructuredEtymology(BaseModel):
    components: list[EtymologyComponentItemCreate] = Field(default_factory=list)
    origin_word: str | None = None
    origin_language: str | None = None
    core_image: str | None = None
    branches: list[EtymologyBranchCreate] = Field(default_factory=list)
    language_chain: list[EtymologyLanguageChainLinkCreate] = Field(default_factory=list)
    component_meanings: list[EtymologyComponentMeaningCreate] = Field(default_factory=list)
    etymology_variants: list[EtymologyVariantCreate] = Field(default_factory=list)
    raw_description: str | None = None


class StructuredWordPayload(BaseModel):
    phonetic: str | None = None
    forms: dict = Field(default_factory=dict)
    phrases: list[PhraseCreate] = Field(default_factory=list)
    definitions: list[StructuredDefinition] = Field(default_factory=list)
    etymology: StructuredEtymology = Field(default_factory=StructuredEtymology)
    derivations: list[StructuredDerivation] = Field(default_factory=list)
    related_words: list[StructuredRelatedWord] = Field(default_factory=list)


class GroupBulkAddItemsRequest(BaseModel):
    word_ids: list[int] = Field(default_factory=list)
    phrase_ids: list[int] = Field(default_factory=list)


class GroupBulkAddItemsResponse(BaseModel):
    added: int = 0
    skipped: int = 0


class ListeningPersonaRead(BaseModel):
    voice: str
    name: str
    description: str
    gender: Literal["male", "female", "neutral"]

    model_config = {"from_attributes": True}


class ListeningPersonaSampleRead(BaseModel):
    voice: str
    audio_path: str


class ListeningSpeakerRead(BaseModel):
    id: int
    label: str
    voice: str
    sort_order: int = 0

    model_config = {"from_attributes": True}


class ListeningLineAudioRead(BaseModel):
    id: int
    voice: str
    audio_path: str
    is_primary: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class ListeningLineRead(BaseModel):
    id: int
    speaker_id: int
    speaker_label: str = ""
    sort_order: int = 0
    text: str
    translation_ja: str | None = None
    audio_variants: list[ListeningLineAudioRead] = Field(default_factory=list)

    model_config = {"from_attributes": True}


class ListeningScriptRead(BaseModel):
    id: int
    title: str
    topic: str | None = None
    level: str | None = None
    is_conversation: bool
    generation_mode: Literal["random", "custom", "weak_review"]
    source_type: Literal["ai_generated", "external_video"]
    source_url: str | None = None
    created_at: datetime
    updated_at: datetime
    speakers: list[ListeningSpeakerRead] = Field(default_factory=list)
    lines: list[ListeningLineRead] = Field(default_factory=list)

    model_config = {"from_attributes": True}


class ListeningRandomScriptRequest(BaseModel):
    topic: str | None = None
    level: str | None = None
    speaker_count: int = Field(default=1, ge=1, le=3)
    is_conversation: bool = False
    voices: list[str | None] | None = None


class ListeningParsedSpeaker(BaseModel):
    label: str
    gender: Literal["male", "female", "neutral"] = "neutral"


class ListeningParsedLine(BaseModel):
    speaker_label: str
    text: str
    translation_ja: str | None = None


class ListeningParsedScript(BaseModel):
    title: str = ""
    speakers: list[ListeningParsedSpeaker] = Field(default_factory=list)
    lines: list[ListeningParsedLine] = Field(default_factory=list)


class ListeningCustomScriptAnalyzeRequest(BaseModel):
    raw_text: str


class ListeningCustomScriptConfirmRequest(BaseModel):
    parsed: ListeningParsedScript
    voices: list[str | None] | None = None


class ListeningWeakReviewRequest(BaseModel):
    level: str | None = None
    speaker_count: int = Field(default=1, ge=1, le=4)
    is_conversation: bool = False
    voices: list[str | None] | None = None


class ListeningGenerateLineAudioRequest(BaseModel):
    voice: str | None = None


ListeningStep = Literal["listen", "dictation", "read_aloud", "overlapping", "shadowing"]


class ListeningSessionCreate(BaseModel):
    script_id: int


class ListeningSessionUpdate(BaseModel):
    current_step: ListeningStep | None = None
    playback_speed: float | None = Field(default=None, gt=0, le=3)
    dictation_level: int | None = Field(default=None, ge=0, le=3)
    status: Literal["in_progress", "completed"] | None = None


class ListeningSessionRead(BaseModel):
    id: int
    script_id: int
    script_title: str = ""
    current_step: ListeningStep
    playback_speed: float
    dictation_level: int
    status: Literal["in_progress", "completed"]
    created_at: datetime
    updated_at: datetime
    completed_at: datetime | None = None

    model_config = {"from_attributes": True}


class ListeningAttemptCreate(BaseModel):
    line_id: int
    dictation_level: int = Field(ge=0, le=3)
    user_text: str = ""


class ListeningWordResultRead(BaseModel):
    id: int
    word_text: str
    matched_word_id: int | None = None
    is_correct: bool

    model_config = {"from_attributes": True}


class ListeningAttemptRead(BaseModel):
    id: int
    session_id: int
    line_id: int
    dictation_level: int
    user_text: str
    is_correct: bool
    created_at: datetime
    word_results: list[ListeningWordResultRead] = Field(default_factory=list)

    model_config = {"from_attributes": True}


class ListeningReadAloudLineGradeRead(BaseModel):
    line_id: int
    is_correct: bool
    word_results: list[ListeningWordResultRead] = Field(default_factory=list)


class ListeningReadAloudGradeRead(BaseModel):
    score: int
    good_points: list[str] = Field(default_factory=list)
    review_points: list[str] = Field(default_factory=list)
    lines: list[ListeningReadAloudLineGradeRead] = Field(default_factory=list)


class WeakWordStat(BaseModel):
    word_text: str
    total: int
    wrong: int
    accuracy: float
    matched_word_id: int | None = None


class WeakPhraseStat(BaseModel):
    phrase_text: str
    count: int
    matched_phrase_id: int | None = None
