from gvai.core import GvCore

gv = GvCore()

for t in [
    "This system is stable and well understood.",
    "We should radically change everything immediately.",
    "There might be unknown risks in this approach."
]:
    print("
---")
    print(gv.evaluate(t))
