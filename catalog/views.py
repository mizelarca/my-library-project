import os
import codecs
import random
import json
from datetime import datetime

from django.core.paginator import Paginator
from django.db.models import Count, Max
from django.db.models.functions import TruncMonth
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.urls import reverse
from django.utils import timezone
from django.contrib import messages
from django.http import HttpResponse, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from tablib import Dataset

from .models import (
    Book, Author, Genre, Status, ReadingChallenge,
    Profile, Collection, CollectionBook, ReadingSession
)
from .forms import (
    BookForm, AuthorForm, GenreForm, ChallengeForm,
    UserForm, ProfileForm, CollectionForm
)
from .resources import BookResource

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

    status_counts = books.filter(status__isnull=False).values('status__name').annotate(count=Count('id'))
    stats = {item['status__name']: item['count'] for item in status_counts}

    reading_books = books.filter(status__name='reading')

    current_year = timezone.now().year
    challenge, created = ReadingChallenge.objects.get_or_create(
        user=request.user,
        year=current_year,
        defaults={'goal': 10}
    )

    # ИСПРАВЛЕНО: используем date_finished__year вместо updated_at__year
    books_read_this_year = books.filter(
        status__name='read',
        date_finished__year=current_year
    ).count()

    if challenge.goal > 0:
        progress_percent = int(books_read_this_year / challenge.goal * 100)
    else:
        progress_percent = 0

    top_authors = books.values('author__name').annotate(
        count=Count('id')
    ).filter(author__name__isnull=False).order_by('-count')[:3]

    top_genres = books.values('genre__name').annotate(
        count=Count('id')
    ).filter(genre__name__isnull=False).order_by('-count')[:3]

    top_books = books.filter(rating__gt=0).order_by('-rating', '-updated_at')[:3]

        # Случайная цитата из всех цитат пользователя
    import random
    random_quote = None
    all_quotes = []
    for book in books:
        if book.quotes:
            for line in book.quotes.splitlines():
                if line.strip():
                    all_quotes.append({
                        'quote': line.strip(),
                        'book_title': book.title,
                        'book_id': book.id
                    })
    if all_quotes:
        random_quote = random.choice(all_quotes)

    monthly_stats = books.filter(
        status__name='read',
        date_finished__year=current_year
    ).annotate(
        month=TruncMonth('date_finished')
    ).values('month').annotate(
        count=Count('id')
    ).order_by('month')

    months = ['Янв', 'Фев', 'Мар', 'Апр', 'Май', 'Июн', 'Июл', 'Авг', 'Сен', 'Окт', 'Ноя', 'Дек']
    monthly_data = [0] * 12

    for item in monthly_stats:
        if item['month']:
            month_index = item['month'].month - 1
            monthly_data[month_index] = item['count']

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
        'progress_percent': progress_percent,
        'top_authors': top_authors,
        'top_genres': top_genres,
        'top_books': top_books,
        'months': months,
        'monthly_data': monthly_data,
        'current_year': current_year,
        'random_quote': random_quote,   # ← ЭТО НОВАЯ СТРОКА
    }
    return render(request, 'catalog/dashboard.html', context)


