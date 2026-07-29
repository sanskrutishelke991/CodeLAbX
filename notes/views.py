from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse, HttpResponse
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import csrf_protect
from django.db.models import Q
import json
from .models import Note, Bookmark


@login_required
def notes_list(request):
    """List all notes with search and filter"""
    query = request.GET.get('q', '')
    color_filter = request.GET.get('color', '')
    
    notes = Note.objects.filter(user=request.user)
    
    if query:
        notes = notes.filter(
            Q(title__icontains=query) | Q(content__icontains=query)
        )
    
    if color_filter:
        notes = notes.filter(color=color_filter)
    
    # Get all unique tags for filtering
    all_tags = set()
    for note in Note.objects.filter(user=request.user):
        all_tags.update(note.tags)
    
    context = {
        'notes': notes,
        'query': query,
        'color_filter': color_filter,
        'all_tags': sorted(all_tags),
        'total_notes': Note.objects.filter(user=request.user).count(),
        'pinned_count': Note.objects.filter(user=request.user, is_pinned=True).count(),
    }
    
    return render(request, 'notes/notes_list.html', context)


@login_required
def note_create(request):
    """Create a new note"""
    if request.method == 'POST':
        title = request.POST.get('title', '').strip()
        content = request.POST.get('content', '').strip()
        color = request.POST.get('color', 'purple')
        tags_str = request.POST.get('tags', '').strip()
        
        if not title:
            messages.error(request, 'Title is required')
            return redirect('notes:create')
        
        tags = [t.strip() for t in tags_str.split(',') if t.strip()] if tags_str else []
        
        note = Note.objects.create(
            user=request.user,
            title=title,
            content=content,
            color=color,
            tags=tags
        )
        
        messages.success(request, f'Note "{note.title}" created!')
        return redirect('notes:list')
    
    return render(request, 'notes/note_form.html', {'action': 'Create'})


@login_required
def note_edit(request, note_id):
    """Edit an existing note"""
    note = get_object_or_404(Note, id=note_id, user=request.user)
    
    if request.method == 'POST':
        note.title = request.POST.get('title', '').strip()
        note.content = request.POST.get('content', '').strip()
        note.color = request.POST.get('color', 'purple')
        tags_str = request.POST.get('tags', '').strip()
        note.tags = [t.strip() for t in tags_str.split(',') if t.strip()] if tags_str else []
        note.save()
        
        messages.success(request, 'Note updated!')
        return redirect('notes:list')
    
    return render(request, 'notes/note_form.html', {
        'action': 'Edit',
        'note': note,
        'tags_str': ', '.join(note.tags) if note.tags else ''
    })


@login_required
@require_POST
def note_delete(request, note_id):
    """Delete a note"""
    note = get_object_or_404(Note, id=note_id, user=request.user)
    note.delete()
    messages.success(request, 'Note deleted!')
    return redirect('notes:list')


@login_required
@require_POST
def note_pin_toggle(request, note_id):
    """Toggle pin status of a note"""
    note = get_object_or_404(Note, id=note_id, user=request.user)
    note.is_pinned = not note.is_pinned
    note.save()
    return JsonResponse({
        'success': True,
        'is_pinned': note.is_pinned
    })


@login_required
def note_export(request, note_id):
    """Export note as text file"""
    note = get_object_or_404(Note, id=note_id, user=request.user)
    
    content = f"Title: {note.title}\n"
    content += f"Created: {note.created_at.strftime('%B %d, %Y')}\n"
    if note.tags:
        content += f"Tags: {', '.join(note.tags)}\n"
    content += f"\n{'='*50}\n\n"
    content += note.content
    
    response = HttpResponse(content, content_type='text/plain')
    response['Content-Disposition'] = f'attachment; filename="{note.title}.txt"'
    return response


@login_required
def bookmarks_list(request):
    """List all bookmarks"""
    type_filter = request.GET.get('type', '')
    
    bookmarks = Bookmark.objects.filter(user=request.user)
    
    if type_filter:
        bookmarks = bookmarks.filter(bookmark_type=type_filter)
    
    context = {
        'bookmarks': bookmarks,
        'type_filter': type_filter,
        'total_bookmarks': Bookmark.objects.filter(user=request.user).count(),
    }
    
    return render(request, 'notes/bookmarks_list.html', context)


@login_required
@require_POST
@csrf_protect
def bookmark_add(request):
    """Add a bookmark via AJAX"""
    try:
        data = json.loads(request.body)
        
        bookmark = Bookmark.objects.create(
            user=request.user,
            title=data.get('title', 'Bookmark'),
            url=data.get('url', ''),
            bookmark_type=data.get('type', 'other'),
            description=data.get('description', ''),
            icon=data.get('icon', '🔖')
        )
        
        return JsonResponse({
            'success': True,
            'bookmark_id': bookmark.id,
            'message': 'Bookmark added!'
        })
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


@login_required
@require_POST
def bookmark_delete(request, bookmark_id):
    """Delete a bookmark"""
    bookmark = get_object_or_404(Bookmark, id=bookmark_id, user=request.user)
    bookmark.delete()
    messages.success(request, 'Bookmark removed!')
    return redirect('notes:bookmarks')