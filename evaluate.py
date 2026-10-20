"""Planted equity-hygiene issues found vs a 'cap table adds up' check.  python evaluate.py [dev|heldout] [out.json]"""
import collections, json, sys
from health import room, check


def run(which):
    if which == "heldout":
        h = json.load(open("heldout/config.json"))
        seeds, cfg = h["seeds"], h["cfg"]
    else:
        seeds, cfg = list(range(1, 151)), None
    per = collections.defaultdict(collections.Counter)
    tot = collections.Counter()
    extra, base_found = [], 0
    for s in seeds:
        rm, want = room.make(s, cfg)
        F, summ = check.check(rm)
        got = {f["code"] for f in F}
        base = rm["company"]["authorized"] < summ["issued"]                      # baseline: issued shares <= authorized
        for i in room.ISSUES:
            if i in want:
                per[i]["planted"] += 1; per[i]["found"] += i in got
                tot["planted"] += 1; tot["found"] += i in got
                base_found += base and i == "AUTHORIZED_EXCEEDED"
        for code in got - want:
            extra.append(dict(seed=s, code=code, msg=[f["msg"] for f in F if f["code"] == code][0]))
        tot["rooms"] += 1; tot["clean_rooms"] += not want; tot["clean_rooms_flagged"] += (not want) and bool(got)
    tot["extra_findings"] = len(extra); tot["baseline_found"] = base_found
    return dict(set=which, totals=dict(tot), per_issue={k: dict(v) for k, v in per.items()}, extra=extra)


if __name__ == "__main__":
    which = sys.argv[1] if len(sys.argv) > 1 else "dev"
    r = run(which)
    t = r["totals"]
    print(f"{which}: {t['rooms']} data rooms, planted issues found {t['found']}/{t['planted']} (baseline {t['baseline_found']}), "
          f"findings not planted {t['extra_findings']}, clean rooms flagged {t.get('clean_rooms_flagged', 0)}/{t.get('clean_rooms', 0)}")
    for k, v in sorted(r["per_issue"].items()):
        print(f"    {k:22s} {v['found']:3d}/{v['planted']:3d}")
    for e in r["extra"][:12]:
        print("   EXTRA", e)
    if len(sys.argv) > 2:
        json.dump(r, open(sys.argv[2], "w"), indent=1)
