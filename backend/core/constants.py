from core.config import SHARED_CONFIG

# 最長想定例「ややこしい単語：delightful / delighted」に揃えた上限（1 文字 = 1 Unicode コードポイント）
GROUP_NAME_MAX_LENGTH = int(SHARED_CONFIG.get("group_name_max_length", 50))
