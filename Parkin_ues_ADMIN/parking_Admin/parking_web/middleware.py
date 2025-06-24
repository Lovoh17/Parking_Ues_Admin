from django.shortcuts import redirect

class AdminAuthMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response
        
    def __call__(self, request):
        public_paths = ['/login/', '/static/']
        
        if not any(request.path.startswith(path) for path in public_paths):
            user = request.session.get('firebase_user')
            if not user or user.get('role') != 'admin':
                return redirect('/login/?next=' + request.path)
        response = self.get_response(request)
        return response