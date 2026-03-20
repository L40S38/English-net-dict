from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from app.constants import GROUP_NAME_MAX_LENGTH


class DefinitionBase(BaseModel):
    part_of_speech: str
    meaning_en: str
    meaning_ja: str
    example_en: str
    example_ja: str
    sort_order: int = 0


class DefinitionCreate(DefinitionBase):
    pass


class DefinitionUpdate(DefinitionBase):
    pass


class DefinitionRead(DefinitionBase):
    id: int

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


class BulkWordRequest(BaseModel):
    words: list[str]


class WordCheckFound(BaseModel):
    id: int
    word: str


class WordCheckResponse(BaseModel):
    found: list[WordCheckFound] = Field(default_factory=list)
    not_found: list[str] = Field(default_factory=list)


class PhraseBase(BaseModel):
    text: str
    meaning: str = ""


class PhraseCreate(PhraseBase):
    pass


class PhraseUpdate(BaseModel):
    meaning: str = ""


class PhraseRead(PhraseBase):
    id: int
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class WordRead(BaseModel):
    id: int
    word: str
    phonetic: str | None = None
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

    model_config = {"from_attributes": True}


class WordListResponse(BaseModel):
    items: list[WordRead]
    total: int


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
    example_en: str = ""
    example_ja: str = ""
    sort_order: int = 0


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


class GroupBulkAddItemsResponse(BaseModel):
    added: int = 0
    skipped: int = 0
