import json
from pathlib import Path

from impact_ai import ImpactDecision

PREFERENCES_FILE = Path("data/user_preferences.json")

def load_topic_weights() -> dict[str, int]:
    try:
        with PREFERENCES_FILE.open(
            "r",
            encoding="utf-8",
        ) as f:
            data = json.load(f)

        return {
            str(key).strip().lower(): int(value)
            for key, value in data.get(
                "topic_weights",
                {},
            ).items()
        }

    except Exception:
        return {}


def preference_score(
    decision: ImpactDecision,
) -> int:

    weights = load_topic_weights()

    score = decision.impact_score

    for topic in decision.topics:
        score += weights.get(
            topic,
            0,
        )

    return score