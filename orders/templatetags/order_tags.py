from django import template

register = template.Library()


@register.filter
def split(value, delimiter=' '):
    return value.split(delimiter)


@register.filter
def multiply(value, arg):
    return value * arg
