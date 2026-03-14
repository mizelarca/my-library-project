from django.db.models import Count
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.urls import reverse
from django.utils import timezone
from .models import Book, Author, Genre, ReadingChallenge, Profile
from .forms import BookForm, AuthorForm, GenreForm, ChallengeForm
from django.db.models import Max
from django.contrib import messages
from .models import Collection, CollectionBook
from django.shortcuts import get_object_or_404
from .models import Book

def home(request):
    return render(request, 'catalog/home.html')

def register(request):
    if request.method == 'POST':
        form = UserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            return redirect('dashboard')
    else:
        form = UserCreationForm()
    return render(request, 'catalog/register.html', {'form': form})

@login_required
def dashboard(request):
    books = Book.objects.filter(owner=request.user)
    total = books.count()
    status_counts = books.values('status__name').annotate(count=Count('id'))
    stats = {item['status__name']: item['count'] for item in status_counts}
    
    # Книги в процессе чтения
    reading_books = books.filter(status__name='reading')
    
    # Логика книжного вызова
    current_year = timezone.now().year
    challenge, created = ReadingChallenge.objects.get_or_create(
        user=request.user,
        year=current_year,
        defaults={'goal': 10}
    )
    
    # Книги, прочитанные в этом году
    books_read_this_year = books.filter(
        status__name='read',
        updated_at__year=current_year
    ).count()
    
    # Процент прогресса (для прогресс-бара)
    if challenge.goal > 0:
        progress_percent = int(books_read_this_year / challenge.goal * 100)
    else:
        progress_percent = 0
    
    # Обработка формы изменения цели
    if request.method == 'POST':
        form = ChallengeForm(request.POST, instance=challenge)
        if form.is_valid():
            form.save()
            return redirect('dashboard')
    else:
        form = ChallengeForm(instance=challenge)
    
    context = {
        'total': total,
        'stats': stats,
        'reading_books': reading_books,
        'challenge': challenge,
        'books_read_this_year': books_read_this_year,
        'form': form,
        'progress_percent': progress_percent,  # для шаблона
    }
    return render(request, 'catalog/dashboard.html', context)

@login_required
def book_list(request):
    books = Book.objects.filter(owner=request.user)
    return render(request, 'catalog/book_list.html', {'books': books})

@login_required
def book_add(request):
    initial_data = {}
    if 'author' in request.GET:
        try:
            author = Author.objects.get(id=request.GET['author'])
            initial_data['author'] = author
        except Author.DoesNotExist:
            pass
    if 'genre' in request.GET:
        try:
            genre = Genre.objects.get(id=request.GET['genre'])
            initial_data['genre'] = genre
        except Genre.DoesNotExist:
            pass

    if request.method == 'POST':
        form = BookForm(request.POST, request.FILES)
        if form.is_valid():
            book = form.save(commit=False)
            book.owner = request.user
            book.save()
            return redirect('book_list')
    else:
        form = BookForm(initial=initial_data)
    return render(request, 'catalog/book_form.html', {'form': form, 'title': 'Добавить книгу'})

@login_required
def book_edit(request, book_id):
    book = get_object_or_404(Book, id=book_id, owner=request.user)
    if request.method == 'POST':
        form = BookForm(request.POST, request.FILES, instance=book)
        if form.is_valid():
            form.save()
            return redirect('book_list')
    else:
        form = BookForm(instance=book)
    return render(request, 'catalog/book_form.html', {'form': form, 'title': 'Редактировать книгу'})

@login_required
def author_add(request):
    next_url = request.GET.get('next', 'book_add')
    if request.method == 'POST':
        form = AuthorForm(request.POST)
        if form.is_valid():
            author = form.save()
            redirect_url = reverse(next_url) + f"?author={author.id}"
            return redirect(redirect_url)
    else:
        form = AuthorForm()
    return render(request, 'catalog/author_form.html', {'form': form, 'next': next_url})

@login_required
def genre_add(request):
    next_url = request.GET.get('next', 'book_add')
    if request.method == 'POST':
        form = GenreForm(request.POST)
        if form.is_valid():
            genre = form.save()
            redirect_url = reverse(next_url) + f"?genre={genre.id}"
            return redirect(redirect_url)
    else:
        form = GenreForm()
    return render(request, 'catalog/genre_form.html', {'form': form, 'next': next_url})

@login_required
def book_detail(request, book_id):
    book = get_object_or_404(Book, id=book_id, owner=request.user)
    return render(request, 'catalog/book_detail.html', {'book': book})

from .forms import UserForm, ProfileForm

@login_required
def profile(request):
    # Создаём профиль, если его нет
    profile_obj, created = Profile.objects.get_or_create(user=request.user)
    
    if request.method == 'POST':
        user_form = UserForm(request.POST, instance=request.user)
        profile_form = ProfileForm(request.POST, request.FILES, instance=profile_obj)
        if user_form.is_valid() and profile_form.is_valid():
            user_form.save()
            profile_form.save()
            messages.success(request, 'Профиль успешно обновлён!')
            return redirect('profile')
    else:
        user_form = UserForm(instance=request.user)
        profile_form = ProfileForm(instance=profile_obj)

    context = {
        'user_form': user_form,
        'profile_form': profile_form,
    }
    return render(request, 'catalog/profile.html', context)

from .models import Collection, CollectionBook
from .forms import CollectionForm

