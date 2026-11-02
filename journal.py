"""
Journal de paper trading (argent fictif, vrais prix).

Commandes :
  ouvrir  TICKER STOP OBJECTIF --raison "..."   → calcule la position (leçon 3) et l'enregistre
  verifier                                       → met à jour les trades ouverts (stop / objectif touchés ?)
  fermer  ID                                     → ferme un trade au prix actuel
  bilan                                          → statistiques de tous tes trades

Exemples :
  .venv\\Scripts\\python.exe journal.py ouvrir SPY 640 700 --raison "rebond sur support, au-dessus MM200"
  .venv\\Scripts\\python.exe journal.py verifier
"""

import argparse
import math
import os
from datetime import date, timedelta

import pandas as pd
import yfinance as yf

FICHIER = "journal.csv"
CAPITAL_DEPART = 10_000
RISQUE_PCT = 0.01
FRAIS = 2
RATIO_MIN = 2
COLONNES = ["id", "ticker", "date_entree", "prix_entree", "stop", "objectif", "actions",
            "raison", "statut", "date_sortie", "prix_sortie", "gain", "commentaire"]


def charger():
    if os.path.exists(FICHIER):
        texte = {c: "object" for c in ["raison", "statut", "date_sortie", "commentaire"]}
        return pd.read_csv(FICHIER, dtype=texte)
    return pd.DataFrame(columns=COLONNES)


def sauver(j):
    j.to_csv(FICHIER, index=False)


def capital_actuel(j):
    return CAPITAL_DEPART + j.loc[j["statut"] == "ferme", "gain"].sum()


def dernier_prix(ticker):
    h = yf.Ticker(ticker).history(period="5d").dropna(subset=["Close"])
    if h.empty:
        raise SystemExit(f"Ticker inconnu ou pas de données : {ticker}")
    return float(h["Close"].iloc[-1])


def fermer_trade(j, idx, prix, commentaire):
    t = j.loc[idx]
    j.loc[idx, ["statut", "date_sortie", "prix_sortie", "commentaire"]] = \
        ["ferme", date.today().isoformat(), round(prix, 2), commentaire]
    j.loc[idx, "gain"] = round((prix - t["prix_entree"]) * t["actions"] - 2 * FRAIS, 2)
    print(f"  #{t['id']} {t['ticker']} fermé à {prix:.2f} ({commentaire}) → {j.loc[idx, 'gain']:+.2f} €")


def ouvrir(args):
    j = charger()
    ticker = args.ticker.upper()
    prix = args.prix or dernier_prix(ticker)
    capital = capital_actuel(j)

    risque_accepte = capital * RISQUE_PCT
    risque_action = prix - args.stop
    gain_action = args.objectif - prix
    print(f"\nPrix actuel {ticker} : {prix:.2f}")
    print(f"1. Risque accepté  = {capital:,.0f} × {RISQUE_PCT:.0%} = {risque_accepte:.2f} €")
    print(f"2. Risque / action = {prix:.2f} − {args.stop:.2f} = {risque_action:.2f}")
    if risque_action <= 0 or gain_action <= 0:
        raise SystemExit("❌ Le stop doit être SOUS le prix et l'objectif AU-DESSUS.")
    nb = math.floor(risque_accepte / risque_action)
    nb = min(nb, math.floor((capital - FRAIS) / prix))
    ratio = gain_action / risque_action
    print(f"3. Nb d'actions    = {risque_accepte:.2f} ÷ {risque_action:.2f} → {nb}")
    print(f"4. Gain / action   = {args.objectif:.2f} − {prix:.2f} = {gain_action:.2f}")
    print(f"5. Ratio           = 1:{ratio:.1f}")

    if ratio < RATIO_MIN:
        raise SystemExit(f"❌ Trade refusé : ratio < 1:{RATIO_MIN} (règle n°2).")
    if nb == 0:
        raise SystemExit("❌ Trade refusé : stop trop loin, 0 action possible.")
    if not args.raison:
        raise SystemExit('❌ Écris pourquoi tu prends ce trade : --raison "..."')

    nouvel_id = int(j["id"].max()) + 1 if len(j) else 1
    j.loc[len(j)] = [nouvel_id, ticker, date.today().isoformat(), round(prix, 2), args.stop,
                     args.objectif, nb, args.raison, "ouvert", None, None, None, None]
    sauver(j)
    print(f"\n✅ Trade #{nouvel_id} ouvert : {nb} × {ticker} à {prix:.2f} (investi {nb * prix:,.0f} €)")


