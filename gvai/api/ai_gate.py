import json
import os
import re
import sys
from collections import Counter
from datetime import datetime

from openai import OpenAI
from gvai.middleware.memory_gate import GVMemoryGate

LOG_FILE = "gvai/logs/gv_log.jsonl"

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))


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


def call_llm(prompt: str):
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": "Be clear, concise, and helpful."},
            {"role": "user", "content": prompt},
        ],
        temperature=0.7,
    )
    return response.choices[0].message.content.strip()


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


def get_prompt():
    if len(sys.argv) > 1:
        return " ".join(sys.argv[1:]).strip()
    return "Explain why the sky is blue."


def main():
    gate = GVMemoryGate()

    prompt = get_prompt()
    ai_output = call_llm(prompt)

    signal = extract_signal(ai_output)
    evaluation = gate.evaluate(signal)
    final_output = format_output(ai_output, evaluation)

    record = {
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "source": "live_llm",
        "prompt": prompt,
        "text": ai_output,
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

    print("\n=== PROMPT ===")
    print(prompt)

    print("\n=== AI OUTPUT ===")
    print(ai_output)

    print("\n=== GV RESULT ===")
    print(final_output)

    print("\n=== RAW ===")
    print(json.dumps(record, indent=2))


if __name__ == "__main__":
    main()
