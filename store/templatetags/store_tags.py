from django import template

from store.money import format_money


register = template.Library()


@register.filter
def money(value):
    return format_money(value)
