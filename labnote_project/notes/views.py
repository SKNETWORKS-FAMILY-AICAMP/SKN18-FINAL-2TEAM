# notes/views.py
import json
from django.shortcuts import render, get_object_or_404
from django.http import JsonResponse
from .models import t_note, t_note_comment

def note_detail(request, pk):
    note = get_object_or_404(t_note, pk=pk)

    comment_ranges = []
    for c in note.comments.all():
        try:
            meta = json.loads(c.content)
            comment_ranges.append({
                "sid": c.pk,
                "start": meta["start"],
                "end": meta["end"],
                "text": meta["text"],
            })
        except:
            pass

    return render(request, "notes/note_detail.html", {
        "note": note,
        "comment_ranges": comment_ranges,
    })


def add_comment(request, pk):
    if request.method == "POST":
        data = json.loads(request.body)
        note = t_note.objects.get(pk=pk)

        t_note_comment.objects.create(
            note=note,
            creator=request.user,
            content=data["content"]  # JSON(str) 저장
        )
        return JsonResponse({"status": "ok"})


def comment_thread(request, comment_id):
    comment = get_object_or_404(t_note_comment, pk=comment_id)
    replies = comment.replies.all()

    html = "<h4>댓글 스레드</h4>"
    html += f"<p><strong>메인 댓글:</strong> {json.loads(comment.content)['text']}</p>"

    html += "<ul>"
    for r in replies:
        html += f"<li>{json.loads(r.content)['text']}</li>"
    html += "</ul>"

    return JsonResponse({"html": html})