from django import forms
from django.contrib.auth import authenticate
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm
from .models import CustomUser


class LoginForm(AuthenticationForm):
    """
    이메일 기반 로그인 폼
    """
    username = forms.EmailField(
        label='이메일',
        widget=forms.EmailInput(attrs={
            'class': 'form-input',
            'placeholder': 'example@lab.com',
            'autocomplete': 'email',
        })
    )
    password = forms.CharField(
        label='비밀번호',
        widget=forms.PasswordInput(attrs={
            'class': 'form-input',
            'placeholder': '••••••••',
            'autocomplete': 'current-password',
        })
    )
    remember_me = forms.BooleanField(
        required=False,
        initial=False,
        label='로그인 상태 유지'
    )

    def clean(self):
        email = self.cleaned_data.get('username')
        password = self.cleaned_data.get('password')

        if email and password:
            self.user_cache = authenticate(
                self.request,
                username=email,
                password=password
            )
            if self.user_cache is None:
                raise forms.ValidationError(
                    '이메일 또는 비밀번호가 올바르지 않습니다.',
                    code='invalid_login',
                )
            elif not self.user_cache.is_active:
                raise forms.ValidationError(
                    '이 계정은 비활성화되었습니다.',
                    code='inactive',
                )
        return self.cleaned_data


class SignUpForm(UserCreationForm):
    """
    회원가입 폼
    """
    email = forms.EmailField(
        label='이메일',
        widget=forms.EmailInput(attrs={
            'class': 'form-input',
            'placeholder': 'example@lab.com',
            'autocomplete': 'email',
        })
    )
    full_name = forms.CharField(
        label='이름',
        max_length=100,
        widget=forms.TextInput(attrs={
            'class': 'form-input',
            'placeholder': '홍길동',
        })
    )
    company = forms.CharField(
        label='회사/소속',
        max_length=255,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-input',
            'placeholder': '소속 기관',
        })
    )
    password1 = forms.CharField(
        label='비밀번호',
        widget=forms.PasswordInput(attrs={
            'class': 'form-input',
            'placeholder': '비밀번호',
            'autocomplete': 'new-password',
        })
    )
    password2 = forms.CharField(
        label='비밀번호 확인',
        widget=forms.PasswordInput(attrs={
            'class': 'form-input',
            'placeholder': '비밀번호 확인',
            'autocomplete': 'new-password',
        })
    )

    class Meta:
        model = CustomUser
        fields = ('email', 'full_name', 'company', 'password1', 'password2')

    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data['email']
        user.full_name = self.cleaned_data['full_name']
        user.company = self.cleaned_data.get('company', '')
        if commit:
            user.save()
        return user
