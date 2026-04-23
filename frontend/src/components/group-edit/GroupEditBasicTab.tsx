import { Card, Field, Row } from "../atom";

interface GroupEditBasicTabProps {
  currentNameDraft: string;
  currentDescriptionDraft: string;
  onChangeName: (value: string) => void;
  onChangeDescription: (value: string) => void;
  onSave: () => void;
  isSaving: boolean;
  saveDisabled: boolean;
  nameLengthHint: string;
}

export function GroupEditBasicTab({
  currentNameDraft,
  currentDescriptionDraft,
  onChangeName,
  onChangeDescription,
  onSave,
  isSaving,
  saveDisabled,
  nameLengthHint,
}: GroupEditBasicTabProps) {
  return (
    <Card stack>
      <h3>グループ名/説明</h3>
      <Field label="名前">
        <input value={currentNameDraft} onChange={(event) => onChangeName(event.target.value)} />
      </Field>
      <p>{nameLengthHint}</p>
      <Field label="説明">
        <textarea
          rows={3}
          value={currentDescriptionDraft}
          onChange={(event) => onChangeDescription(event.target.value)}
        />
      </Field>
      <Row>
        <button type="button" onClick={onSave} disabled={saveDisabled}>
          {isSaving ? "保存中..." : "保存"}
        </button>
      </Row>
    </Card>
  );
}
