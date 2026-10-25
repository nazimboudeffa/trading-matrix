"""Construction du contexte et du prompt envoyés à l'IA pour un signal.

Le contexte ne contient **que** les bougies disponibles jusqu'à la bougie du
signal incluse : aucune donnée future n'est transmise au modèle.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import pandas as pd

from strategies.base import Side, Signal
from strategies.price_action.structure import find_swings, get_trend
from strategies.utils import atr

DEFAULT_CANDLES = 40

SYSTEM_PROMPT = """\
Tu es un analyste de marché expérimenté, spécialisé dans le price action \
(structure de marché, order blocks, réactions sur bougies : engulfing, pinbar) \
et dans la gestion du risque.

Tu analyses un signal produit par une stratégie algorithmique afin d'aider un \
trader à le confronter à son propre jugement.

Règles que tu dois respecter :
- Appuie-toi uniquement sur les données fournies dans la demande. Si une \
information manque, dis-le explicitement au lieu de l'inventer.
- N'invente aucun prix, aucune actualité, aucun indicateur et aucune donnée \
macroéconomique.
- Sois critique : un signal algorithmique n'est pas une opportunité par défaut.
- Si le signal est marqué « EN ATTENTE », il s'agit d'un setup conditionnel non \
déclenché : évalue la probabilité que sa condition se réalise et ne le traite \
jamais comme une entrée acquise.
- Raisonne en R (multiples du risque) à partir de l'entrée, du stop loss et des \
objectifs fournis.
- Ne modifie pas les niveaux du signal sans expliquer clairement pourquoi.
- Ton analyse est éducative et ne constitue pas un conseil en investissement.

Réponds en français, en Markdown, avec des sections courtes, un verdict \
explicite et des niveaux de prix précis."""


@dataclass(frozen=True)
class AIPrompt:
    """Prompt prêt à envoyer, avec sa représentation lisible pour l'UI."""

    system: str
    user: str

    @property
    def messages(self) -> list[dict[str, str]]:
        return [
            {"role": "system", "content": self.system},
            {"role": "user", "content": self.user},
        ]

    def display_text(self) -> str:
        return (
            "=== RÔLE SYSTÈME ===\n"
            f"{self.system}\n\n"
            "=== DEMANDE (texte exact envoyé au modèle) ===\n"
            f"{self.user}"
        )


def _finite(value) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _price(value: float | None) -> str:
    number = _finite(value)
    if number is None:
        return "n/d"
    absolute = abs(number)
    if absolute < 1:
        return f"{number:.5f}"
    if absolute < 100:
        return f"{number:.3f}"
    return f"{number:.2f}"


def _pct_change(level: float | None, reference: float) -> str:
    number = _finite(level)
    if number is None or reference == 0:
        return ""
    return f" ({((number - reference) / reference) * 100:+.2f} %)"


def _side_label(side: Side) -> str:
    if side is Side.LONG:
        return "LONG (achat)"
    if side is Side.SHORT:
        return "SHORT (vente)"
    return side.value


def find_bar_index(df: pd.DataFrame, timestamp) -> int | None:
    """Retourne la position de la bougie du signal (ou la plus proche)."""
    if df is None or len(df) == 0:
        return None
    try:
        position = int(df.index.searchsorted(timestamp))
    except (TypeError, ValueError):
        return None
    for candidate in (position, position - 1):
        if 0 <= candidate < len(df) and df.index[candidate] == timestamp:
            return candidate
    try:
        return int(abs(df.index - timestamp).argmin())
    except (TypeError, ValueError):
        return None


def _candles_table(window: pd.DataFrame) -> str:
    header = (
        f"{'Date':<17}| {'Open':>10} | {'High':>10} | {'Low':>10} | "
        f"{'Close':>10} | {'Volume':>14}"
    )
    separator = (
        f"{'-' * 17}+{'-' * 12}+{'-' * 12}+{'-' * 12}+{'-' * 12}+{'-' * 16}"
    )
    lines = [header, separator]
    for timestamp, row in window.iterrows():
        volume = _finite(row.get("Volume"))
        volume_text = "-" if volume is None else f"{volume:,.0f}".replace(",", " ")
        lines.append(
            f"{timestamp:%Y-%m-%d %H:%M} | "
            f"{_price(row.get('Open')):>10} | "
            f"{_price(row.get('High')):>10} | "
            f"{_price(row.get('Low')):>10} | "
            f"{_price(row.get('Close')):>10} | "
            f"{volume_text:>14}"
        )
    return "\n".join(lines)


def _moving_average(series: pd.Series, period: int) -> float | None:
    if len(series) < period:
        return None
    value = series.iloc[-period:].mean()
    return _finite(value)