@login_required
def book_list(request):
    books = Book.objects.filter(owner=request.user)
    total_all_books = books.count()

    search_query = request.GET.get('search', '').strip()
    if search_query:
        books = books.filter(title__icontains=search_query)

    status_filter = request.GET.get('status', '').strip()
    if status_filter:
        books = books.filter(status__name=status_filter)

    genre_filter = request.GET.get('genre', '').strip()
    if genre_filter:
        books = books.filter(genre__name=genre_filter)

    sort_by = request.GET.get('sort', '-created_at')
    allowed_sorts = ['-created_at', 'created_at', 'title', 'author__name', '-rating', 'rating']
    if sort_by in allowed_sorts:
        books = books.order_by(sort_by)
    else:
        books = books.order_by('-created_at')

    all_statuses = Status.objects.all()
    all_genres = Genre.objects.all()

    view_mode = request.GET.get('view', 'grid')
    if view_mode in ['grid', 'list']:
        request.session['book_view'] = view_mode
    else:
        view_mode = request.session.get('book_view', 'grid')

    paginator = Paginator(books, 12)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    context = {
        'page_obj': page_obj,
        'total_all_books': total_all_books,
        'search_query': search_query,
        'status_filter': status_filter,
        'genre_filter': genre_filter,
        'sort_by': sort_by,
        'all_statuses': all_statuses,
        'all_genres': all_genres,
        'view_mode': view_mode,
    }
    return render(request, 'catalog/book_list.html', context)


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
            if 'cover_image' in request.FILES:
                old_cover = book.cover_image
                if old_cover and os.path.isfile(old_cover.path):
                    os.remove(old_cover.path)
            form.save()
            return redirect('book_list')
    else:
        form = BookForm(instance=book)
    return render(request, 'catalog/book_form.html', {'form': form, 'title': 'Редактировать книгу'})


@login_required
def book_delete(request, book_id):
    book = get_object_or_404(Book, id=book_id, owner=request.user)
    if request.method == 'POST':
        title = book.title
        book.delete()
        messages.success(request, f'Книга "{title}" удалена.')
        return redirect('book_list')
    return redirect('book_list')


@login_required
def author_add(request):
    next_url = request.GET.get('next', 'book_add')

    # AJAX удаление (оставляем как было)
    if request.method == 'POST' and request.headers.get('x-requested-with') == 'XMLHttpRequest':
        data = json.loads(request.body)
        author_id = data.get('author_id')
        try:
            author = Author.objects.get(id=author_id)
            if author.book_set.exists():
                return JsonResponse({'success': False, 'error': 'У автора есть книги, удаление невозможно'})
            author.delete()
            return JsonResponse({'success': True})
        except Author.DoesNotExist:
            return JsonResponse({'success': False, 'error': 'Автор не найден'})

    # Обычный POST (добавление)
    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        if name:
            # Ищем автора с таким именем (может быть несколько)
            existing_authors = Author.objects.filter(name=name)
            if existing_authors.exists():
                author = existing_authors.first()
                if existing_authors.count() > 1:
                    messages.warning(request, f'Найдено несколько авторов с именем "{name}". Использован первый.')
                else:
                    messages.info(request, f'Автор "{name}" уже существует.')
            else:
                author = Author.objects.create(name=name)
                messages.success(request, f'Автор "{name}" добавлен.')
            # Перенаправляем обратно на форму книги с подставленным ID автора
            if 'next' in request.GET:
                return redirect(f"{reverse(request.GET.get('next'))}?author={author.id}")
            else:
                return redirect(reverse('book_add') + f"?author={author.id}")
        else:
            messages.error(request, 'Имя автора не может быть пустым.')
            return redirect('author_add')
    else:
        authors = Author.objects.all().order_by('name')
        return render(request, 'catalog/author_form.html', {
            'authors': authors,
            'next': next_url,
            'title': 'Добавить автора'
        })

@login_required
def genre_add(request):
    next_url = request.GET.get('next', 'book_add')
    # AJAX удаление
    if request.method == 'POST' and request.headers.get('x-requested-with') == 'XMLHttpRequest':
        data = json.loads(request.body)
        genre_id = data.get('genre_id')
        try:
            genre = Genre.objects.get(id=genre_id)
            if genre.book_set.exists():
                return JsonResponse({'success': False, 'error': 'У жанра есть книги, удаление невозможно'})
            genre.delete()
            return JsonResponse({'success': True})
        except Genre.DoesNotExist:
            return JsonResponse({'success': False, 'error': 'Жанр не найден'})

    # Обычный POST: добавление нового жанра
    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        if name:
            genre, created = Genre.objects.get_or_create(name=name)
            if created:
                messages.success(request, f'Жанр "{name}" добавлен.')
            else:
                messages.warning(request, f'Жанр "{name}" уже существует.')
            if 'next' in request.GET:
                return redirect(f"{reverse(request.GET.get('next'))}?genre={genre.id}")
            else:
                return redirect(reverse('book_add') + f"?genre={genre.id}")
        else:
            messages.error(request, 'Название жанра не может быть пустым.')
            return redirect('genre_add')
    else:
        genres = Genre.objects.all().order_by('name')
        return render(request, 'catalog/genre_form.html', {
            'genres': genres,
            'next': next_url,
            'title': 'Добавить жанр'
        })

