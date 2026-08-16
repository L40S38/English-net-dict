interface RadioButtonOption<T extends string> {
  value: T;
  label: string;
  description?: string;
}

interface RadioButtonGroupProps<T extends string> {
  name: string;
  options: ReadonlyArray<RadioButtonOption<T>>;
  value: T;
  onChange: (value: T) => void;
}

export function RadioButtonGroup<T extends string>({
  name,
  options,
  value,
  onChange,
}: RadioButtonGroupProps<T>) {
  return (
    <div className="radio-button-group" role="radiogroup">
      {options.map((option) => (
        <label
          key={option.value}
          className={`radio-button-option${value === option.value ? " selected" : ""}`}
        >
          <input
            type="radio"
            name={name}
            value={option.value}
            checked={value === option.value}
            onChange={() => onChange(option.value)}
          />
          <span className="radio-button-label">{option.label}</span>
          {option.description && <span className="radio-button-description">{option.description}</span>}
        </label>
      ))}
    </div>
  );
}
