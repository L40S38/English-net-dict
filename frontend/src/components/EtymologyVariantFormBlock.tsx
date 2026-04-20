import { Plus, Trash2 } from "lucide-react";
import { Card, Field } from "./atom";
import { ComponentFormBlock } from "./ComponentFormBlock";
import { ComponentMeaningFormBlock } from "./ComponentMeaningFormBlock";
import { LanguageChainFormBlock } from "./LanguageChainFormBlock";
import type {
  ComponentMeaningItem,
  EtymologyComponent,
  EtymologyVariant,
  LanguageChainLink,
} from "../types";

interface EtymologyVariantFormBlockProps {
  variant: EtymologyVariant;
  index: number;
  onUpdate: (index: number, next: EtymologyVariant) => void;
  onRemove: (index: number) => void;
}

function toComponents(input?: EtymologyComponent[]): EtymologyComponent[] {
  return input ?? [];
}

function toComponentMeanings(input?: ComponentMeaningItem[]): ComponentMeaningItem[] {
  return input ?? [];
}

function toLanguageChain(input?: LanguageChainLink[]): LanguageChainLink[] {
  return input ?? [];
}

export function EtymologyVariantFormBlock({
  variant,
  index,
  onUpdate,
  onRemove,
}: EtymologyVariantFormBlockProps) {
  const components = toComponents(variant.components);
  const componentMeanings = toComponentMeanings(variant.component_meanings);
  const languageChain = toLanguageChain(variant.language_chain);

  return (
    <Card variant="sub" stack>
      <div className="inline-form-row">
        <Field label="ラベル" className="field-grow">
          <input
            value={variant.label ?? ""}
            onChange={(e) => onUpdate(index, { ...variant, label: e.target.value || undefined })}
            placeholder="例: Etymology 1"
          />
        </Field>
        <button
          type="button"
          className="icon-button-delete"
          onClick={() => onRemove(index)}
          aria-label="語源バリエーションを削除"
        >
          <Trash2 size={16} />
        </button>
      </div>
      <Field label="抜粋">
        <textarea
          rows={3}
          value={variant.excerpt ?? ""}
          onChange={(e) => onUpdate(index, { ...variant, excerpt: e.target.value || undefined })}
          placeholder="語源の別説や補足"
        />
      </Field>

      <h4>語源分解</h4>
      {components.map((component, componentIndex) => (
        <ComponentFormBlock
          key={`${index}-component-${componentIndex}`}
          component={component}
          index={componentIndex}
          onUpdate={(targetIndex, next) =>
            onUpdate(index, {
              ...variant,
              components: components.map((item, i) => (i === targetIndex ? next : item)),
            })
          }
          onRemove={(targetIndex) =>
            onUpdate(index, {
              ...variant,
              components: components.filter((_, i) => i !== targetIndex),
            })
          }
        />
      ))}
      <button
        type="button"
        className="icon-button-add"
        aria-label="語源分解を追加"
        onClick={() =>
          onUpdate(index, {
            ...variant,
            components: [...components, { text: "", meaning: "", type: "root" }],
          })
        }
      >
        <Plus size={18} />
      </button>

      <h4>語源要素の意味</h4>
      {componentMeanings.map((item, itemIndex) => (
        <ComponentMeaningFormBlock
          key={`${index}-component-meaning-${itemIndex}`}
          item={item}
          index={itemIndex}
          onUpdate={(targetIndex, next) =>
            onUpdate(index, {
              ...variant,
              component_meanings: componentMeanings.map((entry, i) =>
                i === targetIndex ? next : entry,
              ),
            })
          }
          onRemove={(targetIndex) =>
            onUpdate(index, {
              ...variant,
              component_meanings: componentMeanings.filter((_, i) => i !== targetIndex),
            })
          }
        />
      ))}
      <button
        type="button"
        className="icon-button-add"
        aria-label="語源要素の意味を追加"
        onClick={() =>
          onUpdate(index, {
            ...variant,
            component_meanings: [...componentMeanings, { text: "", meaning: "" }],
          })
        }
      >
        <Plus size={18} />
      </button>

      <h4>語源の来歴</h4>
      {languageChain.map((link, linkIndex) => (
        <LanguageChainFormBlock
          key={`${index}-language-chain-${linkIndex}`}
          link={link}
          index={linkIndex}
          onUpdate={(targetIndex, next) =>
            onUpdate(index, {
              ...variant,
              language_chain: languageChain.map((entry, i) => (i === targetIndex ? next : entry)),
            })
          }
          onRemove={(targetIndex) =>
            onUpdate(index, {
              ...variant,
              language_chain: languageChain.filter((_, i) => i !== targetIndex),
            })
          }
        />
      ))}
      <button
        type="button"
        className="icon-button-add"
        aria-label="語源の来歴を追加"
        onClick={() =>
          onUpdate(index, {
            ...variant,
            language_chain: [...languageChain, { lang: "", lang_name: "", word: "", relation: "" }],
          })
        }
      >
        <Plus size={18} />
      </button>
    </Card>
  );
}