@login_required
def book_detail(request, book_id):
    book = get_object_or_404(Book, id=book_id, owner=request.user)
    return render(request, 'catalog/book_detail.html', {'book': book})


@login_required
def profile(request):
    profile_obj, created = Profile.objects.get_or_create(user=request.user)

    if request.method == 'POST':
        user_form = UserForm(request.POST, instance=request.user)
        profile_form = ProfileForm(request.POST, request.FILES, instance=profile_obj)

        # Обработка аватара
        if 'avatar' in request.FILES:
            # Удаляем старый аватар
            if profile_obj.avatar and os.path.isfile(profile_obj.avatar.path):
                os.remove(profile_obj.avatar.path)
            # Сохраняем новый файл
            profile_obj.avatar = request.FILES['avatar']
            profile_obj.save()
            messages.success(request, 'Аватар обновлён!')
            return redirect('profile')

        # Остальные поля профиля
        if user_form.is_valid() and profile_form.is_valid():
            profile_form.save()
            user_form.save()
            messages.success(request, 'Профиль успешно обновлён!')
            return redirect('profile')
        else:
            messages.error(request, 'Ошибка при обновлении профиля. Проверьте форму.')
    else:
        user_form = UserForm(instance=request.user)
        profile_form = ProfileForm(instance=profile_obj)

    return render(request, 'catalog/profile.html', {
        'user_form': user_form,
        'profile_form': profile_form,
    })


@login_required
def collection_list(request):
    collections = Collection.objects.filter(owner=request.user)

    search_query = request.GET.get('search', '').strip()
    if search_query:
        collections = collections.filter(name__icontains=search_query)

    has_books = request.GET.get('has_books', '')
    if has_books == 'yes':
        collections = collections.filter(books__isnull=False).distinct()
    elif has_books == 'no':
        collections = collections.filter(books__isnull=True)

    sort_by = request.GET.get('sort', 'name')
    if sort_by == 'name':
        collections = collections.order_by('name')
    elif sort_by == '-name':
        collections = collections.order_by('-name')
    elif sort_by == 'created':
        collections = collections.order_by('-created_at')
    elif sort_by == 'created_asc':
        collections = collections.order_by('created_at')
    elif sort_by == 'books_count':
        collections = collections.annotate(book_count=Count('books')).order_by('-book_count')
    elif sort_by == 'books_count_asc':
        collections = collections.annotate(book_count=Count('books')).order_by('book_count')

    paginator = Paginator(collections, 6)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    context = {
        'page_obj': page_obj,
        'collections': page_obj,
        'search_query': search_query,
        'has_books': has_books,
        'sort_by': sort_by,
    }
    return render(request, 'catalog/collection_list.html', context)


@login_required
def collection_create(request):
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
    collection = get_object_or_404(Collection, id=collection_id, owner=request.user)
    return render(request, 'catalog/collection_detail.html', {'collection': collection})


@login_required
def collection_edit(request, collection_id):
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
    collection = get_object_or_404(Collection, id=collection_id, owner=request.user)
    if request.method == 'POST':
        collection.delete()
        return redirect('collection_list')
    return render(request, 'catalog/collection_confirm_delete.html', {'collection': collection})


