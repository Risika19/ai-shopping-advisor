from django.shortcuts import render, redirect
from django.contrib import messages
from django.contrib.auth import views as auth_views
from django.contrib.auth.decorators import login_required
from .forms import UserRegisterForm, UserUpdateForm


class CustomLoginView(auth_views.LoginView):
    template_name = 'accounts/login.html'

    def get_redirect_url(self):
        redirect_to = super().get_redirect_url()
        if self.request.user.is_authenticated:
            if redirect_to and 'admin-panel' in redirect_to:
                return redirect_to
            if self.request.user.is_staff or self.request.user.is_superuser:
                return '/admin-panel/'
        return redirect_to or '/'


def register(request):
    if request.method == 'POST':
        form = UserRegisterForm(request.POST)
        if form.is_valid():
            form.save()
            username = form.cleaned_data.get('username')
            messages.success(request, f'Account created for {username}! You can now log in.')
            return redirect('login')
    else:
        form = UserRegisterForm()
    return render(request, 'accounts/register.html', {'form': form})


@login_required
def profile(request):
    if request.method == 'POST':
        form = UserUpdateForm(request.POST, instance=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, 'Your profile has been updated!')
            return redirect('profile')
    else:
        form = UserUpdateForm(instance=request.user)
    return render(request, 'accounts/profile.html', {'form': form})
