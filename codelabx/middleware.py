"""Additional response-security headers for CodeLabX."""


class SecurityHeadersMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        response.setdefault(
            "Permissions-Policy",
            "camera=(), geolocation=(), microphone=(), payment=(), usb=()",
        )
        response.setdefault("X-Permitted-Cross-Domain-Policies", "none")
        response.setdefault("X-DNS-Prefetch-Control", "off")
        response.setdefault("Cross-Origin-Resource-Policy", "same-site")
        response.setdefault(
            "Content-Security-Policy",
            "; ".join(
                [
                    "default-src 'self'",
                    "script-src 'self' 'unsafe-inline'",
                    "style-src 'self' 'unsafe-inline'",
                    "font-src 'self' data:",
                    "img-src 'self' data: blob: https://img.youtube.com",
                    "frame-src https://www.youtube.com https://www.youtube-nocookie.com",
                    "connect-src 'self'",
                    "object-src 'none'",
                    "base-uri 'self'",
                    "form-action 'self'",
                    "frame-ancestors 'none'",
                ]
            ),
        )
        return response
