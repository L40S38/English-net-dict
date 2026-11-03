from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class VoicePersona:
    voice: str
    name: str
    description: str
    gender: str


VOICE_PERSONAS: list[VoicePersona] = [
    VoicePersona(
        voice="alloy",
        name="Alex",
        description="落ち着いた中性的な声。クセのないニュートラルな話し方で聞き取りやすい。",
        gender="neutral",
    ),
    VoicePersona(
        voice="echo",
        name="Ethan",
        description="はっきりとした男性の声。クリアな発音で聞き取りやすい。",
        gender="male",
    ),
    VoicePersona(
        voice="fable",
        name="Felix",
        description="落ち着いた語り口調。物語を読むような英国風の響きを持つ声。",
        gender="male",
    ),
    VoicePersona(
        voice="onyx",
        name="Owen",
        description="低音でどっしりした男性の声。重厚で力強い印象。",
        gender="male",
    ),
    VoicePersona(
        voice="nova",
        name="Nora",
        description="明るくハキハキした女性の声。テンポが良く活発な印象。",
        gender="female",
    ),
    VoicePersona(
        voice="shimmer",
        name="Sophie",
        description="柔らかく軽やかな女性の声。優しく落ち着いた印象。",
        gender="female",
    ),
]

PERSONA_BY_VOICE: dict[str, VoicePersona] = {p.voice: p for p in VOICE_PERSONAS}
ALL_VOICES: list[str] = [p.voice for p in VOICE_PERSONAS]
