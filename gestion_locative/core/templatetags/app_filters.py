from django import template

register = template.Library()


@register.filter
def euro(value):
    """Formate un nombre en euros : 1 234,56 EUR"""
    try:
        val = float(value)
        formatted = f"{val:,.2f}".replace(",", "\u00a0").replace(".", ",")
        return f"{formatted} \u20ac"
    except (ValueError, TypeError):
        return "0,00 \u20ac"


@register.filter
def pct(value):
    """Formate un nombre en pourcentage : 5,25 %"""
    try:
        val = float(value)
        return f"{val:.2f}".replace(".", ",") + " %"
    except (ValueError, TypeError):
        return "0,00 %"