def verifier(args):
    j = charger()
    ouverts = j[j["statut"] == "ouvert"]
    if ouverts.empty:
        print("Aucun trade ouvert.")
        return
    for idx, t in ouverts.iterrows():
        # on commence le lendemain de l'entrée : avant l'achat, le stop ne compte pas
        lendemain = date.fromisoformat(t["date_entree"]) + timedelta(days=1)
        h = yf.Ticker(t["ticker"]).history(start=lendemain) if lendemain <= date.today() else pd.DataFrame()
        if h.empty:
            prix = dernier_prix(t["ticker"])
            latent = (prix - t["prix_entree"]) * t["actions"]
            print(f"  #{t['id']} {t['ticker']} : ouvert aujourd'hui, actuel {prix:.2f} → latent {latent:+.2f} €")
            continue
        # on regarde jour par jour si le stop ou l'objectif a été touché depuis l'entrée
        for _, jour in h.iterrows():
            if jour["Low"] <= t["stop"]:
                fermer_trade(j, idx, min(jour["Open"], t["stop"]), "stop loss")
                break
            if jour["High"] >= t["objectif"]:
                fermer_trade(j, idx, max(jour["Open"], t["objectif"]), "objectif atteint")
                break
        else:
            prix = float(h["Close"].iloc[-1])
            latent = (prix - t["prix_entree"]) * t["actions"]
            print(f"  #{t['id']} {t['ticker']} : entrée {t['prix_entree']:.2f}, actuel {prix:.2f}, "
                  f"stop {t['stop']}, objectif {t['objectif']} → latent {latent:+.2f} €")
    sauver(j)


def fermer(args):
    j = charger()
    idx = j.index[(j["id"] == args.id) & (j["statut"] == "ouvert")]
    if idx.empty:
        raise SystemExit(f"Pas de trade ouvert #{args.id}")
    t = j.loc[idx[0]]
    fermer_trade(j, idx[0], args.prix or dernier_prix(t["ticker"]), args.commentaire or "fermeture manuelle")
    sauver(j)


def bilan(args):
    j = charger()
    fermes = j[j["statut"] == "ferme"]
    print(f"\nCapital fictif : {capital_actuel(j):,.2f} € (départ {CAPITAL_DEPART:,} €)")
    print(f"Trades ouverts : {(j['statut'] == 'ouvert').sum()}   |   fermés : {len(fermes)}")
    if fermes.empty:
        return
    gagnants = fermes[fermes["gain"] > 0]
    perdants = fermes[fermes["gain"] <= 0]
    print(f"Taux de réussite : {len(gagnants) / len(fermes):.0%}")
    if len(gagnants):
        print(f"Gain moyen       : {gagnants['gain'].mean():+.2f} €")
    if len(perdants):
        print(f"Perte moyenne    : {perdants['gain'].mean():+.2f} €")
    print(f"Total            : {fermes['gain'].sum():+.2f} €")
    print("\nDerniers trades :")
    print(fermes.tail(10)[["id", "ticker", "prix_entree", "prix_sortie", "gain", "commentaire"]]
          .to_string(index=False))


def main():
    p = argparse.ArgumentParser(description="Journal de paper trading")
    sp = p.add_subparsers(dest="cmd", required=True)

    o = sp.add_parser("ouvrir")
    o.add_argument("ticker")
    o.add_argument("stop", type=float)
    o.add_argument("objectif", type=float)
    o.add_argument("--raison", default="")
    o.add_argument("--prix", type=float, help="prix d'entrée (par défaut : dernier prix)")
    o.set_defaults(f=ouvrir)

    sp.add_parser("verifier").set_defaults(f=verifier)

    f = sp.add_parser("fermer")
    f.add_argument("id", type=int)
    f.add_argument("--prix", type=float)
    f.add_argument("--commentaire", default="")
    f.set_defaults(f=fermer)

    sp.add_parser("bilan").set_defaults(f=bilan)

    args = p.parse_args()
    args.f(args)


if __name__ == "__main__":
    main()
