import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";

import { Card, Muted, Row, Stack } from "../atom";
import { listeningApi } from "../../lib/api";

export function WeakWordsPanel() {
  const { data, isLoading } = useQuery({
    queryKey: ["listening-weak-words"],
    queryFn: () => listeningApi.getWeakWords(20),
  });

  return (
    <Card stack>
      <h3>苦手な単語</h3>
      {isLoading && <Muted as="p">読み込み中…</Muted>}
      {!isLoading && (data?.length ?? 0) === 0 && <Muted as="p">まだディクテーションの履歴がありません。</Muted>}
      <Stack>
        {data?.map((stat) => (
          <Row key={stat.word_text} justify="between">
            <Link to={`/words/${encodeURIComponent(stat.word_text)}`}>{stat.word_text}</Link>
            <Muted>
              正答率 {Math.round(stat.accuracy * 100)}% ({stat.total - stat.wrong}/{stat.total})
            </Muted>
          </Row>
        ))}
      </Stack>
    </Card>
  );
}
