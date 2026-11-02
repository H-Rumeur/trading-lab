"""
Analyse pas à pas d'un titre : tendance (MM 50/200), niveaux (support/résistance), timing (RSI).
Dessine un graphique annoté et affiche la checklist dans le terminal.

Exemples :
  python analyse.py SPY
  python analyse.py SPY --support 757 --resistance 776
  python analyse.py SPY --support 757 --resistance 776 --stop 746 --objectif 775
  python analyse.py MC.PA --exercice      (graphique sans les réponses, pour t'entraîner)

Sans --support / --resistance, on prend le plus bas / plus haut des 40 derniers jours.
"""

import argparse
import math

import matplotlib.pyplot as plt
import yfinance as yf

JOURS_AFFICHES = 120
JOURS_NIVEAUX = 40
CAPITAL = 10_000
RISQUE_PCT = 0.01


def rsi(close, n=14):
    delta = close.diff()
    hausse = delta.clip(lower=0).ewm(alpha=1 / n, adjust=False).mean()
    baisse = (-delta.clip(upper=0)).ewm(alpha=1 / n, adjust=False).mean()
    return 100 - 100 / (1 + hausse / baisse)


def bougies(ax, df):
    for i, (_, j) in enumerate(df.iterrows()):
        couleur = "#3B8C3B" if j["Close"] >= j["Open"] else "#D04040"
        ax.vlines(i, j["Low"], j["High"], color=couleur, linewidth=0.8)
        bas, haut = sorted([j["Open"], j["Close"]])
        ax.add_patch(plt.Rectangle((i - 0.35, bas), 0.7, max(haut - bas, 0.01),
                                   color=couleur))


