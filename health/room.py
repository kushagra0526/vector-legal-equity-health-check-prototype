"""Synthetic startup data rooms with planted equity-hygiene issues and honest look-alikes."""
import datetime as dt
import random

ISSUES = ["AUTHORIZED_EXCEEDED", "POOL_EXCEEDED", "GRANT_NOT_APPROVED", "GRANT_BEFORE_APPROVAL", "STALE_409A", "STRIKE_BELOW_FMV",
          "ISO_100K", "83B_LATE", "83B_MISSING", "SAFE_UNSIGNED", "SAFE_AMOUNT_MISMATCH", "IP_ASSIGNMENT_MISSING", "FRANCHISE_TAX_METHOD"]
DEV = dict(p_issue=0.18, n_grants=(4, 12), n_safes=(1, 4), authorized=10_000_000, priced_p=0.3, start="2023-02-01")


def iso(d):
    return d.isoformat()


def make(seed, cfg=None):
    c = {**DEV, **(cfg or {})}
    r = random.Random(seed)
    want = {i for i in ISSUES if r.random() < c["p_issue"]}
    if "GRANT_NOT_APPROVED" in want:
        want.discard("GRANT_BEFORE_APPROVAL")                                     # both would sit on the same grant
    start = dt.date.fromisoformat(c["start"]) + dt.timedelta(days=r.randrange(0, 300))
    names = ["Ava", "Ben", "Chen", "Dara", "Eli", "Fay", "Gus", "Hana", "Ivan", "Jo", "Kai", "Lea", "Mo", "Nia", "Oz", "Pia"]
    r.shuffle(names)
    nf = r.choice([2, 2, 3])
    founders = []
    for i in range(nf):
        p = start + dt.timedelta(days=r.randrange(0, 10))
        mailed = p + dt.timedelta(days=r.choice([3, 10, 20, 29, 30]))           # day 30 is still on time
        founders.append(dict(name=names[i], shares=r.choice([3_000_000, 2_500_000, 2_000_000]), purchase_date=iso(p), vesting=True,
                             election_83b_mailed=iso(mailed)))
    if "83B_LATE" in want:
        f0 = founders[0]; f0["election_83b_mailed"] = iso(dt.date.fromisoformat(f0["purchase_date"]) + dt.timedelta(days=r.randrange(31, 90)))
    if "83B_MISSING" in want:
        founders[-1]["election_83b_mailed"] = None
    reserve = r.choice([1_000_000, 1_500_000, 2_000_000])
    authorized = c["authorized"]
    vals, v0 = [], start + dt.timedelta(days=60)
    fmv = round(r.uniform(0.01, 0.05), 4)
    d = v0
    while d < start + dt.timedelta(days=1000):
        vals.append(dict(date=iso(d), fmv=fmv))
        d += dt.timedelta(days=r.randrange(250, 330)); fmv = round(fmv * r.uniform(1.3, 2.5), 4)
    fin = []
    if r.random() < c["priced_p"] or "STALE_409A" in want:
        pdate = dt.date.fromisoformat(vals[-1]["date"]) - dt.timedelta(days=r.randrange(40, 120))
        if pdate > dt.date.fromisoformat(vals[0]["date"]):
            fin.append(dict(date=iso(pdate), kind="priced"))
            vals.append(dict(date=iso(pdate + dt.timedelta(days=r.randrange(10, 30))), fmv=round(fmv * 1.5, 4)))   # fresh 409A after the round
            vals.sort(key=lambda v: v["date"])
    grants, board = [], []
    ng = r.randrange(*c["n_grants"])
    per = reserve // (ng + 2)
    for k in range(ng):
        gd = start + dt.timedelta(days=r.randrange(70, 1000))
        prior = [v for v in vals if dt.date.fromisoformat(v["date"]) <= gd]
        if not prior:
            gd = dt.date.fromisoformat(vals[0]["date"]) + dt.timedelta(days=r.randrange(1, 60))
            prior = vals[:1]
        # avoid accidental staleness: move the grant inside 12 months of its 409A and not across a priced round
        v = prior[-1]
        vd = dt.date.fromisoformat(v["date"])
        if (gd - vd).days > 330 or any(vd < dt.date.fromisoformat(x["date"]) <= gd for x in fin):
            gd = vd + dt.timedelta(days=r.randrange(1, 60))
        shares = r.randrange(per // 4, per)
        g = dict(id=f"G{k + 1:03d}", holder=names[nf + k % (len(names) - nf)], shares=shares, kind=r.choice(["ISO", "ISO", "NSO"]),
                 grant_date=iso(gd), strike=v["fmv"], vest_start=iso(gd), vest_months=48, cliff_months=12, exercised=0)
        if g["kind"] == "ISO" and shares * v["fmv"] / 4 > 95000:
            g["shares"] = int(90000 * 4 / v["fmv"])                               # keep clean ISOs under the $100k/yr line
        grants.append(g)
        board.append(dict(id=f"BC-{k + 1:03d}", date=iso(gd - dt.timedelta(days=r.choice([0, 0, 3, 10]))), approves=[g["id"]]))
    g = grants[0]
    if "GRANT_NOT_APPROVED" in want:
        board = [b for b in board if g["id"] not in b["approves"]]
    elif "GRANT_BEFORE_APPROVAL" in want:
        for b in board:
            if g["id"] in b["approves"]:
                b["date"] = iso(dt.date.fromisoformat(g["grant_date"]) + dt.timedelta(days=r.randrange(5, 25)))
                vd = max(dt.date.fromisoformat(v["date"]) for v in vals if dt.date.fromisoformat(v["date"]) <= dt.date.fromisoformat(g["grant_date"]))
                if (dt.date.fromisoformat(b["date"]) - vd).days > 360 or any(dt.date.fromisoformat(g["grant_date"]) < dt.date.fromisoformat(x["date"]) <= dt.date.fromisoformat(b["date"]) for x in fin):
                    b["date"] = iso(dt.date.fromisoformat(g["grant_date"]) + dt.timedelta(days=2))
                later = [v for v in vals if dt.date.fromisoformat(g["grant_date"]) < dt.date.fromisoformat(v["date"]) <= dt.date.fromisoformat(b["date"])]
                if later:
                    g["strike"] = later[-1]["fmv"]
    g2 = grants[-1]
    if "STALE_409A" in want:
        vd = max(dt.date.fromisoformat(v["date"]) for v in vals if dt.date.fromisoformat(v["date"]) <= dt.date.fromisoformat(g2["grant_date"]))
        nxt = [dt.date.fromisoformat(v["date"]) for v in vals if dt.date.fromisoformat(v["date"]) > vd]
        if fin and dt.date.fromisoformat(fin[0]["date"]) > vd:
            gd = dt.date.fromisoformat(fin[0]["date"]) + dt.timedelta(days=2)       # granted right after the round, before the new 409A
            v_at = max((v for v in vals if dt.date.fromisoformat(v["date"]) <= gd), key=lambda v: v["date"])
            if dt.date.fromisoformat(v_at["date"]) > dt.date.fromisoformat(fin[0]["date"]):
                gd = dt.date.fromisoformat(fin[0]["date"]) + dt.timedelta(days=1)
        else:
            gd = vd + dt.timedelta(days=380)
            if nxt and nxt[0] <= gd:                                              # a newer 409A exists: use the last one instead
                vd = dt.date.fromisoformat(vals[-1]["date"])
                gd = vd + dt.timedelta(days=380)
        g2["grant_date"] = g2["vest_start"] = iso(gd)
        for b in board:
            if g2["id"] in b["approves"]:
                b["date"] = iso(gd)
        g2["strike"] = max(v for v in vals if dt.date.fromisoformat(v["date"]) <= gd)["fmv"] if False else \
            max((v for v in vals if dt.date.fromisoformat(v["date"]) <= gd), key=lambda v: v["date"])["fmv"]
    if "STRIKE_BELOW_FMV" in want:
        gs = grants[len(grants) // 2]
        gs["strike"] = round(gs["strike"] * r.uniform(0.4, 0.8), 4)
    if "POOL_EXCEEDED" in want:
        extra = reserve - sum(x["shares"] for x in grants) + r.randrange(10_000, 200_000)
        grants[-1]["shares"] += max(extra, 10_000)
    else:
        while sum(x["shares"] for x in grants) > reserve:                         # keep clean rooms inside the reserve
            big = max(grants, key=lambda x: x["shares"]); big["shares"] //= 2
    if "ISO_100K" in want:                                                        # needs a high FMV to be realistic
        gi = max(grants[1:-1] or grants, key=lambda x: x["strike"])
        need = int(r.uniform(130000, 300000) * 4 / max(gi["strike"], 1e-6))
        room_left = reserve - sum(x["shares"] for x in grants) + gi["shares"]
        if need <= room_left:
            gi["kind"], gi["shares"] = "ISO", need
        else:
            want.discard("ISO_100K")
    issued = sum(x["shares"] for x in founders)
    while "AUTHORIZED_EXCEEDED" not in want and issued + max(reserve, sum(x["shares"] for x in grants)) > 0.95 * authorized:
        for fo in founders:
            fo["shares"] = int(fo["shares"] * 0.8)
        issued = sum(x["shares"] for x in founders)
    if "AUTHORIZED_EXCEEDED" in want:
        authorized = issued + reserve - r.randrange(10_000, 500_000)
    safes = []
    for k in range(r.randrange(*c["n_safes"])):
        amt = r.choice([25_000, 50_000, 100_000, 150_000, 250_000, 500_000])
        wire = amt - r.choice([0, 0, 0, 15, 25, 45])                              # bank fees up to $45 are not an issue
        safes.append(dict(id=f"SAFE-{k + 1}", investor=f"Fund {k + 1}", amount=amt, cap=r.choice([6e6, 8e6, 10e6, 12e6, 15e6]),
                          signed_company=True, wire=wire))
    if "SAFE_UNSIGNED" in want:
        safes[0]["signed_company"] = False
    if "SAFE_AMOUNT_MISMATCH" in want:
        safes[-1]["wire"] = safes[-1]["amount"] - r.choice([5_000, 10_000, 25_000])
    people = [x["name"] for x in founders] + sorted({g["holder"] for g in grants})
    ip = list(people)
    if "IP_ASSIGNMENT_MISSING" in want:
        ip.remove(r.choice(people))
    issued_now = issued
    gross = r.choice([150_000, 400_000, 900_000, 2_500_000])
    notice = "authorized" if "FRANCHISE_TAX_METHOD" in want else "apvc"
    room = dict(company=dict(name=f"Startup {seed}", authorized=authorized, par=0.00001, gross_assets=gross, franchise_notice_method=notice),
                founders=founders, plan=dict(reserve=reserve, adopted=iso(start)), board=board, grants=grants, valuations=vals,
                financings=fin, safes=safes, ip_assignments=ip, people=people)
    return room, want
