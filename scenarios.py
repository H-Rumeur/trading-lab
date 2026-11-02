"""
Liste de surveillance : tes scénarios "si le prix revient dans telle zone, j'achète".

Commandes :
  python scenarios.py                         → vérifie tous les scénarios
  python scenarios.py ajouter TICKER ZONE_BAS ZONE_HAUT STOP OBJECTIF --note "..."
  python scenarios.py supprimer TICKER

Exemple :
  python scenarios.py ajouter AAPL 305 310 298 341 --note "rebond sur support 302"
"""

import argparse
import os

import pandas as pd
import yfinance as yf

FICHIER = "scenarios.csv"
COLONNES = ["ticker", "zone_bas", "zone_haut", "stop", "objectif", "note"]
RATIO_MIN = 2


def charger():
    if os.path.exists(FICHIER):
        return pd.read_csv(FICHIER, dtype={"note": "object"})
    return pd.DataFrame(columns=COLONNES)


def ajouter(a):
    s = charger()
    if not (a.stop < a.zone_bas <= a.zone_haut < a.objectif):
        raise SystemExit("❌ Il faut : stop < zone bas ≤ zone haut < objectif")
    s = s[s["ticker"] != a.ticker.upper()]
    s.loc[len(s)] = [a.ticker.upper(), a.zone_bas, a.zone_haut, a.stop, a.objectif, a.note]
    s.to_csv(FICHIER, index=False)
    print(f"✅ Scénario {a.ticker.upper()} enregistré")


def supprimer(a):
    s = charger()
    s[s["ticker"] != a.ticker.upper()].to_csv(FICHIER, index=False)
    print(f"🗑️  Scénario {a.ticker.upper()} supprimé")


def verifier(_):
    s = charger()
    if s.empty:
        print("Aucun scénario. Ajoute-en un avec : python scenarios.py ajouter ...")
        return
    for _, sc in s.iterrows():
        h = yf.Ticker(sc["ticker"]).history(period="1y").dropna(subset=["Close"])
        if h.empty:
            print(f"\n{sc['ticker']} : pas de données")
            continue
        prix = h["Close"].iloc[-1]
        mm200 = h["Close"].rolling(200).mean().iloc[-1]
        ratio = (sc["objectif"] - prix) / (prix - sc["stop"]) if prix > sc["stop"] else 0

        print(f"\n=== {sc['ticker']} — {sc['note']} ===")
        print(f"Prix {prix:.2f} | zone {sc['zone_bas']}–{sc['zone_haut']} | "
              f"stop {sc['stop']} | objectif {sc['objectif']}")
        print(f"Tendance : {'haussière ✅' if prix > mm200 else 'sous la MM200 ❌'} (MM200 {mm200:.2f})")

        if prix <= sc["stop"]:
            print("❌ Le prix est passé sous le stop : scénario invalidé, à supprimer.")
        elif prix >= sc["objectif"]:
            print("⏭️  Le prix a dépassé l'objectif : l'occasion est passée.")
        elif sc["zone_bas"] <= prix <= sc["zone_haut"]:
            print(f"🔔 DANS LA ZONE ! Ratio actuel 1:{ratio:.1f}. "
                  "Refais l'analyse (étapes 1 à 3) avant d'ouvrir le trade dans journal.py.")
        else:
            cible = sc["zone_haut"] if prix > sc["zone_haut"] else sc["zone_bas"]
            ecart = (cible - prix) / prix
            print(f"⏳ Pas encore : il faut {ecart:+.1%} pour atteindre la zone "
                  f"(ratio actuel 1:{ratio:.1f}).")


def main():
    p = argparse.ArgumentParser(description="Surveillance des scénarios")
    sp = p.add_subparsers(dest="cmd")
    aj = sp.add_parser("ajouter")
    aj.add_argument("ticker")
    aj.add_argument("zone_bas", type=float)
    aj.add_argument("zone_haut", type=float)
    aj.add_argument("stop", type=float)
    aj.add_argument("objectif", type=float)
    aj.add_argument("--note", default="")
    aj.set_defaults(f=ajouter)
    su = sp.add_parser("supprimer")
    su.add_argument("ticker")
    su.set_defaults(f=supprimer)
    a = p.parse_args()
    (a.f if a.cmd else verifier)(a)


if __name__ == "__main__":
    main()
