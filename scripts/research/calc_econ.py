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

Early Access (optional): --ea-price P turns on an EA scenario. The scenario copies are then sold in EA at P; the EA launch
month makes --ea-first-month of them (default 0.35 [OPINIONE]); the 1.0 launch month earns --full-vs-ea of the EA launch month
(default 0.40: median found by GameDiscoverCo, Dec 2025, on 225 EA graduates [DA VERIFICARE]) at --full-price (default --price).
The point: the EA release IS the launch; 1.0 is a smaller second push, not a second launch.
  python calc_econ.py --price 9.99 --ea-price 7.99 --full-price 9.99 --wishlists 1000,3000,8000 --conv 0.1,0.2,0.3 ...

Real-market base rates (optional): --calibration [PATH] reads ~/.game-launch-strategist/calibration.json (made by
`cohort_bench.py calibrate`) and adds three scenarios from what games of --tier (default B) at this price really sold
(p25 / median / p75 of copies, Boxleiter range x20..x60, [STIMA] with the data date). They sit NEXT to the wishlist scenarios.
  python calc_econ.py --price 7.99 --wishlists 1000,3000,8000 --conv 0.1,0.2,0.3 --calibration --tier B

Defaults (all adjustable): steam-cut 0.30, vat-share 0.10 (blended average of prices that include VAT and
prices that do not), refund 0.06, avg-discount 0.15 (launch discount and sales over year 1), local-tax 0.
"""
from __future__ import annotations

import argparse
import math
from common import load_json, log, write_json

DEFAULTS = dict(steam_cut=0.30, vat_share=0.10, refund=0.06, avg_discount=0.15, local_tax=0.0, costs=0.0,
                hours=0.0, hourly=0.0, partners=1, conv=[0.10, 0.20, 0.30], wishlists=[], currency="EUR",
                ea_price=None, full_price=None, ea_first_month=0.35, full_vs_ea=0.40)
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

    out = dict(inputs={**{k: v for k, v in c.items() if k != "calibration_data"}, **r}, per_copy=[dict(step=s, value=round(x, 2)) for s, x in steps], net_per_copy=round(net, 2),
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
    if c.get("ea_price"):
        out["early_access"] = early_access(c, r, out)
    if c.get("calibration_data"):
        out["calibrated"] = calibrated(c, out)
    return out


def calibrated(c: dict, out: dict) -> dict | None:
    """Scenarios from real base rates: copies of a typical game of the tier at this price, low (x20) and high (x60) estimate."""
    from cohort_bench import base_rate
    cal = c["calibration_data"]
    g, label = base_rate(cal, c.get("tier") or "B", float(c["price"]), c.get("genre"))
    if not g.get("n"):
        return None
    net, cash, total = out["net_per_copy"], out["costs"]["cash"], out["costs"]["total"]
    rows = []
    for name, q in (("pessimistico (p25)", "p25"), ("base (mediana)", "median"), ("ottimistico (p75)", "p75"), ("raro (p90)", "p90")):
        lo, hi = g["copies"][q]
        rows.append(dict(name=name, copies_low=lo, copies_high=hi, net_low=round(lo * net, 2), net_high=round(hi * net, 2),
                         profit_cash_low=round(lo * net - cash, 2), profit_cash_high=round(hi * net - cash, 2),
                         covers_time=(lo * net >= total, hi * net >= total) if total else None))
    return dict(group=label, n=g["n"], small_sample=g.get("small_sample"), milestone=cal.get("primary"), data_from=cal.get("data_from"),
                data_to=cal.get("data_to"), generated_on=cal.get("generated_on"), popular=g.get("popular"), scenarios=rows)


def early_access(c: dict, r: dict, out: dict) -> dict:
    """EA scenario: per scenario, net of the EA launch month and of the 1.0 launch month (a share of the EA month)."""
    ea_p, full_p = float(c["ea_price"]), float(c.get("full_price") or c["price"])
    if ea_p <= 0 or full_p <= 0:
        raise SystemExit("ea_price and full_price must be > 0")
    first, ratio = rate(c.get("ea_first_month", 0.35), "ea_first_month"), float(c.get("full_vs_ea", 0.40))
    ratio = ratio / 100 if ratio > 1.5 else ratio
    net_at = lambda p: p * (1 - r["avg_discount"]) * (1 - r["vat_share"]) * (1 - r["refund"]) * (1 - r["steam_cut"]) * (1 - r["local_tax"])
    ne, nf = net_at(ea_p), net_at(full_p)
    rows = []
    for s_ in out["scenarios"]:
        m_copies = round(s_["copies"] * first)
        m_net = m_copies * ne
        f_net = m_net * ratio
        rows.append(dict(name=s_["name"], ea_year_net=round(s_["copies"] * ne, 2), ea_month_copies=m_copies, ea_month_net=round(m_net, 2),
                         full_month_net=round(f_net, 2), full_month_copies=round(f_net / nf) if nf else 0))
    return dict(ea_price=ea_p, full_price=full_p, net_per_copy_ea=round(ne, 2), net_per_copy_full=round(nf, 2), ea_first_month=first, full_vs_ea=ratio,
                breakeven_copies_ea=math.ceil(out["costs"]["total"] / ne) if out["costs"]["total"] > 0 else 0, scenarios=rows)


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
    ea = o.get("early_access")
    if ea:
        L += ["", "## Accesso anticipato (Early Access) e poi 1.0", "",
              f"Prezzo in EA {ea['ea_price']:.2f} (netto per copia {ea['net_per_copy_ea']:.2f}), prezzo alla 1.0 {ea['full_price']:.2f} (netto {ea['net_per_copy_full']:.2f}). "
              f"Break-even con il prezzo EA: **{ea['breakeven_copies_ea']}** copie.",
              f"Ipotesi: il mese di uscita in EA fa il {ea['ea_first_month']:.0%} delle copie dell'anno [OPINIONE]; il mese della 1.0 incassa il {ea['full_vs_ea']:.0%} del mese di uscita in EA "
              "(mediana GameDiscoverCo, dicembre 2025, 225 giochi usciti dall'EA [DA VERIFICARE]).", "",
              "| Scenario | Netto anno in EA | Copie mese EA | Netto mese EA | Netto mese 1.0 | Copie mese 1.0 |", "|---|---|---|---|---|---|"]
        L += [f"| {x['name']} | {x['ea_year_net']:.0f} | {x['ea_month_copies']} | {x['ea_month_net']:.0f} | {x['full_month_net']:.0f} | {x['full_month_copies']} |" for x in ea["scenarios"]]
        L += ["", "**L'uscita in EA è il lancio vero**: la 1.0 di solito porta meno del primo mese in EA, quindi l'EA va preparato come un lancio completo (pagina, wishlist, creator, prezzo)."]
    cb = o.get("calibrated")
    if cb:
        L += ["", f"## Scenari dal mercato reale ({cb['group']}, n = {cb['n']}) **[STIMA]**", "",
              f"Copie vendute a {cb['milestone'][1:]} giorni dall'uscita dai giochi reali di questa fascia usciti dal {cb['data_from']} al {cb['data_to']} "
              f"(calibrazione del {cb['generated_on']}, `cohort_bench.py`); copie = recensioni × 20..60. "
              + ("**Campione piccolo: solo indicativo.** " if cb.get("small_sample") else "")
              + "Non sostituiscono gli scenari da wishlist: sono il controllo con la realtà.", "",
              "| Scenario | Copie | Netto | Utile (cassa) |", "|---|---|---|---|"]
        L += [f"| {x['name']} | {x['copies_low']:,} … {x['copies_high']:,} | {x['net_low']:.0f} … {x['net_high']:.0f} | {x['profit_cash_low']:.0f} … {x['profit_cash_high']:.0f} |" for x in cb["scenarios"]]
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
    ap.add_argument("--ea-price", dest="ea_price", type=float, help="Early Access price: turns on the EA scenario")
    ap.add_argument("--full-price", dest="full_price", type=float, help="price at 1.0 (default --price)")
    ap.add_argument("--ea-first-month", dest="ea_first_month", help="share of year-1 copies sold in the EA launch month (default 0.35)")
    ap.add_argument("--full-vs-ea", dest="full_vs_ea", help="1.0 launch month revenue as a share of the EA launch month (default 0.40)")
    ap.add_argument("--calibration", nargs="?", const="auto", help="real-market base rates (default path ~/.game-launch-strategist/calibration.json)")
    ap.add_argument("--tier", help="tier of the game in the calibration (A/B/C, default B)"); ap.add_argument("--genre", help="genre bucket of the calibration, e.g. casual")
    ap.add_argument("-o", "--out", help="JSON output (also read by wl_track.py and status_page.py)"); ap.add_argument("--md", help="Markdown output file")
    a = ap.parse_args()
    c = dict(DEFAULTS)
    if a.config:
        c.update(load_json(a.config))
    c.update({k: v for k, v in vars(a).items() if k not in ("config", "out", "md", "calibration") and v is not None})
    if a.calibration:
        import os
        from common import user_dir
        cp = user_dir("calibration.json") if a.calibration == "auto" else a.calibration
        if os.path.exists(cp):
            c["calibration_data"] = load_json(cp)
        else:
            log(f"no calibration file at {cp}: run cohort_bench.py update + calibrate first (scenarios from wishlists only)")
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
