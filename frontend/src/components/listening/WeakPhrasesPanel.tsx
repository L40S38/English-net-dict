import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";

import { Card, Muted, Row, Stack } from "../atom";
import { listeningApi } from "../../lib/api";

export function WeakPhrasesPanel() {
  const { data, isLoading } = useQuery({
    queryKey: ["listening-weak-phrases"],
    queryFn: () => listeningApi.getWeakPhrases(20),
  });

  return (
    <Card stack>
      <h3>苦手な熟語</h3>
      {isLoading && <Muted as="p">読み込み中…</Muted>}
      {!isLoading && (data?.length ?? 0) === 0 && <Muted as="p">まだ音読の履歴がありません。</Muted>}
      <Stack>
        {data?.map((stat) => (
          <Row key={stat.phrase_text} justify="between">
            {stat.matched_phrase_id ? (
              <Link to={`/phrases/${stat.matched_phrase_id}`}>{stat.phrase_text}</Link>
            ) : (
              <span>{stat.phrase_text}</span>
            )}
            <Muted>{stat.count}回</Muted>
          </Row>
        ))}
      </Stack>
    </Card>
  );
}
