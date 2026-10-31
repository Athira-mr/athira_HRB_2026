
# =========================================================
# IMPORTS
# =========================================================

# Used for working with dates and time.
from datetime import datetime, time, timedelta

# Used for accurate monetary calculations.
from decimal import Decimal, InvalidOperation

# Generates unique IDs for simulated payment transactions.
from uuid import uuid4

# Provides database transactions and row-level locking.
from django.db import transaction

# Retrieves a database object or returns HTTP 404.
from django.shortcuts import get_object_or_404

# Handles Django's timezone-aware date and time.
from django.utils import timezone

# Converts URL date strings into Python date objects.
from django.utils.dateparse import parse_date

# Database aggregation function for calculating revenue.
from django.db.models import Sum

# Gets the number of days in a particular month.
from calendar import monthrange

# Django REST Framework imports.
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from rest_framework.response import Response
from rest_framework.views import APIView

# Import database models.
from .models import (
    RoomType,
    Room,
    Guest,
    Booking,
    Payment,
    SeasonalRate
)

# Import serializers.
from .serializers import (
    RoomTypeSerializer,
    RoomSerializer,
    GuestSerializer,
    BookingSerializer,
    PaymentSerializer,
    SeasonalRateSerializer
)


# =========================================================
# 1. ROOM TYPE API
# =========================================================
# Handles room category operations.
# Example: Standard, Deluxe and Suite.

class RoomTypeViewSet(viewsets.ModelViewSet):

    # Retrieves all room types from the database.
    queryset = RoomType.objects.all()

    # Converts RoomType model objects into JSON.
    serializer_class = RoomTypeSerializer

    # Authentication is required for API access.
    permission_classes = [IsAuthenticated]

    # Only administrators can create, update or delete room types.
    def get_permissions(self):

        if self.action in ['create', 'update', 'partial_update', 'destroy']:
            return [IsAdminUser()]

        return [IsAuthenticated()]


# =========================================================
# 2. ROOM API AND ROOM AVAILABILITY
# =========================================================
# Handles room information and availability searching.