@login_required
def collection_list(request):
    """Список коллекций пользователя"""
    collections = Collection.objects.filter(owner=request.user)
    return render(request, 'catalog/collection_list.html', {'collections': collections})

@login_required
def collection_create(request):
    """Создание новой коллекции"""
    if request.method == 'POST':
        form = CollectionForm(request.POST)
        if form.is_valid():
            collection = form.save(commit=False)
            collection.owner = request.user
            collection.save()
            return redirect('collection_detail', collection_id=collection.id)
    else:
        form = CollectionForm()
    return render(request, 'catalog/collection_form.html', {'form': form, 'title': 'Новая коллекция'})

@login_required
def collection_detail(request, collection_id):
    """Просмотр одной коллекции с книгами"""
    collection = get_object_or_404(Collection, id=collection_id, owner=request.user)
    # Книги уже доступны через collection.books.all() благодаря related_name
    return render(request, 'catalog/collection_detail.html', {'collection': collection})

@login_required
def collection_edit(request, collection_id):
    """Редактирование названия/описания коллекции"""
    collection = get_object_or_404(Collection, id=collection_id, owner=request.user)
    if request.method == 'POST':
        form = CollectionForm(request.POST, instance=collection)
        if form.is_valid():
            form.save()
            return redirect('collection_detail', collection_id=collection.id)
    else:
        form = CollectionForm(instance=collection)
    return render(request, 'catalog/collection_form.html', {'form': form, 'title': 'Редактировать коллекцию'})

@login_required
def collection_delete(request, collection_id):
    """Удаление коллекции"""
    collection = get_object_or_404(Collection, id=collection_id, owner=request.user)
    if request.method == 'POST':
        collection.delete()
        return redirect('collection_list')
    return render(request, 'catalog/collection_confirm_delete.html', {'collection': collection})

@login_required
def add_book_to_collection(request, book_id):
    """Добавление книги в коллекцию (со страницы книги)"""
    book = get_object_or_404(Book, id=book_id, owner=request.user)
    if request.method == 'POST':
        collection_id = request.POST.get('collection_id')
        if collection_id:
            collection = get_object_or_404(Collection, id=collection_id, owner=request.user)
            # Проверяем, нет ли уже такой связи
            if not CollectionBook.objects.filter(collection=collection, book=book).exists():
                # Определяем следующий порядок
                last_order = collection.collectionbook_set.aggregate(Max('order'))['order__max'] or 0
                CollectionBook.objects.create(
                    collection=collection, 
                    book=book, 
                    order=last_order + 1
                )
                messages.success(request, f'Книга добавлена в коллекцию "{collection.name}"')
            else:
                messages.warning(request, f'Книга уже есть в коллекции "{collection.name}"')
        return redirect('book_detail', book_id=book.id)
    
    # GET запрос — показать форму выбора коллекции
    user_collections = Collection.objects.filter(owner=request.user)
    return render(request, 'catalog/add_to_collection.html', {
        'book': book,
        'collections': user_collections,
    })

@login_required
def remove_book_from_collection(request, collection_id, book_id):
    """Удаление книги из коллекции"""
    collection = get_object_or_404(Collection, id=collection_id, owner=request.user)
    book = get_object_or_404(Book, id=book_id, owner=request.user)
    CollectionBook.objects.filter(collection=collection, book=book).delete()
    messages.success(request, f'Книга удалена из коллекции "{collection.name}"')
    return redirect('collection_detail', collection_id=collection.id)

@login_required
def collection_add_books(request, collection_id):
    collection = get_object_or_404(Collection, id=collection_id, owner=request.user)
    # Все книги пользователя, которые ещё не в этой коллекции
    books_in_collection = collection.books.all()
    available_books = Book.objects.filter(owner=request.user).exclude(id__in=books_in_collection.values_list('id', flat=True))
    
    if request.method == 'POST':
        # Получаем список выбранных книг
        book_ids = request.POST.getlist('books')
        if book_ids:
            # Определяем текущий максимальный порядок
            last_order = collection.collectionbook_set.aggregate(Max('order'))['order__max'] or 0
            for idx, book_id in enumerate(book_ids, start=1):
                book = get_object_or_404(Book, id=book_id, owner=request.user)
                # Проверяем, не добавлена ли уже книга (на всякий случай)
                if not CollectionBook.objects.filter(collection=collection, book=book).exists():
                    CollectionBook.objects.create(
                        collection=collection,
                        book=book,
                        order=last_order + idx
                    )
            messages.success(request, f'Добавлено {len(book_ids)} книг в коллекцию "{collection.name}".')
        else:
            messages.warning(request, 'Ни одной книги не выбрано.')
        return redirect('collection_detail', collection_id=collection.id)
    
    context = {
        'collection': collection,
        'available_books': available_books,
    }
    return render(request, 'catalog/collection_add_books.html', context)

@login_required
def book_delete(request, book_id):
    book = get_object_or_404(Book, id=book_id, owner=request.user)
    if request.method == 'POST':
        book.delete()
        messages.success(request, f'Книга "{book.title}" удалена.')
        return redirect('book_list')
    return redirect('book_list')

@login_required
def book_delete(request, book_id):
    book = get_object_or_404(Book, id=book_id, owner=request.user)
    if request.method == 'POST':
        title = book.title
        book.delete()
        messages.success(request, f'Книга "{title}" удалена.')
        return redirect('book_list')
    return redirect('book_list')