def main():
    p = argparse.ArgumentParser()
    p.add_argument("ticker")
    p.add_argument("--support", type=float)
    p.add_argument("--resistance", type=float)
    p.add_argument("--stop", type=float)
    p.add_argument("--objectif", type=float)
    p.add_argument("--exercice", action="store_true",
                   help="cache les réponses (tendance, niveaux, RSI) pour s'entraîner")
    a = p.parse_args()
    ticker = a.ticker.upper()

    df = yf.Ticker(ticker).history(period="2y").dropna(subset=["Close"])
    if df.empty:
        raise SystemExit(f"Pas de données pour {ticker}")
    df["mm50"] = df["Close"].rolling(50).mean()
    df["mm200"] = df["Close"].rolling(200).mean()
    df["rsi"] = rsi(df["Close"])
    recent = df.tail(JOURS_NIVEAUX)
    support = a.support or recent["Low"].min()
    resistance = a.resistance or recent["High"].max()
    vue = df.tail(JOURS_AFFICHES)
    d = vue.iloc[-1]
    prix = d["Close"]

    # ------------------------------------------------------------- terminal
    tendance = "HAUSSIÈRE" if prix > d["mm200"] and d["mm50"] > d["mm200"] else \
               "BAISSIÈRE" if prix < d["mm200"] and d["mm50"] < d["mm200"] else "INDÉCISE"
    position = (prix - support) / (resistance - support)
    print(f"\n=== Analyse {ticker} au {vue.index[-1]:%d/%m/%Y} — prix {prix:.2f} ===")
    if a.exercice:
        print("Mode exercice : les réponses sont cachées, à toi de faire les étapes !")
    else:
        print(f"1. Tendance : prix {prix:.2f} | MM50 {d['mm50']:.2f} | MM200 {d['mm200']:.2f} → {tendance}")
        print(f"2. Niveaux  : support {support:.2f} | résistance {resistance:.2f} "
              f"→ le prix est à {position:.0%} du chemin entre les deux")
        print(f"3. RSI      : {d['rsi']:.0f} → " + ("suracheté" if d["rsi"] > 70 else
                                                   "survendu" if d["rsi"] < 30 else "neutre"))
    if a.stop and a.objectif:
        r_action, g_action = prix - a.stop, a.objectif - prix
        if r_action <= 0 or g_action <= 0:
            print("4. Calcul   : stop doit être sous le prix, objectif au-dessus")
        else:
            risque = CAPITAL * RISQUE_PCT
            print(f"4. Calcul   : risque {risque:.0f} € | risque/action {r_action:.2f} | "
                  f"{math.floor(risque / r_action)} actions | gain/action {g_action:.2f} | "
                  f"ratio 1:{g_action / r_action:.1f} → " +
                  ("OK" if g_action / r_action >= 2 else "REFUSÉ (< 1:2)"))

    # ------------------------------------------------------------- graphique
    fig, (ax, ax2) = plt.subplots(2, 1, figsize=(12, 7.5), sharex=True,
                                  gridspec_kw={"height_ratios": [3, 1]})
    x = range(len(vue))
    xl = int(len(vue) * 0.12)  # position des étiquettes de niveaux
    bougies(ax, vue)
    ax.plot(x, vue["mm50"], color="#E08A00", linewidth=1.6, label="MM 50 jours")
    ax.plot(x, vue["mm200"], color="#7F77DD", linewidth=1.6, label="MM 200 jours")
    if not a.exercice or a.resistance:
        ax.axhline(resistance, color="#D04040", linestyle="--", linewidth=1.2)
        ax.text(xl, resistance, f" Résistance {resistance:.0f}", color="#D04040", va="bottom", fontsize=10)
    if not a.exercice or a.support:
        ax.axhline(support, color="#3B8C3B", linestyle="--", linewidth=1.2)
        ax.text(xl, support, f" Support {support:.0f}", color="#3B8C3B", va="bottom", fontsize=10)
    if a.stop:
        ax.axhline(a.stop, color="black", linestyle=":", linewidth=1)
        ax.text(xl, a.stop, f" Stop {a.stop:.0f}", va="top", fontsize=9)
    if a.objectif:
        ax.axhline(a.objectif, color="#185FA5", linestyle=":", linewidth=1)
        ax.text(xl, a.objectif, f" Objectif {a.objectif:.0f}", color="#185FA5", va="top", fontsize=9)

    # étiquette du prix : en dessous s'il est dans le haut du graphique, au-dessus sinon
    en_haut = prix > (vue["Low"].min() + vue["High"].max()) / 2
    ax.annotate(f"Prix actuel {prix:.0f}", xy=(len(vue) - 1, prix), textcoords="offset points",
                xytext=(-140, -50 if en_haut else 50), arrowprops={"arrowstyle": "->"},
                fontsize=10, va="center")

    if not a.exercice:
        encadre = {"boxstyle": "round", "facecolor": "white", "alpha": 0.9}
        # encadrés là où le prix ne passe pas : en bas si haussier, en haut sinon
        y1, y2, va = (0.16, 0.07, "bottom") if tendance == "HAUSSIÈRE" else (0.95, 0.86, "top")
        texte1 = f"① Tendance {tendance.lower()}"
        if tendance == "HAUSSIÈRE":
            texte1 += " : prix et MM50 au-dessus de la MM200"
        elif tendance == "BAISSIÈRE":
            texte1 += " : prix et MM50 sous la MM200"
        ax.text(0.35, y1, texte1, transform=ax.transAxes, va=va, fontsize=10, bbox=encadre)
        ax.text(0.35, y2, f"② Prix à {position:.0%} entre support et résistance",
                transform=ax.transAxes, va=va, fontsize=10, bbox=encadre)
        ax2.text(0.01, 0.92, f"③ RSI {d['rsi']:.0f}", transform=ax2.transAxes, va="top",
                 fontsize=10, bbox=encadre)
    ax.set_title(f"{ticker} — {JOURS_AFFICHES} derniers jours")
    ax.legend(loc="best")
    ax.grid(alpha=0.25)

    ax2.plot(x, vue["rsi"], color="#185FA5")
    ax2.axhline(70, color="#D04040", linestyle="--", linewidth=0.8)
    ax2.axhline(30, color="#3B8C3B", linestyle="--", linewidth=0.8)
    ax2.set_ylim(0, 100)
    ax2.set_ylabel("RSI")
    ax2.grid(alpha=0.25)
    pas = max(len(vue) // 8, 1)
    ax2.set_xticks(list(x)[::pas])
    ax2.set_xticklabels([f"{dt:%d/%m}" for dt in vue.index[::pas]])

    plt.tight_layout()
    fichier = f"analyse_{ticker}{'_exercice' if a.exercice else ''}.png"
    plt.savefig(fichier, dpi=120)
    print(f"\nGraphique : {fichier}")


if __name__ == "__main__":
    main()
