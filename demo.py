"""A Series A data room, first-pass health check: findings with documents, citations and cures."""
from health import room, check

rm, planted = room.make(1009, dict(p_issue=0.22, n_grants=[8, 20], n_safes=[2, 7], authorized=15_000_000, priced_p=0.6, start="2024-01-15"))
co = rm["company"]
print(f"{co['name']}: {len(rm['founders'])} founders, {len(rm['grants'])} option grants, {len(rm['safes'])} SAFEs, "
      f"{len(rm['valuations'])} 409A reports, {len(rm['financings'])} priced round(s)\n")
F, summary = check.check(rm)
for f in sorted(F, key=lambda x: ["HIGH", "MEDIUM", "LOW"].index(x["level"])):
    print(f"  {f['level']:6s} {f['code']:22s} {f['msg']}")
    print(f"         {f['cite']}  ->  {f['cure']}")
ft = summary["franchise_tax"]
print(f"\nDelaware franchise tax: authorized-shares method ${ft['authorized_method']:,.0f} vs assumed-par-value-capital ${ft['apvc_method']:,.0f}")
print(f"Post-money SAFE ownership at conversion (sum of amount / cap): {summary['post_money_safe_ownership']:.1%}")
