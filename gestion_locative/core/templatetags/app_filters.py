from django import template

register = template.Library()


# Affiche pour une donnee absente ou illisible : ne jamais la confondre avec un zero.
VALEUR_ABSENTE = "\u2014"


@register.filter
def euro(value):
    """Formate un nombre en euros : 1 234,56 EUR (— si la valeur est absente)."""
    if value is None or value == "":
        return VALEUR_ABSENTE
    try:
        val = float(value)
    except (ValueError, TypeError, ArithmeticError):
        return VALEUR_ABSENTE
    formatted = f"{val:,.2f}".replace(",", "\u00a0").replace(".", ",")
    return f"{formatted} \u20ac"


@register.filter
def pct(value):
    """Formate un nombre en pourcentage : 5,25 % (— si la valeur est absente)."""
    if value is None or value == "":
        return VALEUR_ABSENTE
    try:
        val = float(value)
    except (ValueError, TypeError, ArithmeticError):
        return VALEUR_ABSENTE
    return f"{val:.2f}".replace(".", ",") + " %"
