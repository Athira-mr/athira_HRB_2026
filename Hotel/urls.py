
# Import Django admin.
from django.contrib import admin

# Import path and include for URL routing.
from django.urls import path, include

# Import SimpleJWT views for generating and refreshing tokens.
from rest_framework_simplejwt.views import (
    TokenObtainPairView,
    TokenRefreshView,
)

urlpatterns = [

    # Django admin panel.
    path("admin/", admin.site.urls),

    # All hotel room booking API endpoints.
    path("api/", include("roombooking.urls")),

    # Login endpoint: generates access and refresh tokens.
    path(
        "api/token/",
        TokenObtainPairView.as_view(),
        name="token_obtain_pair",
    ),

    # Refresh endpoint: generates a new access token.
    path(
        "api/token/refresh/",
        TokenRefreshView.as_view(),
        name="token_refresh",
    ),

]
