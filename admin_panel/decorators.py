from django.shortcuts import redirect
from django.urls import reverse
from django.contrib import messages
from functools import wraps


from urllib.parse import urlencode


def admin_required(view_func):
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        if not request.user.is_authenticated:
            path = request.get_full_path()
            login_url = reverse('login')
            return redirect(f'{login_url}?{urlencode({"next": path})}')
        if not (request.user.is_superuser or request.user.is_staff):
            messages.error(request, 'You do not have permission to access the admin panel.')
            return redirect('home')
        return view_func(request, *args, **kwargs)
    return _wrapped_view
