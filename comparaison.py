"""
Comparaison de 3 approches sur le même ETF :
  1. Buy & hold        : acheter au début, ne plus toucher
  2. Filtre MM 200     : 100 % investi si le prix clôture au-dessus de sa
                         moyenne 200 jours, 100 % en cash sinon
  3. Croisement MM     : la stratégie de backtest.py (MM 20/50, risque 1 %)

Testée sur deux périodes : une longue avec des krachs (2000-2025)
et la récente (2015-2025), pour voir si le résultat dépend de la période.

Lancer :  .venv\\Scripts\\python.exe comparaison.py
"""

import math

import matplotlib.pyplot as plt

import backtest as bt

TICKER = "SPY"
PERIODES = [("2000-01-01", "2025-12-31"), ("2015-01-01", "2025-12-31")]
CAPITAL = 10_000
FRAIS = 2
MM_FILTRE = 200


def filtre_mm(df):
    """100 % investi au-dessus de la MM 200, cash en dessous.
    Signal calculé sur la clôture d'hier, exécuté à l'ouverture d'aujourd'hui."""
    mm = df["Close"].rolling(MM_FILTRE).mean()
    au_dessus = (df["Close"] > mm).shift(1, fill_value=False)

    cash, actions, nb_trades, equity = CAPITAL, 0, 0, []
    for i in range(len(df)):
        prix = df["Open"].iloc[i]
        if au_dessus.iloc[i] and actions == 0:
            actions = math.floor((cash - FRAIS) / prix)
            cash -= actions * prix + FRAIS
            nb_trades += 1
        elif not au_dessus.iloc[i] and actions > 0:
            cash += actions * prix - FRAIS
            actions = 0
        equity.append(cash + actions * df["Close"].iloc[i])
    return equity, nb_trades


def croisement(df):
    # on remet les réglages "de base" pour que la comparaison soit stable,
    # quels que soient tes essais dans backtest.py
    bt.CAPITAL, bt.FRAIS, bt.RISQUE_PCT = CAPITAL, FRAIS, 0.01
    bt.MM_COURTE, bt.MM_LONGUE, bt.JOURS_STOP = 20, 50, 20
    resultat, trades = bt.backtest(df)
    return resultat["equity"], len(trades)


def ligne(nom, courbe, nb_trades):
    fin = courbe.iloc[-1]
    annees = (courbe.index[-1] - courbe.index[0]).days / 365.25
    annuel = (fin / CAPITAL) ** (1 / annees) - 1
    print(f"{nom:<22}{fin:>12,.0f} €{fin / CAPITAL - 1:>+10.0%}{annuel:>+9.1%}/an"
          f"{bt.drawdown_max(courbe):>12.1%}{nb_trades:>8}")


def main():
    fig, axes = plt.subplots(len(PERIODES), 1, figsize=(11, 4.5 * len(PERIODES)))
    for ax, (debut, fin) in zip(axes, PERIODES):
        df = bt.telecharger(TICKER, debut, fin)
        bt.CAPITAL, bt.FRAIS = CAPITAL, FRAIS
        bh = bt.buy_and_hold(df)
        f_equity, f_trades = filtre_mm(df)
        f_courbe = bh.copy()
        f_courbe[:] = f_equity
        c_courbe, c_trades = croisement(df)

        print(f"\n=== {TICKER} du {df.index[0]:%d/%m/%Y} au {df.index[-1]:%d/%m/%Y} ===")
        print(f"{'Approche':<22}{'Final':>14}{'Total':>10}{'Par an':>12}{'Pire chute':>12}{'Achats':>8}")
        ligne("Buy & hold", bh, 1)
        ligne(f"Filtre MM {MM_FILTRE}", f_courbe, f_trades)
        ligne("Croisement MM 20/50", c_courbe, c_trades)

        ax.plot(bh.index, bh, label="Buy & hold")
        ax.plot(f_courbe.index, f_courbe, label=f"Filtre MM {MM_FILTRE}")
        ax.plot(c_courbe.index, c_courbe, label="Croisement MM 20/50 (risque 1 %)")
        ax.axhline(CAPITAL, color="gray", linestyle="--", linewidth=0.8)
        ax.set_yscale("log")
        ax.set_title(f"{TICKER} {debut[:4]}-{fin[:4]} : évolution de {CAPITAL:,} € (échelle log)")
        ax.set_ylabel("Capital (€)")
        ax.legend()
        ax.grid(alpha=0.3, which="both")

    plt.tight_layout()
    plt.savefig("comparaison.png", dpi=120)
    print("\nGraphique : comparaison.png")


if __name__ == "__main__":
    main()