class RoomViewSet(viewsets.ModelViewSet):

    # select_related reduces extra database queries for room_type.
    queryset = Room.objects.select_related('room_type').all()

    serializer_class = RoomSerializer

    # All API operations require authentication.
    permission_classes = [IsAuthenticated]

    # Only administrators can manage room records.
    def get_permissions(self):

        if self.action in ['create', 'update', 'partial_update', 'destroy']:
            return [IsAdminUser()]

        return [IsAuthenticated()]

    # -----------------------------------------------------
    # GET /api/rooms/available/
    # -----------------------------------------------------
    # Finds rooms available for the requested dates and guests.
    #
    # Required:
    # check_in, check_out, guests
    #
    # Optional:
    # room_type, min_price, max_price

    @action(detail=False, methods=['get'], url_path='available')
    def available(self, request):

        # Read query parameters from the URL.
        check_in_value = request.query_params.get('check_in')
        check_out_value = request.query_params.get('check_out')
        guests_value = request.query_params.get('guests')

        # Validate required parameters.
        if not check_in_value or not check_out_value or not guests_value:
            raise ValidationError({
                'detail': 'check_in, check_out and guests are required.'
            })

        # Convert date strings into Python date objects.
        check_in = parse_date(check_in_value)
        check_out = parse_date(check_out_value)

        # Reject invalid date formats.
        if not check_in or not check_out:
            raise ValidationError({
                'detail': 'Enter dates in YYYY-MM-DD format.'
            })

        # Check-in cannot be in the past.
        if check_in < timezone.localdate():
            raise ValidationError({
                'check_in': 'Check-in date cannot be in the past.'
            })

        # Checkout must be later than check-in.
        if check_out <= check_in:
            raise ValidationError({
                'check_out': 'Check-out must be after check-in.'
            })

        # Validate the number of guests.
        try:
            guests = int(guests_value)

            if guests < 1:
                raise ValueError

        except (ValueError, TypeError):
            raise ValidationError({
                'guests': 'Guests must be a positive integer.'
            })

        # Get rooms that are not under maintenance.
        # An OCCUPIED room may still be available for a future date.
        rooms = Room.objects.select_related('room_type').exclude(
            status='MAINTENANCE'
        )

        # Only rooms with sufficient guest capacity are considered.
        rooms = rooms.filter(
            room_type__capacity__gte=guests
        )

        # Find bookings that overlap the requested period.
        #
        # Overlap condition:
        # Existing check-in < requested checkout
        # AND existing checkout > requested check-in
        #
        # Cancelled bookings do not block availability.
        booked_room_ids = Booking.objects.filter(
            check_in__lt=check_out,
            check_out__gt=check_in
        ).exclude(
            status='CANCELLED'
        ).values_list('room_id', flat=True)

        # Exclude rooms that already have overlapping bookings.
        rooms = rooms.exclude(id__in=booked_room_ids)

        # Optional filter: room type ID.
        room_type = request.query_params.get('room_type')

        if room_type:

            try:
                rooms = rooms.filter(
                    room_type_id=int(room_type)
                )

            except (ValueError, TypeError):
                raise ValidationError({
                    'room_type': 'Enter a valid room type ID.'
                })

        # Optional filter: minimum weekday base price.
        min_price = request.query_params.get('min_price')
        minimum = None

        if min_price is not None:

            try:
                minimum = Decimal(min_price)

                if not minimum.is_finite() or minimum < 0:
                    raise InvalidOperation

                rooms = rooms.filter(
                    price_per_night__gte=minimum
                )

            except (InvalidOperation, ValueError):
                raise ValidationError({
                    'min_price': 'Enter a valid non-negative price.'
                })

        # Optional filter: maximum weekday base price.
        max_price = request.query_params.get('max_price')
        maximum = None

        if max_price is not None:

            try:
                maximum = Decimal(max_price)

                if not maximum.is_finite() or maximum < 0:
                    raise InvalidOperation

                rooms = rooms.filter(
                    price_per_night__lte=maximum
                )

            except (InvalidOperation, ValueError):
                raise ValidationError({
                    'max_price': 'Enter a valid non-negative price.'
                })

        # Minimum price cannot exceed maximum price.
        if (
            minimum is not None
            and maximum is not None
            and minimum > maximum
        ):
            raise ValidationError({
                'price': 'Minimum price cannot exceed maximum price.'
            })

        # Apply pagination if pagination is configured in settings.py.
        page = self.paginate_queryset(rooms)

        if page is not None:

            serializer = self.get_serializer(page, many=True)

            return self.get_paginated_response(serializer.data)

        # Serialize all matching rooms if pagination is disabled.
        serializer = self.get_serializer(rooms, many=True)

        return Response(serializer.data)


# =========================================================
# 3. GUEST API
# =========================================================
# Handles guest registration and guest information.

class GuestViewSet(viewsets.ModelViewSet):

    # Retrieves guest records.
    queryset = Guest.objects.all()

    # Converts guest objects into JSON.
    serializer_class = GuestSerializer

    # Only authenticated users can access guest information.
    permission_classes = [IsAuthenticated]


# =========================================================
# 4. BOOKING API
# =========================================================
# Handles booking creation, modification, cancellation,
# check-in and check-out.

