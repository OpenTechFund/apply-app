import argparse
import datetime
from typing import Tuple
from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand
from django.db import transaction

from hypha.apply.users.models import User
from hypha.apply.funds.models import FundType, Round


def get_next_month_start_end() -> Tuple[datetime.date, datetime.date]:
    next_month_start = (datetime.date.today().replace(day=1) + datetime.timedelta(days=32)).replace(day=1)
    following_month = next_month_start + datetime.timedelta(days=32)
    next_month_end = (following_month - datetime.timedelta(days=following_month.day))
    return (next_month_start, next_month_end)


def check_not_negative(value) -> int:
    """Used to validate `older_than_days` argument

    Args:
        value: Argument to be validated

    Returns:
        int: Valid non-negative value

    Raises:
        argparse.ArgumentTypeError: if not non-negative integer
    """
    try:
        ivalue = int(value)
    except ValueError:
        ivalue = -1

    if ivalue < 0:
        raise argparse.ArgumentTypeError(
            f'"{value}" is an invalid non-negative integer value'
        )
    return ivalue

class Command(BaseCommand):
    help = (
        "Automatically create a new IFF round for the next month"
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "days_before_month_start",
            action="store",
            type=check_not_negative,
            help="Time in days when the new round should be created",
        )

        parser.add_argument(
            "iff_fund_id",
            action="store",
            type=int,
            help="The ID of the IFF fund",
        )

        parser.add_argument(
            "program_specialist_ids",
            action="store",
            type=str,
            help="the IDs of the program specialists to be made lead",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        fund_id = options["iff_fund_id"]
        days_before_month_start = options["days_before_month_start"]
        ps_ids = [int(id) for id in options["program_specialist_ids"].split(",")]

        fund = FundType.objects.get(id=fund_id)

        next_month_start, next_month_end = get_next_month_start_end()

        print("DAYS")
        print(days_before_month_start)
        print((next_month_start - datetime.date.today()).days > days_before_month_start)

        if (next_month_start - datetime.date.today()).days > days_before_month_start:
            self.stdout.write("Current date difference is not less than or equal to days_before_months_start, thus a new IFF round will not be created.")
            return

        current_title = f"IFF-{datetime.date.today().year}-{datetime.date.today().month}"
        next_title = f"IFF-{next_month_start.year}-{next_month_start.month}"


        leads = []

        for id in ps_ids:
            try:
                leads.append(User.objects.get(id=id))
            except User.DoesNotExist:
                self.stdout.write(f"Failed to find a user with ID of: {id}")

        if leads:
            try:
                current_round = Round.objects.get(title=current_title)

                # Alternate round leads, whoever was last shouldn't be it this time
                lead = next(lead for lead in leads if lead != current_round.lead)
            except Round.DoesNotExist:
                import random

                lead = random.choice(leads)

            next_round = Round(
                title=next_title,
                lead=lead,
                start_date=next_month_start,
                end_date=next_month_end
            )

            try:
                fund.add_child(instance=next_round)

                next_round._copy_forms("forms")
                next_round._copy_forms("review_forms")
                next_round._copy_forms("external_review_forms")
                next_round._copy_forms("determination_forms")

                self.stdout.write(f"A new IFF round has been created with the title: \"{next_title}\"")
            except ValidationError: # If the round already exists, don't do anything else
                self.stdout.write(
                    f"An IFF round already exists for this time and a new one will not be created!"
                )
        else:
            self.stdout.write(f"No valid leads were found thus IFF round \"{next_title}\" will not be created")
