import fs from "node:fs";
import path from "node:path";
import type { Plugin } from "vite";

interface SharedConfig {
  group_name_max_length?: number;
  api_base_url_default?: string;
}

function parseSharedConfigYaml(raw: string): SharedConfig {
  const result: SharedConfig = {};
  for (const line of raw.split(/\r?\n/)) {
    const trimmed = line.trim();
    if (!trimmed || trimmed.startsWith("#")) {
      continue;
    }
    const separator = trimmed.indexOf(":");
    if (separator <= 0) {
      continue;
    }
    const key = trimmed.slice(0, separator).trim();
    let value = trimmed.slice(separator + 1).trim();
    if (value.startsWith('"') && value.endsWith('"')) {
      value = value.slice(1, -1);
    }
    if (key === "group_name_max_length") {
      const numeric = Number(value);
      if (Number.isFinite(numeric)) {
        result.group_name_max_length = numeric;
      }
    }
    if (key === "api_base_url_default") {
      result.api_base_url_default = value;
    }
  }
  return result;
}

export function sharedConfigPlugin(): Plugin {
  const configPath = path.resolve(__dirname, "..", "config.yaml");
  const raw = fs.existsSync(configPath) ? fs.readFileSync(configPath, "utf-8") : "";
  const parsed = parseSharedConfigYaml(raw);
  const groupNameMaxLength = Number(parsed.group_name_max_length ?? 50);
  const apiBaseUrlDefault = String(parsed.api_base_url_default ?? "http://localhost:8000");

  return {
    name: "shared-config-plugin",
    config() {
      return {
        define: {
          __SHARED_GROUP_NAME_MAX_LENGTH__: JSON.stringify(groupNameMaxLength),
          __SHARED_API_BASE_URL_DEFAULT__: JSON.stringify(apiBaseUrlDefault),
        },
      };
    },
  };
}
