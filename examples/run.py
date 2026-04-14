from gvai.gv_identity import GvIdentity

gv = GvIdentity()
current = gv.start_new_conversation()

print("Start GV:", current)

# Simulated turns
turns = [
    (0.1, 0.0, 0.9, 0.1),  # good
    (0.2, 0.1, 0.8, 0.2),  # slight drift
    (0.4, 0.3, 0.6, 0.4),  # messy
    (0.1, 0.0, 0.9, 0.1),  # recovery
]

for i, (d, c, coh, v) in enumerate(turns, 1):
    current = gv.update(current, d, c, coh, v)
    print(f"Turn {i} → GV: {current:.3f}")
