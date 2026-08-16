// ディクテーションの穴あけ優先順位:
// 1. 機能語(冠詞・前置詞・助動詞・代名詞・接続語) - 弱く読まれ聞き取りにくい
// 2. 連結・脱落が起きやすい句動詞/コロケーション(2語セットで穴あけ)
// 3. 語尾(-s/-ed/-ing/比較級など) - 語幹は聞こえても語尾を落としやすい
// 4. TOEIC頻出の内容語 - 意味からの予測力も鍛える
// 5. (Part2の応答キーワードは自由生成スクリプトには直接適用しないため対象外)

type BlankCategory = "function" | "phrasal" | "inflection" | "content" | "other";

const CATEGORY_PRIORITY: Record<BlankCategory, number> = {
  function: 1,
  phrasal: 2,
  inflection: 3,
  content: 4,
  other: 5,
};

const FUNCTION_WORDS = new Set([
  "a", "an", "the",
  "in", "on", "at", "for", "with", "by", "to", "of", "from", "about", "into", "onto",
  "over", "under", "between", "among", "through", "during", "before", "after", "since",
  "until", "without", "within",
  "can", "could", "should", "would", "will", "shall", "must", "may", "might",
  "is", "are", "was", "were", "be", "been", "being", "do", "does", "did", "have", "has", "had",
  "it", "they", "them", "one", "he", "she", "we", "you", "i", "him", "his", "her", "its",
  "their", "our", "your", "my",
  "and", "but", "or", "so", "because", "although", "while", "if", "that", "than",
]);

const PHRASAL_VERBS: ReadonlyArray<readonly [string, string]> = [
  ["turn", "in"], ["call", "up"], ["put", "on"], ["fill", "out"], ["pick", "up"],
  ["set", "up"], ["go", "over"], ["take", "care"], ["find", "out"], ["check", "in"],
  ["come", "up"], ["look", "for"], ["give", "up"], ["work", "out"], ["point", "out"],
  ["carry", "out"], ["deal", "with"], ["get", "up"], ["sign", "up"], ["follow", "up"],
  ["look", "into"], ["hand", "in"], ["drop", "off"], ["pick", "out"], ["catch", "up"],
];

const TOEIC_VOCAB = new Set([
  "attest", "expedite", "feasible", "waive", "refurbish", "versatile", "streamline",
  "comply", "allocate", "negotiate", "endorse", "reimburse", "facilitate", "implement",
  "designate", "consolidate", "prioritize", "anticipate", "deteriorate", "substantial",
  "subsequent", "preliminary", "comprehensive", "discrepancy", "itinerary", "logistics",
  "procurement", "warranty", "invoice", "renovation", "inventory", "shipment", "vendor",
  "complimentary", "proficient", "punctual", "meticulous", "lucrative", "viable",
]);

const INFLECTION_SUFFIX_RE = /(ing|ed|er|es|s)$/i;

interface BlankUnit {
  indices: number[];
  priority: number;
}

function classifyWords(words: string[]): BlankUnit[] {
  const claimed = new Set<number>();
  const units: BlankUnit[] = [];

  // 句動詞/コロケーションは隣接2語を1セットとして先に拾う
  for (let i = 0; i < words.length - 1; i += 1) {
    if (claimed.has(i) || claimed.has(i + 1)) continue;
    const a = words[i].toLowerCase();
    const b = words[i + 1].toLowerCase();
    if (PHRASAL_VERBS.some(([x, y]) => x === a && y === b)) {
      claimed.add(i);
      claimed.add(i + 1);
      units.push({ indices: [i, i + 1], priority: CATEGORY_PRIORITY.phrasal });
    }
  }

  for (let i = 0; i < words.length; i += 1) {
    if (claimed.has(i)) continue;
    const lower = words[i].toLowerCase();
    if (FUNCTION_WORDS.has(lower)) {
      units.push({ indices: [i], priority: CATEGORY_PRIORITY.function });
      continue;
    }
    if (lower.length >= 5 && INFLECTION_SUFFIX_RE.test(lower)) {
      units.push({ indices: [i], priority: CATEGORY_PRIORITY.inflection });
      continue;
    }
    if (TOEIC_VOCAB.has(lower) || lower.length >= 7) {
      units.push({ indices: [i], priority: CATEGORY_PRIORITY.content });
      continue;
    }
    units.push({ indices: [i], priority: CATEGORY_PRIORITY.other });
  }

  return units;
}

/** `count` 個を `total` 個の中からできるだけ均等な間隔で選ぶ(インデックス配列を返す)。 */
function evenlySpacedIndices(total: number, count: number): number[] {
  if (count >= total) {
    return Array.from({ length: total }, (_, i) => i);
  }
  if (count <= 0) {
    return [];
  }
  const step = total / count;
  return Array.from({ length: count }, (_, i) => Math.floor(i * step));
}

// 機能語だけで予算を使い切ると句動詞・語尾・内容語の練習機会が消えてしまうため、
// 最後のtierでない限り1カテゴリが目標数の中で占めてよい上限割合を設ける。
const MAX_SINGLE_TIER_SHARE = 0.6;

/**
 * 優先度(機能語→句動詞→語尾→内容語→その他)順に、目標割合に達するまで
 * ブランク対象の単語インデックスを選ぶ。句動詞は2語セットで選ばれる。
 * 同じ優先度内では文の先頭に偏らないよう均等な間隔で選び、上位優先度の
 * カテゴリが候補豊富でも予算を独占しないようtierごとに上限をかける。
 * 入力が同じなら常に同じ結果を返す(ランダム性なし)。
 */
export function selectBlankWordIndices(words: string[], ratio: number): Set<number> {
  if (words.length === 0 || ratio <= 0) {
    return new Set();
  }
  const targetCount = Math.min(words.length, Math.max(1, Math.round(words.length * ratio)));

  const tierMap = new Map<number, number[][]>();
  for (const unit of classifyWords(words)) {
    const list = tierMap.get(unit.priority);
    if (list) {
      list.push(unit.indices);
    } else {
      tierMap.set(unit.priority, [unit.indices]);
    }
  }
  const priorities = Array.from(tierMap.keys()).sort((a, b) => a - b);

  const selected = new Set<number>();
  priorities.forEach((priority, tierPosition) => {
    if (selected.size >= targetCount) {
      return;
    }
    const groups = tierMap.get(priority)!;
    const remaining = targetCount - selected.size;
    const isLastTier = tierPosition === priorities.length - 1;
    const tierBudget = isLastTier
      ? remaining
      : Math.min(remaining, Math.max(1, Math.round(targetCount * MAX_SINGLE_TIER_SHARE)));

    let groupsToTake = 1;
    while (groupsToTake < groups.length) {
      const probeWordCount = evenlySpacedIndices(groups.length, groupsToTake).reduce(
        (sum, gi) => sum + groups[gi].length,
        0,
      );
      if (probeWordCount >= tierBudget) break;
      groupsToTake += 1;
    }

    for (const groupIndex of evenlySpacedIndices(groups.length, groupsToTake)) {
      if (selected.size >= targetCount) break;
      for (const wordIndex of groups[groupIndex]) {
        selected.add(wordIndex);
      }
    }
  });
  return selected;
}
