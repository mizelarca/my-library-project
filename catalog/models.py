from django.db import models
from django.contrib.auth.models import User

# Модель для авторов
class Author(models.Model):
    name = models.CharField(max_length=200, verbose_name="Имя автора")
    
    def __str__(self):
        return self.name
    
    class Meta:
        verbose_name = "Автор"
        verbose_name_plural = "Авторы"

# Модель для жанров
class Genre(models.Model):
    name = models.CharField(max_length=100, verbose_name="Название жанра")
    
    def __str__(self):
        return self.name
    
    class Meta:
        verbose_name = "Жанр"
        verbose_name_plural = "Жанры"

# Модель для статусов книг
class Status(models.Model):
    STATUS_CHOICES = [
        ('unread', 'Непрочитано'),
        ('reading', 'В процессе'),
        ('read', 'Прочитано'),
        ('abandoned', 'Брошено'),
    ]
    
    name = models.CharField(max_length=50, verbose_name="Статус", choices=STATUS_CHOICES, default='unread')
    
    def __str__(self):
        return dict(self.STATUS_CHOICES).get(self.name, self.name)
    
    class Meta:
        verbose_name = "Статус"
        verbose_name_plural = "Статусы"

# Модель для книг (главная модель)
class Book(models.Model):
    title = models.CharField(max_length=300, verbose_name="Название книги")
    author = models.ForeignKey(Author, on_delete=models.CASCADE, verbose_name="Автор")
    genre = models.ForeignKey(Genre, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Жанр")
    status = models.ForeignKey(Status, on_delete=models.SET_NULL, null=True, verbose_name="Статус")
    owner = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name="Владелец")
    cover_image = models.ImageField(upload_to='covers/', null=True, blank=True, verbose_name="Обложка")
    description = models.TextField(blank=True, null=True, verbose_name="Описание")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Дата добавления")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Дата обновления")
    rating = models.PositiveSmallIntegerField(
        verbose_name="Рейтинг",
        choices=[(i, str(i)) for i in range(6)],
        default=0,
        help_text="Оцените книгу от 0 до 5 звёзд"
    )

class Collection(models.Model):
    """Коллекция книг пользователя"""
    name = models.CharField(max_length=200, verbose_name="Название коллекции")
    owner = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name="Владелец", related_name='collections')
    description = models.TextField(blank=True, null=True, verbose_name="Описание")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Дата создания")
    
    # Связь с книгами через промежуточную модель
    books = models.ManyToManyField(Book, through='CollectionBook', related_name='collections')
    
    def __str__(self):
        return self.name
    
    class Meta:
        verbose_name = "Коллекция"
        verbose_name_plural = "Коллекции"
        ordering = ['-created_at']

class CollectionBook(models.Model):
    """Промежуточная модель для связи коллекции и книги"""
    collection = models.ForeignKey(Collection, on_delete=models.CASCADE)
    book = models.ForeignKey(Book, on_delete=models.CASCADE)
    added_at = models.DateTimeField(auto_now_add=True)
    # Можно добавить порядок сортировки
    order = models.PositiveIntegerField(default=0, blank=False, null=False)
    
    class Meta:
        ordering = ['order']
        unique_together = ['collection', 'book']  # чтобы книга не дублировалась в коллекции
    
    def __str__(self):
        return f"{self.book.title} в {self.collection.name}"

# Создадим модель Книжный вызов
class ReadingChallenge(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='challenge')
    year = models.PositiveIntegerField(default=2026)  # можно автоматически определять
    goal = models.PositiveIntegerField(default=10, verbose_name="Цель (книг в год)")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.user.username} – {self.goal} книг в {self.year}"

class Profile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    avatar = models.ImageField(upload_to='avatars/', null=True, blank=True, verbose_name="Аватар")
    bio = models.TextField(max_length=500, blank=True, verbose_name="О себе")
    # можно добавить другие поля по желанию

    def __str__(self):
        return f"Профиль {self.user.username}"