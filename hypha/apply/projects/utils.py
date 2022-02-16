from django.conf import settings

from .models import Deliverable, Project


def fetch_and_save_deliverables(project_id, program_project_id=''):
    """
    Get deliverables from various third party integrations.
    """
    if settings.INTACCT_ENABLED:
        from hypha.apply.projects.services.sageintacct.utils import fetch_deliverables
        deliverables = fetch_deliverables(program_project_id)
        save_deliverables(project_id, deliverables)


def save_deliverables(project_id, deliverables=[]):
    project = Project.objects.get(id=project_id)
    if deliverables:
        project.deliverables.all().delete()
    new_deliverable_list = []
    for deliverable in deliverables:
        item_id = deliverable['ITEMID']
        item_name = deliverable['ITEMNAME']
        qty_remaining = int(float(deliverable['QTY_REMAINING']))
        price = deliverable['PRICE']
        new_deliverable_list.append(
            Deliverable(
                external_id=item_id,
                name=item_name,
                available_to_invoice=qty_remaining,
                unit_price=price,
                project=project
            )
        )
    Deliverable.objects.bulk_create(new_deliverable_list)
