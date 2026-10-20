"""Equity legal-health check over a startup data room. Every finding cites the documents it used and suggests a cure.

room = dict(
  company=dict(name, authorized, par, gross_assets, franchise_notice_method),
  founders=[dict(name, shares, purchase_date, vesting=bool, election_83b_mailed=date|None)],
  plan=dict(reserve, adopted),
  board=[dict(id, date, approves=[grant ids])],
  grants=[dict(id, holder, shares, kind ISO|NSO, grant_date, strike, vest_start, vest_months, cliff_months, exercised)],
  valuations=[dict(date, fmv)],                 # 409A reports
  financings=[dict(date, kind "priced")],
  safes=[dict(id, investor, amount, cap, signed_company=bool, wire=amount|None)],
  ip_assignments=[names], people=[names])
Dates are ISO strings. Rules are data; this is a first pass for attorney review, not legal advice.
"""
import datetime as dt
import math

WIRE_FEE_TOLERANCE = 50.0


def D(s):
    return dt.date.fromisoformat(s)


def add_months(d, m):
    y, mo = divmod(d.month - 1 + m, 12)
    day = min(d.day, [31, 29 if (d.year + y) % 4 == 0 else 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31][mo])
    return dt.date(d.year + y, mo + 1, day)


def franchise_tax(authorized, issued, par, gross_assets):
    """Delaware: authorized-shares method vs assumed-par-value-capital method (rates as data; check corp.delaware.gov)."""
    if authorized <= 5000:
        asm = 175.0
    elif authorized <= 10000:
        asm = 250.0
    else:
        asm = 250.0 + 85.0 * math.ceil((authorized - 10000) / 10000)
    asm = min(asm, 200000.0)
    assumed_par = gross_assets / issued if issued else 0
    apvc = max(assumed_par, par) * authorized
    apvc_tax = max(400.0, 400.0 * math.ceil(apvc / 1_000_000))
    return asm, min(apvc_tax, 200000.0)


def iso_split(g, fmv):
    """Shares first exercisable per calendar year at grant-date FMV; > $100k in a year -> excess is NSO (IRC 422(d))."""
    start, n, months, cliff = D(g["vest_start"]), g["shares"], g["vest_months"], g["cliff_months"]
    per_year = {}
    for m in range(1, months + 1):
        if m < cliff:
            continue
        sh = n * cliff / months if m == cliff else n / months
        y = add_months(start, m).year
        per_year[y] = per_year.get(y, 0) + sh
    return {y: s * fmv for y, s in per_year.items() if s * fmv > 100000}


