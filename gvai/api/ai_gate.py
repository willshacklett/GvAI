import json
import os
import re
from collections import Counter
from datetime import datetime

from gvai.middleware.memory_gate import GVMemoryGate

LOG_FILE = "gvai/logs/gv_log.jsonl"


def extract_signal(text: str):
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    line_count = min(len(lines), 5)

    sentences = [s.strip() for s in re.split(r'[.!?]+', text) if s.strip()]
    sentence_count = max(1, len(sentences))

    words = re.findall(r"\b\w+\b", text.lower())
    word_count = max(1, len(words))

    avg_sentence_len = word_count / sentence_count

    norm_sentence_count = min(sentence_count / 5.0, 2.0)
    norm_avg_len = min(avg_sentence_len / 20.0, 2.0)

    punct_count = len(re.findall(r'[,:;!?()"\-]', text))
    punct_density = punct_count / word_count
    norm_punct = min(punct_density * 5.0, 2.0)

    long_word_ratio = sum(1 for w in words if len(w) >= 8) / word_count
    norm_long_words = min(long_word_ratio * 5.0, 2.0)

    counts = Counter(words)
    repeated_words = sum(c for c in counts.values() if c > 1)
    repetition_ratio = repeated_words / word_count
    norm_repetition = min(repetition_ratio * 3.0, 2.0)

    norm_lines = min(line_count / 3.0, 2.0)

    return [
        float(norm_sentence_count),
        float(norm_avg_len),
        float(norm_punct),
        float(norm_long_words),
        float(norm_repetition),
        float(norm_lines),
    ]


def sample_outputs():
    return [
        "The sky is blue because shorter wavelengths of sunlight scatter more strongly in the atmosphere.",
        "The sky is blue. Blue light scatters more. That is the short version.",
        "The sky is blue, blue, blue because scattering happens and happens and happens across the atmosphere in a repeated pattern.",
        "Blue light is scattered by molecules in the atmosphere more than longer wavelengths, especially when sunlight passes through the air during the day.",
        "The explanation becomes unstable when wording gets repetitive, overly stretched, fragmented, and oddly punctuated... maybe! maybe! maybe!",
    ]


def format_output(text, evaluation):
    decision = evaluation["decision"]
    confidence = evaluation["confidence"]
    gv = round(evaluation["avg_gv"], 2)

    if decision == "block":
        return f"⛔ BLOCKED (GV={gv}, confidence={confidence})"

    if decision == "warn":
        return f"⚠️ GV Warning (confidence={confidence}, gv={gv})\n\n{text}"

    return f"✅ (GV={gv}, confidence={confidence})\n\n{text}"


def append_log(record):
    os.makedirs("gvai/logs", exist_ok=True)
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps(record) + "\n")


def main():
    gate = GVMemoryGate()
    os.makedirs("gvai/logs", exist_ok=True)

    for i, text in enumerate(sample_outputs(), start=1):
        signal = extract_signal(text)
        evaluation = gate.evaluate(signal)
        final_output = format_output(text, evaluation)

        record = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "source": "ai_gate",
            "run": i,
            "text": text,
            "signal": signal,
            "decision": evaluation["decision"],
            "confidence": evaluation["confidence"],
            "gv": evaluation["avg_gv"],
            "current_gv": evaluation["current_gv"],
            "history": evaluation["history"],
            "details": evaluation["result"],
            "display": final_output,
        }
        append_log(record)

        print(f"\n=== RUN {i} ===")
        print("SIGNAL:", signal)
        print(final_output)
        print(json.dumps(record, indent=2))


if __name__ == "__main__":
    main()