class BookingViewSet(viewsets.ModelViewSet):

    # Retrieves bookings with related guest and room information.
    queryset = Booking.objects.select_related(
        'guest',
        'room',
        'room__room_type'
    ).all()

    serializer_class = BookingSerializer

    # Authentication is required.
    permission_classes = [IsAuthenticated]

    # -----------------------------------------------------
    # CREATE BOOKING
    # -----------------------------------------------------
    # POST /api/bookings/
    #
    # Uses transaction.atomic() and select_for_update()
    # to prevent two simultaneous requests from booking
    # the same room for overlapping dates.

    def perform_create(self, serializer):

        # Get the room selected in the validated request.
        selected_room = serializer.validated_data['room']

        # Start a database transaction.
        with transaction.atomic():

            # Lock the selected room row.
            # Another booking request for this room must wait.
            room = get_object_or_404(
                Room.objects.select_for_update(),
                pk=selected_room.pk
            )

            # Get requested dates.
            check_in = serializer.validated_data['check_in']
            check_out = serializer.validated_data['check_out']

            # Recheck overlapping bookings after acquiring the lock.
            overlapping_bookings = Booking.objects.filter(
                room=room,
                check_in__lt=check_out,
                check_out__gt=check_in
            ).exclude(
                status='CANCELLED'
            )

            # Stop creation if another booking already exists.
            if overlapping_bookings.exists():
                raise ValidationError({
                    'room': 'This room is already booked for the selected dates.'
                })

            # Save the booking.
            # BookingSerializer calculates the price automatically.
            serializer.save(room=room)

    # -----------------------------------------------------
    # UPDATE BOOKING
    # -----------------------------------------------------
    # PUT/PATCH /api/bookings/{id}/
    #
    # Locks the room before updating booking dates or room.
    # This prevents concurrent overlapping updates.

    def perform_update(self, serializer):

        # Only pending bookings can be modified.
        if serializer.instance.status != 'PENDING':
            raise ValidationError({
                'detail': 'Only pending bookings can be updated.'
            })

        # Get the new room if supplied; otherwise use existing room.
        selected_room = serializer.validated_data.get(
            'room',
            serializer.instance.room
        )

        # Lock the room and update inside a transaction.
        with transaction.atomic():

            room = get_object_or_404(
                Room.objects.select_for_update(),
                pk=selected_room.pk
            )

            # Get the updated dates.
            check_in = serializer.validated_data.get(
                'check_in',
                serializer.instance.check_in
            )

            check_out = serializer.validated_data.get(
                'check_out',
                serializer.instance.check_out
            )

            # Check for other bookings overlapping the updated dates.
            overlapping_bookings = Booking.objects.filter(
                room=room,
                check_in__lt=check_out,
                check_out__gt=check_in
            ).exclude(
                status='CANCELLED'
            ).exclude(
                pk=serializer.instance.pk
            )

            if overlapping_bookings.exists():
                raise ValidationError({
                    'room': 'This room is already booked for the selected dates.'
                })

            # Save updated booking.
            # Serializer recalculates total_price.
            serializer.save(room=room)

    # -----------------------------------------------------
    # CANCEL BOOKING
    # -----------------------------------------------------
    # POST /api/bookings/{id}/cancel/
    #
    # Cancellation rules:
    # 7 or more days before check-in = 100% refund.
    # 24 hours to less than 7 days = 50% refund.
    # Less than 24 hours = cancellation rejected.

    @action(detail=True, methods=['post'], url_path='cancel')
    def cancel_booking(self, request, pk=None):

        # Use a transaction to update booking and payment together.
        with transaction.atomic():

            # Lock the booking so two cancellation requests
            # cannot process the same booking simultaneously.
            booking = get_object_or_404(
                Booking.objects.select_for_update(),
                pk=pk
            )

            # Prevent cancelling the same booking twice.
            if booking.status == 'CANCELLED':
                raise ValidationError({
                    'detail': 'This booking is already cancelled.'
                })

            # Only pending and confirmed bookings can be cancelled.
            if booking.status not in ['PENDING', 'CONFIRMED']:
                raise ValidationError({
                    'detail': 'This booking cannot be cancelled.'
                })

            # A DateField has no time component.
            # Therefore, check-in is treated as midnight
            # at the beginning of the scheduled check-in date.
            check_in_datetime = timezone.make_aware(
                datetime.combine(
                    booking.check_in,
                    time.min
                )
            )

            # Calculate remaining time until check-in.
            time_remaining = check_in_datetime - timezone.now()

            # Cancellation is not allowed within 24 hours.
            if time_remaining < timedelta(hours=24):
                raise ValidationError({
                    'detail': (
                        'Cancellation is not allowed within 24 hours '
                        'of check-in.'
                    )
                })

            # Find a successful payment and lock its database row.
            payment = Payment.objects.select_for_update().filter(
                booking=booking,
                payment_status='SUCCESS'
            ).first()

            # Default refund values when no successful payment exists.
            refund_percentage = Decimal('0.00')
            refund_amount = Decimal('0.00')

            if payment:

                # 100% refund for cancellations at least 7 days earlier.
                if time_remaining >= timedelta(days=7):
                    refund_percentage = Decimal('100.00')

                # 50% refund for cancellations from 24 hours
                # to less than 7 days before check-in.
                else:
                    refund_percentage = Decimal('50.00')

                # Calculate the refund from the original payment amount.
                refund_amount = (
                    payment.amount
                    * refund_percentage
                    / Decimal('100')
                )

                # Store refund information in the payment record.
                payment.refund_percentage = refund_percentage
                payment.refund_amount = refund_amount

                # Use different statuses for full and partial refunds.
                if refund_percentage == Decimal('100.00'):
                    payment.payment_status = 'REFUNDED'
                else:
                    payment.payment_status = 'PARTIALLY_REFUNDED'

                payment.save()

            # Update the booking status.
            booking.status = 'CANCELLED'

            booking.save(
                update_fields=['status']
            )

            # Return cancellation and refund information.
            return Response({
                'message': 'Booking cancelled successfully.',
                'booking_id': booking.id,
                'booking_status': booking.status,
                'refund_percentage': str(refund_percentage),
                'refund_amount': str(refund_amount)
            }, status=status.HTTP_200_OK)

    # -----------------------------------------------------
    # CHECK-IN
    # -----------------------------------------------------
    # POST /api/bookings/{id}/check-in/
    #
    # Changes:
    # Booking status -> CHECKED_IN
    # Room status -> OCCUPIED

    @action(detail=True, methods=['post'], url_path='check-in')
    def check_in_guest(self, request, pk=None):

        # Keep booking and room updates in one transaction.
        with transaction.atomic():

            # Lock the booking row.
            booking = get_object_or_404(
                Booking.objects.select_for_update(),
                pk=pk
            )

            # Only confirmed bookings can check in.
            if booking.status != 'CONFIRMED':
                raise ValidationError({
                    'detail': 'Only confirmed bookings can check in.'
                })

            # Check-in cannot happen before the scheduled date.
            today = timezone.localdate()

            if today < booking.check_in:
                raise ValidationError({
                    'detail': 'Check-in is not allowed before the booking date.'
                })

            # Check-in cannot happen on or after checkout date.
            if today >= booking.check_out:
                raise ValidationError({
                    'detail': 'The booking checkout date has passed.'
                })

            # Lock the room row before changing its status.
            room = get_object_or_404(
                Room.objects.select_for_update(),
                pk=booking.room_id
            )

            # Only available rooms can be occupied.
            if room.status != 'AVAILABLE':
                raise ValidationError({
                    'detail': 'Room is not available for check-in.'
                })

            # Update booking status.
            booking.status = 'CHECKED_IN'

            booking.save(
                update_fields=['status']
            )

            # Update room status.
            room.status = 'OCCUPIED'

            room.save(
                update_fields=['status']
            )

            # Return updated booking and room information.
            return Response({
                'message': 'Guest checked in successfully.',
                'booking_id': booking.id,
                'booking_status': booking.status,
                'room_status': room.status
            }, status=status.HTTP_200_OK)

    # -----------------------------------------------------
    # CHECK-OUT
    # -----------------------------------------------------
    # POST /api/bookings/{id}/check-out/
    #
    # Changes:
    # Booking status -> CHECKED_OUT
    # Room status -> AVAILABLE

    @action(detail=True, methods=['post'], url_path='check-out')
    def check_out_guest(self, request, pk=None):

        # Use a transaction to update both records safely.
        with transaction.atomic():

            # Lock the booking record.
            booking = get_object_or_404(
                Booking.objects.select_for_update(),
                pk=pk
            )

            # Only checked-in guests can check out.
            if booking.status != 'CHECKED_IN':
                raise ValidationError({
                    'detail': 'Only checked-in guests can check out.'
                })

            # Lock the corresponding room record.
            room = get_object_or_404(
                Room.objects.select_for_update(),
                pk=booking.room_id
            )

            # Mark the booking as checked out.
            booking.status = 'CHECKED_OUT'

            booking.save(
                update_fields=['status']
            )

            # Make the room available for future bookings.
            room.status = 'AVAILABLE'

            room.save(
                update_fields=['status']
            )

            # Return updated status information.
            return Response({
                'message': 'Guest checked out successfully.',
                'booking_id': booking.id,
                'booking_status': booking.status,
                'room_status': room.status
            }, status=status.HTTP_200_OK)


