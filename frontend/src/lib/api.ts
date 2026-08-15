import axios, { AxiosError, type InternalAxiosRequestConfig } from "axios";
import type {
  ChatMessage,
  ChatReply,
  ChatSession,
  Definition,
  Derivation,
  EtymologyComponentCache,
  EtymologyComponentListResponse,
  EtymologyComponentSearchResponse,
  Etymology,
  GroupSuggestResponse,
  GroupBulkAddItemsResponse,
  GroupSearchResponse,
  GroupImage,
  InflectionAction,
  InflectionCheckResponse,
  ListeningAttempt,
  ListeningLine,
  ListeningLineAudio,
  ListeningParsedScript,
  ListeningPersona,
  ListeningPersonaSample,
  ListeningReadAloudGrade,
  ListeningScript,
  ListeningSession,
  ListeningSessionStatus,
  ListeningStep,
  MigrationInflectionApplyDecision,
  MigrationInflectionApplyResponse,
  MigrationInflectionTargetsResponse,
  PhraseImage,
  PhraseCheckResponse,
  Phrase,
  PhraseDefinition,
  WordSummary,
  RelatedWord,
  SearchSuggestItem,
  WeakPhraseStat,
  WeakWordStat,
  Word,
  WordCreateResponse,
  WordForms,
  WordImage,
  WordListResponse,
  WordCheckResponse,
  WordGroup,
  WordGroupItem,
  WordGroupListResponse,
  WordSortBy,
  SortOrder,
} from "../types";
import { SHARED_API_BASE_URL_DEFAULT } from "./sharedConfig";

const api = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL ?? SHARED_API_BASE_URL_DEFAULT,
});

const MAX_RETRY_COUNT = 3;
const RETRY_BASE_DELAY_MS = 300;
const CONNECTION_ERROR_EVENT = "api-connection-error";
const CONNECTION_RECOVERED_EVENT = "api-connection-recovered";
let hasActiveConnectionError = false;

interface RetryRequestConfig extends InternalAxiosRequestConfig {
  _retryCount?: number;
}

function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => window.setTimeout(resolve, ms));
}

function isIdempotentMethod(method?: string): boolean {
  const normalized = (method ?? "get").toLowerCase();
  return normalized === "get" || normalized === "head" || normalized === "options";
}

function isRetryableConnectionError(error: AxiosError): boolean {
  if (error.response) {
    return false;
  }
  // POST/PUT/DELETE 等は、サーバー側で処理が完了した後にレスポンスだけが
  // ネットワークエラーで失われるケースがあり、自動リトライすると同じ操作が
  // 二重に実行されてしまう（例: 単語の重複作成）。安全に再送できるのは
  // 副作用のない GET 系メソッドのみ。
  if (!isIdempotentMethod(error.config?.method)) {
    return false;
  }
  if (error.code === "ERR_NETWORK" || error.code === "ECONNABORTED") {
    return true;
  }
  return /network error/i.test(error.message ?? "");
}

function notifyConnectionError(): void {
  hasActiveConnectionError = true;
  window.dispatchEvent(
    new CustomEvent(CONNECTION_ERROR_EVENT, {
      detail: {
        message: "サーバーに接続できません。ネットワークまたはサーバー状態を確認してください。",
      },
    }),
  );
}

function notifyConnectionRecovered(): void {
  if (!hasActiveConnectionError) {
    return;
  }
  hasActiveConnectionError = false;
  window.dispatchEvent(new CustomEvent(CONNECTION_RECOVERED_EVENT));
}

api.interceptors.response.use(
  async (response) => {
    notifyConnectionRecovered();
    return response;
  },
  async (error: AxiosError) => {
    const config = error.config as RetryRequestConfig | undefined;
    if (!config || !isRetryableConnectionError(error)) {
      throw error;
    }
    const retryCount = config._retryCount ?? 0;
    if (retryCount >= MAX_RETRY_COUNT) {
      notifyConnectionError();
      throw error;
    }
    config._retryCount = retryCount + 1;
    const delayMs = RETRY_BASE_DELAY_MS * 2 ** retryCount;
    await sleep(delayMs);
    return api.request(config);
  },
);

