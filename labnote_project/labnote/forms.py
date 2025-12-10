from django import forms
from notes.models import t_note  # 기존 Note 사용

class NoteForm(forms.ModelForm):
    class Meta:
        model = t_note
        fields = ["title", "content", "summary", "visibility", "favorite"]