# =========================================================
# 5. PAYMENT API
# =========================================================
# Implements simulated payment processing.
#
# No real payment gateway is connected.
# The server calculates the amount from Booking.total_price.
# A successful simulated payment confirms the booking.

class PaymentViewSet(viewsets.ModelViewSet):

    # Retrieve payments along with their booking information.
    queryset = Payment.objects.select_related(
        'booking'
    ).all()

    serializer_class = PaymentSerializer

    # Only authenticated users can access payment APIs.
    permission_classes = [IsAuthenticated]

    # -----------------------------------------------------
    # CREATE SIMULATED PAYMENT
    # -----------------------------------------------------
    # POST /api/payments/
    #
    # Expected request:
    # {
    #     "booking": 1,
    #     "payment_method": "UPI"
    # }
    #
    # Amount, transaction ID and payment status are generated
    # by the server, not accepted from the client.

    def perform_create(self, serializer):

        # Get the booking selected by the client.
        selected_booking = serializer.validated_data['booking']

        # Process the simulated payment inside a transaction.
        with transaction.atomic():

            # Lock the booking to prevent simultaneous payments.
            booking = get_object_or_404(
                Booking.objects.select_for_update(),
                pk=selected_booking.pk
            )

            # A cancelled booking cannot receive payment.
            if booking.status == 'CANCELLED':
                raise ValidationError({
                    'detail': 'Payment cannot be made for a cancelled booking.'
                })

            # Only pending bookings can receive a new payment.
            if booking.status != 'PENDING':
                raise ValidationError({
                    'detail': 'Payment is allowed only for pending bookings.'
                })

            # Prevent duplicate successful payments.
            existing_payment = Payment.objects.filter(
                booking=booking,
                payment_status__in=[
                    'SUCCESS',
                    'REFUNDED',
                    'PARTIALLY_REFUNDED'
                ]
            ).exists()

            if existing_payment:
                raise ValidationError({
                    'detail': 'A successful payment already exists for this booking.'
                })

            # Generate a unique simulated transaction ID.
            transaction_id = f"SIM-{uuid4().hex.upper()}"

            # Create a simulated successful payment.
            # The amount comes directly from the booking total.
            serializer.save(
                amount=booking.total_price,
                payment_status='SUCCESS',
                transaction_id=transaction_id
            )

            # Confirm the booking after successful payment.
            booking.status = 'CONFIRMED'

            booking.save(
                update_fields=['status']
            )


