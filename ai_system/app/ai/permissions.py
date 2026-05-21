import os
import logging
from rest_framework import authentication, exceptions
from django.conf import settings

logger = logging.getLogger(__name__)

class MafqoodAPIKeyAuthentication(authentication.BaseAuthentication):
    """
    Custom DRF authentication class that validates the X-Api-Key header.
    Strictly returns HTTP 401 Unauthorized with detailed messages when checks fail.
    """
    def authenticate(self, request):
        # Extract X-Api-Key header
        api_key = request.headers.get('X-Api-Key')
        
        # Check against configured key
        expected_key = getattr(settings, 'MAFQOOD_API_KEY', 'mafqood-shared-secret-key-2026')
        
        if not api_key:
            logger.warning("X-Api-Key header is missing from incoming request.")
            raise exceptions.AuthenticationFailed("X-Api-Key header is missing.")
            
        if api_key != expected_key:
            logger.warning(f"Invalid X-Api-Key received: '{api_key}' (expected: '{expected_key}')")
            raise exceptions.AuthenticationFailed("Invalid X-Api-Key.")
            
        # Return a dummy user and auth token to satisfy DRF signature
        return (None, None)

    def authenticate_header(self, request):
        """
        Returns the value for the WWW-Authenticate header in case of 401 response.
        This guarantees that DRF retains HTTP 401 Unauthorized instead of converting it to 403 Forbidden.
        """
        return 'Api-Key realm="Mafqood"'