export const wordApi = {
  async list(params?: {
    q?: string;
    page?: number;
    page_size?: number;
    sort_by?: WordSortBy;
    sort_order?: SortOrder;
  }) {
    const { data } = await api.get<WordListResponse>("/api/words", { params });
    return data;
  },
  async searchForGroup(params: {
    q: string;
    page_words?: number;
    page_phrases?: number;
    page_size?: number;
    sort_by?: WordSortBy;
    sort_order?: SortOrder;
  }) {
    const { data } = await api.get<GroupSearchResponse>("/api/words/search-for-group", { params });
    return data;
  },
  async suggest(q: string, limit = 10) {
    const { data } = await api.get<string[]>("/api/words/suggest", {
      params: { q, limit },
    });
    return data;
  },
  async searchByEtymologyComponent(text: string, params?: { page?: number; page_size?: number }) {
    const { data } = await api.get<EtymologyComponentSearchResponse>(
      "/api/words/by-etymology-component",
      {
        params: { text, page: params?.page ?? 1, page_size: params?.page_size ?? 50 },
      },
    );
    return data;
  },
  async get(wordId: number) {
    const { data } = await api.get<Word>(`/api/words/${wordId}`);
    return data;
  },
  async byIds(wordIds: number[]) {
    if (wordIds.length === 0) return [] as Word[];
    const { data } = await api.post<Word[]>("/api/words/by-ids", { word_ids: wordIds });
    return data;
  },
  async getByWord(word: string) {
    const { data } = await api.get<Word>(`/api/words/by-text/${encodeURIComponent(word)}`);
    return data;
  },
  async create(
    word: string,
    options?: {
      inflection_action?: InflectionAction | null;
      lemma_word?: string | null;
    },
  ) {
    const { data } = await api.post<WordCreateResponse>("/api/words", {
      word,
      inflection_action: options?.inflection_action ?? null,
      lemma_word: options?.lemma_word ?? null,
    });
    return data;
  },
  async bulkCreate(words: string[]) {
    const { data } = await api.post<Word[]>("/api/words/bulk", { words });
    return data;
  },
  async check(words: string[]) {
    const { data } = await api.post<WordCheckResponse>("/api/words/check", { words });
    return data;
  },
  async checkInflection(payload: { word?: string; words?: string[] }) {
    const { data } = await api.post<InflectionCheckResponse>(
      "/api/words/check-inflection",
      payload,
    );
    return data;
  },
  async rescrape(wordId: number) {
    const { data } = await api.post<Word>(`/api/words/${wordId}/rescrape`);
    return data;
  },
  async delete(wordId: number) {
    await api.delete(`/api/words/${wordId}`);
  },
  async updateDefinition(wordId: number, def: Definition) {
    const { data } = await api.put<Definition>(`/api/words/${wordId}/definitions/${def.id}`, def);
    return data;
  },
  async updateEtymology(wordId: number, etymology: Etymology) {
    const { data } = await api.put<Etymology>(`/api/words/${wordId}/etymology`, etymology);
    return data;
  },
  async updateFull(
    wordId: number,
    payload: {
      word?: string;
      phonetic?: string | null;
      forms?: WordForms;
      phrases?: Array<{
        text: string;
        meaning: string;
      }>;
      definitions: Array<{
        id?: number | null;
        part_of_speech: string;
        meaning_en: string;
        meaning_ja: string;
        examples: Array<{
          id?: number | null;
          example_en: string;
          example_ja: string;
          sort_order: number;
        }>;
        sort_order: number;
      }>;
      etymology?: Etymology | null;
      derivations: Array<{
        id?: number | null;
        derived_word: string;
        part_of_speech: string;
        meaning_ja: string;
        sort_order: number;
      }>;
      related_words: Array<{
        id?: number | null;
        related_word: string;
        relation_type: "synonym" | "confusable" | "cognate" | "antonym";
        note: string;
      }>;
    },
  ) {
    const { data } = await api.put<Word>(`/api/words/${wordId}/full`, payload);
    return data;
  },
  async createDerivation(wordId: number, payload: Omit<Derivation, "id">) {
    const { data } = await api.post<Derivation>(`/api/words/${wordId}/derivations`, payload);
    return data;
  },
  async updateDerivation(wordId: number, derivation: Derivation) {
    const { data } = await api.put<Derivation>(
      `/api/words/${wordId}/derivations/${derivation.id}`,
      derivation,
    );
    return data;
  },
  async deleteDerivation(wordId: number, derivationId: number) {
    await api.delete(`/api/words/${wordId}/derivations/${derivationId}`);
  },
  async createRelatedWord(wordId: number, payload: Omit<RelatedWord, "id" | "linked_word_id">) {
    const { data } = await api.post<RelatedWord>(`/api/words/${wordId}/related-words`, payload);
    return data;
  },
  async updateRelatedWord(wordId: number, relatedWord: RelatedWord) {
    const { data } = await api.put<RelatedWord>(
      `/api/words/${wordId}/related-words/${relatedWord.id}`,
      relatedWord,
    );
    return data;
  },
  async deleteRelatedWord(wordId: number, relatedWordId: number) {
    await api.delete(`/api/words/${wordId}/related-words/${relatedWordId}`);
  },
  async generateImage(wordId: number, prompt?: string) {
    const { data } = await api.post<WordImage>(`/api/words/${wordId}/generate-image`, {
      prompt: prompt ?? null,
    });
    return data;
  },
  async getDefaultImagePrompt(wordId: number) {
    const { data } = await api.get<{ prompt: string }>(`/api/words/${wordId}/default-image-prompt`);
    return data.prompt;
  },
  async generateAudio(wordId: number) {
    const { data } = await api.post<Word>(`/api/words/${wordId}/generate-audio`);
    return data;
  },
  async generateExampleAudio(wordId: number, exampleId: number) {
    const { data } = await api.post<Definition["examples"][number]>(
      `/api/words/${wordId}/examples/${exampleId}/generate-audio`,
    );
    return data;
  },
  async listPhrases(wordId: number) {
    const { data } = await api.get<Phrase[]>(`/api/words/${wordId}/phrases`);
    return data;
  },
  async addPhrase(wordId: number, payload: { text: string; meaning?: string }) {
    const { data } = await api.post<Phrase>(`/api/words/${wordId}/phrases`, payload);
    return data;
  },
  async removePhrase(wordId: number, phraseId: number) {
    await api.delete(`/api/words/${wordId}/phrases/${phraseId}`);
  },
};

