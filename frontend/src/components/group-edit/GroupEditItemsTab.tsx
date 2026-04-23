import { Card, Muted, Row, Stack } from "../atom";
import type { WordGroup, WordGroupItem } from "../../types";

interface GroupEditItemsTabProps {
  group: WordGroup;
  isRemoving: boolean;
  onRemove: (item: WordGroupItem) => void;
}

export function GroupEditItemsTab({ group, isRemoving, onRemove }: GroupEditItemsTabProps) {
  return (
    <Card stack>
      <h3>登録済みアイテム（削除）</h3>
      {group.items.length === 0 && <Muted as="p">まだ追加されていません。</Muted>}
      {group.items.map((item) => (
        <Card key={item.id} variant="sub" stack>
          {item.item_type === "word" && (
            <Row>
              <strong>単語</strong>
              <span>{item.word}</span>
            </Row>
          )}
          {item.item_type === "phrase" && (
            <Stack gap="sm">
              <Row>
                <strong>熟語</strong>
                <Muted as="span">{item.phrase_text}</Muted>
              </Row>
              {item.phrase_meaning && <Muted as="p">意味: {item.phrase_meaning}</Muted>}
            </Stack>
          )}
          {item.item_type === "example" && (
            <Stack gap="sm">
              <strong>例文</strong>
              {item.word && (
                <p>
                  <strong>{item.word}</strong>
                  {item.definition_part_of_speech && (
                    <Muted as="span"> [{item.definition_part_of_speech}]</Muted>
                  )}
                  {item.definition_meaning_ja && (
                    <Muted as="span"> {item.definition_meaning_ja}</Muted>
                  )}
                </p>
              )}
              <Muted as="p">{item.example_en}</Muted>
              {item.example_ja && <Muted as="p">{item.example_ja}</Muted>}
            </Stack>
          )}
          <Row>
            <button
              type="button"
              className="button-delete"
              onClick={() => onRemove(item)}
              disabled={isRemoving}
            >
              削除
            </button>
          </Row>
        </Card>
      ))}
    </Card>
  );
}