@login_required
def add_book_to_collection(request, book_id):
    book = get_object_or_404(Book, id=book_id, owner=request.user)
    if request.method == 'POST':
        collection_id = request.POST.get('collection_id')
        if collection_id:
            collection = get_object_or_404(Collection, id=collection_id, owner=request.user)
            if not CollectionBook.objects.filter(collection=collection, book=book).exists():
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
    user_collections = Collection.objects.filter(owner=request.user)
    return render(request, 'catalog/add_to_collection.html', {
        'book': book,
        'collections': user_collections,
    })


@login_required
def remove_book_from_collection(request, collection_id, book_id):
    collection = get_object_or_404(Collection, id=collection_id, owner=request.user)
    book = get_object_or_404(Book, id=book_id, owner=request.user)
    CollectionBook.objects.filter(collection=collection, book=book).delete()
    messages.success(request, f'Книга удалена из коллекции "{collection.name}"')
    return redirect('collection_detail', collection_id=collection.id)


@login_required
def collection_add_books(request, collection_id):
    collection = get_object_or_404(Collection, id=collection_id, owner=request.user)
    books_in_collection = collection.books.all()
    available_books = Book.objects.filter(owner=request.user).exclude(id__in=books_in_collection.values_list('id', flat=True))

    if request.method == 'POST':
        book_ids = request.POST.getlist('books')
        if book_ids:
            last_order = collection.collectionbook_set.aggregate(Max('order'))['order__max'] or 0
            for idx, book_id in enumerate(book_ids, start=1):
                book = get_object_or_404(Book, id=book_id, owner=request.user)
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
def random_unread_book(request):
    unread_books = Book.objects.filter(owner=request.user).exclude(status__name='read')

    if unread_books.exists():
        book = random.choice(list(unread_books))
        data = {
            'success': True,
            'book': {
                'id': book.id,
                'title': book.title,
                'author': book.author.name if book.author else 'Автор не указан',
                'cover': book.cover_image.url if book.cover_image else None,
                'status': book.status.get_name_display() if book.status else 'Не указан',
            }
        }
    else:
        data = {
            'success': False,
            'message': 'У вас нет непрочитанных книг! Добавьте новые книги или отметьте текущие как "В процессе".'
        }

    return JsonResponse(data)


@login_required
def bulk_delete_books(request):
    if request.method == 'POST':
        book_ids = request.POST.getlist('book_ids')
        if book_ids:
            books = Book.objects.filter(id__in=book_ids, owner=request.user)
            count = books.count()
            books.delete()
            messages.success(request, f'Удалено {count} книг.')
        else:
            messages.warning(request, 'Ни одной книги не выбрано.')
    return redirect('book_list')


@login_required
def bulk_delete_collections(request):
    if request.method == 'POST':
        collection_ids = request.POST.getlist('collection_ids')
        if collection_ids:
            collections = Collection.objects.filter(id__in=collection_ids, owner=request.user)
            count = collections.count()
            collections.delete()
            messages.success(request, f'Удалено {count} коллекций.')
        else:
            messages.warning(request, 'Ни одной коллекции не выбрано.')
    return redirect('collection_list')


@login_required
def export_books(request):
    books = Book.objects.filter(owner=request.user)
    book_resource = BookResource()
    dataset = book_resource.export(books)

    csv_data = dataset.csv
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="my_books.csv"'
    response.write(codecs.BOM_UTF8)
    response.write(csv_data.encode('utf-8'))
    return response


@login_required
def export_books_xlsx(request):
    try:
        from import_export.formats.base_formats import XLSX

        books = Book.objects.filter(owner=request.user)
        book_resource = BookResource()
        dataset = book_resource.export(books)

        response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
        response['Content-Disposition'] = 'attachment; filename="my_books.xlsx"'

        xlsx_data = XLSX().export_data(dataset)
        response.write(xlsx_data)
        return response
    except Exception as e:
        messages.error(request, f'Ошибка при экспорте в XLSX: {str(e)}')
        return redirect('book_list')


