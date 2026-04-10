from django import template

register = template.Library()

@register.filter(name='euros')
def euros(value):
    if value is None:
        return ''
    try:
        formatted = f"{float(value):,.2f}"
        formatted = formatted.replace(',', '\u202f').replace('.', ',')
        return f"{formatted}\u00a0€"
    except (ValueError, TypeError):
        return value

@register.filter(name='euros_abs')
def euros_abs(value):
    if value is None:
        return ''
    try:
        return euros(abs(float(value)))
    except (ValueError, TypeError):
        return value
