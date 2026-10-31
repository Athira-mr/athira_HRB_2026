
from rest_framework.routers import DefaultRouter
from django.urls import path
from .views import (
    RoomTypeViewSet,
    RoomViewSet,
    GuestViewSet,
    BookingViewSet,
    PaymentViewSet,
    SeasonalRateViewSet,
    OccupancyReportAPIView
)

# Create a router to generate API URLs automatically.
router = DefaultRouter()

# Register each ViewSet with the router.
router.register('room-types', RoomTypeViewSet)
router.register('rooms', RoomViewSet)
router.register('guests', GuestViewSet)
router.register('bookings', BookingViewSet)
router.register('payments', PaymentViewSet)
router.register('seasonal-rates', SeasonalRateViewSet)
# Export the generated URL patterns.
urlpatterns = [
    path(
        'reports/occupancy/',
        OccupancyReportAPIView.as_view(),
        name='occupancy-report'
    ),
]

urlpatterns += router.urls