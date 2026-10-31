# for business logic

from decimal import Decimal
from datetime import timedelta

from .models import SeasonalRate


def calculate_booking_price(room, check_in, check_out):
    """
    Calculate the total booking price.

    Pricing priority:
    1. Seasonal price
    2. Weekend price
    3. Normal weekday price

    Check-in date is included.
    Check-out date is excluded.
    """

    total_price = Decimal("0.00")

    # Calculate the number of nights one by one.
    current_date = check_in

    while current_date < check_out:

        # Check whether a seasonal price applies to this room type.
        seasonal_rate = SeasonalRate.objects.filter(
            room_type=room.room_type,
            start_date__lte=current_date,
            end_date__gte=current_date
        ).first()

        if seasonal_rate:
            # Seasonal pricing has the highest priority.
            nightly_price = seasonal_rate.price_per_night

        elif current_date.weekday() >= 5:
            # Saturday = 5 and Sunday = 6.
            nightly_price = room.weekend_price

        else:
            # Monday to Friday.
            nightly_price = room.price_per_night

        # Add this night's price to the total.
        total_price += nightly_price

        # Move to the next night.
        current_date += timedelta(days=1)

    return total_price