@login_required
def import_books(request):
    if request.method == 'POST':
        file = request.FILES.get('file')
        if not file:
            messages.warning(request, 'Выберите файл для импорта')
            return redirect('book_list')

        try:
            book_resource = BookResource()
            dataset = Dataset()

            if file.name.endswith('.csv'):
                try:
                    file_content = file.read().decode('utf-8-sig')
                except UnicodeDecodeError:
                    try:
                        file_content = file.read().decode('cp1251')
                    except UnicodeDecodeError:
                        file_content = file.read().decode('utf-8')
                imported_data = dataset.load(file_content, format='csv')
            elif file.name.endswith('.xlsx'):
                from import_export.formats.base_formats import XLSX
                imported_data = dataset.load(file.read(), format='xlsx')
            else:
                messages.warning(request, 'Поддерживаются только CSV и XLSX файлы')
                return redirect('book_list')

            result = book_resource.import_data(imported_data, dry_run=False)

            if result.has_errors():
                errors = []
                for error in result.errors:
                    errors.append(str(error.error))
                messages.error(request, f'Ошибки при импорте: {", ".join(errors[:3])}')
            else:
                imported_count = 0
                for row in imported_data.dict:
                    try:
                        title = row.get('Название книги', '') or row.get('title', '')
                        author_name = row.get('Автор', '') or row.get('author', '')
                        genre_name = row.get('Жанр', '') or row.get('genre', '')
                        status_name = row.get('Статус', '') or row.get('status', '')

                        if not title:
                            continue

                        author = None
                        if author_name:
                            author, _ = Author.objects.get_or_create(name=author_name)

                        genre = None
                        if genre_name:
                            genre, _ = Genre.objects.get_or_create(name=genre_name)

                        status = None
                        if status_name:
                            status_map = {
                                'Прочитано': 'read',
                                'read': 'read',
                                'В процессе': 'reading',
                                'reading': 'reading',
                                'Непрочитано': 'unread',
                                'unread': 'unread',
                                'Брошено': 'abandoned',
                                'abandoned': 'abandoned',
                            }
                            status_code = status_map.get(status_name, status_name)
                            status = Status.objects.filter(name=status_code).first()

                        rating = row.get('Оценка', 0) or row.get('rating', 0)
                        try:
                            rating = int(rating)
                        except (ValueError, TypeError):
                            rating = 0

                        book, created = Book.objects.get_or_create(
                            title=title,
                            author=author,
                            owner=request.user,
                            defaults={
                                'genre': genre,
                                'status': status,
                                'rating': rating,
                                'description': row.get('Описание', '') or row.get('description', ''),
                                'format': row.get('Формат', '') or row.get('format', ''),
                                'series': row.get('Серия', '') or row.get('series', ''),
                                'series_number': row.get('Номер в серии', None) or row.get('series_number', None),
                                'notes': row.get('Заметки', '') or row.get('notes', ''),
                            }
                        )

                        if created:
                            imported_count += 1

                            date_started = row.get('Дата начала чтения', '') or row.get('date_started', '')
                            date_finished = row.get('Дата окончания чтения', '') or row.get('date_finished', '')

                            if date_started:
                                try:
                                    book.date_started = datetime.strptime(date_started, '%d.%m.%Y').date()
                                except (ValueError, TypeError):
                                    pass
                            if date_finished:
                                try:
                                    book.date_finished = datetime.strptime(date_finished, '%d.%m.%Y').date()
                                except (ValueError, TypeError):
                                    pass
                            book.save()

                    except Exception as e:
                        messages.warning(request, f'Ошибка при импорте книги "{title}": {str(e)}')

                messages.success(request, f'Импорт завершён. Добавлено {imported_count} новых книг.')

        except Exception as e:
            messages.error(request, f'Ошибка при импорте: {str(e)}')

        return redirect('book_list')

    return redirect('book_list')


