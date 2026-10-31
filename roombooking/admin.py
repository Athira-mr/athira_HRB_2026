from django.contrib import admin

# Register your models here.
from django.contrib import admin
from .models import RoomType, Room, Guest, Booking, Payment,SeasonalRate


# Register RoomType model
@admin.register(RoomType)
class RoomTypeAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'capacity')
@admin.register(SeasonalRate)
class SeasonalRateAdmin(admin.ModelAdmin):

    list_display = (
        'id',
        'room_type',
        'season_name',
        'start_date',
        'end_date',
        'price_per_night'
    )

    list_filter = ('room_type',)

# Register Room model
@admin.register(Room)
class RoomAdmin(admin.ModelAdmin):

    list_display = (
        'id',
        'room_number',
        'room_type',
        'price_per_night',
        'weekend_price',
        'status'
    )

    list_filter = ('room_type', 'status')

    search_fields = ('room_number',)


# Register Guest model
@admin.register(Guest)
class GuestAdmin(admin.ModelAdmin):
    list_display = ('id', 'first_name', 'last_name', 'email', 'phone')
    search_fields = ('first_name', 'last_name', 'email')


# Register Booking model
@admin.register(Booking)
class BookingAdmin(admin.ModelAdmin):
    list_display = ('id', 'guest', 'room', 'check_in', 'check_out', 'status')
    list_filter = ('status',)


# Register Payment model
@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ('id', 'booking', 'amount', 'payment_method', 'payment_status')
    list_filter = ('payment_status', 'payment_method')