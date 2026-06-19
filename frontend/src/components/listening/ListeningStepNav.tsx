import { Tabs } from "../common/Tabs";
import type { ListeningStep } from "../../types";

const STEP_ITEMS: Array<{ key: ListeningStep; label: string }> = [
  { key: "listen", label: "① 聞く" },
  { key: "dictation", label: "② ディクテーション" },
  { key: "read_aloud", label: "③ 音読" },
  { key: "overlapping", label: "④ 追っかけ" },
  { key: "shadowing", label: "⑤ シャドーイング" },
];

interface ListeningStepNavProps {
  currentStep: ListeningStep;
  onChange: (step: ListeningStep) => void;
}

export function ListeningStepNav({ currentStep, onChange }: ListeningStepNavProps) {
  return <Tabs items={STEP_ITEMS} activeKey={currentStep} onChange={onChange} />;
}
