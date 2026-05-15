from gvai.universal_scalar import GVEvidence, gv_scalar

CASES = [
    ("stable_recoverable", "software", GVEvidence(1.0, 1.0, 1.0, 0.1)),
    ("transient_noise", "queue", GVEvidence(0.8, 0.9, 0.8, 0.6)),
    ("persistent_degradation", "service", GVEvidence(0.45, 0.35, 0.30, 0.5)),
    ("irrecoverable_failure", "generic", GVEvidence(0.05, 0.05, 0.05, 0.9)),
    ("biological_slow_recovery", "biology", GVEvidence(0.35, 0.40, 0.45, 0.3)),
    ("economic_recovery_loss", "economics", GVEvidence(0.30, 0.25, 0.35, 0.4)),
]

def main():
    rows = []
    for name, domain, evidence in CASES:
        score = gv_scalar(evidence)
        rows.append({"name": name, "domain": domain, "gv": score})
        print(rows[-1])

    assert rows[0]["gv"] > rows[2]["gv"] > rows[3]["gv"]
    assert rows[1]["gv"] > rows[2]["gv"]
    assert rows[4]["gv"] > rows[3]["gv"]

    print("\nUNIVERSAL SCALAR CONTRACT SMOKE TEST PASSED")

if __name__ == "__main__":
    main()