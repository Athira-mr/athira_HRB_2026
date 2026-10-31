
from rest_framework import serializers
from django.db.models import Q
from decimal import Decimal
import re

from .models import (
    RoomType,
    Room,
    Guest,
    Booking,
    Payment,
    SeasonalRate
)

from .services import calculate_booking_price


# =========================================================
# 1. ROOM TYPE SERIALIZER
# =========================================================
# Converts RoomType model objects into JSON and validates
# room type information received from API requests.

class RoomTypeSerializer(serializers.ModelSerializer):

    class Meta:
        model = RoomType
        fields = '__all__'

    def validate_name(self, value):
        value = value.strip()

        if not value:
            raise serializers.ValidationError(
                "Room type name cannot be empty."
            )

        # Prevent duplicate names, ignoring uppercase/lowercase.
        existing = RoomType.objects.filter(name__iexact=value)

        if self.instance:
            existing = existing.exclude(pk=self.instance.pk)

        if existing.exists():
            raise serializers.ValidationError(
                "This room type already exists."
            )

        return value

    def validate_capacity(self, value):
        if value < 1:
            raise serializers.ValidationError(
                "Room capacity must be at least 1."
            )

        return value


# =========================================================
# 2. ROOM SERIALIZER
# =========================================================
# Handles room details.
# Room status is read-only because check-in and check-out
# endpoints must control the room status.

class RoomSerializer(serializers.ModelSerializer):

    class Meta:
        model = Room
        fields = '__all__'

        read_only_fields = ('status',)

    def validate_room_number(self, value):
        value = value.strip()

        if not value:
            raise serializers.ValidationError(
                "Room number cannot be empty."
            )

        # Room numbers must be unique regardless of case.
        existing = Room.objects.filter(
            room_number__iexact=value
        )

        if self.instance:
            existing = existing.exclude(pk=self.instance.pk)

        if existing.exists():
            raise serializers.ValidationError(
                "This room number already exists."
            )

        return value

    def validate_price_per_night(self, value):
        if value <= Decimal('0.00'):
            raise serializers.ValidationError(
                "Weekday price must be greater than zero."
            )

        return value

    def validate_weekend_price(self, value):
        if value <= Decimal('0.00'):
            raise serializers.ValidationError(
                "Weekend price must be greater than zero."
            )

        return value


# =========================================================
# 3. GUEST SERIALIZER
# =========================================================
# Handles guest registration and guest information.
# Validates names, email and phone number.

class GuestSerializer(serializers.ModelSerializer):

    class Meta:
        model = Guest
        fields = '__all__'

    def validate_first_name(self, value):
        value = value.strip()

        if not value:
            raise serializers.ValidationError(
                "First name cannot be empty."
            )

        if not re.fullmatch(r"[A-Za-z ]+", value):
            raise serializers.ValidationError(
                "First name should contain only letters and spaces."
            )

        return value

    def validate_last_name(self, value):
        value = value.strip()

        if not value:
            raise serializers.ValidationError(
                "Last name cannot be empty."
            )

        if not re.fullmatch(r"[A-Za-z ]+", value):
            raise serializers.ValidationError(
                "Last name should contain only letters and spaces."
            )

        return value

    def validate_email(self, value):
        value = value.strip().lower()

        # Email addresses are checked without case sensitivity.
        existing = Guest.objects.filter(email__iexact=value)

        if self.instance:
            existing = existing.exclude(pk=self.instance.pk)

        if existing.exists():
            raise serializers.ValidationError(
                "A guest with this email already exists."
            )

        return value

    def validate_phone(self, value):
        value = value.strip()

        if not re.fullmatch(r'\+?[0-9]{10,15}', value):
            raise serializers.ValidationError(
                "Enter a valid phone number containing 10 to 15 digits."
            )

        return value


# =========================================================
# 4. BOOKING SERIALIZER
# =========================================================
# Handles room bookings.
#
# Important:
# - Checks booking dates.
# - Prevents overlapping reservations.
# - Prevents booking rooms under maintenance.
# - Calculates the total price on the server.
# - Does not allow clients to modify booking status or price.

