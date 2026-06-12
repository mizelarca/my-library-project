from django import forms
from django.contrib.auth.models import User

from .models import Book, Author, Genre, Status, ReadingChallenge, Profile, Collection


class BookForm(forms.ModelForm):
    class Meta:
        model = Book
        fields = [
            'title', 'author', 'genre', 'status',
            'cover_image', 'description', 'rating',
            'date_started', 'date_finished',
            'format', 'notes', 'series', 'series_number'
        ]
        widgets = {
            'description': forms.Textarea(attrs={'rows': 3, 'class': 'form-control'}),
            'date_started': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'date_finished': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'notes': forms.Textarea(attrs={'rows': 3, 'class': 'form-control'}),
            'series_number': forms.NumberInput(attrs={'class': 'form-control'}),
            'title': forms.TextInput(attrs={'class': 'form-control'}),
            'author': forms.Select(attrs={'class': 'form-select'}),
            'genre': forms.Select(attrs={'class': 'form-select'}),
            'status': forms.Select(attrs={'class': 'form-select'}),
            'cover_image': forms.ClearableFileInput(attrs={'class': 'form-control'}),
            'format': forms.Select(attrs={'class': 'form-select'}),
            'rating': forms.NumberInput(attrs={'class': 'form-control', 'min': 0, 'max': 5, 'step': 1}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['author'].queryset = Author.objects.all()
        self.fields['genre'].queryset = Genre.objects.all()
        self.fields['status'].queryset = Status.objects.all()
        # Делаем поле рейтинга необязательным
        self.fields['rating'].required = False


class AuthorForm(forms.ModelForm):
    class Meta:
        model = Author
        fields = ['name']
        labels = {'name': 'Имя автора'}
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
        }


class GenreForm(forms.ModelForm):
    class Meta:
        model = Genre
        fields = ['name']
        labels = {'name': 'Название жанра'}
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
        }


class ChallengeForm(forms.ModelForm):
    class Meta:
        model = ReadingChallenge
        fields = ['goal']
        labels = {'goal': 'Сколько книг хотите прочитать в этом году?'}
        widgets = {
            'goal': forms.NumberInput(attrs={'min': 1, 'class': 'form-control'}),
        }


class UserForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ['username', 'email', 'first_name', 'last_name']
        labels = {
            'username': 'Логин',
            'email': 'Email',
            'first_name': 'Имя',
            'last_name': 'Фамилия',
        }
        widgets = {
            'username': forms.TextInput(attrs={'class': 'form-control'}),
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
            'first_name': forms.TextInput(attrs={'class': 'form-control'}),
            'last_name': forms.TextInput(attrs={'class': 'form-control'}),
        }


class ProfileForm(forms.ModelForm):
    class Meta:
        model = Profile
        fields = ['avatar', 'bio', ]
        labels = {
            'avatar': 'Аватар',
            'bio': 'О себе',
        }
        widgets = {
            'avatar': forms.FileInput(attrs={'class': 'form-control', 'accept': 'image/*'}),
            'bio': forms.Textarea(attrs={'rows': 3, 'class': 'form-control'}),
        }

class CollectionForm(forms.ModelForm):
    class Meta:
        model = Collection
        fields = ['name', 'description']
        labels = {
            'name': 'Название',
            'description': 'Описание (необязательно)',
        }
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={'rows': 3, 'class': 'form-control'}),
        }
