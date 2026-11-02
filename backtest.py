"""
Backtester simple : croisement de moyennes mobiles + gestion du risque (leçon 3).

Stratégie testée :
  - ACHAT  quand la moyenne courte croise AU-DESSUS de la moyenne longue
  - VENTE  quand elle recroise EN DESSOUS, ou si le stop loss est touché
  - Stop loss = plus bas des N derniers jours (≈ dernier support, leçon 4)
  - Taille de position = formule de la leçon 3 (risque 1 % du capital)

On compare avec "acheter au début et ne plus toucher" (buy & hold).

Lancer :  .venv\\Scripts\\python.exe backtest.py
"""

import math

import matplotlib.pyplot as plt
import pandas as pd
import yfinance as yf

# ----------------------------------------------------------------------------
# PARAMÈTRES : c'est ici que tu joues
# ----------------------------------------------------------------------------
TICKER = "AAPL"          # SPY = ETF S&P 500 (les 500 plus grosses entreprises US)
DEBUT = "2015-01-01"
FIN = "2025-12-31"
CAPITAL = 10_000        # capital de départ
RISQUE_PCT = 0.01      # 1 % de risque par trade
FRAIS = 2               # frais par ordre (achat OU vente)
MM_COURTE = 50
MM_LONGUE = 200
JOURS_STOP = 20         # stop = plus bas des 20 derniers jours


def telecharger(ticker, debut, fin):
    df = yf.download(ticker, start=debut, end=fin, auto_adjust=True,
                     progress=False, multi_level_index=False)
    if df.empty:
        raise SystemExit(f"Aucune donnée pour {ticker}")
    return df[["Open", "High", "Low", "Close"]]


def backtest(df):
    df = df.copy()
    df["mm_courte"] = df["Close"].rolling(MM_COURTE).mean()
    df["mm_longue"] = df["Close"].rolling(MM_LONGUE).mean()
    df["plus_bas"] = df["Low"].rolling(JOURS_STOP).min()

    au_dessus = df["mm_courte"] > df["mm_longue"]
    df["croise_haut"] = au_dessus & ~au_dessus.shift(1, fill_value=False)
    df["croise_bas"] = ~au_dessus & au_dessus.shift(1, fill_value=False)

    cash, actions, stop, prix_achat = CAPITAL, 0, None, None
    trades, equity = [], []

    for i in range(len(df)):
        jour = df.iloc[i]
        hier = df.iloc[i - 1] if i > 0 else None

        # --- On est en position : stop loss ou signal de sortie ? ---
        if actions > 0:
            prix_vente, raison = None, None
            if jour["Low"] <= stop:
                # si le marché ouvre déjà sous le stop, on vend au prix d'ouverture
                prix_vente, raison = min(jour["Open"], stop), "stop loss"
            elif hier["croise_bas"]:
                prix_vente, raison = jour["Open"], "croisement baissier"

            if prix_vente is not None:
                cash += actions * prix_vente - FRAIS
                gain = (prix_vente - prix_achat) * actions - 2 * FRAIS
                trades.append({"entree": entree_date, "sortie": df.index[i],
                               "achat": prix_achat, "vente": prix_vente,
                               "actions": actions, "gain": gain, "raison": raison})
                actions = 0

        # --- On n'est pas en position : signal d'achat hier ? ---
        elif hier is not None and hier["croise_haut"] and not pd.isna(hier["plus_bas"]):
            prix = jour["Open"]
            stop_prevu = hier["plus_bas"]
            risque_par_action = prix - stop_prevu
            if risque_par_action > 0:
                risque_accepte = cash * RISQUE_PCT                      # ligne 1
                nb = math.floor(risque_accepte / risque_par_action)     # lignes 2-3
                nb = min(nb, math.floor((cash - FRAIS) / prix))         # pas plus que le cash dispo
                if nb > 0:
                    cash -= nb * prix + FRAIS
                    actions, stop, prix_achat = nb, stop_prevu, prix
                    entree_date = df.index[i]

        equity.append(cash + actions * jour["Close"])

    df["equity"] = equity
    return df, pd.DataFrame(trades)


def buy_and_hold(df):
    nb = math.floor((CAPITAL - FRAIS) / df["Open"].iloc[0])
    reste = CAPITAL - FRAIS - nb * df["Open"].iloc[0]
    return reste + nb * df["Close"]


def drawdown_max(courbe):
    return (courbe / courbe.cummax() - 1).min()


def main():
    df = telecharger(TICKER, DEBUT, FIN)
    df, trades = backtest(df)
    bh = buy_and_hold(df)

    fin_strat, fin_bh = df["equity"].iloc[-1], bh.iloc[-1]
    print(f"\n=== {TICKER} du {df.index[0]:%d/%m/%Y} au {df.index[-1]:%d/%m/%Y} ===")
    print(f"Capital de départ        : {CAPITAL:>10,.0f} €")
    print("\n--- Stratégie croisement de moyennes ---")
    print(f"Capital final            : {fin_strat:>10,.0f} €  ({fin_strat / CAPITAL - 1:+.1%})")
    print(f"Nombre de trades         : {len(trades):>10}")
    if len(trades):
        gagnants = trades[trades["gain"] > 0]
        print(f"Trades gagnants          : {len(gagnants) / len(trades):>10.0%}")
        print(f"Gain moyen (gagnants)    : {gagnants['gain'].mean():>10,.0f} €")
        print(f"Perte moy. (perdants)    : {trades[trades['gain'] <= 0]['gain'].mean():>10,.0f} €")
        print(f"Frais payés au total     : {len(trades) * 2 * FRAIS:>10,.0f} €")
        print(f"Sorties par stop loss    : {(trades['raison'] == 'stop loss').sum():>10}")
    print(f"Pire chute (drawdown)    : {drawdown_max(df['equity']):>10.1%}")
    print("\n--- Buy & hold (acheter et ne plus toucher) ---")
    print(f"Capital final            : {fin_bh:>10,.0f} €  ({fin_bh / CAPITAL - 1:+.1%})")
    print(f"Pire chute (drawdown)    : {drawdown_max(bh):>10.1%}")

    trades.to_csv("trades.csv", index=False)

    plt.figure(figsize=(11, 5))
    plt.plot(df.index, df["equity"], label="Stratégie (croisement MM)")
    plt.plot(df.index, bh, label="Buy & hold")
    plt.axhline(CAPITAL, color="gray", linestyle="--", linewidth=0.8)
    plt.title(f"{TICKER} : évolution de {CAPITAL:,} €")
    plt.ylabel("Capital (€)")
    plt.legend()
    plt.grid(alpha=0.3)
    plt.tight_layout()
    plt.savefig("resultat.png", dpi=120)
    print("\nGraphique : resultat.png   |   Détail des trades : trades.csv")


if __name__ == "__main__":
    main()