class BookingSerializer(serializers.ModelSerializer):

    class Meta:
        model = Booking
        fields = '__all__'

        read_only_fields = (
            'total_price',
            'status',
            'created_at',
        )

    def validate(self, attrs):

        # For updates, use existing values when fields are omitted.
        room = attrs.get(
            'room',
            self.instance.room if self.instance else None
        )

        check_in = attrs.get(
            'check_in',
            self.instance.check_in if self.instance else None
        )

        check_out = attrs.get(
            'check_out',
            self.instance.check_out if self.instance else None
        )

        if not room:
            raise serializers.ValidationError({
                'room': 'Room is required.'
            })

        if not check_in:
            raise serializers.ValidationError({
                'check_in': 'Check-in date is required.'
            })

        if not check_out:
            raise serializers.ValidationError({
                'check_out': 'Check-out date is required.'
            })

        # A guest cannot book a room for a past date.
        if check_in < timezone_now_date():
            raise serializers.ValidationError({
                'check_in': 'Check-in date cannot be in the past.'
            })

        # Checkout must be after check-in.
        if check_out <= check_in:
            raise serializers.ValidationError({
                'check_out': 'Check-out must be after check-in.'
            })

        # Maintenance rooms cannot be booked.
        # OCCUPIED rooms may still be booked for future dates.
        if room.status == 'MAINTENANCE':
            raise serializers.ValidationError({
                'room': 'This room is under maintenance.'
            })

        # Find existing reservations that overlap the requested dates.
        overlapping_bookings = Booking.objects.filter(
            room=room,
            check_in__lt=check_out,
            check_out__gt=check_in
        ).exclude(
            status='CANCELLED'
        )

        # Exclude the current booking when updating it.
        if self.instance:
            overlapping_bookings = overlapping_bookings.exclude(
                pk=self.instance.pk
            )

        if overlapping_bookings.exists():
            raise serializers.ValidationError({
                'room': 'This room is already booked for the selected dates.'
            })

        return attrs

    def create(self, validated_data):

        # Calculate the total price using the server-side service.
        # Client-provided total_price is read-only and ignored.
        room = validated_data['room']
        check_in = validated_data['check_in']
        check_out = validated_data['check_out']

        total_price = calculate_booking_price(
            room,
            check_in,
            check_out
        )

        # Save the booking with the calculated price.
        booking = Booking.objects.create(
            **validated_data,
            total_price=total_price
        )

        return booking

    def update(self, instance, validated_data):

        # Recalculate price if booking details are updated.
        room = validated_data.get('room', instance.room)
        check_in = validated_data.get('check_in', instance.check_in)
        check_out = validated_data.get('check_out', instance.check_out)

        total_price = calculate_booking_price(
            room,
            check_in,
            check_out
        )

        # Update the remaining booking fields.
        for attr, value in validated_data.items():
            setattr(instance, attr, value)

        instance.total_price = total_price
        instance.save()

        return instance


# =========================================================
# 5. PAYMENT SERIALIZER
# =========================================================
# Handles payment information.
#
# Security:
# - Payment amount is read-only.
# - Payment status is read-only.
# - Refund amount and percentage are read-only.
# - Transaction ID is read-only.
#
# The server will calculate payment amount from booking.total_price.

class PaymentSerializer(serializers.ModelSerializer):

    class Meta:
        model = Payment
        fields = '__all__'

        read_only_fields = (
            'amount',
            'payment_status',
            'refund_amount',
            'refund_percentage',
            'transaction_id',
            'created_at',
        )

    def validate_booking(self, value):

        if not value:
            raise serializers.ValidationError(
                "Booking is required."
            )

        if value.status == 'CANCELLED':
            raise serializers.ValidationError(
                "Payment cannot be created for a cancelled booking."
            )

        return value


# =========================================================
# 6. SEASONAL RATE SERIALIZER
# =========================================================
# Handles seasonal room pricing.
# Prevents overlapping seasonal rates for the same room type.

class SeasonalRateSerializer(serializers.ModelSerializer):

    class Meta:
        model = SeasonalRate
        fields = '__all__'

    def validate_price_per_night(self, value):
        if value <= Decimal('0.00'):
            raise serializers.ValidationError(
                "Seasonal price must be greater than zero."
            )

        return value

    def validate(self, attrs):

        room_type = attrs.get(
            'room_type',
            self.instance.room_type if self.instance else None
        )

        start_date = attrs.get(
            'start_date',
            self.instance.start_date if self.instance else None
        )

        end_date = attrs.get(
            'end_date',
            self.instance.end_date if self.instance else None
        )

        if start_date and end_date and end_date < start_date:
            raise serializers.ValidationError({
                'end_date': 'End date cannot be before start date.'
            })

        if room_type and start_date and end_date:

            # Find seasonal rates that overlap this date range.
            overlapping_rates = SeasonalRate.objects.filter(
                room_type=room_type,
                start_date__lte=end_date,
                end_date__gte=start_date
            )

            # Exclude the current record during updates.
            if self.instance:
                overlapping_rates = overlapping_rates.exclude(
                    pk=self.instance.pk
                )

            if overlapping_rates.exists():
                raise serializers.ValidationError({
                    'start_date': (
                        'Another seasonal rate already exists '
                        'for this room type during these dates.'
                    )
                })

        return attrs


# =========================================================
# HELPER FUNCTION
# =========================================================
# Returns today's date using Django's timezone settings.

def timezone_now_date():
    from django.utils import timezone
    return timezone.localdate()
