# Equity legal-health check: a software first pass over a startup data room

Unofficial prototype by Kushagra Pratap Singh. Not affiliated with Vector Legal. Not legal advice.

Vector Legal is an AI-native law firm for startups. Their software "takes the first pass and attorneys spend their time on judgment", and their services include **legal health checks**, cap table management and investor-ready data rooms ([YC](https://www.ycombinator.com/companies/vector-legal), [site](https://vectorlegal.com)). Most of an equity health check is cross-document consistency plus dated rules. That is exactly the part software can do first, with every finding citing the documents it used and a cure the attorney can accept or change.

## What it checks (`health/check.py`, stdlib)
| code | rule (cite) | suggested cure |
|---|---|---|
| AUTHORIZED_EXCEEDED | issued + outstanding options + remaining reserve > authorized (DGCL §161) | charter amendment + §204 ratification |
| POOL_EXCEEDED | options granted > plan reserve | reserve increase + ratify |
| GRANT_NOT_APPROVED / GRANT_BEFORE_APPROVAL | no board consent, or the consent is dated after the grant (DGCL §157) | ratify; grant date = approval date |
| STALE_409A | 409A older than 12 months at grant, or a **priced round between the report and the grant** (Treas. Reg. 1.409A-1(b)(5)(iv)(B)(2)(i)) | new 409A; re-price |
| STRIKE_BELOW_FMV | strike < 409A FMV at the effective grant date | re-price |
| ISO_100K | more than $100,000 first exercisable in a calendar year (IRC 422(d)), per vesting schedule | split the excess to NSO |
| 83B_LATE / 83B_MISSING | 83(b) not mailed within 30 days of purchase (day 30 is on time) or no proof in the room (IRC 83(b)(2)) | tax counsel; can't be re-filed |
| SAFE_UNSIGNED / SAFE_AMOUNT_MISMATCH | not countersigned; wire ≠ purchase amount (bank fees ≤ $50 tolerated) | countersign; amend or collect |
| IP_ASSIGNMENT_MISSING | founder or option holder without a signed IP assignment | CIIAA with nunc pro tunc assignment |
| FRANCHISE_TAX_METHOD | Delaware notice uses authorized shares ($175/$250/+$85 per 10k) when assumed par value capital ($400 per $1M, min $400) is lower (8 Del. C. §503) | file using APVC |

It also reports post-money SAFE ownership at conversion (Σ purchase amount ÷ post-money cap).

```
$ python demo.py
Startup 1009: 2 founders, 10 option grants, 2 SAFEs, 4 409A reports, 0 priced round(s)
  HIGH   AUTHORIZED_EXCEEDED    issued 5,500,000 + options/reserve exceed 6,848,045 authorized shares
         DGCL s.161 (shares beyond authorized are void)  ->  charter amendment + ratification under DGCL s.204
  HIGH   GRANT_NOT_APPROVED     G001 (Oz) has no board approval
  HIGH   IP_ASSIGNMENT_MISSING  Dara has no signed invention/IP assignment
  MEDIUM SAFE_UNSIGNED          SAFE-1 (Fund 1) not countersigned by the company
  MEDIUM SAFE_AMOUNT_MISMATCH   SAFE-2: SAFE $150,000, wire $140,000
Delaware franchise tax: authorized-shares method $58,390 vs assumed-par-value-capital $1,600
Post-money SAFE ownership at conversion (sum of amount / cap): 3.3%
```

## Results
**Held-out:** [`heldout/config.json`](heldout/config.json), frozen in git (commit `b027998`) before the first run. 100 bigger data rooms: 15M authorized, 8–20 grants, 2–7 SAFEs, priced rounds in 60% of rooms.

| | result |
|---|---|
| planted issues found (12 kinds) | **258 / 258** |
| findings that weren't planted | 0 |
| clean rooms flagged | 0 / 9 |
| "issued ≤ authorized" cap-table check | 0 / 258 (it ignores options and the reserve) |

**Look-alikes that correctly pass:**
- an 83(b) mailed on day 30;
- a grant on its approval day;
- a strike equal to FMV;
- a wire short by a $15–45 bank fee;
- a grant after a priced round that has a fresh 409A.

Dev (150 rooms): 327 / 327, 0 extra. This was after three **dev-found generator bugs**: an ISO plant creating absurd share counts, the pool clean-up shrinking a planted grant, and two plants colliding on one grant. The checker didn't change.

## Honest limits
- **Near-circular:** structured synthetic data, and I wrote both the generator and the checker. Real data rooms are PDFs. Extraction (board consents, stock purchase agreements, 83(b) proofs, 409A reports) is the hard part, and this assumes it's done.
- **ISO $100K** couldn't be planted realistically in the held-out rooms (409A prices were too low), so held-out has 0 of them. Dev had 1 and a unit test covers the math.
- **Rules are simplified first-pass screens:** 409A "material event" is reduced to priced rounds, and franchise-tax rates are taken from public summaries. An attorney decides; every finding says which documents to open.

## Run
```
python demo.py
python evaluate.py heldout      # first run kept in out/heldout_first_run.json
python -m pytest -q             # 6 tests, stdlib only
```
