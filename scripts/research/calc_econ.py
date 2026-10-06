#!/usr/bin/env python3
"""Light economic plan for a Steam launch: gross -> net per copy, break-even, three scenarios, sensitivity.

Every rate is an INPUT with a stated default, not a fact: platform cut, VAT/sales-tax share, refunds and
local taxes change by country and over time (the skill labels them [DA VERIFICARE] and cites the source).
Same inputs always give the same numbers, so the plan can be re-run when a rate or a price changes.

Per copy sold:
  net = price x (1 - avg_discount) x (1 - vat_share) x (1 - refund) x (1 - steam_cut) x (1 - local_tax)
  break-even copies = total costs / net        (total costs = cash costs + hours x hourly rate)
Scenarios: copies = wishlists at launch x conversion in year 1 (wishlists -> purchases). Percent values
above 1 are read as percentages (30 -> 0.30).

Examples:
  python calc_econ.py --price 14.99 --costs 3500 --hours 600 --hourly 12 --partners 2 \\
      --wishlists 3000,8000,20000 --conv 0.10,0.20,0.30 --md launch/03-pricing-calc.md -o launch/_raw/econ.json
  python calc_econ.py --config launch/_raw/econ_inputs.json         # same flags, as a JSON object

Defaults (all adjustable): steam-cut 0.30, vat-share 0.10 (blended average of prices that include VAT and
prices that do not), refund 0.06, avg-discount 0.15 (launch discount and sales over year 1), local-tax 0.
"""
from __future__ import annotations

import argparse
import math
from common import load_json, log, write_json

DEFAULTS = dict(steam_cut=0.30, vat_share=0.10, refund=0.06, avg_discount=0.15, local_tax=0.0, costs=0.0,
                hours=0.0, hourly=0.0, partners=1, conv=[0.10, 0.20, 0.30], wishlists=[], currency="EUR")
NAMES = ["pessimistico", "base", "ottimistico"]


def rate(x, name: str) -> float:
    x = float(x)
    x = x / 100 if x > 1 else x
    if not 0 <= x < 1:
        raise SystemExit(f"{name} must be in [0, 1) (or a percentage below 100), got {x}")
    return x


def floats(v) -> list[float]:
    return [float(x) for x in (v.split(",") if isinstance(v, str) else v) if str(x).strip()]


def compute(c: dict) -> dict:
    price = float(c["price"])
    if price <= 0:
        raise SystemExit("price must be > 0")
    r = {k: rate(c[k], k) for k in ("steam_cut", "vat_share", "refund", "avg_discount", "local_tax")}
    steps, v = [("Prezzo di listino", price)], price
    for label, key in (("dopo sconti medi anno 1", "avg_discount"), ("al netto IVA/sales tax", "vat_share"),
                       ("al netto rimborsi", "refund"), ("al netto quota Steam", "steam_cut"),
                       ("al netto imposte/contributi locali", "local_tax")):
        v *= 1 - r[key]
        steps.append((label, v))
    net = v
    cash, time_cost = float(c["costs"]), float(c["hours"]) * float(c["hourly"])
    total = cash + time_cost
    conv, wl = floats(c["conv"]), floats(c["wishlists"])
    partners = max(1, int(c["partners"]))

    def be(cost):
        return math.ceil(cost / net) if cost > 0 else 0

    out = dict(inputs={**c, **r}, per_copy=[dict(step=s, value=round(x, 2)) for s, x in steps], net_per_copy=round(net, 2),
               net_share_of_list_price=round(net / price, 3), costs=dict(cash=cash, time=round(time_cost, 2), total=round(total, 2)),
               breakeven=dict(copies_cash=be(cash), copies_with_time=be(total),
                              wishlists_needed={f"{round(x * 100)}%": math.ceil(be(total) / x) for x in conv if x > 0}),
               scenarios=[], sensitivity=[])
    for i, w in enumerate(wl):
        cv = conv[min(i, len(conv) - 1)]
        copies = round(w * cv)
        net_total = copies * net
        out["scenarios"].append(dict(
            name=NAMES[i] if i < len(NAMES) else f"scenario {i + 1}", wishlists=int(w), conversion=cv, copies=copies,
            gross=round(copies * price, 2), net=round(net_total, 2), profit_cash=round(net_total - cash, 2),
            profit_with_time=round(net_total - total, 2), per_partner=round((net_total - cash) / partners, 2),
            times_breakeven=round(copies / be(total), 2) if be(total) else None))
    for label, mult_price, refund in (("prezzo -20%", 0.8, None), ("prezzo +20%", 1.2, None), ("rimborsi doppi", 1.0, min(0.99, 2 * r["refund"]))):
        n = price * mult_price * (1 - r["avg_discount"]) * (1 - r["vat_share"]) * (1 - (refund if refund is not None else r["refund"])) \
            * (1 - r["steam_cut"]) * (1 - r["local_tax"])
        out["sensitivity"].append(dict(case=label, net_per_copy=round(n, 2), breakeven_copies=math.ceil(total / n) if total > 0 else 0))
    return out


