
from django.db import models
from django.core.validators import (
    MinValueValidator,
    MaxValueValidator,
    RegexValidator
)
from decimal import Decimal


# =========================================================
# 1. ROOM TYPE MODEL
# =========================================================
# Stores categories of hotel rooms.
# Example: Standard, Deluxe, Suite.

class RoomType(models.Model):

    name = models.CharField(
        max_length=100,
        unique=True
    )

    description = models.TextField(
        blank=True,
        null=True
    )

    # Minimum capacity must be at least 1 guest.
    capacity = models.PositiveIntegerField(
        validators=[MinValueValidator(1)]
    )

    def __str__(self):
        return self.name


# =========================================================
# 2. SEASONAL RATE MODEL
# =========================================================
# Stores special room prices for particular date ranges.
# Example: Christmas season or summer holidays.

class SeasonalRate(models.Model):

    room_type = models.ForeignKey(
        RoomType,
        on_delete=models.CASCADE,
        related_name='seasonal_rates'
    )

    season_name = models.CharField(max_length=100)

    start_date = models.DateField()

    end_date = models.DateField()

    price_per_night = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))]
    )

    class Meta:

        # Database-level validation.
        constraints = [
            models.CheckConstraint(
                condition=models.Q(end_date__gte=models.F('start_date')),
                name='season_end_after_start'
            ),
            models.CheckConstraint(
                condition=models.Q(price_per_night__gt=0),
                name='season_price_positive'
            ),
        ]

        # Helps filter seasonal rates efficiently.
        indexes = [
            models.Index(
                fields=['room_type', 'start_date', 'end_date']
            ),
        ]

    def __str__(self):
        return f"{self.season_name} - {self.room_type.name}"


# =========================================================
# 3. ROOM MODEL
# =========================================================
# Stores individual hotel rooms.
# Each room belongs to one room type.

class Room(models.Model):

    ROOM_STATUS = [
        ('AVAILABLE', 'Available'),
        ('OCCUPIED', 'Occupied'),
        ('MAINTENANCE', 'Maintenance'),
    ]

    room_number = models.CharField(
        max_length=20,
        unique=True
    )

    room_type = models.ForeignKey(
        RoomType,
        on_delete=models.PROTECT,
        related_name='rooms'
    )

    # Normal weekday price.
    price_per_night = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))]
    )

    # Weekend price.
    weekend_price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))]
    )

    status = models.CharField(
        max_length=20,
        choices=ROOM_STATUS,
        default='AVAILABLE'
    )

    class Meta:

        constraints = [
            models.CheckConstraint(
                condition=models.Q(price_per_night__gt=0),
                name='room_weekday_price_positive'
            ),
            models.CheckConstraint(
                condition=models.Q(weekend_price__gt=0),
                name='room_weekend_price_positive'
            ),
        ]

        indexes = [
            models.Index(
                fields=['room_type', 'status']
            ),
        ]

    def __str__(self):
        return f"Room {self.room_number}"


# =========================================================
# 4. GUEST MODEL
# =========================================================
# Stores hotel guest information.

class Guest(models.Model):

    phone_validator = RegexValidator(
        regex=r'^\+?[0-9]{10,15}$',
        message='Enter a valid phone number.'
    )

    first_name = models.CharField(max_length=100)

    last_name = models.CharField(max_length=100)

    email = models.EmailField(unique=True)

    phone = models.CharField(
        max_length=16,
        validators=[phone_validator]
    )

    address = models.TextField(
        blank=True,
        null=True
    )

    def __str__(self):
        return f"{self.first_name} {self.last_name}"


# =========================================================
# 5. BOOKING MODEL
# =========================================================
# Stores room reservations made by guests.
# One guest can have multiple bookings.
# One room can have multiple bookings on different dates.

class Booking(models.Model):

    BOOKING_STATUS = [
        ('PENDING', 'Pending'),
        ('CONFIRMED', 'Confirmed'),
        ('CHECKED_IN', 'Checked In'),
        ('CHECKED_OUT', 'Checked Out'),
        ('CANCELLED', 'Cancelled'),
    ]

    guest = models.ForeignKey(
        Guest,
        on_delete=models.CASCADE,
        related_name='bookings'
    )

    room = models.ForeignKey(
        Room,
        on_delete=models.PROTECT,
        related_name='bookings'
    )

    check_in = models.DateField()

    check_out = models.DateField()

    # Calculated by the server.
    # The client must not decide the booking price.
    total_price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal('0.00')
    )

    status = models.CharField(
        max_length=20,
        choices=BOOKING_STATUS,
        default='PENDING'
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:

        constraints = [
            # Checkout must be after check-in.
            models.CheckConstraint(
                condition=models.Q(check_out__gt=models.F('check_in')),
                name='booking_checkout_after_checkin'
            ),

            # Booking total cannot be negative.
            models.CheckConstraint(
                condition=models.Q(total_price__gte=0),
                name='booking_total_nonnegative'
            ),
        ]

        indexes = [
            models.Index(
                fields=['room', 'check_in', 'check_out']
            ),
            models.Index(
                fields=['status']
            ),
        ]

    def __str__(self):
        return f"Booking {self.id} - Room {self.room.room_number}"


# =========================================================
# 6. PAYMENT MODEL
# =========================================================
# Stores payment and refund information for bookings.
# Payment amount and refund values are handled by the server.

class Payment(models.Model):

    PAYMENT_STATUS = [
        ('PENDING', 'Pending'),
        ('SUCCESS', 'Success'),
        ('FAILED', 'Failed'),
        ('REFUNDED', 'Refunded'),

        # NEW: Used when only part of the payment is refunded.
        ('PARTIALLY_REFUNDED', 'Partially Refunded'),
    ]

    PAYMENT_METHOD = [
        ('CASH', 'Cash'),
        ('CARD', 'Card'),
        ('UPI', 'UPI'),
        ('ONLINE', 'Online'),
    ]

    booking = models.ForeignKey(
        Booking,
        on_delete=models.CASCADE,
        related_name='payments'
    )

    amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.00'))]
    )

    payment_method = models.CharField(
        max_length=20,
        choices=PAYMENT_METHOD
    )

    payment_status = models.CharField(
        max_length=30,
        choices=PAYMENT_STATUS,
        default='PENDING'
    )

    # Amount returned to the guest.
    refund_amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal('0.00')
    )

    # Refund percentage: 0%, 50%, or 100%.
    refund_percentage = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal('0.00'),
        validators=[
            MinValueValidator(Decimal('0.00')),
            MaxValueValidator(Decimal('100.00'))
        ]
    )

    transaction_id = models.CharField(
        max_length=100,
        unique=True,
        null=True,
        blank=True
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:

        constraints = [
            models.CheckConstraint(
                condition=models.Q(amount__gte=0),
                name='payment_amount_nonnegative'
            ),

            models.CheckConstraint(
                condition=models.Q(refund_amount__gte=0),
                name='payment_refund_nonnegative'
            ),

            # Refund cannot exceed the original payment.
            models.CheckConstraint(
                condition=models.Q(
                    refund_amount__lte=models.F('amount')
                ),
                name='payment_refund_not_exceed_amount'
            ),

            models.CheckConstraint(
                condition=(
                    models.Q(refund_percentage__gte=0) &
                    models.Q(refund_percentage__lte=100)
                ),
                name='payment_refund_percentage_valid'
            ),
        ]

        indexes = [
            models.Index(fields=['booking']),
        ]

    def __str__(self):
        return f"Payment {self.id} - {self.payment_status}"