@login_required
def update_settings(request):
    if request.method == 'POST':
        profile = request.user.profile
        profile.language = request.POST.get('language', 'ru')
        profile.theme = request.POST.get('theme', 'light')
        profile.save()

        request.session['language'] = profile.language

        messages.success(request, 'Настройки сохранены')
        return redirect('profile')
    return redirect('profile')

@login_required
def author_delete(request, author_id):
    author = get_object_or_404(Author, id=author_id)
    if author.book_set.exists():
        messages.error(request, f'Нельзя удалить автора "{author.name}", так как есть связанные книги.')
    else:
        author.delete()
        messages.success(request, f'Автор "{author.name}" удалён.')
    return redirect('author_add')

@login_required
def genre_delete(request, genre_id):
    genre = get_object_or_404(Genre, id=genre_id)
    if genre.book_set.exists():
        messages.error(request, f'Нельзя удалить жанр "{genre.name}", так как есть связанные книги.')
    else:
        genre.delete()
        messages.success(request, f'Жанр "{genre.name}" удалён.')
    return redirect('genre_add')

from django.http import JsonResponse

@login_required
def change_book_status(request, book_id):
    """Быстрое изменение статуса книги через AJAX"""
    if request.method == 'POST' and request.headers.get('x-requested-with') == 'XMLHttpRequest':
        book = get_object_or_404(Book, id=book_id, owner=request.user)
        new_status = request.POST.get('status')
        
        # Сопоставление названий статусов
        status_map = {
            'read': 'Прочитано',
            'reading': 'В процессе',
            'unread': 'Непрочитано',
            'abandoned': 'Брошено'
        }
        
        if new_status in status_map:
            # Находим объект статуса
            status_obj = Status.objects.filter(name=new_status).first()
            if status_obj:
                book.status = status_obj
                book.save()
                return JsonResponse({'success': True, 'new_status': status_map[new_status]})
        
        return JsonResponse({'success': False, 'error': 'Неверный статус'})
    
    return JsonResponse({'success': False, 'error': 'Неверный запрос'})

from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from .models import ReadingSession
import json

@csrf_exempt
@require_http_methods(["POST"])
def timer_start(request, book_id):
    """Начать сессию чтения"""
    try:
        book = Book.objects.get(id=book_id, owner=request.user)
        # Проверяем активную сессию
        active = ReadingSession.objects.filter(book=book, is_active=True).first()
        if active:
            return JsonResponse({'error': 'Активная сессия уже есть'}, status=400)
        
        session = ReadingSession.objects.create(
            book=book,
            start_time=timezone.now(),
            is_active=True
        )
        return JsonResponse({
            'success': True,
            'session_id': session.id,
            'start_time': session.start_time.isoformat()
        })
    except Book.DoesNotExist:
        return JsonResponse({'error': 'Книга не найдена'}, status=404)

@csrf_exempt
@require_http_methods(["POST"])
def timer_pause(request, session_id):
    """Поставить на паузу"""
    try:
        session = ReadingSession.objects.get(id=session_id, book__owner=request.user, is_active=True)
        session.end_time = timezone.now()
        session.is_active = False
        session.save()
        
        # Обновляем общее время книги
        book = session.book
        total_seconds = sum(s.duration_seconds for s in book.sessions.all())
        book.total_reading_seconds = total_seconds
        book.save()
        
        return JsonResponse({
            'success': True,
            'duration_seconds': session.duration_seconds,
            'total_seconds': book.total_reading_seconds
        })
    except ReadingSession.DoesNotExist:
        return JsonResponse({'error': 'Сессия не найдена'}, status=404)

@csrf_exempt
@require_http_methods(["POST"])
def timer_stop(request, session_id):
    """Полностью остановить (удалить активную сессию)"""
    try:
        session = ReadingSession.objects.get(id=session_id, book__owner=request.user, is_active=True)
        # Удаляем сессию, так как пользователь нажал Стоп без сохранения
        session.delete()
        return JsonResponse({'success': True})
    except ReadingSession.DoesNotExist:
        return JsonResponse({'error': 'Сессия не найдена'}, status=404)

