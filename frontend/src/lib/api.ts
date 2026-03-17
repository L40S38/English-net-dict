import axios from "axios";
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
  GroupImage,
  RelatedWord,
  Word,
  WordForms,
  WordImage,
  WordListResponse,
  WordGroup,
  WordGroupItem,
  WordGroupListResponse,
  WordSortBy,
  SortOrder,
} from "../types";

const api = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000",
});

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
  async getByWord(word: string) {
    const { data } = await api.get<Word>(`/api/words/by-text/${encodeURIComponent(word)}`);
    return data;
  },
  async create(word: string) {
    const { data } = await api.post<Word[]>("/api/words", { word });
    return data;
  },
  async bulkCreate(words: string[]) {
    const { data } = await api.post<Word[]>("/api/words/bulk", { words });
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
      definitions: Array<{
        id?: number | null;
        part_of_speech: string;
        meaning_en: string;
        meaning_ja: string;
        example_en: string;
        example_ja: string;
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
  async suggest(groupId: number, payload: { keywords: string[]; limit?: number }) {
    const { data } = await api.post<GroupSuggestResponse>(`/api/groups/${groupId}/suggest`, payload);
    return data;
  },
  async generateImage(groupId: number, prompt?: string) {
    const { data } = await api.post<GroupImage>(`/api/groups/${groupId}/generate-image`, {
      prompt: prompt ?? null,
    });
    return data;
  },
  async getDefaultImagePrompt(groupId: number) {
    const { data } = await api.get<{ prompt: string }>(`/api/groups/${groupId}/default-image-prompt`);
    return data.prompt;
  },
};

export default api;
