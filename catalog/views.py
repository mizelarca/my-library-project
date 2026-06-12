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
from tablib import Dataset

from .models import (
    Book, Author, Genre, Status, ReadingChallenge,
    Profile, Collection, CollectionBook
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

    books_read_this_year = books.filter(
        status__name='read',
        updated_at__year=current_year
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

        if user_form.is_valid() and profile_form.is_valid():
            # Если загружен новый аватар, удаляем старый файл
            if 'avatar' in request.FILES:
                old_avatar = profile_obj.avatar
                if old_avatar and os.path.isfile(old_avatar.path):
                    os.remove(old_avatar.path)
            profile_form.save()
            user_form.save()
            messages.success(request, 'Профиль успешно обновлён!')
            return redirect('profile')
        else:
            messages.error(request, 'Ошибка при обновлении профиля. Проверьте поля.')
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