def md(o: dict) -> str:
    cur, i = o["inputs"]["currency"], o["inputs"]
    L = ["# Piano economico (calcolato da `calc_econ.py`)", "",
         f"Valuta: {cur}. Tutte le aliquote sono **input [DA VERIFICARE]** con fonte nel report; non sono consulenza fiscale.", "",
         "## Dal lordo al netto, per copia", "", "| Passaggio | Valore |", "|---|---|"]
    L += [f"| {s['step']} | {s['value']:.2f} |" for s in o["per_copy"]]
    L += ["", f"**Netto per copia: {o['net_per_copy']:.2f}** ({o['net_share_of_list_price'] * 100:.0f}% del prezzo di listino).",
          f"Ipotesi: sconto medio {i['avg_discount']:.0%}, IVA/sales tax {i['vat_share']:.0%}, rimborsi {i['refund']:.0%}, "
          f"quota Steam {i['steam_cut']:.0%}, imposte e contributi {i['local_tax']:.0%}.", "", "## Break-even", "",
          f"- Costi per cassa: {o['costs']['cash']:.0f}; tempo di sviluppo ({i['hours']:.0f} h x {i['hourly']:.0f}): {o['costs']['time']:.0f}; totale {o['costs']['total']:.0f}.",
          f"- Copie per recuperare i costi per cassa: **{o['breakeven']['copies_cash']}**; con il costo del tempo: **{o['breakeven']['copies_with_time']}**.",
          "- Wishlist al lancio necessarie (break-even con tempo) per conversione anno 1: "
          + ", ".join(f"{k} -> {v}" for k, v in o["breakeven"]["wishlists_needed"].items()) + "."]
    if o["scenarios"]:
        L += ["", "## Tre scenari (copie = wishlist x conversione)", "",
              "| Scenario | Wishlist | Conv. | Copie | Lordo | Netto | Utile (cassa) | Utile (con tempo) | A testa | x break-even |", "|---|---|---|---|---|---|---|---|---|---|"]
        L += [f"| {s['name']} | {s['wishlists']} | {s['conversion']:.0%} | {s['copies']} | {s['gross']:.0f} | {s['net']:.0f} | "
              f"{s['profit_cash']:.0f} | {s['profit_with_time']:.0f} | {s['per_partner']:.0f} | {s['times_breakeven']} |" for s in o["scenarios"]]
    L += ["", "## Sensibilità", "", "| Caso | Netto per copia | Copie break-even |", "|---|---|---|"]
    L += [f"| {s['case']} | {s['net_per_copy']:.2f} | {s['breakeven_copies']} |" for s in o["sensitivity"]]
    L += ["", "_Le conversioni wishlist -> acquisto sono un'ipotesi [DA VERIFICARE] sui comparabili; il modello non include vendite non passate dalla wishlist, DLC, bundle né ricavi di altri store._"]
    return "\n".join(L) + "\n"


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--config", help="JSON file with the same keys as the flags (flags override it)")
    ap.add_argument("--price", type=float, help="list price")
    ap.add_argument("--steam-cut", dest="steam_cut"); ap.add_argument("--vat-share", dest="vat_share")
    ap.add_argument("--refund"); ap.add_argument("--avg-discount", dest="avg_discount"); ap.add_argument("--local-tax", dest="local_tax")
    ap.add_argument("--costs", type=float, help="cash costs (Steam fee, tools, licences, marketing)")
    ap.add_argument("--hours", type=float, help="development hours"); ap.add_argument("--hourly", type=float, help="hourly rate for the time cost (can be figurative)")
    ap.add_argument("--partners", type=int, help="people sharing the profit"); ap.add_argument("--currency")
    ap.add_argument("--wishlists", help="comma list for the 3 scenarios (pessimistic,base,optimistic)")
    ap.add_argument("--conv", help="year-1 conversion per scenario, e.g. 0.10,0.20,0.30")
    ap.add_argument("-o", "--out", help="JSON output (also read by wl_track.py and status_page.py)"); ap.add_argument("--md", help="Markdown output file")
    a = ap.parse_args()
    c = dict(DEFAULTS)
    if a.config:
        c.update(load_json(a.config))
    c.update({k: v for k, v in vars(a).items() if k not in ("config", "out", "md") and v is not None})
    if "price" not in c:
        ap.error("--price (or price in --config) is required")
    o = compute(c)
    text = md(o)
    if a.md:
        with open(a.md, "w", encoding="utf-8", newline="\n") as f:
            f.write(text)
        log(f"wrote {a.md}")
    else:
        print(text)
    if a.out:
        write_json(o, a.out)


if __name__ == "__main__":
    main()
