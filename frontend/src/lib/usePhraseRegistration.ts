import { useMemo } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";

import { phraseApi } from "./api";

/**
 * 未登録の熟語候補テキスト群に対して、登録状況の確認と新規登録を行う共通フック。
 * 熟語詳細ページの関連語（Wiktionary由来）と単語詳細ページの関連語（多語のためidiom候補になりうるもの）の
 * 両方から利用され、チェック/登録ロジックの重複実装を避ける。
 */
export function usePhraseRegistration(candidateTexts: string[]) {
  const navigate = useNavigate();
  const uniqueTexts = useMemo(
    () =>
      Array.from(
        new Set(candidateTexts.map((text) => text.trim()).filter((text) => text.length > 0)),
      ),
    [candidateTexts],
  );

  const phraseCheckQuery = useQuery({
    queryKey: ["phrase", "registration-check", uniqueTexts],
    queryFn: () => phraseApi.check(uniqueTexts),
    enabled: uniqueTexts.length > 0,
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

  const getPhraseId = (text: string) => phraseIdMap.get(text) ?? phraseIdMap.get(text.toLowerCase());
  const isRegistering = (text: string) =>
    registerPhraseMutation.isPending && registerPhraseMutation.variables === text;

  return {
    getPhraseId,
    registerPhrase: (text: string) => registerPhraseMutation.mutate(text),
    isRegistering,
    isMutating: registerPhraseMutation.isPending,
  };
}
