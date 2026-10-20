from health import check, room


def test_franchise_tax_methods():
    asm, apvc = check.franchise_tax(10_000_000, 8_000_000, 0.00001, 400_000)
    assert asm == 250 + 85 * 999                                  # $85,165 under the authorized-shares method
    assert apvc == 400                                            # 0.05/share x 10M = $500k APVC -> minimum $400


def test_83b_day_30_is_on_time_day_31_late():
    rm, _ = room.make(5)
    fo = rm["founders"][0]
    import datetime as dt
    p = dt.date.fromisoformat(fo["purchase_date"])
    fo["election_83b_mailed"] = (p + dt.timedelta(days=30)).isoformat()
    assert "83B_LATE" not in {f["code"] for f in check.check(rm)[0]}
    fo["election_83b_mailed"] = (p + dt.timedelta(days=31)).isoformat()
    assert "83B_LATE" in {f["code"] for f in check.check(rm)[0]}


def test_iso_split():
    g = dict(shares=1_000_000, vest_start="2025-01-01", vest_months=48, cliff_months=12)
    over = check.iso_split(g, 1.00)                                # $250k/yr at $1 -> over the $100k limit
    assert over and min(over.values()) > 100000


def test_wire_fee_tolerated_shortfall_flagged():
    rm, _ = room.make(8)
    rm["safes"][0]["wire"] = rm["safes"][0]["amount"] - 25
    assert "SAFE_AMOUNT_MISMATCH" not in {f["code"] for f in check.check(rm)[0]}
    rm["safes"][0]["wire"] = rm["safes"][0]["amount"] - 10_000
    assert "SAFE_AMOUNT_MISMATCH" in {f["code"] for f in check.check(rm)[0]}


def test_priced_round_makes_older_409a_stale():
    rm, _ = room.make(9)
    g = rm["grants"][0]
    rm["valuations"] = [dict(date="2025-01-10", fmv=0.05)]
    rm["financings"] = [dict(date="2025-03-01", kind="priced")]
    g["grant_date"] = g["vest_start"] = "2025-03-05"; g["strike"] = 0.05
    for b in rm["board"]:
        if g["id"] in b["approves"]:
            b["date"] = "2025-03-05"
    assert any(f["code"] == "STALE_409A" and g["id"] in f["msg"] for f in check.check(rm)[0])


def test_dev_rooms_match_labels():
    for s in range(1, 30):
        rm, want = room.make(s)
        assert {f["code"] for f in check.check(rm)[0]} == want
