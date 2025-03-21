from django import template
from wagtail.coreutils import camelcase_to_underscore

register = template.Library()


@register.filter(name="widget_type")
def widget_type(bound_field):
    """Get widget type of a field"""
    return camelcase_to_underscore(bound_field.field.widget.__class__.__name__)


@register.filter(name="field_type")
def field_type(bound_field):
    """Get type of field"""
    return camelcase_to_underscore(bound_field.field.__class__.__name__)


@register.simple_tag
def verbose_name(instance) -> str:
    """Get the verbose name of a wagtail page (in lowercase)"""
    return instance.specific._meta.verbose_name.title().lower()
