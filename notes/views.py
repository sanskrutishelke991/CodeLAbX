from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.db.models import Q
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.csrf import csrf_protect
from django.views.decorators.http import require_POST

from ai_tools.api import (
    choice_field,
    parse_json_object,
    safe_api_errors,
    text_field,
)

from .models import Bookmark, Note
from .validators import validate_bookmark_url


MAX_NOTE_CONTENT_CHARS = 100_000
MAX_NOTE_TAGS = 10
MAX_NOTE_TAG_CHARS = 30
VALID_NOTE_COLORS = {value for value, _label in Note.COLOR_CHOICES}


def _note_values(request):
    title = request.POST.get("title", "").strip()
    content = request.POST.get("content", "").strip()
    color = request.POST.get("color", "purple")
    raw_tags = request.POST.get("tags", "")

    if not title:
        raise ValidationError("Title is required.")
    if len(title) > 200:
        raise ValidationError("Title must be 200 characters or fewer.")
    if len(content) > MAX_NOTE_CONTENT_CHARS:
        raise ValidationError("Note content is too long.")
    if color not in VALID_NOTE_COLORS:
        raise ValidationError("Choose a valid note color.")

    tags = []
    seen = set()
    for raw_tag in raw_tags.split(","):
        tag = raw_tag.strip()
        if not tag:
            continue
        if len(tag) > MAX_NOTE_TAG_CHARS:
            raise ValidationError(
                f"Each tag must be {MAX_NOTE_TAG_CHARS} characters or fewer."
            )
        normalized = tag.casefold()
        if normalized not in seen:
            seen.add(normalized)
            tags.append(tag)
    if len(tags) > MAX_NOTE_TAGS:
        raise ValidationError(f"Use at most {MAX_NOTE_TAGS} tags.")

    return {
        "title": title,
        "content": content,
        "color": color,
        "tags": tags,
    }


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
    
    page_obj = Paginator(notes, 12).get_page(request.GET.get('page'))

    context = {
        'notes': page_obj,
        'page_obj': page_obj,
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
    if request.method == "POST":
        try:
            values = _note_values(request)
        except ValidationError as exc:
            messages.error(request, exc.message)
            return redirect("notes:create")
        note = Note.objects.create(user=request.user, **values)
        messages.success(request, f'Note "{note.title}" created!')
        return redirect("notes:list")
    
    return render(request, 'notes/note_form.html', {'action': 'Create'})


@login_required
def note_edit(request, note_id):
    """Edit an existing note"""
    note = get_object_or_404(Note, id=note_id, user=request.user)
    
    if request.method == "POST":
        try:
            values = _note_values(request)
        except ValidationError as exc:
            messages.error(request, exc.message)
            return redirect("notes:edit", note_id=note.id)
        for field, value in values.items():
            setattr(note, field, value)
        note.save(
            update_fields=["title", "content", "color", "tags", "updated_at"]
        )
        messages.success(request, "Note updated!")
        return redirect("notes:list")
    
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
    note.save(update_fields=["is_pinned", "updated_at"])
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
    
    response = HttpResponse(content, content_type="text/plain; charset=utf-8")
    response["Content-Disposition"] = (
        f'attachment; filename="codelabx-note-{note.id}.txt"'
    )
    response["Cache-Control"] = "no-store"
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
@safe_api_errors
def bookmark_add(request):
    """Validate and add one bookmark."""
    data = parse_json_object(request)

    title = text_field(
        data,
        "title",
        default="Bookmark",
        min_length=1,
        max_length=200,
    )
    url = text_field(
        data,
        "url",
        required=True,
        min_length=1,
        max_length=500,
    )
    bookmark_type = choice_field(
        data,
        "type",
        choices={"day", "roadmap", "test", "code", "other"},
        default="other",
    )
    description = text_field(
        data,
        "description",
        default="",
        max_length=2000,
    )
    icon = text_field(
        data,
        "icon",
        default="🔖",
        max_length=10,
    )

    bookmark = Bookmark.objects.create(
        user=request.user,
        title=title,
        url=validate_bookmark_url(url),
        bookmark_type=bookmark_type,
        description=description,
        icon=icon,
    )

    return JsonResponse(
        {
            "success": True,
            "bookmark_id": bookmark.id,
            "message": "Bookmark added!",
        }
    )


@login_required
@require_POST
def bookmark_delete(request, bookmark_id):
    """Delete a bookmark"""
    bookmark = get_object_or_404(Bookmark, id=bookmark_id, user=request.user)
    bookmark.delete()
    messages.success(request, 'Bookmark removed!')
    return redirect('notes:bookmarks')