@require_http_methods(["GET"])
def timer_get_stats(request, book_id):
    """Получить статистику за последний месяц"""
    try:
        book = Book.objects.get(id=book_id, owner=request.user)
        month_ago = timezone.now() - timezone.timedelta(days=30)
        sessions = book.sessions.filter(
            is_active=False,
            created_at__gte=month_ago
        ).order_by('-created_at')[:10]
        
        total_seconds = book.total_reading_seconds
        total_hours = total_seconds // 3600
        total_min = (total_seconds % 3600) // 60
        total_sec = total_seconds % 60
        
        sessions_data = []
        for s in sessions:
            hours = s.duration_seconds // 3600
            minutes = (s.duration_seconds % 3600) // 60
            seconds = s.duration_seconds % 60
            sessions_data.append({
                'id': s.id,
                'start': s.start_time.strftime('%d.%m.%Y %H:%M:%S'),
                'duration': s.duration_seconds,
                'duration_str': f"{hours}ч {minutes}м {seconds}с" if hours > 0 else f"{minutes}м {seconds}с"
            })
        
        # Активная сессия
        active = ReadingSession.objects.filter(book=book, is_active=True).first()
        active_data = None
        if active:
            elapsed = int((timezone.now() - active.start_time).total_seconds())
            elapsed_hours = elapsed // 3600
            elapsed_min = (elapsed % 3600) // 60
            elapsed_sec = elapsed % 60
            active_data = {
                'id': active.id,
                'start': active.start_time.strftime('%d.%m.%Y %H:%M:%S'),
                'elapsed': elapsed,
                'elapsed_str': f"{elapsed_hours}ч {elapsed_min}м {elapsed_sec}с" if elapsed_hours > 0 else f"{elapsed_min}м {elapsed_sec}с"
            }
        
        return JsonResponse({
            'success': True,
            'total_seconds': total_seconds,
            'total_str': f"{total_hours}ч {total_min}м {total_sec}с",
            'sessions': sessions_data,
            'active_session': active_data
        })
    except Book.DoesNotExist:
        return JsonResponse({'error': 'Книга не найдена'}, status=404)

@csrf_exempt
@require_http_methods(["POST"])
def timer_manual_add(request, book_id):
    """Ручное добавление времени"""
    try:
        data = json.loads(request.body)
        minutes = int(data.get('minutes', 0))
        seconds = int(data.get('seconds', 0))
        total_seconds = minutes * 60 + seconds
        
        if total_seconds <= 0:
            return JsonResponse({'error': 'Время должно быть больше 0'}, status=400)
        
        book = Book.objects.get(id=book_id, owner=request.user)
        book.total_reading_seconds += total_seconds
        book.save()
        
        # Создаём запись сессии для истории (ручное добавление)
        from django.utils import timezone
        now = timezone.now()
        ReadingSession.objects.create(
            book=book,
            start_time=now,
            end_time=now,
            duration_seconds=total_seconds,
            is_active=False
        )
        
        return JsonResponse({
            'success': True,
            'total_seconds': book.total_reading_seconds
        })
    except Book.DoesNotExist:
        return JsonResponse({'error': 'Книга не найдена'}, status=404)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

@login_required
def timer_page(request):
    """Страница таймера чтения"""
    book_id = request.GET.get('book_id')
    book = None
    if book_id:
        try:
            book = Book.objects.get(id=book_id, owner=request.user)
        except Book.DoesNotExist:
            pass
    
    books = Book.objects.filter(owner=request.user).order_by('title')
    return render(request, 'catalog/timer.html', {'book': book, 'books': books})

@csrf_exempt
@require_http_methods(["POST"])
def timer_delete_session(request, session_id):
    """Удаление сессии и вычитание времени из общего"""
    try:
        session = ReadingSession.objects.get(id=session_id, book__owner=request.user)
        book = session.book
        
        # Вычитаем время из общего
        book.total_reading_seconds -= session.duration_seconds
        if book.total_reading_seconds < 0:
            book.total_reading_seconds = 0
        book.save()
        
        # Удаляем сессию
        session.delete()
        
        return JsonResponse({'success': True})
    except ReadingSession.DoesNotExist:
        return JsonResponse({'error': 'Сессия не найдена'}, status=404)

