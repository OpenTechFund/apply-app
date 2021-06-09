from django.db import models
from django.utils.translation import gettext_lazy as _

from ..admin_forms import ScreeningStatusAdminForm


class ScreeningStatus(models.Model):
    title = models.CharField(max_length=128)
    yes = models.BooleanField(
        default=False, verbose_name="Yes/No",
        help_text=_('Tick mark for Yes otherwise No.')
    )
    default = models.BooleanField(
        default=False, verbose_name="Default Yes/No",
        help_text=_('Only one Yes and No screening status can be set as default.')
    )

    base_form_class = ScreeningStatusAdminForm

    class Meta:
        verbose_name_plural = "screening statuses"

    def __str__(self):
        return self.title
