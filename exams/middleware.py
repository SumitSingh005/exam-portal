"""
Security middleware for rate limiting and login attempt tracking.
"""
import time
from collections import defaultdict
from django.http import JsonResponse


class RateLimitMiddleware:
    """
    Middleware to limit requests per IP address.
    """
    
    def __init__(self, get_response):
        self.get_response = get_response
        # Track requests: {ip: [(timestamp, path)]}
        self.request_history = defaultdict(list)
        # Configuration
        self.window_seconds = 60  # 1 minute window
        self.max_requests = 30    # Max requests per window
    
    def __call__(self, request):
        # Get client IP
        client_ip = self.get_client_ip(request)
        
        # Check rate limit for auth endpoints
        if self.is_auth_endpoint(request.path):
            if not self.check_rate_limit(client_ip, request.path):
                return JsonResponse({
                    'error': 'Too many requests. Please try again later.'
                }, status=429)
        
        # Clean old entries
        self.clean_old_entries(client_ip)
        
        # Record this request
        self.request_history[client_ip].append((time.time(), request.path))
        
        response = self.get_response(request)
        return response
    
    def get_client_ip(self, request):
        """Extract client IP from request."""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            return x_forwarded_for.split(',')[0].strip()
        return request.META.get('REMOTE_ADDR', 'unknown')
    
    def is_auth_endpoint(self, path):
        """Check if path is an auth endpoint that needs rate limiting."""
        auth_paths = [
            '/accounts/login/',
            '/accounts/signup/',
            '/accounts/password-reset/',
            '/admin/login/',
        ]
        return any(path.startswith(p) for p in auth_paths)
    
    def check_rate_limit(self, client_ip, path):
        """Check if client has exceeded rate limit."""
        now = time.time()
        window_start = now - self.window_seconds
        
        # Filter to only requests in the current window
        recent_requests = [
            ts for ts in self.request_history[client_ip]
            if ts[0] >= window_start and ts[1] == path
        ]
        
        return len(recent_requests) < self.max_requests
    
    def clean_old_entries(self, client_ip):
        """Remove entries older than the window and cleanup keys."""
        now = time.time()
        window_start = now - self.window_seconds
        
        # Keep only recent requests
        self.request_history[client_ip] = [
            ts for ts in self.request_history[client_ip]
            if ts[0] >= window_start
        ]
        
        # Memory fix: if no requests left for this IP, remove the key entirely
        if not self.request_history[client_ip]:
            del self.request_history[client_ip]


class SecurityHeadersMiddleware:
    """
    Add security headers to all responses.
    """
    
    def __init__(self, get_response):
        self.get_response = get_response
    
    def __call__(self, request):
        response = self.get_response(request)
        
        # Add security headers
        response['X-Content-Type-Options'] = 'nosniff'
        response['X-XSS-Protection'] = '1; mode=block'
        response['Referrer-Policy'] = 'strict-origin-when-cross-origin'
        
        # Content Security Policy (CSP)
        # Note: Adjust based on your needs
        response['Content-Security-Policy'] = (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline' 'unsafe-eval'; "
            "style-src 'self' 'unsafe-inline'; "
            "img-src 'self' data:; "
            "font-src 'self'; "
            "connect-src 'self'; "
            "frame-ancestors 'self';"
        )
        
        return response