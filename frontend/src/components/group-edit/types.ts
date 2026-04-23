export interface GroupCandidateSelectionPayload {
  word_ids: number[];
  phrase_ids: number[];
  examples: Array<{ word_id: number; definition_id: number }>;
}
