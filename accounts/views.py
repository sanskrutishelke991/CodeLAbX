from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, authenticate, logout
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.contrib import messages
from .forms import ProfileUpdateForm
from .models import UserProfile


def register(request):
    if request.user.is_authenticated:
        return redirect('dashboard:home')
    
    if request.method == 'POST':
        form = UserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            username = form.cleaned_data.get('username')
            messages.success(request, f'Account created for {username}! You can now log in.')
            return redirect('accounts:login')
    else:
        form = UserCreationForm()
    
    return render(request, 'accounts/register.html', {'form': form})


def login_view(request):
    if request.user.is_authenticated:
        return redirect('dashboard:home')
    
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        user = authenticate(request, username=username, password=password)
        
        if user is not None:
            login(request, user)
            messages.success(request, f'Welcome back, {username}!')
            return redirect('dashboard:home')
        else:
            messages.error(request, 'Invalid username or password.')
    
    return render(request, 'accounts/login.html')


def logout_view(request):
    logout(request)
    messages.info(request, 'You have been logged out successfully.')
    return redirect('accounts:login')


@login_required
def profile(request):
    """User's own profile page"""
    # Ensure profile exists
    profile_obj, created = UserProfile.objects.get_or_create(user=request.user)
    
    context = {
        'profile_user': request.user,
        'profile': profile_obj,
        'is_own_profile': True,
    }
    
    # Get stats
    try:
        from progress.models import UserLevel, UserBadge, UserStreak
        level = UserLevel.objects.filter(user=request.user).first()
        badges = UserBadge.objects.filter(user=request.user).select_related('badge').order_by('-earned_at')[:6]
        streak = UserStreak.objects.filter(user=request.user).first()
        
        context['level'] = level
        context['recent_badges'] = badges
        context['total_badges'] = UserBadge.objects.filter(user=request.user).count()
        context['streak'] = streak
    except Exception as e:
        print(f"Progress error: {e}")
    
    # Get roadmaps
    try:
        from learning.models import Roadmap
        active_roadmaps = Roadmap.objects.filter(
            user=request.user, 
            status='active'
        ).order_by('-created_at')[:3]
        context['active_roadmaps'] = active_roadmaps
    except Exception as e:
        print(f"Roadmap error: {e}")
    
    return render(request, 'accounts/profile.html', context)


@login_required
def profile_edit(request):
    """Edit user profile"""
    profile_obj, created = UserProfile.objects.get_or_create(user=request.user)
    
    if request.method == 'POST':
        form = ProfileUpdateForm(request.POST, request.FILES, instance=profile_obj)
        if form.is_valid():
            form.save()
            messages.success(request, 'Profile updated successfully!')
            return redirect('accounts:profile')
    else:
        form = ProfileUpdateForm(instance=profile_obj)
    
    return render(request, 'accounts/profile_edit.html', {
        'form': form,
        'profile': profile_obj,
    })


def public_profile(request, username):
    """View any user's public profile"""
    profile_user = get_object_or_404(User, username=username)
    profile_obj, created = UserProfile.objects.get_or_create(user=profile_user)
    
    # Check if profile is public (or if viewing own)
    if not profile_obj.is_public and profile_user != request.user:
        messages.warning(request, 'This profile is private.')
        return redirect('dashboard:home')
    
    context = {
        'profile_user': profile_user,
        'profile': profile_obj,
        'is_own_profile': profile_user == request.user,
    }
    
    # Get stats
    try:
        from progress.models import UserLevel, UserBadge, UserStreak
        level = UserLevel.objects.filter(user=profile_user).first()
        badges = UserBadge.objects.filter(user=profile_user).select_related('badge').order_by('-earned_at')[:6]
        streak = UserStreak.objects.filter(user=profile_user).first()
        
        context['level'] = level
        context['recent_badges'] = badges
        context['total_badges'] = UserBadge.objects.filter(user=profile_user).count()
        context['streak'] = streak
    except Exception as e:
        print(f"Progress error: {e}")
    
    return render(request, 'accounts/profile.html', context)


@login_required
def settings(request):
    return render(request, 'accounts/settings.html')