export const chatApi = {
  async sessions(wordId: number) {
    const { data } = await api.get<ChatSession[]>(`/api/words/${wordId}/chat/sessions`);
    return data;
  },
  async createSession(wordId: number, title?: string) {
    const { data } = await api.post<ChatSession>(`/api/words/${wordId}/chat/sessions`, {
      title,
    });
    return data;
  },
  async messages(sessionId: number) {
    const { data } = await api.get<ChatMessage[]>(`/api/chat/sessions/${sessionId}/messages`);
    return data;
  },
  async sendMessage(sessionId: number, content: string) {
    const { data } = await api.post<ChatReply>(`/api/chat/sessions/${sessionId}/messages`, {
      content,
    });
    return data;
  },
  async updateSession(sessionId: number, title: string) {
    const { data } = await api.patch<ChatSession>(`/api/chat/sessions/${sessionId}`, {
      title,
    });
    return data;
  },
  async deleteSession(sessionId: number) {
    await api.delete(`/api/chat/sessions/${sessionId}`);
  },
};

export const componentChatApi = {
  async sessions(componentText: string) {
    const { data } = await api.get<ChatSession[]>(
      `/api/etymology-components/${encodeURIComponent(componentText)}/chat/sessions`,
    );
    return data;
  },
  async createSession(componentText: string, title?: string) {
    const { data } = await api.post<ChatSession>(
      `/api/etymology-components/${encodeURIComponent(componentText)}/chat/sessions`,
      { title },
    );
    return data;
  },
};

