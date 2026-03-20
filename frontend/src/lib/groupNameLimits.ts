import { GROUP_NAME_MAX_LENGTH } from "./constants";

export function groupNameTooLong(name: string): boolean {
  return name.trim().length > GROUP_NAME_MAX_LENGTH;
}

export function groupNameLengthErrorMessage(): string {
  return `グループ名は${GROUP_NAME_MAX_LENGTH}文字以内で入力してください。`;
}