def build_signal_prompt(
    sig: Signal,
    df: pd.DataFrame,
    *,
    symbol: str = "",
    timeframe: str = "",
    strategy_name: str = "",
    strategy_description: str = "",
    candles: int = DEFAULT_CANDLES,
) -> AIPrompt:
    """Construit le prompt d'analyse d'un signal (données passées uniquement)."""
    symbol = symbol or str(sig.meta.get("symbol") or "")
    timeframe = timeframe or str(sig.meta.get("timeframe") or "")
    strategy_name = strategy_name or str(sig.meta.get("strategy_name") or "")
    index = find_bar_index(df, sig.time)
    pending = bool(sig.meta.get("pending"))

    lines: list[str] = ["## Signal à analyser", ""]
    lines.append(f"- Symbole : {symbol or 'non renseigné'}")
    lines.append(f"- Unité de temps : {timeframe or 'non renseignée'}")
    lines.append(f"- Date / heure du signal : {sig.time:%Y-%m-%d %H:%M}")
    if pending:
        lines.append(
            "- Bougie de référence : dernière bougie disponible — le setup se "
            "déclencherait sur une bougie ultérieure"
        )
    lines.append(f"- Sens : {_side_label(sig.side)}")
    lines.append(f"- Type de setup : {sig.setup_type}")
    if pending:
        lines.append("- Statut : EN ATTENTE — setup conditionnel, non déclenché")
        condition = sig.meta.get("condition")
        if condition:
            lines.append(f"- Condition de déclenchement : {condition}")
        entry_mode = sig.meta.get("entry_mode")
        if entry_mode == "limite":
            lines.append(
                "- Entrée prévue : ordre limite dans la zone, si le prix y revient"
            )
        elif entry_mode == "confirmation":
            lines.append(
                "- Entrée prévue : à la clôture d'une bougie de réaction dans la zone"
            )
        distance = _finite(sig.meta.get("distance_pct"))
        if distance is not None:
            lines.append(f"- Distance du prix à l'entrée prévue : {distance:.2f} %")
    else:
        lines.append("- Statut : signal confirmé (bougie de réaction clôturée)")
    if strategy_name:
        lines.append(f"- Stratégie d'origine : {strategy_name}")
    lines.append(f"- Prix d'entrée : {_price(sig.entry)}")
    lines.append(f"- Stop Loss : {_price(sig.sl)}{_pct_change(sig.sl, sig.entry)}")
    lines.append(f"- TP1 : {_price(sig.tp1)}{_pct_change(sig.tp1, sig.entry)}")
    if sig.tp2 is not None:
        lines.append(f"- TP2 : {_price(sig.tp2)}{_pct_change(sig.tp2, sig.entry)}")

    rr = _finite(sig.meta.get("rr"))
    if rr is None:
        risk = abs(sig.entry - sig.sl)
        rr = abs(sig.tp1 - sig.entry) / risk if risk > 0 else None
    if rr is not None:
        lines.append(f"- Ratio risque / rendement (TP1) : {rr:.2f} R")
    lines.append(f"- Score de confluence de la stratégie : {sig.confidence} / 100")

    if sig.zone_price_low is not None and sig.zone_price_high is not None:
        lines.append(
            f"- Order Block d'origine : {_price(sig.zone_price_low)} → "
            f"{_price(sig.zone_price_high)}"
        )
    if sig.reason:
        lines.append("- Raisons du signal : " + " | ".join(sig.reason))
    if strategy_description:
        lines.append(f"- Règles de la stratégie : {strategy_description}")

    lines.extend(["", "## Contexte de marché", ""])

    if index is None or df is None or len(df) == 0:
        lines.append(
            "Les données OHLCV ne sont pas disponibles pour ce signal : "
            "tu ne peux pas analyser la structure de marché."
        )
    else:
        start = max(0, index - max(1, candles) + 1)
        window = df.iloc[start : index + 1]
        if pending:
            lines.append(
                f"{len(window)} dernières bougies, jusqu'à la dernière bougie "
                "disponible incluse (la dernière ligne du tableau). Le signal est "
                "conditionnel : aucune donnée future n'est fournie, le déclenchement "
                "dépendra des bougies à venir."
            )
        else:
            lines.append(
                f"{len(window)} dernières bougies, jusqu'à la bougie du signal incluse "
                "(la dernière ligne du tableau correspond au signal). Aucune donnée "
                "postérieure au signal n'est fournie."
            )
        lines.append("")
        lines.append("```text")
        lines.append(_candles_table(window))
        lines.append("```")

        history = df.iloc[: index + 1]
        row = df.iloc[index]
        open_price = _finite(row.get("Open"))
        high = _finite(row.get("High"))
        low = _finite(row.get("Low"))
        close = _finite(row.get("Close"))
        signal_atr = _finite(sig.meta.get("atr"))
        if signal_atr is None:
            try:
                signal_atr = _finite(atr(history, 14).iloc[-1])
            except (KeyError, IndexError):
                signal_atr = None

        lines.extend(["", "## Indicateurs et lecture technique au moment du signal", ""])
        if signal_atr is not None:
            atr_pct = (signal_atr / close * 100) if close else None
            suffix = f" ({atr_pct:.2f} % du prix)" if atr_pct is not None else ""
            lines.append(f"- ATR(14) : {_price(signal_atr)}{suffix}")
        sma20 = _moving_average(history["Close"], 20)
        sma50 = _moving_average(history["Close"], 50)
        sma200 = _moving_average(history["Close"], 200)
        for period, value in ((20, sma20), (50, sma50), (200, sma200)):
            if value is not None:
                position = "au-dessus" if close is not None and close >= value else "en dessous"
                lines.append(f"- SMA({period}) : {_price(value)} — prix {position}")

        recent = history.iloc[-20:]
        recent_high = _finite(recent["High"].max())
        recent_low = _finite(recent["Low"].min())
        if recent_high is not None and recent_low is not None:
            lines.append(
                f"- Plus haut / plus bas des 20 dernières bougies : "
                f"{_price(recent_high)} / {_price(recent_low)}"
            )
        try:
            trend = get_trend(find_swings(history, 3, 3))
        except (KeyError, IndexError, ValueError):
            trend = "n/d"
        lines.append(f"- Tendance de structure (swings 3/3) : {trend}")

        if None not in (open_price, high, low, close) and high > low:
            body = abs(close - open_price)
            upper_wick = high - max(open_price, close)
            lower_wick = min(open_price, close) - low
            total = high - low
            lines.append(
                "- Bougie du signal : "
                f"corps {body / total * 100:.0f} % de la mèche totale, "
                f"mèche haute {upper_wick / total * 100:.0f} %, "
                f"mèche basse {lower_wick / total * 100:.0f} %"
            )

    if pending:
        work = [
            (
                "1. **Verdict** : ce setup conditionnel est-il pertinent, à surveiller "
                "ou à écarter ? Donne un niveau de confiance (faible / moyen / élevé) et "
                "justifie-le."
            ),
            (
                "2. **Lecture de la structure** : décris la tendance, les swings, la "
                "position du prix par rapport à l'Order Block et la probabilité que le "
                "prix atteigne la zone d'entrée."
            ),
            (
                "3. **Qualité de la confluence** : évalue l'alignement entre structure, "
                "zone, type de réaction attendu et ratio risque / rendement."
            ),
            (
                "4. **Risques** : identifie les scénarios défavorables, ce qui invaliderait "
                "le setup avant même son déclenchement, et le niveau exact à surveiller."
            ),
            (
                "5. **Plan conditionnel** : explique comment placer l'ordre (limite ou "
                "attente de confirmation), où placer le stop et comment gérer les objectifs."
            ),
            (
                "6. **Points d'attention** : liste ce qu'il faudrait vérifier avant "
                "d'agir (contexte supérieur, liquidité, news, session...)."
            ),
            (
                "7. **Condition de déclenchement** : reformule précisément ce qui doit se "
                "passer dans les prochaines bougies pour valider ou annuler le setup, sans "
                "inventer de données futures."
            ),
        ]
    else:
        work = [
            (
                "1. **Verdict** : le signal est-il favorable, à surveiller ou à écarter ? "
                "Donne un niveau de confiance (faible / moyen / élevé) et justifie-le."
            ),
            (
                "2. **Lecture de la structure** : décris la tendance, les swings et la "
                "position du prix par rapport à l'Order Block."
            ),
            (
                "3. **Qualité de la confluence** : évalue l'alignement entre structure, "
                "zone, réaction price action et ratio risque / rendement."
            ),
            (
                "4. **Risques** : identifie les scénarios défavorables et le niveau exact "
                "qui invaliderait le signal."
            ),
            (
                "5. **Plan de gestion** : comment gérer l'entrée, le stop et les objectifs "
                "(partiels, trailing, conservation des niveaux)."
            ),
            (
                "6. **Points d'attention** : liste ce qu'il faudrait vérifier avant "
                "d'agir (contexte supérieur, liquidité, news, session...)."
            ),
        ]

    lines.extend(
        [
            "",
            "## Travail demandé",
            "",
            *work,
            "",
            (
                "Termine par une phrase rappelant que cette analyse est éducative et ne "
                "constitue pas un conseil en investissement."
            ),
        ]
    )

    return AIPrompt(system=SYSTEM_PROMPT, user="\n".join(lines))