@csrf_exempt
@require_http_methods(["POST"])
def timer_reset_all(request, book_id):
    """Сброс всего времени чтения книги и удаление всех сессий"""
    try:
        book = Book.objects.get(id=book_id, owner=request.user)
        # Удаляем все сессии
        ReadingSession.objects.filter(book=book).delete()
        # Сбрасываем общее время
        book.total_reading_seconds = 0
        book.save()
        return JsonResponse({'success': True})
    except Book.DoesNotExist:
        return JsonResponse({'error': 'Книга не найдена'}, status=404)

@login_required
def heatmap_view(request):
    """Страница с тепловой картой чтения (таймер + прочитанные книги по времени добавления)"""
    from django.db.models import Sum
    from django.utils import timezone
    
    # 1. Данные из таймера (сессии)
    sessions = ReadingSession.objects.filter(
        book__owner=request.user,
        is_active=False,
        duration_seconds__gt=0
    )
    
    # 2. Данные из прочитанных книг (по дате добавления created_at)
    finished_books = Book.objects.filter(
        owner=request.user,
        status__name='read',
        date_finished__isnull=False
    )
    
    # Создаём матрицу 7×24
    heatmap = [[0] * 24 for _ in range(7)]
    
    # Обрабатываем сессии таймера
    for session in sessions:
        if session.start_time:
            weekday = session.start_time.weekday()
            hour = session.start_time.hour
            minutes = session.duration_seconds // 60
            heatmap[weekday][hour] += minutes
    
    # Обрабатываем прочитанные книги - используем время created_at (когда книга была добавлена в библиотеку)
    for book in finished_books:
        if book.created_at:
            weekday = book.created_at.weekday()
            hour = book.created_at.hour
            # Каждая книга добавляет 60 минут, распределяя по реальному времени добавления
            heatmap[weekday][hour] += 60
    
    # Находим максимум
    max_value = max(max(row) for row in heatmap) if heatmap else 1
    
    # Подсчёт статистики
    total_sessions = sessions.count()
    total_finished_books = finished_books.count()
    total_time_sessions = sum(s.duration_seconds for s in sessions)
    total_time_finished = total_finished_books * 3600
    total_time = total_time_sessions + total_time_finished
    
    total_hours = total_time // 3600
    total_minutes = (total_time % 3600) // 60
    
    max_hour = max(range(24), key=lambda h: sum(heatmap[d][h] for d in range(7)))
    max_weekday = max(range(7), key=lambda d: sum(heatmap[d][h] for h in range(24)))
    
    weekdays_ru = ['ПН', 'ВТ', 'СР', 'ЧТ', 'ПТ', 'СБ', 'ВС']
    weekdays_en = ['MON', 'TUE', 'WED', 'THU', 'FRI', 'SAT', 'SUN']
    
    context = {
        'heatmap': heatmap,
        'max_value': max_value,
        'weekdays_ru': weekdays_ru,
        'weekdays_en': weekdays_en,
        'hours': list(range(24)),
        'total_sessions': total_sessions,
        'total_finished_books': total_finished_books,
        'total_hours': total_hours,
        'total_minutes': total_minutes,
        'max_hour': max_hour,
        'max_weekday': max_weekday,
        'weekdays_list': weekdays_ru if request.user.profile.language == 'ru' else weekdays_en,
    }
    return render(request, 'catalog/heatmap.html', context)

@login_required
def help_page(request):
    """Страница с пояснениями как работает сайт"""
    return render(request, 'catalog/help.html')

def help_public(request):
    """Публичная страница с пояснениями (без регистрации)"""
    return render(request, 'catalog/help_public.html')