def check(room):
    F = []
    co = room["company"]

    def f(code, level, msg, cite, cure, docs):
        F.append(dict(code=code, level=level, msg=msg, cite=cite, cure=cure, docs=docs))

    issued = sum(x["shares"] for x in room["founders"]) + sum(g.get("exercised", 0) for g in room["grants"])
    reserved_left = room["plan"]["reserve"] - sum(g["shares"] for g in room["grants"])
    if issued + max(reserved_left, 0) + sum(g["shares"] - g.get("exercised", 0) for g in room["grants"]) > co["authorized"]:
        f("AUTHORIZED_EXCEEDED", "HIGH", f"issued {issued:,} + options/reserve exceed {co['authorized']:,} authorized shares",
          "DGCL s.161 (shares beyond authorized are void)", "charter amendment + ratification under DGCL s.204", ["charter", "cap table"])
    granted = sum(g["shares"] for g in room["grants"])
    if granted > room["plan"]["reserve"]:
        f("POOL_EXCEEDED", "HIGH", f"{granted:,} options granted vs {room['plan']['reserve']:,} reserved", "equity plan share reserve",
          "board + stockholder approval to increase the reserve; ratify excess grants", ["equity plan", "option ledger"])
    approved = {gid: b for b in room["board"] for gid in b["approves"]}
    vals = sorted(room["valuations"], key=lambda v: v["date"])
    priced = sorted(x["date"] for x in room["financings"] if x["kind"] == "priced")
    for g in room["grants"]:
        b = approved.get(g["id"])
        if b is None:
            f("GRANT_NOT_APPROVED", "HIGH", f"{g['id']} ({g['holder']}) has no board approval", "equity plan / DGCL s.157",
              "board ratification; re-check strike at ratification date", [g["id"]])
        elif D(b["date"]) > D(g["grant_date"]):
            f("GRANT_BEFORE_APPROVAL", "MEDIUM", f"{g['id']} dated {g['grant_date']}, approved {b['date']}", "DGCL s.157",
              "treat grant date as the approval date; re-test strike vs FMV then", [g["id"], b["id"]])
        eff = D(b["date"]) if b and D(b["date"]) > D(g["grant_date"]) else D(g["grant_date"])
        prior = [v for v in vals if D(v["date"]) <= eff]
        if not prior:
            f("NO_409A", "HIGH", f"{g['id']} granted {eff} with no 409A report on or before that date", "Treas. Reg. 1.409A-1(b)(5)(iv)(B)",
              "obtain a 409A; assess strike vs FMV", [g["id"]])
            continue
        v = prior[-1]
        stale = eff > add_months(D(v["date"]), 12)
        event = [p for p in priced if D(v["date"]) < D(p) <= eff]
        if stale or event:
            f("STALE_409A", "HIGH", f"{g['id']} on {eff} relied on the {v['date']} 409A" +
              (" (older than 12 months)" if stale else f" (priced round on {event[0]} in between)"),
              "Treas. Reg. 1.409A-1(b)(5)(iv)(B)(2)(i)", "new 409A; re-price or re-grant affected options", [g["id"], v["date"]])
        if g["strike"] + 1e-9 < v["fmv"]:
            f("STRIKE_BELOW_FMV", "HIGH", f"{g['id']} strike ${g['strike']:.4f} < 409A FMV ${v['fmv']:.4f}", "IRC 409A / 422(b)(4)",
              "re-price to FMV (tender offer if needed)", [g["id"], v["date"]])
        if g["kind"] == "ISO":
            over = iso_split(g, v["fmv"])
            if over:
                y, amt = next(iter(sorted(over.items())))
                f("ISO_100K", "MEDIUM", f"{g['id']}: ${amt:,.0f} first exercisable in {y} (limit $100,000)", "IRC 422(d)",
                  "treat the excess as NSO in the grant notice and ledger", [g["id"]])
    for fo in room["founders"]:
        if not fo["vesting"]:
            continue
        m = fo.get("election_83b_mailed")
        if m is None:
            f("83B_MISSING", "HIGH", f"{fo['name']}: vesting stock bought {fo['purchase_date']}, no 83(b) proof in the data room",
              "IRC 83(b)(2): within 30 days of transfer", "find the IRS-stamped copy / certified-mail receipt; if never filed, tax counsel",
              [fo["name"]])
        elif D(m) > D(fo["purchase_date"]) + dt.timedelta(days=30):
            f("83B_LATE", "HIGH", f"{fo['name']}: 83(b) mailed {m}, {(D(m) - D(fo['purchase_date'])).days} days after {fo['purchase_date']}",
              "IRC 83(b)(2): within 30 days of transfer", "cannot be cured by re-filing; tax counsel on vesting income", [fo["name"]])
    for s in room["safes"]:
        if not s["signed_company"]:
            f("SAFE_UNSIGNED", "MEDIUM", f"{s['id']} ({s['investor']}) not countersigned by the company", "contract formation",
              "countersign and date", [s["id"]])
        if s["wire"] is None:
            f("SAFE_UNFUNDED", "MEDIUM", f"{s['id']}: no wire matched for ${s['amount']:,.0f}", "SAFE purchase amount",
              "match bank statement or confirm unpaid", [s["id"]])
        elif abs(s["wire"] - s["amount"]) > WIRE_FEE_TOLERANCE:
            f("SAFE_AMOUNT_MISMATCH", "MEDIUM", f"{s['id']}: SAFE ${s['amount']:,.0f}, wire ${s['wire']:,.0f}", "SAFE purchase amount",
              "amend SAFE or collect the difference", [s["id"]])
    people = set(room["people"])
    for p in sorted(people - set(room["ip_assignments"])):
        f("IP_ASSIGNMENT_MISSING", "HIGH", f"{p} has no signed invention/IP assignment", "chain of title to company IP",
          "sign a CIIAA with a nunc pro tunc assignment of prior work", [p])
    asm, apvc = franchise_tax(co["authorized"], issued, co["par"], co["gross_assets"])
    if co.get("franchise_notice_method") == "authorized" and apvc < asm:
        f("FRANCHISE_TAX_METHOD", "LOW", f"notice uses the authorized-shares method (${asm:,.0f}); assumed-par-value-capital gives ${apvc:,.0f}",
          "8 Del. C. s.503", "file the annual report using the APVC method with gross assets and issued shares", ["franchise tax notice"])
    safe_own = sum(s["amount"] / s["cap"] for s in room["safes"])
    return F, dict(issued=issued, franchise_tax=dict(authorized_method=asm, apvc_method=apvc),
                   post_money_safe_ownership=round(safe_own, 4))
