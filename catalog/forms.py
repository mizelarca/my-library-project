from .models import ReadingChallenge
from django import forms
from .models import Book, Author, Genre, Status

class BookForm(forms.ModelForm):
    class Meta:
        model = Book
        fields = ['title', 'author', 'genre', 'status', 'cover_image', 'description', 'rating']
        widgets = {
            'description': forms.Textarea(attrs={'rows': 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['author'].queryset = Author.objects.all()
        self.fields['genre'].queryset = Genre.objects.all()
        self.fields['status'].queryset = Status.objects.all()


class AuthorForm(forms.ModelForm):
    class Meta:
        model = Author
        fields = ['name']
        labels = {'name': 'Имя автора'}

class GenreForm(forms.ModelForm):
    class Meta:
        model = Genre
        fields = ['name']
        labels = {'name': 'Название жанра'}

        from .models import ReadingChallenge

class ChallengeForm(forms.ModelForm):
    class Meta:
        model = ReadingChallenge
        fields = ['goal']
        labels = {'goal': 'Сколько книг хотите прочитать в этом году?'}
        widgets = {
            'goal': forms.NumberInput(attrs={'min': 1, 'class': 'form-control'})
        }

from django.contrib.auth.models import User
from .models import Profile

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

class ProfileForm(forms.ModelForm):
    class Meta:
        model = Profile
        fields = ['avatar', 'bio']
        labels = {
            'avatar': 'Аватар',
            'bio': 'О себе',
        }

from .models import Collection

class CollectionForm(forms.ModelForm):
    class Meta:
        model = Collection
        fields = ['name']
        labels = {
            'name': 'Название',
        }