# =========================================================
# 6. SEASONAL RATE API
# =========================================================
# Handles seasonal room price management.

class SeasonalRateViewSet(viewsets.ModelViewSet):

    # Retrieve seasonal pricing records.
    queryset = SeasonalRate.objects.select_related(
        'room_type'
    ).all()

    serializer_class = SeasonalRateSerializer

    # Authentication is required.
    permission_classes = [IsAuthenticated]

    # Only administrators can manage seasonal rates.
    def get_permissions(self):

        if self.action in ['create', 'update', 'partial_update', 'destroy']:
            return [IsAdminUser()]

        return [IsAuthenticated()]


# =========================================================
# 7. MONTHLY OCCUPANCY AND REVENUE REPORT
# =========================================================
# Returns occupancy percentage and successful payment revenue
# grouped by room type for a selected month.

class OccupancyReportAPIView(APIView):

    # Only authenticated users can view the report.
    permission_classes = [IsAuthenticated]

    # -----------------------------------------------------
    # GET /api/reports/occupancy/?month=2026-11
    # -----------------------------------------------------

    def get(self, request):

        # Read the month from the query parameters.
        month_value = request.query_params.get('month')

        # Month is mandatory.
        if not month_value:
            raise ValidationError({
                'month': 'Month is required. Use YYYY-MM format.'
            })

        # Convert YYYY-MM into a date object.
        try:

            selected_month = datetime.strptime(
                month_value,
                '%Y-%m'
            ).date()

        except ValueError:

            raise ValidationError({
                'month': 'Invalid month. Use YYYY-MM format, e.g. 2026-11.'
            })

        # Get the first day of the selected month.
        month_start = selected_month.replace(day=1)

        # Calculate the number of days in the selected month.
        days_in_month = monthrange(
            selected_month.year,
            selected_month.month
        )[1]

        # Calculate the first day of the next month.
        # This makes it easier to filter bookings within the month.
        next_month = (
            month_start.replace(day=28) + timedelta(days=4)
        ).replace(day=1)

        # Get all room categories.
        room_types = RoomType.objects.all()

        # Store the report for each room category.
        report_data = []

        # Calculate occupancy and revenue for each room type.
        for room_type in room_types:

            # Get rooms belonging to the current room type.
            # Rooms currently under maintenance are excluded.
            rooms = Room.objects.filter(
                room_type=room_type
            ).exclude(
                status='MAINTENANCE'
            )

            # Count the rooms in this category.
            total_rooms = rooms.count()

            # Total possible room-nights during this month.
            total_room_nights = total_rooms * days_in_month

            # Get the IDs of rooms in this category.
            room_ids = rooms.values_list(
                'id',
                flat=True
            )

            # Find bookings that overlap the selected month.
            # Pending and cancelled bookings are excluded.
            bookings = Booking.objects.filter(
                room_id__in=room_ids,
                check_in__lt=next_month,
                check_out__gt=month_start,
                status__in=[
                    'CONFIRMED',
                    'CHECKED_IN',
                    'CHECKED_OUT'
                ]
            )

            # Start with zero booked room-nights.
            booked_room_nights = 0

            # Calculate only the nights falling inside this month.
            for booking in bookings:

                # Use the later of booking check-in and month start.
                actual_start = max(
                    booking.check_in,
                    month_start
                )

                # Use the earlier of booking checkout and next month.
                actual_end = min(
                    booking.check_out,
                    next_month
                )

                # Add the number of nights inside the selected month.
                booked_room_nights += (
                    actual_end - actual_start
                ).days

            # Calculate occupancy percentage.
            if total_room_nights > 0:

                occupancy_percentage = round(
                    (
                        booked_room_nights
                        / total_room_nights
                    ) * 100,
                    2
                )

            else:
                occupancy_percentage = 0

            # Convert month boundaries into timezone-aware datetimes.
            month_start_datetime = timezone.make_aware(
                datetime.combine(
                    month_start,
                    time.min
                )
            )

            next_month_datetime = timezone.make_aware(
                datetime.combine(
                    next_month,
                    time.min
                )
            )

            # Calculate successful payment revenue recorded
            # during the selected calendar month.
            revenue_result = Payment.objects.filter(
                booking__room__room_type=room_type,
                payment_status='SUCCESS',
                created_at__gte=month_start_datetime,
                created_at__lt=next_month_datetime
            ).aggregate(
                total_revenue=Sum('amount')
            )

            # If no successful payments exist, revenue is zero.
            revenue = (
                revenue_result['total_revenue']
                or Decimal('0.00')
            )

            # Add the room type's information to the report.
            report_data.append({
                'room_type': room_type.name,
                'total_rooms': total_rooms,
                'total_room_nights': total_room_nights,
                'booked_room_nights': booked_room_nights,
                'occupancy_percentage': occupancy_percentage,
                'revenue': str(revenue)
            })

        # Return the complete report as JSON.
        return Response({
            'month': month_value,
            'room_type_reports': report_data
        }, status=status.HTTP_200_OK)
