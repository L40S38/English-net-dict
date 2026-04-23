import { useMemo } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { Link, useNavigate } from "react-router-dom";

import { Card, Muted, Stack } from "./atom";
import { WordLinkRow } from "./WordLinkRow";
import { phraseApi } from "../lib/api";
import { EMPTY_MESSAGES } from "../lib/constants";
import type { Phrase } from "../types";

interface PhraseWiktionaryRelationsProps {
  phrase: Phrase;
}

const SECTIONS: { label: string; items: (phrase: Phrase) => string[] }[] = [
  { label: "類義語", items: (p) => p.wiktionary_synonyms ?? [] },
  { label: "対義語", items: (p) => p.wiktionary_antonyms ?? [] },
  { label: "参照", items: (p) => p.wiktionary_see_also ?? [] },
  { label: "派生語", items: (p) => p.wiktionary_derived_terms ?? [] },
  { label: "成句・慣用句", items: (p) => p.wiktionary_phrases ?? [] },
];

export function PhraseWiktionaryRelations({ phrase }: PhraseWiktionaryRelationsProps) {
  const navigate = useNavigate();
  const groups = useMemo(
    () =>
      SECTIONS.map((section) => ({
        label: section.label,
        items: section.items(phrase),
      })),
    [phrase],
  );
  const relationTexts = useMemo(
    () =>
      Array.from(
        new Set(
          groups
            .flatMap((group) => group.items)
            .map((text) => text.trim())
            .filter((text) => text.length > 0),
        ),
      ),
    [groups],
  );
  const phraseCheckQuery = useQuery({
    queryKey: ["phrase", "relations", "check", relationTexts],
    queryFn: () => phraseApi.check(relationTexts),
    enabled: relationTexts.length > 0,
  });
  const phraseIdMap = useMemo(() => {
    const map = new Map<string, number>();
    for (const found of phraseCheckQuery.data?.found ?? []) {
      map.set(found.text, found.id);
      map.set(found.text.toLowerCase(), found.id);
    }
    return map;
  }, [phraseCheckQuery.data?.found]);
  const registerPhraseMutation = useMutation({
    mutationFn: (text: string) => phraseApi.create({ text }),
    onSuccess: (createdPhrase) => {
      navigate(`/phrases/${createdPhrase.id}`);
    },
  });

  return (
    <Card>
      <h3>関連語</h3>
      <Stack>
        {groups.map((group) => (
          <Card key={group.label} variant="sub" stack>
            <strong>{group.label}</strong>
            {group.items.length === 0 && <Muted as="p">{EMPTY_MESSAGES.noData}</Muted>}
            {group.items.map((text, idx) => (
              <Card key={`${group.label}-${idx}-${text}`} variant="sub" stack>
                <WordLinkRow
                  value={text}
                  linkedWordId={null}
                  trailing={
                    (() => {
                      const phraseId = phraseIdMap.get(text) ?? phraseIdMap.get(text.toLowerCase());
                      if (!phraseId) {
                        const pending = registerPhraseMutation.isPending && registerPhraseMutation.variables === text;
                        return (
                          <button
                            type="button"
                            className="detail-link-button"
                            onClick={() => registerPhraseMutation.mutate(text)}
                            disabled={registerPhraseMutation.isPending}
                          >
                            {pending ? "登録中..." : "登録"}
                          </button>
                        );
                      }
                      return (
                        <Link className="detail-link-button" to={`/phrases/${phraseId}`}>
                          詳細
                        </Link>
                      );
                    })()
                  }
                />
              </Card>
            ))}
          </Card>
        ))}
      </Stack>
    </Card>
  );
}
