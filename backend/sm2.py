"""SM-2 review scheduling + fingerprint update rules for the Agentathon coach."""
from datetime import date, timedelta


def sm2(quality: int, repetitions: int, interval_days: int, ease: float):
    """Classic SM-2. quality: 0-5. Returns (repetitions, interval_days, ease)."""
    if quality < 3:
        repetitions = 0
        interval_days = 1
    else:
        if repetitions == 0:
            interval_days = 1
        elif repetitions == 1:
            interval_days = 6
        else:
            interval_days = round(interval_days * ease)
        repetitions += 1
    ease = ease + (0.1 - (5 - quality) * (0.08 + (5 - quality) * 0.02))
    ease = max(1.3, ease)
    return repetitions, interval_days, ease


def next_due(interval_days: int) -> str:
    return (date.today() + timedelta(days=interval_days)).isoformat()


def bump_fingerprint(score: float) -> float:
    """Confirmed error of this type."""
    return min(1.0, score + 0.25)


def decay_fingerprint(score: float) -> float:
    """Clean, optimized solve on a problem tagged with this type."""
    return score * 0.6


def is_mastered(score: float, last_two_qualities: list) -> bool:
    return score < 0.1 and len(last_two_qualities) >= 2 and all(q >= 4 for q in last_two_qualities[-2:])


if __name__ == "__main__":
    reps, interval, ease = 0, 0, 2.5
    for q in [4, 5, 4, 2, 5]:
        reps, interval, ease = sm2(q, reps, interval, ease)
        print(f"quality={q} -> reps={reps}, interval={interval}d, ease={ease:.2f}, due={next_due(interval)}")