export const groupChatApi = {
  async sessions(groupId: number) {
    const { data } = await api.get<ChatSession[]>(`/api/groups/${groupId}/chat/sessions`);
    return data;
  },
  async createSession(groupId: number, title?: string) {
    const { data } = await api.post<ChatSession>(`/api/groups/${groupId}/chat/sessions`, { title });
    return data;
  },
};

export const phraseChatApi = {
  async sessions(phraseId: number) {
    const { data } = await api.get<ChatSession[]>(`/api/phrases/${phraseId}/chat/sessions`);
    return data;
  },
  async createSession(phraseId: number, title?: string) {
    const { data } = await api.post<ChatSession>(`/api/phrases/${phraseId}/chat/sessions`, {
      title,
    });
    return data;
  },
};

export const componentApi = {
  async list(params?: { q?: string; page?: number; page_size?: number }) {
    const { data } = await api.get<EtymologyComponentListResponse>("/api/etymology-components", {
      params: {
        q: params?.q,
        page: params?.page ?? 1,
        page_size: params?.page_size ?? 20,
      },
    });
    return data;
  },
  async create(componentText: string) {
    const { data } = await api.post<EtymologyComponentCache>(
      `/api/etymology-components/${encodeURIComponent(componentText)}`,
    );
    return data;
  },
  async get(componentText: string) {
    const { data } = await api.get<EtymologyComponentCache>(
      `/api/etymology-components/${encodeURIComponent(componentText)}`,
    );
    return data;
  },
  async rescrape(componentText: string) {
    const { data } = await api.post<EtymologyComponentCache>(
      `/api/etymology-components/${encodeURIComponent(componentText)}/rescrape`,
    );
    return data;
  },
};

export const groupApi = {
  async list(params?: { q?: string; page?: number; page_size?: number }) {
    const { data } = await api.get<WordGroupListResponse>("/api/groups", {
      params: {
        q: params?.q,
        page: params?.page ?? 1,
        page_size: params?.page_size ?? 20,
      },
    });
    return data;
  },
  async create(payload: { name: string; description?: string }) {
    const { data } = await api.post<WordGroup>("/api/groups", payload);
    return data;
  },
  async get(groupId: number) {
    const { data } = await api.get<WordGroup>(`/api/groups/${groupId}`);
    return data;
  },
  async update(groupId: number, payload: { name: string; description?: string }) {
    const { data } = await api.put<WordGroup>(`/api/groups/${groupId}`, payload);
    return data;
  },
  async delete(groupId: number) {
    await api.delete(`/api/groups/${groupId}`);
  },
  async addItem(
    groupId: number,
    payload: {
      item_type: "word" | "phrase" | "example";
      word_id?: number | null;
      definition_id?: number | null;
      phrase_id?: number | null;
      phrase_text?: string | null;
      phrase_meaning?: string | null;
      sort_order?: number;
    },
  ) {
    const { data } = await api.post<WordGroupItem>(`/api/groups/${groupId}/items`, payload);
    return data;
  },
  async removeItem(groupId: number, itemId: number) {
    await api.delete(`/api/groups/${groupId}/items/${itemId}`);
  },
  async bulkAddItems(groupId: number, payload: { word_ids?: number[]; phrase_ids?: number[] }) {
    const { data } = await api.post<GroupBulkAddItemsResponse>(
      `/api/groups/${groupId}/bulk-add-items`,
      payload,
    );
    return data;
  },
  async suggest(groupId: number, payload: { keywords: string[]; limit?: number }) {
    const { data } = await api.post<GroupSuggestResponse>(
      `/api/groups/${groupId}/suggest`,
      payload,
    );
    return data;
  },
  async generateImage(groupId: number, prompt?: string) {
    const { data } = await api.post<GroupImage>(`/api/groups/${groupId}/generate-image`, {
      prompt: prompt ?? null,
    });
    return data;
  },
  async getDefaultImagePrompt(groupId: number) {
    const { data } = await api.get<{ prompt: string }>(
      `/api/groups/${groupId}/default-image-prompt`,
    );
    return data.prompt;
  },
};

