from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from django.db.models.signals import pre_save, pre_delete
from django.dispatch import receiver
import os

# Модель для авторов
class Author(models.Model):
    name = models.CharField(max_length=200, unique=True, verbose_name="Имя автора")

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = "Автор"
        verbose_name_plural = "Авторы"

# Модель для жанров
class Genre(models.Model):
    name = models.CharField(max_length=100, unique=True, verbose_name="Название жанра")

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

    name = models.CharField(
        max_length=50,
        verbose_name="Статус",
        choices=STATUS_CHOICES,
        default='unread'
    )

    def __str__(self):
        return dict(self.STATUS_CHOICES).get(self.name, self.name)

    class Meta:
        verbose_name = "Статус"
        verbose_name_plural = "Статусы"

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

    # Дополнительные поля
    FORMAT_CHOICES = [
        ('paper', 'Бумажная'),
        ('ebook', 'Электронная'),
        ('audio', 'Аудио'),
    ]
    format = models.CharField(
        max_length=10,
        choices=FORMAT_CHOICES,
        blank=True,
        null=True,
        verbose_name="Формат"
    )
    notes = models.TextField(
        blank=True,
        null=True,
        verbose_name="Личные заметки"
    )
    quotes = models.TextField(
        blank=True,
        null=True,
        verbose_name="Цитаты из книги"
    )
    series = models.CharField(
        max_length=200,
        blank=True,
        null=True,
        verbose_name="Серия"
    )
    series_number = models.PositiveIntegerField(
        blank=True,
        null=True,
        verbose_name="Номер в серии"
    )
    date_started = models.DateField(
        verbose_name="Дата начала чтения",
        null=True,
        blank=True,
        help_text="Когда начали читать"
    )
    date_finished = models.DateField(
        verbose_name="Дата окончания чтения",
        null=True,
        blank=True,
        help_text="Когда закончили читать"
    )
    # Поле для музыки
    music_url = models.URLField(blank=True, null=True, verbose_name="Ссылка на музыку")
    music_title = models.CharField(max_length=200, blank=True, null=True, verbose_name="Название трека")
    # Поле для настроения

    MOOD_CHOICES = [
        ('sad', 'Грустная'),
        ('funny', 'Смешная'),
        ('shocking', 'Шокирующая'),
        ('cozy', 'Уютная'),
        ('exciting', 'Захватывающая'),
        ('thoughtful', 'Заставляет думать'),
        ('useful', 'Полезная'),
        ('calming', 'Успокаивающая'),
        ('angry', 'Бесила'),
        ('beautiful', 'Визуально красивая'),
    ]
    mood = models.CharField(max_length=20, blank=True, null=True, choices=MOOD_CHOICES, verbose_name="Настроение от книги")
    total_reading_seconds = models.PositiveIntegerField(default=0)
    
    def get_mood_display_en(self):
        """Возвращает английское название настроения"""
        mood_map_en = {
            'sad': 'Sad',
            'funny': 'Funny',
            'shocking': 'Shocking',
            'cozy': 'Cozy',
            'exciting': 'Exciting',
            'thoughtful': 'Thoughtful',
            'useful': 'Useful',
            'calming': 'Calming',
            'angry': 'Angry',
            'beautiful': 'Beautiful',
        }
        return mood_map_en.get(self.mood, '')
    
    def __str__(self):
        return f"{self.title} — {self.author.name}"
    mood = models.CharField(max_length=20, blank=True, null=True, choices=MOOD_CHOICES, verbose_name="Настроение от книги")
    
    # Время чтения (в секундах)
    total_reading_seconds = models.PositiveIntegerField(default=0, verbose_name='Общее время чтения (сек)')

    def __str__(self):
        return f"{self.title} — {self.author.name}"

    class Meta:
        verbose_name = "Книга"
        verbose_name_plural = "Книги"
        ordering = ['-created_at']


  # Модель для сессий чтения (таймер)
class ReadingSession(models.Model):
    book = models.ForeignKey(Book, on_delete=models.CASCADE, related_name='sessions')
    start_time = models.DateTimeField(default=timezone.now)
    end_time = models.DateTimeField(null=True, blank=True)
    duration_seconds = models.PositiveIntegerField(default=0)  # в секундах
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-created_at']
    
    def save(self, *args, **kwargs):
        # Если сессия завершена и длительность не посчитана
        if not self.is_active and self.end_time and self.duration_seconds == 0:
            delta = self.end_time - self.start_time
            self.duration_seconds = int(delta.total_seconds())
        super().save(*args, **kwargs)
    
    def __str__(self):
        return f"{self.book.title} - {self.start_time.strftime('%d.%m.%Y %H:%M:%S')}"


# Модель для коллекций
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


# Промежуточная модель для связи коллекции и книги
class CollectionBook(models.Model):
    """Промежуточная модель для связи коллекции и книги"""
    collection = models.ForeignKey(Collection, on_delete=models.CASCADE)
    book = models.ForeignKey(Book, on_delete=models.CASCADE)
    added_at = models.DateTimeField(auto_now_add=True)
    order = models.PositiveIntegerField(default=0, blank=False, null=False)

    class Meta:
        ordering = ['order']
        unique_together = ['collection', 'book']  # чтобы книга не дублировалась в коллекции

    def __str__(self):
        return f"{self.book.title} в {self.collection.name}"


# Модель книжного вызова
class ReadingChallenge(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='challenge')
    year = models.PositiveIntegerField(default=2026)
    goal = models.PositiveIntegerField(default=10, verbose_name="Цель (книг в год)")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.user.username} – {self.goal} книг в {self.year}"


class Profile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    avatar = models.ImageField(upload_to='avatars/', blank=True, null=True)
    bio = models.TextField(max_length=500, blank=True, null=True)

    # Новые поля
    theme = models.CharField(max_length=10, choices=[('light', 'Светлая'), ('dark', 'Тёмная')], default='light')
    language = models.CharField(max_length=10, choices=[('ru', 'Русский'), ('en', 'English')], default='ru')

    def __str__(self):
        return f'Профиль пользователя {self.user.username}'


@receiver(pre_save, sender=Book)
def delete_old_cover(sender, instance, **kwargs):
    if not instance.pk:
        return
    try:
        old_cover = sender.objects.get(pk=instance.pk).cover_image
    except sender.DoesNotExist:
        return
    if old_cover and old_cover != instance.cover_image:
        if os.path.isfile(old_cover.path):
            os.remove(old_cover.path)

@receiver(pre_save, sender=Profile)
def delete_old_avatar(sender, instance, **kwargs):
    if not instance.pk:
        return
    try:
        old_avatar = sender.objects.get(pk=instance.pk).avatar
    except sender.DoesNotExist:
        return
    if old_avatar and old_avatar != instance.avatar:
        if os.path.isfile(old_avatar.path):
            os.remove(old_avatar.path)
