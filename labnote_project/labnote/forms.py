from django import forms
from notes.models import t_note
from ckeditor.widgets import CKEditorWidget

class NoteForm(forms.ModelForm):
    content = forms.CharField(widget=CKEditorWidget())  # 여기서 위젯만 교체

    class Meta:
        model = t_note
        fields = ["title", "content", "summary", "visibility", "favorite"]