export const phraseApi = {
  async list(params?: {
    q?: string;
    sort_by?: "created_at" | "updated_at" | "text";
    sort_order?: "desc" | "asc";
    page?: number;
    page_size?: number;
  }) {
    const { data } = await api.get<Phrase[]>("/api/phrases", {
      params: {
        q: params?.q,
        sort_by: params?.sort_by ?? "updated_at",
        sort_order: params?.sort_order ?? "desc",
        page: params?.page ?? 1,
        page_size: params?.page_size ?? 50,
      },
    });
    return data;
  },
  async get(phraseId: number) {
    const { data } = await api.get<Phrase>(`/api/phrases/${phraseId}`);
    return data;
  },
  async create(payload: { text: string; meaning?: string }) {
    const { data } = await api.post<Phrase>("/api/phrases", payload);
    return data;
  },
  async check(texts: string[]) {
    const { data } = await api.post<PhraseCheckResponse>("/api/phrases/check", { texts });
    return data;
  },
  async update(phraseId: number, payload: { meaning: string }) {
    const { data } = await api.put<Phrase>(`/api/phrases/${phraseId}`, payload);
    return data;
  },
  async updateFull(
    phraseId: number,
    payload: {
      text: string;
      meaning: string;
      definitions: Array<{
        id?: number | null;
        part_of_speech: string;
        meaning_en: string;
        meaning_ja: string;
        example_en: string;
        example_ja: string;
        sort_order: number;
      }>;
      word_ids: number[];
      wiktionary_synonyms?: string[];
      wiktionary_antonyms?: string[];
      wiktionary_see_also?: string[];
      wiktionary_derived_terms?: string[];
      wiktionary_phrases?: string[];
    },
  ) {
    const { data } = await api.put<Phrase>(`/api/phrases/${phraseId}/full`, payload);
    return data;
  },
  async listWords(phraseId: number) {
    const { data } = await api.get<WordSummary[]>(`/api/phrases/${phraseId}/words`);
    return data;
  },
  async enrich(phraseId: number) {
    const { data } = await api.post<Phrase>(`/api/phrases/${phraseId}/enrich`);
    return data;
  },
  async generateImage(phraseId: number, prompt?: string) {
    const { data } = await api.post<PhraseImage>(`/api/phrases/${phraseId}/generate-image`, {
      prompt: prompt ?? null,
    });
    return data;
  },
  async getDefaultImagePrompt(phraseId: number) {
    const { data } = await api.get<{ prompt: string }>(
      `/api/phrases/${phraseId}/default-image-prompt`,
    );
    return data.prompt;
  },
  async generateAudio(phraseId: number) {
    const { data } = await api.post<Phrase>(`/api/phrases/${phraseId}/generate-audio`);
    return data;
  },
  async generateDefinitionAudio(phraseId: number, definitionId: number) {
    const { data } = await api.post<PhraseDefinition>(
      `/api/phrases/${phraseId}/definitions/${definitionId}/generate-audio`,
    );
    return data;
  },
  async delete(phraseId: number) {
    await api.delete(`/api/phrases/${phraseId}`);
  },
};

export const searchApi = {
  async suggest(q: string, limit = 10) {
    const { data } = await api.get<SearchSuggestItem[]>("/api/search/suggest", {
      params: { q, limit },
    });
    return data;
  },
};

