# labnote/views.py
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from notes.models import t_note
from .forms import NoteForm
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.db.models import Count

# 연구 노트 생성
@login_required
def research_note_create(request):
    if request.method == "POST":
        form = NoteForm(request.POST)
        if form.is_valid():
            note = form.save(commit=False)
            note.owner = request.user
            note.save()
            return redirect("labnote:note_list")
    else:
        form = NoteForm()

    return render(request, "note_form.html", {"form": form})

# 연구 노트 수정
@login_required
def research_note_update(request, note_id):
    note = get_object_or_404(t_note, note_sid=note_id, owner=request.user)

    if request.method == "POST":
        form = NoteForm(request.POST, instance=note)
        if form.is_valid():
            form.save()
            return redirect("labnote:note_list")
    else:
        form = NoteForm(instance=note)

    return render(request, "note_form.html", {"form": form})

@login_required
def note_detail(request, note_id):
    note = get_object_or_404(t_note, note_sid=note_id, owner=request.user)
    return render(request, "note_detail.html", {"note": note})

@login_required
def note_list(request):
    view_mode = request.GET.get("view", "card")
    notes = t_note.objects.all().order_by('-created_at')

    return render(request, "note_list.html", {
        "notes": notes,
        "view_mode": view_mode,
    })

@login_required
def research_note_list(request):
    view_mode = request.GET.get("view", "card")

    per_page = request.GET.get('per_page', '10')
    try:
        per_page = int(per_page)
        if per_page not in [10, 20, 50, 100]:
            per_page = 10
    except ValueError:
        per_page = 10

    q = request.GET.get('q', '')
    notes = t_note.objects.filter(owner=request.user, deleted_at__isnull=True).order_by('-created_at')
    if q:
        notes = notes.filter(title__icontains=q)

    paginator = Paginator(notes, per_page)
    page = request.GET.get('page')

    try:
        notes_page = paginator.page(page)
    except PageNotAnInteger:
        notes_page = paginator.page(1)
    except EmptyPage:
        notes_page = paginator.page(paginator.num_pages)

    per_page_options = [10, 20, 50, 100]  # 표시 개수 옵션

    return render(request, "note_list.html", {
        "notes": notes_page,
        "view_mode": view_mode,
        "per_page": per_page,
        "per_page_options": per_page_options,
        "q": q,
    })