# labnote/views.py
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from notes.models import t_note  # 기존 모델 사용
from .forms import NoteForm  # 아래에서 제공

# 연구 노트 목록 - 로그인 사용자 기반
@login_required
def research_note_list(request):
    view_mode = request.GET.get("view", "card")  # view_mode 받아오기
    notes = t_note.objects.filter(owner=request.user, deleted_at__isnull=True).order_by('-created_at')
    return render(request, "note_list.html", {"notes": notes, "view_mode": view_mode})

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