export const listeningApi = {
  async getPersonas() {
    const { data } = await api.get<ListeningPersona[]>("/api/listening/personas");
    return data;
  },
  async getPersonaSample(voice: string) {
    const { data } = await api.get<ListeningPersonaSample>(`/api/listening/personas/${voice}/sample`);
    return data;
  },
  async generateRandomScript(payload?: {
    topic?: string;
    level?: string;
    speaker_count?: number;
    is_conversation?: boolean;
    voices?: (string | null)[];
  }) {
    const { data } = await api.post<ListeningScript>("/api/listening/scripts/random", payload ?? {});
    return data;
  },
  async analyzeCustomScript(rawText: string) {
    const { data } = await api.post<ListeningParsedScript>("/api/listening/scripts/custom/analyze", {
      raw_text: rawText,
    });
    return data;
  },
  async confirmCustomScript(parsed: ListeningParsedScript, voices?: (string | null)[]) {
    const { data } = await api.post<ListeningScript>("/api/listening/scripts/custom/confirm", {
      parsed,
      voices: voices ?? null,
    });
    return data;
  },
  async generateWeakReviewScript(payload?: {
    level?: string;
    speaker_count?: number;
    is_conversation?: boolean;
    voices?: (string | null)[];
  }) {
    const { data } = await api.post<ListeningScript>("/api/listening/scripts/weak-review", payload ?? {});
    return data;
  },
  async getScript(scriptId: number) {
    const { data } = await api.get<ListeningScript>(`/api/listening/scripts/${scriptId}`);
    return data;
  },
  async generateLineAudio(lineId: number, voice?: string) {
    const { data } = await api.post<ListeningLine>(`/api/listening/lines/${lineId}/generate-audio`, {
      voice: voice ?? null,
    });
    return data;
  },
  async getLineAudioVariants(lineId: number) {
    const { data } = await api.get<ListeningLineAudio[]>(`/api/listening/lines/${lineId}/audio-variants`);
    return data;
  },
  async gradeReadAloud(sessionId: number, audioBlob: Blob) {
    const formData = new FormData();
    formData.append("audio", audioBlob, "recording.webm");
    const { data } = await api.post<ListeningReadAloudGrade>(
      `/api/listening/sessions/${sessionId}/read-aloud-grade`,
      formData,
      { headers: { "Content-Type": "multipart/form-data" } },
    );
    return data;
  },
  async createSession(scriptId: number) {
    const { data } = await api.post<ListeningSession>("/api/listening/sessions", {
      script_id: scriptId,
    });
    return data;
  },
  async getSession(sessionId: number) {
    const { data } = await api.get<ListeningSession>(`/api/listening/sessions/${sessionId}`);
    return data;
  },
  async updateSession(
    sessionId: number,
    payload: Partial<{
      current_step: ListeningStep;
      playback_speed: number;
      dictation_level: number;
      status: ListeningSessionStatus;
    }>,
  ) {
    const { data } = await api.patch<ListeningSession>(`/api/listening/sessions/${sessionId}`, payload);
    return data;
  },
  async recordAttempt(
    sessionId: number,
    payload: { line_id: number; dictation_level: number; user_text: string },
  ) {
    const { data } = await api.post<ListeningAttempt>(
      `/api/listening/sessions/${sessionId}/attempts`,
      payload,
    );
    return data;
  },
  async listSessions(status?: ListeningSessionStatus) {
    const { data } = await api.get<ListeningSession[]>("/api/listening/sessions", {
      params: { status },
    });
    return data;
  },
  async deleteSession(sessionId: number) {
    await api.delete(`/api/listening/sessions/${sessionId}`);
  },
  async getWeakWords(limit = 50) {
    const { data } = await api.get<WeakWordStat[]>("/api/listening/analytics/weak-words", {
      params: { limit },
    });
    return data;
  },
  async getWeakPhrases(limit = 50) {
    const { data } = await api.get<WeakPhraseStat[]>("/api/listening/analytics/weak-phrases", {
      params: { limit },
    });
    return data;
  },
};

export const migrationApi = {
  async listInflectionTargets(params?: { page?: number; page_size?: number }) {
    const { data } = await api.get<MigrationInflectionTargetsResponse>(
      "/api/migration/inflection/targets",
      {
        params: {
          page: params?.page ?? 1,
          page_size: params?.page_size ?? 100,
        },
      },
    );
    return data;
  },
  async applyInflection(decisions: MigrationInflectionApplyDecision[]) {
    const { data } = await api.post<MigrationInflectionApplyResponse>(
      "/api/migration/inflection/apply",
      { decisions },
    );
    return data;
  },
};

export default api;
